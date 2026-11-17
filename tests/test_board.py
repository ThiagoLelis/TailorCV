"""Board HTTP API, exercised against a real server over a temporary generated_cvs/ tree.

Run: python3 -m unittest discover -s tests
"""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import board  # noqa: E402


class BoardApiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "generated_cvs"
        self.root.mkdir()
        server = board.create_server(self.root, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def write_application(self, stage, folder, created, notes="", **extra):
        path = self.root / stage / folder
        path.mkdir(parents=True)
        front = {"company": folder.split("_")[1], "role": "Engineer", "created": created, **extra}
        lines = ["---", *(f"{k}: {v}" for k, v in front.items()), "---", ""]
        (path / "application.md").write_text("\n".join(lines) + notes, encoding="utf-8")
        return path

    def call(self, method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                if resp.headers.get_content_type() == "application/json":
                    return resp.status, json.loads(raw)
                return resp.status, raw
        except urllib.error.HTTPError as err:
            raw = err.read()
            return err.code, json.loads(raw) if raw else None

    def test_lists_applications_with_stage_newest_first(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")
        self.write_application("applied", "2026-11-16_Globex_Engineer", "2026-11-16",
                               job_url="https://jobs.example.com/1")
        self.write_application("awaiting", "2026-11-12_Initech_Engineer", "2026-11-12")

        status, body = self.call("GET", "/api/applications")

        self.assertEqual(status, 200)
        self.assertEqual(body["stages"], ["awaiting", "applied", "in-process", "offer", "closed"])
        self.assertEqual([(a["id"], a["stage"]) for a in body["applications"]], [
            ("2026-11-16_Globex_Engineer", "applied"),
            ("2026-11-12_Initech_Engineer", "awaiting"),
            ("2026-11-10_Acme_Engineer", "awaiting"),
        ])
        self.assertEqual(body["applications"][0]["company"], "Globex")
        self.assertEqual(body["applications"][0]["job_url"], "https://jobs.example.com/1")

    def test_moving_to_another_stage_moves_the_folder(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")

        status, body = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move",
                                 {"stage": "applied"})

        self.assertEqual(status, 200)
        self.assertEqual(body["stage"], "applied")
        self.assertTrue((self.root / "applied" / "2026-11-10_Acme_Engineer" / "application.md").is_file())
        self.assertFalse((self.root / "awaiting" / "2026-11-10_Acme_Engineer").exists())

    def test_rejects_unknown_stage_and_unknown_application(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")

        status, _ = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move", {"stage": "hired"})
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/applications/2026-11-11_Nope_Engineer/move", {"stage": "applied"})
        self.assertEqual(status, 404)
        self.assertTrue((self.root / "awaiting" / "2026-11-10_Acme_Engineer").is_dir())

    def test_closing_requires_a_reason_and_records_it(self):
        folder = self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10",
                                        notes="Talked to Ana.\n")

        status, _ = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move", {"stage": "closed"})
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move",
                              {"stage": "closed", "closed_reason": "ghosted"})
        self.assertEqual(status, 400)
        self.assertTrue(folder.is_dir())

        status, body = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move",
                                 {"stage": "closed", "closed_reason": "rejected"})

        self.assertEqual(status, 200)
        self.assertEqual(body["closed_reason"], "rejected")
        text = (self.root / "closed" / "2026-11-10_Acme_Engineer" / "application.md").read_text()
        self.assertIn("closed_reason: rejected", text)
        self.assertTrue(text.endswith("Talked to Ana.\n"))

    def test_leaving_closed_clears_the_reason(self):
        self.write_application("closed", "2026-11-10_Acme_Engineer", "2026-11-10",
                               closed_reason="posting-closed")

        status, body = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/move",
                                 {"stage": "awaiting"})

        self.assertEqual(status, 200)
        self.assertNotIn("closed_reason", body)
        text = (self.root / "awaiting" / "2026-11-10_Acme_Engineer" / "application.md").read_text()
        self.assertNotIn("closed_reason", text)

    def test_opening_an_application_returns_notes_job_info_and_files(self):
        folder = self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10",
                                        notes="Talked to Ana.\n")
        (folder / "vaga_info.md").write_text("# Acme\n\nResearch.\n")
        (folder / "Thiago Lelis - Acme.pdf").write_bytes(b"%PDF-1.4")
        (folder / "Thiago Lelis - Acme.md").write_text("# CV")

        status, body = self.call("GET", "/api/applications/2026-11-10_Acme_Engineer")

        self.assertEqual(status, 200)
        self.assertEqual(body["stage"], "applied")
        self.assertEqual(body["notes"], "Talked to Ana.\n")
        self.assertEqual(body["job_info"], "# Acme\n\nResearch.\n")
        self.assertEqual(body["files"], ["Thiago Lelis - Acme.md", "Thiago Lelis - Acme.pdf", "vaga_info.md"])

    def test_serves_a_file_of_the_application(self):
        folder = self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10")
        (folder / "Thiago Lelis - Acme.pdf").write_bytes(b"%PDF-1.4")

        status, body = self.call("GET", "/files/2026-11-10_Acme_Engineer/Thiago%20Lelis%20-%20Acme.pdf")

        self.assertEqual(status, 200)
        self.assertEqual(body, b"%PDF-1.4")

    def test_saving_notes_keeps_the_frontmatter(self):
        self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10",
                               job_url="https://jobs.example.com/1", notes="old\n")

        status, _ = self.call("PUT", "/api/applications/2026-11-10_Acme_Engineer/notes",
                              {"notes": "## 16/11\nRecruiter call — went well.\n"})

        self.assertEqual(status, 200)
        _, body = self.call("GET", "/api/applications/2026-11-10_Acme_Engineer")
        self.assertEqual(body["notes"], "## 16/11\nRecruiter call — went well.\n")
        self.assertEqual(body["job_url"], "https://jobs.example.com/1")
        self.assertEqual(body["company"], "Acme")

    def test_rejects_paths_that_escape_the_root(self):
        self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10")
        (self.root.parent / "secret.txt").write_text("nope")

        for path in ["/files/2026-11-10_Acme_Engineer/..%2F..%2F..%2Fsecret.txt",
                     "/files/..%2F..%2Fsecret.txt/x",
                     "/api/applications/..%2F..%2Fsecret.txt"]:
            status, _ = self.call("GET", path)
            self.assertIn(status, (400, 404), path)

    def test_writes_from_other_websites_are_refused(self):
        folder = self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")
        move = "/api/applications/2026-11-10_Acme_Engineer/move"

        # A plain cross-site form/fetch can't set application/json without a CORS preflight.
        status, _ = self.call("POST", move, {"stage": "applied"}, {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        status, _ = self.call("POST", move, {"stage": "applied"}, {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.call("PUT", "/api/applications/2026-11-10_Acme_Engineer/notes", {"notes": "x"},
                              {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertTrue(folder.is_dir())

        status, _ = self.call("POST", move, {"stage": "applied"}, {"Origin": self.base})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
