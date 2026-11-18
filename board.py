"""TailorCV board: a local server over generated_cvs/, where each Stage is a folder.

Run: python3 board.py [--root generated_cvs] [--port 8765]
Check for a Duplicate Application: python3 board.py --check <url> [<url> ...]
  (exit 1 and print the open Application for that Job Posting; exit 0 and print nothing if there is none)
See docs/adr/0001 and 0002.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import platform
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"  # never exposed to the network: the API writes files and has no auth
CLOSED = "closed"
STAGES = ["awaiting", "applied", "in-process", "offer", CLOSED]
CLOSED_REASONS = ["rejected", "withdrawn", "posting-closed"]
APPLICATION_FILE = "application.md"
JOB_INFO_FILE = "job_info.md"
UI_DIR = Path(__file__).parent / "board_ui"
UI_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}
API_ROUTE = re.compile(r"^/api/applications/([^/]+)(?:/(move|notes|open-folder))?$")
FILE_ROUTE = re.compile(r"^/files/([^/]+)/([^/]+)$")


class BoardError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


def parse_application(text: str) -> tuple[dict[str, str], str]:
    """Split application.md into (frontmatter, notes)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    front: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            notes = "\n".join(lines[i + 1:])
            return front, notes[1:] if notes.startswith("\n") else notes
        key, sep, value = line.partition(":")
        if sep:
            front[key.strip()] = _unquote(value.strip())
    return {}, text


def render_application(front: dict[str, str], notes: str) -> str:
    lines = ["---", *(f"{key}: {_quote(value)}" for key, value in front.items()), "---", ""]
    return "\n".join(lines) + notes


_PLAIN = re.compile(r"^[\w./:?=&%+@~#-][\w ./:?=&%+@~#,()'-]*$")


def _quote(value: str) -> str:
    value = str(value)
    return value if _PLAIN.match(value) and not value.endswith(" ") else json.dumps(value, ensure_ascii=False)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_TRACKING = {"ref", "source", "t", "trk", "refid", "trackingid", "gclid", "fbclid"}
_LISTING_PAGES = {"jobs", "careers", "career", "join", "join-us", "opportunities", "vagas"}


def posting_keys(url: str) -> set[str]:
    """Keys identifying the Job Posting behind `url`; empty for a link that identifies none (a listing page).

    Two links lead to the same Job Posting only if they share a key (see GLOSSARY.md).
    """
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")  # hostname is already lowercase
    segments = [s for s in parts.path.split("/") if s]
    lower = [s.lower() for s in segments]
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    params = {k.lower(): v.lower() for k, v in query}

    if "ashby_jid" in params:
        return {f"ashby:{params['ashby_jid']}"}
    if "gh_jid" in params:
        return {f"greenhouse:{params['gh_jid']}"}
    if host == "jobs.ashbyhq.com" and len(lower) >= 2 and re.fullmatch(_UUID, lower[1]):
        return {f"ashby:{lower[1]}"}
    if host == "jobs.lever.co" and len(lower) >= 2:
        return {f"lever:{lower[1]}"}
    if host.endswith("greenhouse.io") and "jobs" in lower[:-1]:
        return {f"greenhouse:{lower[lower.index('jobs') + 1]}"}
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        path = "/".join(lower)
        if match := re.match(r"jobs/view/(?:.*-)?(\d+)$", path):
            return {f"linkedin-job:{match[1]}"}
        if match := re.match(r"posts/.*?-(\d{15,})-", path) or re.search(r"urn:li:activity:(\d+)", path):
            return {f"linkedin-post:{match[1]}"}

    if lower and lower[-1] in ("apply", "application"):
        segments.pop()
        lower.pop()
    if not lower or (len(lower) == 1 and lower[0] in _LISTING_PAGES):
        return set()
    kept = sorted((k, v) for k, v in query
                  if k.lower() not in _TRACKING and not k.lower().startswith(("utm_", "hsa_")))
    normalized = host + "/" + "/".join(segments)
    if kept:
        normalized += "?" + urllib.parse.urlencode(kept)
    return {f"url:{normalized}"}


class Board:
    def __init__(self, root: Path):
        self.root = root

    def applications(self) -> list[dict]:
        found = [self.summary(file.parent)
                 for stage in STAGES for file in (self.root / stage).glob(f"*/{APPLICATION_FILE}")]
        return sorted(found, key=lambda a: (a.get("created", ""), a["id"]), reverse=True)

    def find(self, app_id: str) -> Path:
        _require_segment(app_id, "application id")
        for stage in STAGES:
            folder = self.root / stage / app_id
            if (folder / APPLICATION_FILE).is_file():
                return folder
        raise BoardError(HTTPStatus.NOT_FOUND, "application not found")

    def open_application_for(self, urls: list[str]) -> dict | None:
        """The open (not Closed) Application for the Job Posting behind any of `urls`, newest first."""
        wanted = set().union(*(posting_keys(url) for url in urls))
        for app in self.applications():  # newest first
            if app["stage"] == CLOSED:
                continue
            links = (app.get(field, "") for field in ("job_url", "apply_url"))
            if any(posting_keys(link) & wanted for link in links if link):
                return app
        return None

    def summary(self, folder: Path) -> dict:
        front, _ = _read(folder)
        return {**front, "id": folder.name, "stage": folder.parent.name}

    def move(self, app_id: str, stage: str, closed_reason: str | None = None) -> dict:
        if stage not in STAGES:
            raise BoardError(HTTPStatus.BAD_REQUEST, f"unknown stage: {stage}")
        if stage == CLOSED and closed_reason not in CLOSED_REASONS:
            raise BoardError(HTTPStatus.BAD_REQUEST, f"closed_reason must be one of {CLOSED_REASONS}")
        folder = self.find(app_id)
        target = self.root / stage / app_id
        if target != folder and target.exists():
            raise BoardError(HTTPStatus.CONFLICT, f"{stage}/{app_id} already exists")

        # Rewrite the file first: if it fails, the Application is still in its old Stage, unchanged.
        front, notes = _read(folder)
        if stage == CLOSED:
            front["closed_reason"] = closed_reason
        else:
            front.pop("closed_reason", None)
        if target != folder:
            # Keep only the last entry per Stage; later Stages' entries would be stale (docs/adr/0003).
            for later in STAGES[STAGES.index(stage) + 1:]:
                front.pop(_entered_field(later), None)
            front[_entered_field(stage)] = now().isoformat(timespec="minutes")
        _write(folder, front, notes)
        if target != folder:
            target.parent.mkdir(parents=True, exist_ok=True)
            folder.rename(target)
        return self.summary(target)

    def detail(self, app_id: str) -> dict:
        folder = self.find(app_id)
        _, notes = _read(folder)
        job_info = folder / JOB_INFO_FILE
        return {
            **self.summary(folder),
            "notes": notes,
            "job_info": job_info.read_text(encoding="utf-8") if job_info.is_file() else None,
            "files": sorted(p.name for p in folder.iterdir() if p.is_file() and p.name != APPLICATION_FILE),
        }

    def save_notes(self, app_id: str, notes: str) -> dict:
        if not isinstance(notes, str):
            raise BoardError(HTTPStatus.BAD_REQUEST, "notes must be a string")
        folder = self.find(app_id)
        front, _ = _read(folder)
        _write(folder, front, notes)
        return self.detail(app_id)

    def open_folder(self, app_id: str) -> dict:
        """Show the Application's folder in the OS file manager, with the CV's PDF selected if any."""
        folder = self.find(app_id)
        # The CV is what gets attached, so a cover letter PDF only wins when it is the only PDF.
        pdfs = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
                      key=lambda p: ("cover letter" in p.name.lower(), p.name))
        try:
            reveal(folder, pdfs[0] if pdfs else None)
        except (OSError, subprocess.CalledProcessError) as err:
            raise BoardError(HTTPStatus.INTERNAL_SERVER_ERROR, f"could not open the folder: {err}")
        return {"opened": folder.name}

    def file(self, app_id: str, name: str) -> Path:
        _require_segment(name, "file name")
        path = self.find(app_id) / name
        if not path.is_file():
            raise BoardError(HTTPStatus.NOT_FOUND, "file not found")
        return path


def now() -> datetime:
    """Local wall-clock time; the one seam tests replace."""
    return datetime.now()


def _entered_field(stage: str) -> str:
    """Frontmatter field recording when an Application last entered `stage` (e.g. `in_process_at`)."""
    return stage.replace("-", "_") + "_at"


def _read(folder: Path) -> tuple[dict[str, str], str]:
    return parse_application((folder / APPLICATION_FILE).read_text(encoding="utf-8"))


def _write(folder: Path, front: dict[str, str], notes: str) -> None:
    (folder / APPLICATION_FILE).write_text(render_application(front, notes), encoding="utf-8")


def _is_wsl() -> bool:
    return "microsoft" in platform.uname().release.lower()


def reveal_command(folder: Path, select: Path | None) -> list[str]:
    """The command that opens `folder` in the file manager, highlighting `select` where the OS can."""
    if sys.platform == "darwin":
        return ["open", "-R", str(select)] if select else ["open", str(folder)]
    if _is_wsl():
        def windows(path: Path) -> str:
            return subprocess.check_output(["wslpath", "-w", str(path.resolve())], text=True).strip()
        if not select:
            return ["explorer.exe", windows(folder)]
        # Explorer only parses /select,"<path>"; WSL would quote the whole argument when the path has
        # spaces and Explorer would fall back to Documents. PowerShell passes the argument through as is.
        path = windows(select).replace("'", "''")  # escape for a PowerShell single-quoted string
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                f"Start-Process explorer.exe -ArgumentList '/select,\"{path}\"'"]
    return ["xdg-open", str(folder)]


def reveal(folder: Path, select: Path | None) -> None:
    # Fire and forget: explorer.exe exits non-zero even on success, and the window outlives the request.
    subprocess.Popen(reveal_command(folder, select), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def _require_segment(name: str, what: str) -> None:
    """Reject anything that is not a single path segment, so requests can't escape the root."""
    if name in ("", ".", "..") or "/" in name or "\\" in name:
        raise BoardError(HTTPStatus.BAD_REQUEST, f"invalid {what}")


def create_server(root: Path, port: int) -> ThreadingHTTPServer:
    board = Board(Path(root))
    unquote = urllib.parse.unquote

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._dispatch(self._get)

        def do_POST(self):
            self._dispatch(self._post)

        def do_PUT(self):
            self._dispatch(self._put)

        def _dispatch(self, route):
            try:
                route(urllib.parse.urlsplit(self.path).path)
            except BoardError as err:
                self._json({"error": str(err)}, err.status)

        def _get(self, path):
            if path == "/api/applications":
                return self._json({"stages": STAGES, "closed_reasons": CLOSED_REASONS,
                                   "applications": board.applications()})
            if (match := API_ROUTE.match(path)) and not match.group(2):
                return self._json(board.detail(unquote(match.group(1))))
            if match := FILE_ROUTE.match(path):
                file = board.file(unquote(match.group(1)), unquote(match.group(2)))
                return self._send(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            if path == "/" or (path.count("/") == 1 and Path(path).suffix in UI_TYPES):
                ui = UI_DIR / ("index.html" if path == "/" else path[1:])
                if ui.is_file():
                    return self._send(ui.read_bytes(), UI_TYPES[ui.suffix] + "; charset=utf-8")
            raise BoardError(HTTPStatus.NOT_FOUND, "not found")

        def _post(self, path):
            match = API_ROUTE.match(path)
            if not match or match.group(2) not in ("move", "open-folder"):
                raise BoardError(HTTPStatus.NOT_FOUND, "not found")
            body = self._body()
            if match.group(2) == "open-folder":
                return self._json(board.open_folder(unquote(match.group(1))))
            self._json(board.move(unquote(match.group(1)), body.get("stage", ""), body.get("closed_reason")))

        def _put(self, path):
            match = API_ROUTE.match(path)
            if not match or match.group(2) != "notes":
                raise BoardError(HTTPStatus.NOT_FOUND, "not found")
            self._json(board.save_notes(unquote(match.group(1)), self._body().get("notes")))

        def _send(self, body: bytes, content_type: str, status=HTTPStatus.OK):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            """Read a write request's JSON body, refusing requests another website could forge."""
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{self.headers.get('Host')}":
                raise BoardError(HTTPStatus.FORBIDDEN, "cross-origin request refused")
            if self.headers.get_content_type() != "application/json":
                raise BoardError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "expected application/json")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                raise BoardError(HTTPStatus.BAD_REQUEST, "invalid JSON")
            if not isinstance(data, dict):
                raise BoardError(HTTPStatus.BAD_REQUEST, "expected a JSON object")
            return data

        def _json(self, payload, status=HTTPStatus.OK):
            self._send(json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8", status)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((HOST, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="TailorCV application board")
    parser.add_argument("--root", default=Path(__file__).parent / "generated_cvs", type=Path)
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--check", nargs="+", metavar="URL",
                        help="exit 1 and print the open Application for these Job Posting links, if any")
    args = parser.parse_args()
    if args.check:
        app = Board(args.root).open_application_for(args.check)
        if app:
            print(f"{app['stage']}/{app['id']}  {app.get('company', '?')} — {app.get('role', '?')}")
            sys.exit(1)
        return
    server = create_server(args.root, args.port)
    print(f"TailorCV board on http://{HOST}:{args.port}  (root: {args.root})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
