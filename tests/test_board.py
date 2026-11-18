"""Board HTTP API, exercised against a real server over a temporary generated_cvs/ tree.

Run: python3 -m unittest discover -s tests
"""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import board  # noqa: E402


class BoardServerCase(unittest.TestCase):
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


class BoardApiTest(BoardServerCase):
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

    def test_lists_and_opens_the_fit(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10", fit="4")
        _, data = self.call("GET", "/api/applications")
        self.assertEqual(data["applications"][0]["fit"], "4")
        _, detail = self.call("GET", "/api/applications/2026-11-10_Acme_Engineer")
        self.assertEqual(detail["fit"], "4")

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
        (folder / "job_info.md").write_text("# Acme\n\nResearch.\n")
        (folder / "Jane Doe - Acme.pdf").write_bytes(b"%PDF-1.4")
        (folder / "Jane Doe - Acme.md").write_text("# CV")

        status, body = self.call("GET", "/api/applications/2026-11-10_Acme_Engineer")

        self.assertEqual(status, 200)
        self.assertEqual(body["stage"], "applied")
        self.assertEqual(body["notes"], "Talked to Ana.\n")
        self.assertEqual(body["job_info"], "# Acme\n\nResearch.\n")
        self.assertEqual(body["files"], ["Jane Doe - Acme.md", "Jane Doe - Acme.pdf", "job_info.md"])

    def test_serves_a_file_of_the_application(self):
        folder = self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10")
        (folder / "Jane Doe - Acme.pdf").write_bytes(b"%PDF-1.4")

        status, body = self.call("GET", "/files/2026-11-10_Acme_Engineer/Jane%20Doe%20-%20Acme.pdf")

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


class TimeInStageTest(BoardServerCase):
    """Entering a Stage records when, as `<stage>_at` in the frontmatter (see docs/adr/0003)."""

    APP = "2026-11-10_Acme_Engineer"

    def move_at(self, when, stage, **body):
        with mock.patch.object(board, "now", return_value=datetime(*when)):
            status, summary = self.call("POST", f"/api/applications/{self.APP}/move", {"stage": stage, **body})
        self.assertEqual(status, 200)
        return summary

    def test_entering_a_stage_records_when(self):
        self.write_application("awaiting", self.APP, "2026-11-10")

        summary = self.move_at((2026, 11, 17, 14, 30), "applied")

        self.assertEqual(summary["applied_at"], "2026-11-17T14:30")
        _, body = self.call("GET", "/api/applications")
        self.assertEqual(body["applications"][0]["applied_at"], "2026-11-17T14:30")

    def test_moving_back_restarts_the_stage_and_forgets_later_ones(self):
        self.write_application("in-process", self.APP, "2026-11-10", applied_at="2026-11-11T09:00",
                               in_process_at="2026-11-14T10:00", offer_at="2026-11-15T10:00",
                               closed_at="2026-11-16T10:00")

        summary = self.move_at((2026, 11, 17, 14, 30), "applied")

        self.assertEqual(summary["applied_at"], "2026-11-17T14:30")
        for later in ("in_process_at", "offer_at", "closed_at"):
            self.assertNotIn(later, summary)
        text = (self.root / "applied" / self.APP / "application.md").read_text()
        self.assertNotIn("in_process_at", text)

    def test_closing_without_a_response_keeps_when_it_was_applied(self):
        self.write_application("applied", self.APP, "2026-11-10", applied_at="2026-11-11T09:00")

        summary = self.move_at((2026, 11, 23, 8, 5), "closed", closed_reason="rejected")

        self.assertEqual(summary["applied_at"], "2026-11-11T09:00")
        self.assertEqual(summary["closed_at"], "2026-11-23T08:05")
        self.assertNotIn("in_process_at", summary)

    def test_moving_to_the_current_stage_keeps_its_entry(self):
        self.write_application("applied", self.APP, "2026-11-10", applied_at="2026-11-11T09:00")

        summary = self.move_at((2026, 11, 17, 14, 30), "applied")

        self.assertEqual(summary["applied_at"], "2026-11-11T09:00")


if __name__ == "__main__":
    unittest.main()


class OpenFolderTest(BoardServerCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(board, "reveal")
        self.reveal = patcher.start()
        self.addCleanup(patcher.stop)

    def test_opens_the_folder_with_the_cv_pdf_selected_over_a_cover_letter(self):
        folder = self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10")
        (folder / "Jane Doe - Acme.pdf").write_bytes(b"%PDF-1.4")
        (folder / "Jane Doe - Acme - Cover Letter.pdf").write_bytes(b"%PDF-1.4")
        (folder / "Jane Doe - Acme.md").write_text("cv")

        status, _ = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/open-folder", {})

        self.assertEqual(status, 200)
        self.reveal.assert_called_once_with(folder, folder / "Jane Doe - Acme.pdf")

    def test_opens_just_the_folder_when_there_is_no_pdf(self):
        folder = self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")

        self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/open-folder", {})

        self.reveal.assert_called_once_with(folder, None)

    def test_reports_a_missing_file_manager(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")
        self.reveal.side_effect = FileNotFoundError("xdg-open")

        status, body = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/open-folder", {})

        self.assertEqual(status, 500)
        self.assertIn("xdg-open", body["error"])

    def test_refuses_other_websites_and_unknown_applications(self):
        self.write_application("awaiting", "2026-11-10_Acme_Engineer", "2026-11-10")

        status, _ = self.call("POST", "/api/applications/2026-11-10_Acme_Engineer/open-folder", {},
                              {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.call("POST", "/api/applications/..%2F..%2Fetc/open-folder", {})
        self.assertIn(status, (400, 404))
        self.reveal.assert_not_called()


class RevealCommandTest(unittest.TestCase):
    folder = Path("/cvs/applied/2026-11-10_Acme_Engineer")
    pdf = folder / "Jane Doe - Acme.pdf"

    def test_linux_opens_the_folder(self):
        with mock.patch.object(board.sys, "platform", "linux"), mock.patch.object(board, "_is_wsl", return_value=False):
            self.assertEqual(board.reveal_command(self.folder, self.pdf), ["xdg-open", str(self.folder)])

    def test_macos_reveals_the_pdf(self):
        with mock.patch.object(board.sys, "platform", "darwin"):
            self.assertEqual(board.reveal_command(self.folder, self.pdf), ["open", "-R", str(self.pdf)])
            self.assertEqual(board.reveal_command(self.folder, None), ["open", str(self.folder)])

    def test_wsl_selects_the_pdf_in_explorer(self):
        with mock.patch.object(board.sys, "platform", "linux"), mock.patch.object(board, "_is_wsl", return_value=True), \
                mock.patch.object(board.subprocess, "check_output", return_value="C:\\cv\\Jane O'Doe - Acme.pdf\n"):
            command = board.reveal_command(self.folder, self.pdf)
            self.assertEqual(command[0], "powershell.exe")
            self.assertEqual(command[-1],
                             "Start-Process explorer.exe -ArgumentList '/select,\"C:\\cv\\Jane O''Doe - Acme.pdf\"'")
            self.assertEqual(board.reveal_command(self.folder, None), ["explorer.exe", "C:\\cv\\Jane O'Doe - Acme.pdf"])


class PostingKeysTest(unittest.TestCase):
    def assertKeys(self, url, *keys):
        self.assertEqual(board.posting_keys(url), set(keys), url)

    def test_ashby_on_its_board_and_embedded_in_a_careers_page(self):
        uuid = "7085c73e-c2a7-4b2f-9a36-49d780e03c2a"
        self.assertKeys(f"https://jobs.ashbyhq.com/buffer/{uuid}", f"ashby:{uuid}")
        self.assertKeys(f"https://jobs.ashbyhq.com/buffer/{uuid}/application", f"ashby:{uuid}")
        self.assertKeys(f"https://buffer.com/journey/{uuid}?ashby_jid={uuid}", f"ashby:{uuid}")
        self.assertKeys(f"https://superhuman.com/company/careers/jobs?ashby_jid={uuid.upper()}", f"ashby:{uuid}")

    def test_lever_with_and_without_apply(self):
        base = "https://jobs.lever.co/bluecoding/456ce1b0-5a77-4a27-9a82-37d0074f14ec"
        self.assertKeys(base, "lever:456ce1b0-5a77-4a27-9a82-37d0074f14ec")
        self.assertKeys(base + "/apply", "lever:456ce1b0-5a77-4a27-9a82-37d0074f14ec")

    def test_greenhouse_on_its_boards_and_embedded(self):
        self.assertKeys("https://boards.greenhouse.io/acme/jobs/4012345", "greenhouse:4012345")
        self.assertKeys("https://job-boards.greenhouse.io/acme/jobs/4012345?utm_source=x", "greenhouse:4012345")
        self.assertKeys("https://acme.com/careers/?gh_jid=4012345", "greenhouse:4012345")

    def test_linkedin_job_on_any_subdomain_and_slug(self):
        self.assertKeys("https://www.linkedin.com/jobs/view/4488830591/", "linkedin-job:4488830591")
        self.assertKeys("https://br.linkedin.com/jobs/view/ai-engineer-at-awesome-motive-4488830591?trk=abc",
                        "linkedin-job:4488830591")

    def test_linkedin_post(self):
        self.assertKeys("https://www.linkedin.com/posts/veraspichka_django-python-htmx-share-7523842219053711362-a8GR/",
                        "linkedin-post:7523842219053711362")
        self.assertKeys("https://www.linkedin.com/feed/update/urn:li:activity:7523842219053711362/",
                        "linkedin-post:7523842219053711362")

    def test_other_links_ignore_tracking_scheme_www_and_trailing_slash(self):
        self.assertKeys("https://fitnext.app.loxo.co/job/NDI0NzQtbW1nczBrb2hiMnRsbjJiOA==?t=1794576631300",
                        "url:fitnext.app.loxo.co/job/NDI0NzQtbW1nczBrb2hiMnRsbjJiOA==")
        self.assertEqual(board.posting_keys("http://www.ruzora.com/jobs/ai-engineer/?utm_campaign=x#apply"),
                         board.posting_keys("https://ruzora.com/jobs/ai-engineer"))
        self.assertEqual(board.posting_keys("https://jobs.hireez.com/hatchworks/4909a1af/HREZ-18119/apply"),
                         board.posting_keys("https://jobs.hireez.com/hatchworks/4909a1af/HREZ-18119"))

    def test_other_query_parameters_identify_the_posting(self):
        self.assertNotEqual(board.posting_keys("https://acme.com/job?id=1"),
                            board.posting_keys("https://acme.com/job?id=2"))

    def test_listing_pages_identify_no_posting(self):
        self.assertKeys("https://www.bluecoding.com/jobs")
        self.assertKeys("https://talent.bluecoding.com/")
        self.assertKeys("https://acme.com/careers/")


class OpenApplicationTest(BoardServerCase):
    ASHBY = "https://jobs.ashbyhq.com/acme/7085c73e-c2a7-4b2f-9a36-49d780e03c2a"

    def setUp(self):
        super().setUp()
        self.board = board.Board(self.root)

    def test_finds_an_open_application_by_job_or_apply_url(self):
        self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10",
                               job_url="https://www.linkedin.com/jobs/view/123/", apply_url=self.ASHBY)

        self.assertEqual(self.board.open_application_for(["https://br.linkedin.com/jobs/view/eng-123"])["id"],
                         "2026-11-10_Acme_Engineer")
        # Same posting reached from another source: the LinkedIn job's apply link is the Ashby posting.
        found = self.board.open_application_for(["https://www.linkedin.com/jobs/view/999/", self.ASHBY + "/application"])
        self.assertEqual((found["stage"], found["id"]), ("applied", "2026-11-10_Acme_Engineer"))
        self.assertIsNone(self.board.open_application_for(["https://www.linkedin.com/jobs/view/999/"]))

    def test_every_stage_but_closed_blocks(self):
        for stage in ("awaiting", "in-process", "offer"):
            self.write_application(stage, f"2026-11-10_Acme{stage}_Engineer", "2026-11-10", job_url=self.ASHBY)
            self.assertIsNotNone(self.board.open_application_for([self.ASHBY]), stage)
            (self.root / stage / f"2026-11-10_Acme{stage}_Engineer" / "application.md").unlink()

        self.write_application("closed", "2026-11-10_Acme_Engineer", "2026-11-10", job_url=self.ASHBY)
        self.assertIsNone(self.board.open_application_for([self.ASHBY]))

    def test_listing_pages_never_match(self):
        self.write_application("applied", "2026-11-10_BlueCoding_Engineer", "2026-11-10",
                               job_url="https://www.bluecoding.com/jobs", apply_url="https://talent.bluecoding.com/")

        self.assertIsNone(self.board.open_application_for(["https://www.bluecoding.com/jobs"]))

    def test_newest_match_wins(self):
        self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10", job_url=self.ASHBY)
        self.write_application("awaiting", "2026-11-12_Acme_Engineer", "2026-11-12", job_url=self.ASHBY)

        self.assertEqual(self.board.open_application_for([self.ASHBY])["id"], "2026-11-12_Acme_Engineer")

    def test_cli_exit_codes(self):
        self.write_application("applied", "2026-11-10_Acme_Engineer", "2026-11-10", job_url=self.ASHBY)
        script = str(Path(board.__file__))

        found = subprocess.run([sys.executable, script, "--root", str(self.root), "--check", self.ASHBY],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(found.returncode, 1)
        self.assertEqual(found.stdout.strip(), "applied/2026-11-10_Acme_Engineer  Acme — Engineer")

        missing = subprocess.run([sys.executable, script, "--root", str(self.root), "--check", "https://acme.com/job/2"],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual((missing.returncode, missing.stdout), (0, ""))
