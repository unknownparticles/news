import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import automation as flow
from test_reports import daily


class AutomationTest(unittest.TestCase):
    def test_publish_failure_cannot_push(self):
        calls = []
        with patch.object(flow, "repository"), patch.object(flow, "import_reviewed"), \
                patch.object(flow, "command", side_effect=lambda *a, **kw: calls.append(a) or ""), \
                patch.object(flow, "check", side_effect=ValueError("测试失败")):
            with self.assertRaises(ValueError):
                flow.publish()
        self.assertFalse(any(call[:2] == ("git", "push") for call in calls))

    def test_old_draft_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".local").mkdir()
            (root / ".local/daily.json").write_text(json.dumps(daily()))
            with patch.object(flow, "ROOT", root), patch.object(flow, "command") as command:
                with self.assertRaises(ValueError):
                    flow.import_reviewed("2026-10-26")
                command.assert_not_called()

    def test_existing_daily_is_not_imported_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports/daily").mkdir(parents=True)
            (root / "reports/daily/2026-10-26.json").write_text("{}")
            with patch.object(flow, "ROOT", root), patch.object(flow, "command") as command:
                flow.import_reviewed("2026-10-26")
                command.assert_not_called()

    def test_wrong_repository_is_rejected(self):
        with patch.object(flow, "command", return_value="https://github.com/other/repo.git"):
            with self.assertRaises(ValueError):
                flow.repository()

    def test_private_files_and_real_tokens_are_not_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            bad = root / "reports/example.json"
            with patch.object(flow, "ROOT", root):
                for path in (".local/daily.json", "config/.env", "../private.json", ".codex/config.toml"):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        flow.check_public_files([path])
                bad.write_text("ghp_" + "a" * 36)
                with self.assertRaises(ValueError):
                    flow.check_public_files(["reports/example.json"])
                bad.write_text("规则可讨论年龄条件，但不包含用户资料。")
                flow.check_public_files(["reports/example.json"])

    def test_site_verification_rejects_old_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/index.html").write_text("new content")
            def command(*args, **kwargs):
                if args[:2] == ("git", "rev-parse"):
                    return "new-sha"
                if args[:3] == ("gh", "run", "list"):
                    return json.dumps([{"databaseId": 1, "headSha": "new-sha", "status": "completed", "conclusion": "success"}])
                return "old content"
            with patch.object(flow, "ROOT", root), patch.object(flow, "load_reports", return_value=[daily()]), \
                    patch.object(flow, "command", side_effect=command):
                with self.assertRaises(RuntimeError):
                    flow.verify_deployment()

    def test_internal_link_cannot_escape_site(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/index.html").write_text('<a href="../../private.json">bad</a>')
            with patch.object(flow, "ROOT", root), self.assertRaises(ValueError):
                flow.audit_links()
