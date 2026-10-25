import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from echo_recon.runner import run_process


class ProcessRunnerTests(unittest.TestCase):
    def test_cancel_before_start_does_not_spawn_child(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            cancel = threading.Event()
            cancel.set()
            result = run_process([sys.executable, "-c", "raise SystemExit(99)"], path, 10, cancel)
            self.assertEqual(result["status"], "cancelled")
            self.assertIn("Cancelled before process start", path.read_text())

    def test_success_output_is_saved(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            result = run_process([sys.executable, "-c", "print('hello')"], path, 10, threading.Event())
            self.assertEqual(result["status"], "ok")
            self.assertIn("hello", path.read_text())

    def test_nonzero_exit_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            result = run_process([sys.executable, "-c", "print('failed'); raise SystemExit(7)"], path, 10, threading.Event())
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["returncode"], 7)
            self.assertIn("failed", path.read_text())

    def test_timeout_terminates_child_and_preserves_log(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            # Use the shell builtin printf so slow Python interpreter startup in
            # a loaded test runner cannot consume the one-second timeout budget.
            result = run_process(["/bin/sh", "-c", "printf 'started\n'; exec sleep 10"], path, 1, threading.Event())
            self.assertEqual(result["status"], "timeout")
            self.assertIn("started", path.read_text())

    def test_cancel_terminates_child_and_preserves_log(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            cancel = threading.Event()
            def cancel_after_output():
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    try:
                        if path.exists() and "running" in path.read_text(errors="replace"):
                            cancel.set()
                            return
                    except OSError:
                        pass
                    time.sleep(0.05)
                cancel.set()
            threading.Thread(target=cancel_after_output, daemon=True).start()
            result = run_process([sys.executable, "-c", "import time; print('running', flush=True); time.sleep(10)"], path, 10, cancel)
            self.assertEqual(result["status"], "cancelled")
            self.assertIn("running", path.read_text())

    def test_argv_is_not_interpreted_by_a_shell(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.log"
            argument = "; echo unsafe"
            result = run_process([sys.executable, "-c", "import sys; print(sys.argv[1])", argument], path, 10, threading.Event())
            self.assertEqual(result["status"], "ok")
            self.assertEqual(path.read_text().strip(), argument)


if __name__ == "__main__":
    unittest.main()
