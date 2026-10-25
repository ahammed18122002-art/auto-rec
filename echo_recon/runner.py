"""Sequential subprocess runner with process-group cancellation and bounded runtime."""
from __future__ import annotations

import json
import os
import queue
import re
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .scope import Target, bound_active_hosts, filter_in_scope_hosts, parse_target, redact_url
from .tools import TOOLS, ToolSpec, build_command, tool_status, runtime_env
from .reports import write_reports

MessageFn = Callable[[str], None]


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _signal_process_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError, AttributeError):
        try:
            proc.send_signal(sig)
        except Exception:
            pass


def run_process(argv: list[str], output_path: Path, timeout_seconds: int,
                cancel_event: threading.Event, log: MessageFn | None = None) -> dict:
    """Run a child without shell; persist output continuously and terminate stuck groups."""
    started = time.monotonic()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if cancel_event.is_set():
        output_path.write_text("Cancelled before process start.\n", encoding="utf-8")
        return {"status": "cancelled", "returncode": None, "duration_seconds": 0, "message": "Cancelled before process start."}
    if not argv or not isinstance(argv[0], str):
        return {"status": "failed", "returncode": None, "duration_seconds": 0, "message": "Invalid command"}
    try:
        with output_path.open("wb") as stream:
            proc = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True, env=runtime_env())
            # Measure the watchdog after spawn; a slow OS/process scheduler must
            # not consume the tool's entire runtime budget before it starts.
            deadline = time.monotonic() + timeout_seconds
            offset = 0
            last_flush = 0.0
            status = "ok"
            while proc.poll() is None:
                now = time.monotonic()
                if cancel_event.is_set():
                    status = "cancelled"
                    _signal_process_group(proc, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        _signal_process_group(proc, signal.SIGKILL)
                        proc.wait()
                    break
                if now >= deadline:
                    status = "timeout"
                    _signal_process_group(proc, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        _signal_process_group(proc, signal.SIGKILL)
                        proc.wait()
                    break
                if log and now - last_flush >= 1.0:
                    stream.flush()
                    try:
                        with output_path.open("rb") as reader:
                            reader.seek(offset)
                            chunk = reader.read()
                            offset = reader.tell()
                        if chunk:
                            text_chunk = chunk.decode("utf-8", errors="replace")
                            for line in text_chunk.splitlines()[-12:]:
                                if line.strip():
                                    log(line[:500])
                    except OSError:
                        pass
                    last_flush = now
                time.sleep(0.15)
            stream.flush()
            returncode = proc.wait()
    except FileNotFoundError:
        return {"status": "missing", "returncode": None, "duration_seconds": round(time.monotonic()-started, 2),
                "message": f"Executable not found: {argv[0]}"}
    except Exception as exc:
        return {"status": "failed", "returncode": None, "duration_seconds": round(time.monotonic()-started, 2),
                "message": f"Runner exception: {type(exc).__name__}: {exc}"}

    if status == "ok" and returncode != 0:
        status = "failed"
    message = ""
    if status == "timeout":
        message = f"Runtime limit reached ({timeout_seconds}s); partial output was saved."
    elif status == "cancelled":
        message = "Stopped by user; partial output was saved."
    elif status == "failed":
        message = f"Tool exited with code {returncode}; output was saved."
    return {"status": status, "returncode": returncode,
            "duration_seconds": round(time.monotonic()-started, 2), "message": message}


def _parse_subfinder_output(path: Path, target: Target) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    candidates = []
    for line in lines:
        value = line.strip().lower().rstrip(".")
        # Subfinder -silent should emit a hostname per line. Do not extract arbitrary URLs.
        if value.startswith("http://") or value.startswith("https://"):
            from urllib.parse import urlsplit
            value = (urlsplit(value).hostname or "").lower()
        if value:
            candidates.append(value)
    return filter_in_scope_hosts(candidates, target.host)


def run_scan(target_value: str, selected_tools: list[str], max_runtime_seconds: int,
             cancel_event: threading.Event, log: MessageFn | None = None) -> dict:
    """Run chosen tools serially; always save a report for completed/partial jobs."""
    if not 60 <= int(max_runtime_seconds) <= 7200:
        raise ValueError("Per-tool watchdog must be between 60 and 7200 seconds.")
    target = parse_target(target_value)
    start_time = utc_now()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{stamp}_{re.sub(r'[^a-zA-Z0-9.-]', '_', target.host)[:60]}"
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = base_dir / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    wordlist = base_dir / "wordlists" / "common_paths.txt"

    status_snapshot = tool_status()
    results: list[dict] = []
    hosts = [target.host]
    passive_discovered_hosts: list[str] = []
    selected_set = set(selected_tools)
    ordered = [spec for spec in TOOLS if spec.key in selected_set]
    if log:
        log(f"Run folder: outputs/{run_id}")
        log(f"Target: {redact_url(target.url)}")
        log("Tools run sequentially; retries are disabled where supported; out-of-scope hosts are filtered.")

    for spec in ordered:
        if cancel_event.is_set():
            results.append({"tool": spec.label, "key": spec.key, "status": "skipped", "returncode": None,
                            "duration_seconds": 0, "message": "Not started because the scan was cancelled.", "output_file": ""})
            continue
        out_path = out_dir / f"{spec.key}.log"
        if not status_snapshot[spec.key]["installed"]:
            results.append({"tool": spec.label, "key": spec.key, "status": "missing", "returncode": None,
                            "duration_seconds": 0, "message": str(status_snapshot[spec.key]["status"]),
                            "output_file": out_path.name})
            out_path.write_text(f"{spec.binary} was not found in PATH. Run ./install_linux.sh and check the tool list.\n", encoding="utf-8")
            if log:
                log(f"[{spec.label}] skipped: executable not installed")
            continue

        if spec.key == "sqlmap" and not target.has_query_parameters:
            message = "Skipped: SQLmap requires a parameterized URL, such as https://example.com/item?id=1."
            results.append({"tool": spec.label, "key": spec.key, "status": "skipped", "returncode": None,
                            "duration_seconds": 0, "message": message, "output_file": out_path.name})
            out_path.write_text(message + "\n", encoding="utf-8")
            if log:
                log(f"[{spec.label}] {message}")
            continue

        # Use only hosts confirmed in-scope from passive enumeration; never scan arbitrary discovered domains.
        if spec.key in {"dnsx", "httpx"}:
            hostfile = out_dir / "hosts_in_scope.txt"
            hostfile.write_text("\n".join(hosts) + "\n", encoding="utf-8")
        argv, skip_message = build_command(spec, target, out_dir, wordlist, max_runtime_seconds)
        if argv is None:
            results.append({"tool": spec.label, "key": spec.key, "status": "skipped", "returncode": None,
                            "duration_seconds": 0, "message": skip_message, "output_file": out_path.name})
            out_path.write_text(skip_message + "\n", encoding="utf-8")
            continue
        if log:
            log(f"[{spec.label}] starting (per-tool watchdog {max_runtime_seconds}s)")
        result = run_process(argv, out_path, int(max_runtime_seconds), cancel_event,
                             (lambda s: log(f"[{spec.label}] {s}")) if log else None)
        result.update({"tool": spec.label, "key": spec.key, "output_file": out_path.name})
        results.append(result)
        if log:
            log(f"[{spec.label}] {result['status']} · {result.get('duration_seconds', 0)} sec")
        if spec.key == "subfinder" and result["status"] == "ok":
            passive_discovered_hosts = _parse_subfinder_output(out_path, target)
            (out_dir / "passive_hosts_in_scope.txt").write_text(
                "\n".join(passive_discovered_hosts) + ("\n" if passive_discovered_hosts else ""), encoding="utf-8")
            hosts = bound_active_hosts(target.host, passive_discovered_hosts, max_hosts=100)
            (out_dir / "hosts_in_scope.txt").write_text("\n".join(hosts) + "\n", encoding="utf-8")
            if log:
                log(f"[Scope] passive discovery returned {len(passive_discovered_hosts)} in-scope host(s); active DNS/HTTP probing capped at {len(hosts)} host(s)")

    final_status = "cancelled" if cancel_event.is_set() else (
        "partial" if any(r["status"] in {"failed", "timeout", "missing"} for r in results) else "completed")
    findings = {
        "app": "Echo Recon Linux Edition",
        "version": "echo 2026.10",
        "run_id": run_id,
        "started_at": start_time,
        "finished_at": utc_now(),
        "target": redact_url(target.url),
        "scope": f"Exact host {target.host} and passive-discovered DNS descendants only; active web checks use submitted origin.",
        "status": final_status,
        "max_runtime_seconds_per_tool": int(max_runtime_seconds),
        "selected_tools": [spec.key for spec in ordered],
        "tools": results,
        "passive_discovered_host_count": len(passive_discovered_hosts),
        "active_probe_host_cap": 100,
        "host_count_in_scope": len(hosts),
        "hosts_in_scope": hosts,
        "report_dir": str(out_dir),
        "notes": [
            "Only run on assets you own or are explicitly authorized to assess.",
            "A scanner signal is not a confirmed vulnerability until manually verified.",
            "Missing tools, failed tools, timeouts and cancellation remain visible in the report.",
            "Rates vary by tool; rate caps are applied where the specific CLI supports them.",
            "Live DNS/HTTP host probing is capped at 100 hosts per run; the full filtered passive list is saved separately.",
        ],
    }
    write_reports(out_dir, findings)
    if log:
        log(f"Report saved: outputs/{run_id}/report.html")
        log(f"Final status: {final_status}")
    return findings
