"""Run the Linux installer while keeping sudo input out of logs and files."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable

LineFn = Callable[[str], None]


def run_installer(repo_root: Path, password: str, log: LineFn | None = None) -> dict:
    """Run install_linux.sh with sudo; the password is sent only to sudo stdin.

    The installer itself is launched as root so apt can operate, but the script
    uses SUDO_USER to place CLI binaries in that user's ~/.local/bin instead of
    accidentally installing them only in /root.
    """
    script = (repo_root / "install_linux.sh").resolve()
    if not script.is_file():
        raise FileNotFoundError(f"Installer script not found: {script}")

    if os.geteuid() == 0:
        argv = ["bash", str(script)]
        stdin_data = None
    else:
        if not password:
            return {"returncode": 1, "wrong_password": False, "tail": ["sudo password is required"]}
        argv = ["sudo", "-k", "-S", "-p", "", "bash", str(script)]
        stdin_data = password + "\n"
    # Do not log argv's stdin, the password, or any environment values containing secrets.
    password = ""
    proc = subprocess.Popen(argv, cwd=str(repo_root), stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            bufsize=1, close_fds=True, start_new_session=True)
    if stdin_data is not None:
        try:
            assert proc.stdin is not None
            proc.stdin.write(stdin_data)
            proc.stdin.flush()
        except BrokenPipeError:
            # sudo may reject the invocation before consuming stdin; still drain its output.
            pass
        finally:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except OSError:
                pass
            stdin_data = ""
    tail: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\r\n")
        tail.append(line)
        if len(tail) > 250:
            del tail[:len(tail) - 250]
        if log:
            log(line)
    code = proc.wait()
    output = "\n".join(tail).lower()
    wrong_password = code != 0 and bool(re.search(
        r"incorrect password|sorry, try again|authentication failure|a password is required|no password was provided",
        output,
    ))
    return {"returncode": code, "wrong_password": wrong_password, "tail": tail[-30:]}
