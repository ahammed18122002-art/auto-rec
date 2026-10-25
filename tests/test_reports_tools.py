import json
import tempfile
import threading
import unittest
from pathlib import Path

from echo_recon.reports import write_reports
from echo_recon.scope import parse_target
from echo_recon.tools import TOOLS, build_command, runtime_env, runtime_path


class ToolAndReportTests(unittest.TestCase):
    def test_exactly_fourteen_tool_definitions(self):
        self.assertEqual(len(TOOLS), 14)
        self.assertEqual(len({t.key for t in TOOLS}), 14)



    def test_all_fourteen_tools_have_official_repository_records(self):
        root = Path(__file__).resolve().parent.parent
        data = json.loads((root / "tool_repositories.json").read_text(encoding="utf-8"))
        records = data["tools"]
        self.assertEqual(len(records), 14)
        self.assertEqual(len({item["key"] for item in records}), 14)
        self.assertTrue(all(item["repository"].startswith("https://github.com/") for item in records))

    def test_runtime_path_includes_user_local_bin(self):
        path = runtime_path().split(":")
        self.assertIn(str(Path.home() / ".local" / "bin"), path)
        self.assertIn(str(Path.home() / "go" / "bin"), path)
        self.assertEqual(runtime_env()["PATH"], runtime_path())

    def test_sqlmap_skips_without_query_parameters(self):
        target = parse_target("https://example.com")
        with tempfile.TemporaryDirectory() as td:
            cmd, message = build_command(next(t for t in TOOLS if t.key == "sqlmap"), target, Path(td), Path(td)/"words", 3600)
            self.assertIsNone(cmd)
            self.assertIn("query parameters", message)

    def test_sqlmap_is_low_level_and_has_no_dump_or_shell_flags(self):
        target = parse_target("https://example.com/item?id=1")
        with tempfile.TemporaryDirectory() as td:
            cmd, message = build_command(next(t for t in TOOLS if t.key == "sqlmap"), target, Path(td), Path(td)/"words", 3600)
            self.assertIsNotNone(cmd)
            self.assertIn("--risk=1", cmd)
            self.assertIn("--retries=0", cmd)
            self.assertFalse(any(x in cmd for x in ("--dump", "--os-shell", "--file-read")))

    def test_report_is_written_and_html_escapes_tool_output_text(self):
        sample = {"run_id": "run1", "target": "https://example.com", "status": "partial", "tools": [
            {"tool": "<script>", "status": "failed", "returncode": 3, "duration_seconds": 1, "message": "<bad>", "output_file": "t.log"}],
            "notes": ["manual verification"], "hosts_in_scope": ["example.com"], "host_count_in_scope": 1}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_reports(root, sample)
            self.assertTrue((root / "report.html").exists())
            self.assertTrue((root / "report.md").exists())
            data = json.loads((root / "report.json").read_text())
            self.assertEqual(data["status"], "partial")
            html = (root / "report.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
