import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from echo_recon import installer


class CapturedInput:
    def __init__(self):
        self.value = ""
        self.closed = False
    def write(self, value):
        self.value += value
    def flush(self):
        pass
    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, output, returncode):
        self.stdin = CapturedInput()
        self.stdout = io.StringIO(output)
        self.returncode = returncode
    def wait(self):
        return self.returncode


class InstallerTests(unittest.TestCase):
    def test_password_only_goes_to_stdin_not_command_arguments_or_logs(self):
        secret = "very-secret-test-password"
        process = FakeProcess("sudo: 1 incorrect password attempt\n", 1)
        calls = {}
        def fake_popen(argv, **kwargs):
            calls["argv"] = argv
            calls["proc"] = process
            return process
        logs = []
        with tempfile.TemporaryDirectory() as td, \
             patch.object(installer.os, "geteuid", return_value=1000), \
             patch.object(installer.subprocess, "Popen", side_effect=fake_popen):
            Path(td, "install_linux.sh").write_text("#!/bin/sh\nexit 0\n")
            result = installer.run_installer(Path(td), secret, logs.append)
        self.assertTrue(result["wrong_password"])
        self.assertNotIn(secret, " ".join(calls["argv"]))
        self.assertEqual(process.stdin.value, secret + "\n")
        self.assertTrue(process.stdin.closed)
        self.assertNotIn(secret, "\n".join(logs))

    def test_successful_install_result_is_detected(self):
        process = FakeProcess("[OK] nmap\nInstaller steps finished\n", 0)
        with tempfile.TemporaryDirectory() as td, \
             patch.object(installer.os, "geteuid", return_value=1000), \
             patch.object(installer.subprocess, "Popen", return_value=process):
            Path(td, "install_linux.sh").write_text("#!/bin/sh\nexit 0\n")
            result = installer.run_installer(Path(td), "password-for-test")
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(result["wrong_password"])
        self.assertIn("Installer steps finished", "\n".join(result["tail"]))


if __name__ == "__main__":
    unittest.main()
