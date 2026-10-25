"""Minimal Chrome-inspired Linux GUI for Echo Recon."""
from __future__ import annotations

import os
import platform
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from pathlib import Path

from .runner import run_scan
from .scope import parse_target
from .tools import TOOLS, tool_status
from .installer import run_installer

APP_VERSION = "2026.10"
BG = "#f1f3f4"
SURFACE = "#ffffff"
SURFACE_ALT = "#f8f9fa"
LINE = "#dadce0"
TEXT = "#202124"
MUTED = "#5f6368"
BLUE = "#1a73e8"
BLUE_HOVER = "#1765cc"
GREEN = "#188038"
RED = "#d93025"
TERMINAL_BG = "#101418"
TERMINAL_FG = "#e8eaed"


class EchoReconApp:
    def __init__(self, root: tk.Tk):
        if platform.system() != "Linux":
            raise RuntimeError("Echo Recon supports Linux only.")
        self.root = root
        self.root.title(f"Echo Recon echo {APP_VERSION} · Linux")
        self.root.geometry("1240x940")
        self.root.minsize(1000, 720)
        self.root.configure(bg=BG)
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.install_worker: threading.Thread | None = None
        self.status_worker: threading.Thread | None = None
        self.last_report: Path | None = None
        self.vars = {spec.key: tk.BooleanVar(value=spec.default_selected) for spec in TOOLS}
        self.authorized = tk.BooleanVar(value=False)
        self.runtime = tk.StringVar(value="3600")
        self.status_text = tk.StringVar(value="Checking toolchain · Linux")
        self.toolchain_status = tk.StringVar(value="Checking required tools…")
        self.toolchain_detail = tk.StringVar(value="Checking the local Linux PATH")
        self.install_state = tk.StringVar(value="Password is used only for sudo; it is not saved.")
        self.tool_states: dict = {}
        self._build_styles()
        self._build_ui()
        self._refresh_tool_status(silent=True)
        self.root.after(120, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Sans", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Sans", 9))
        style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=("Sans", 10))
        style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=("Sans", 9))
        style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, insertcolor=TEXT,
                        bordercolor=LINE, padding=(9, 7))
        style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                        foreground=TEXT, arrowcolor=TEXT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=SURFACE, foreground=TEXT, font=("Sans", 9), padding=3)
        style.map("TCheckbutton", background=[("active", SURFACE)], foreground=[("active", TEXT)])
        style.configure("TLabelframe", background=SURFACE, foreground=TEXT, bordercolor=LINE)
        style.configure("TLabelframe.Label", background=SURFACE, foreground=MUTED, font=("Sans", 9, "bold"))
        style.configure("Primary.TButton", background=BLUE, foreground="#ffffff", padding=(13, 8),
                        borderwidth=0, font=("Sans", 10, "bold"))
        style.map("Primary.TButton", background=[("active", BLUE_HOVER), ("disabled", "#b9c7dc")],
                  foreground=[("disabled", "#eef2f7")])
        style.configure("Secondary.TButton", background="#e8f0fe", foreground="#174ea6",
                        padding=(10, 7), borderwidth=0, font=("Sans", 9, "bold"))
        style.map("Secondary.TButton", background=[("active", "#d2e3fc")])
        style.configure("Stop.TButton", background="#fce8e6", foreground=RED,
                        padding=(10, 7), borderwidth=0, font=("Sans", 9, "bold"))
        style.map("Stop.TButton", background=[("active", "#fad2cf")])

    def _build_ui(self) -> None:
        # Chrome-inspired top strip: minimal branding, authorship and version.
        header = tk.Frame(self.root, bg=SURFACE, height=70, highlightbackground=LINE, highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)
        left = tk.Frame(header, bg=SURFACE)
        left.pack(side="left", fill="y", padx=20, pady=10)
        tk.Label(left, text="◉  Echo Recon", bg=SURFACE, fg=BLUE,
                 font=("Sans", 14, "bold")).pack(anchor="w")
        tk.Label(left, text=f"Developed by Ahammed  ·  Supported by nazmul  ·  echo {APP_VERSION}",
                 bg=SURFACE, fg=MUTED, font=("Sans", 9)).pack(anchor="w", pady=(3, 0))
        tk.Label(header, textvariable=self.status_text, bg=SURFACE, fg=MUTED,
                 font=("Sans", 9)).pack(side="right", padx=(8, 12))
        ttk.Button(header, text="—", width=3, style="Secondary.TButton",
                   command=self.root.iconify).pack(side="right", padx=(0, 8), pady=17)

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(10, 12))

        # Requirements/toolchain card, auto-checked at startup.
        toolchain = tk.Frame(main, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        toolchain.pack(fill="x", pady=(0, 10))
        title_row = tk.Frame(toolchain, bg=SURFACE)
        title_row.pack(fill="x", padx=13, pady=(10, 5))
        tk.Label(title_row, text="LOCAL TOOLCHAIN", bg=SURFACE, fg=MUTED,
                 font=("Sans", 8, "bold")).pack(side="left")
        ttk.Button(title_row, text="Check again", style="Secondary.TButton",
                   command=self._refresh_tool_status).pack(side="right", padx=(8, 0))
        self.install_button = ttk.Button(title_row, text="Download all repositories",
                                         style="Primary.TButton", command=self._start_install)
        self.install_button.pack(side="right")

        second_row = tk.Frame(toolchain, bg=SURFACE)
        second_row.pack(fill="x", padx=13, pady=(0, 7))
        status_stack = tk.Frame(second_row, bg=SURFACE)
        status_stack.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.status_label = tk.Label(status_stack, textvariable=self.toolchain_status, bg=SURFACE,
                                     fg=MUTED, font=("Sans", 10, "bold"))
        self.status_label.pack(anchor="w")
        self.detail_label = tk.Label(status_stack, textvariable=self.toolchain_detail, bg=SURFACE,
                                     fg=MUTED, font=("Sans", 9), justify="left", anchor="w", wraplength=620)
        self.detail_label.pack(anchor="w", pady=(3, 0))

        password_stack = tk.Frame(second_row, bg=SURFACE)
        password_stack.pack(side="right", anchor="e")
        tk.Label(password_stack, text="sudo password (not saved)", bg=SURFACE, fg=MUTED,
                 font=("Sans", 8)).pack(anchor="w")
        password_row = tk.Frame(password_stack, bg=SURFACE)
        password_row.pack(anchor="w", pady=(3, 0))
        self.password_entry = ttk.Entry(password_row, width=25, show="•")
        self.password_entry.pack(side="left")
        self.password_entry.bind("<Return>", lambda _event: self._start_install())
        self.install_feedback = tk.Label(password_stack, textvariable=self.install_state, bg=SURFACE,
                                         fg=MUTED, font=("Sans", 8), justify="left", wraplength=300)
        self.install_feedback.pack(anchor="w", pady=(3, 0))

        # Target controls.
        target_card = tk.Frame(main, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        target_card.pack(fill="x", pady=(0, 10))
        tk.Label(target_card, text="TARGET", bg=SURFACE, fg=MUTED,
                 font=("Sans", 8, "bold")).grid(row=0, column=0, sticky="w", padx=(13, 6), pady=(9, 0))
        tk.Label(target_card, text="PER-TOOL LIMIT", bg=SURFACE, fg=MUTED,
                 font=("Sans", 8, "bold")).grid(row=0, column=1, sticky="w", padx=(0, 13), pady=(9, 0))
        self.target_entry = ttk.Entry(target_card, font=("Sans", 11))
        self.target_entry.grid(row=1, column=0, sticky="ew", padx=(13, 12), pady=(5, 10))
        self.target_entry.insert(0, "https://example.com")
        ttk.Combobox(target_card, textvariable=self.runtime, values=("900", "1800", "3600", "7200"),
                     state="readonly", width=10).grid(row=1, column=1, sticky="w", padx=(0, 13), pady=(5, 10))
        target_card.columnconfigure(0, weight=1)
        tk.Label(target_card, text="Use only a domain or URL you own or have explicit permission to test.",
                 bg=SURFACE, fg=MUTED, font=("Sans", 8)).grid(row=2, column=0, columnspan=2,
                                                               sticky="w", padx=13, pady=(0, 9))

        # Minimal two-column selection card.
        tools_panel = ttk.LabelFrame(main, text="  TOOLS  ·  SELECT WHAT TO RUN  ", padding=(10, 6))
        tools_panel.pack(fill="x", pady=(0, 8))
        self.tool_checks: list[ttk.Checkbutton] = []
        for i, spec in enumerate(TOOLS):
            col, row = i % 3, i // 3
            chk = ttk.Checkbutton(tools_panel, text=f"{spec.label}  ·  {spec.category}",
                                  variable=self.vars[spec.key])
            chk.grid(row=row, column=col, sticky="w", padx=(5, 18), pady=1)
            self.tool_checks.append(chk)
        tools_panel.columnconfigure(0, weight=1)
        tools_panel.columnconfigure(1, weight=1)
        tools_panel.columnconfigure(2, weight=1)

        controls = tk.Frame(main, bg=BG)
        controls.pack(fill="x", pady=(0, 7))
        ttk.Button(controls, text="Run selected tools", style="Primary.TButton",
                   command=self._start_scan).pack(side="left")
        ttk.Button(controls, text="Stop scan", style="Stop.TButton",
                   command=self._stop_scan).pack(side="left", padx=(7, 0))
        ttk.Button(controls, text="Open latest report", style="Secondary.TButton",
                   command=self._open_report).pack(side="right")
        ttk.Checkbutton(controls, text="I own this target or have explicit permission to assess it.",
                        variable=self.authorized).pack(side="left", padx=(14, 0))

        # Large terminal panel to make live step-by-step activity readable.
        terminal = tk.Frame(main, bg=TERMINAL_BG, highlightbackground="#c4c7c5", highlightthickness=1)
        terminal.pack(fill="both", expand=True)
        terminal_header = tk.Frame(terminal, bg="#202124", height=38)
        terminal_header.pack(fill="x")
        terminal_header.pack_propagate(False)
        tk.Label(terminal_header, text="●  LIVE TERMINAL  /  STEP-BY-STEP OUTPUT", bg="#202124",
                 fg="#bdc1c6", font=("Sans", 9, "bold")).pack(side="left", padx=11, pady=7)
        ttk.Button(terminal_header, text="Clear", style="Secondary.TButton",
                   command=self._clear_log).pack(side="right", padx=6, pady=3)
        terminal_body = tk.Frame(terminal, bg=TERMINAL_BG)
        terminal_body.pack(fill="both", expand=True)
        terminal_body.rowconfigure(0, weight=1)
        terminal_body.columnconfigure(0, weight=1)
        self.log_box = tk.Text(terminal_body, height=19, bg=TERMINAL_BG, fg=TERMINAL_FG,
                               insertbackground=TERMINAL_FG, selectbackground="#284a72", relief="flat",
                               wrap="none", font=("Monospace", 10), padx=12, pady=10,
                               state="disabled", undo=False)
        yscroll = ttk.Scrollbar(terminal_body, orient="vertical", command=self.log_box.yview)
        xscroll = ttk.Scrollbar(terminal_body, orient="horizontal", command=self.log_box.xview)
        self.log_box.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.log_box.tag_configure("ok", foreground="#81c995")
        self.log_box.tag_configure("error", foreground="#f28b82")
        self.log_box.tag_configure("info", foreground="#8ab4f8")
        self._append_log(f"Echo Recon echo {APP_VERSION} started · Linux local execution")
        self._append_log("Tool checks are running. Use Download all repositories to install missing dependencies.")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        line = str(message).rstrip()
        low = line.lower()
        tag = "error" if any(x in low for x in ("error", "failed", "missing", "incorrect password")) else (
            "ok" if any(x in low for x in ("[ok]", "completed", "saved:")) else "info" if line.startswith(("[", "==", "---")) else None)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n", tag or ())
        self.log_box.see("end")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 5000:
            self.log_box.delete("1.0", f"{lines - 4000}.0")
        self.log_box.configure(state="disabled")

    def _refresh_tool_status(self, silent: bool = False) -> None:
        if self.status_worker and self.status_worker.is_alive():
            return
        self.toolchain_status.set("Checking required tools…")
        self.status_label.configure(fg=MUTED)
        self.status_worker = threading.Thread(target=self._tool_status_worker, daemon=True)
        self.status_worker.start()
        if not silent:
            self._append_log("[check] Checking local tool requirements…")

    def _tool_status_worker(self) -> None:
        try:
            self.events.put(("tool_status", tool_status()))
        except Exception as exc:
            self.events.put(("tool_status_error", f"{type(exc).__name__}: {exc}"))

    def _apply_tool_status(self, states: dict) -> None:
        self.tool_states = states
        installed = sum(bool(item.get("installed")) for item in states.values())
        missing = [spec.label for spec in TOOLS if not states.get(spec.key, {}).get("installed")]
        total = len(TOOLS)
        if installed == total:
            self.toolchain_status.set(f"●  All requirements ready · {installed}/{total}")
            self.status_label.configure(fg=GREEN)
            self.toolchain_detail.set("All required local command-line tools were detected.")
            self.detail_label.configure(fg=GREEN)
            self.install_state.set("All tools detected. Reinstalling is optional.")
            self.install_feedback.configure(fg=GREEN)
        else:
            self.toolchain_status.set(f"●  Missing requirements · {installed}/{total} ready")
            self.status_label.configure(fg=RED)
            shown_missing = missing[:6]
            suffix = f", +{len(missing) - len(shown_missing)} more" if len(missing) > len(shown_missing) else ""
            self.toolchain_detail.set("Missing: " + ", ".join(shown_missing) + suffix)
            self.detail_label.configure(fg=RED)
            self.install_feedback.configure(fg=MUTED)
            self._append_log("[check] " + str(installed) + f"/{total} tools detected. Missing: " + ", ".join(missing))
        self.status_text.set(f"Tools {installed}/{total} · Linux")

    def _start_install(self) -> None:
        if self.install_worker and self.install_worker.is_alive():
            messagebox.showinfo("Installation running", "Tool installation is already in progress.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Scan active", "Stop or finish the scan before installing/updating tools.")
            return
        password = self.password_entry.get()
        self.password_entry.delete(0, "end")
        if not password and os.geteuid() != 0:
            messagebox.showwarning("sudo password required", "Type your Linux sudo password in the box below Download all repositories.")
            return
        self.install_button.configure(state="disabled")
        self.install_state.set("Starting installer…")
        self.install_feedback.configure(fg=MUTED)
        self._append_log("\n[install] Download all repositories requested. Password input is not written to logs/files.")
        self.install_worker = threading.Thread(target=self._installer_worker, args=(password,), daemon=True)
        self.install_worker.start()

    def _installer_worker(self, password: str) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        try:
            result = run_installer(repo_root, password, lambda line: self.events.put(("install_log", line)))
            self.events.put(("install_done", result))
        except Exception as exc:
            self.events.put(("install_done", {"returncode": 1, "wrong_password": False,
                                               "tail": [f"Installer error: {type(exc).__name__}: {exc}"]}))
        finally:
            password = ""

    def _start_scan(self) -> None:
        if self.install_worker and self.install_worker.is_alive():
            messagebox.showwarning("Installation active", "Wait until tool installation finishes before scanning.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Scan active", "A scan is already running. Stop it before starting another scan.")
            return
        if not self.authorized.get():
            messagebox.showwarning("Authorization required", "Confirm that this is your asset or you have explicit permission to assess it.")
            return
        target_value = self.target_entry.get().strip()
        try:
            parsed = parse_target(target_value)
        except ValueError as exc:
            messagebox.showerror("Invalid target", str(exc))
            return
        chosen = [key for key, var in self.vars.items() if var.get()]
        if not chosen:
            messagebox.showwarning("No tools selected", "Select at least one tool.")
            return
        try:
            max_runtime = int(self.runtime.get())
        except ValueError:
            max_runtime = 3600
        self.cancel_event = threading.Event()
        self.status_text.set("Running · " + parsed.host)
        self._append_log("\n" + "─" * 70)
        self._append_log(f"Scan started: {parsed.origin}")
        self._append_log(f"Selected tools: {len(chosen)} · per-tool watchdog: {max_runtime}s · sequential mode")
        self.worker = threading.Thread(target=self._worker_run,
                                       args=(target_value, chosen, max_runtime, self.cancel_event), daemon=True)
        self.worker.start()

    def _worker_run(self, target: str, chosen: list[str], max_runtime: int, cancel_event: threading.Event) -> None:
        try:
            result = run_scan(target, chosen, max_runtime, cancel_event,
                              lambda line: self.events.put(("log", line)))
            self.events.put(("done", result))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _stop_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.status_text.set("Stopping…")
            self._append_log("[stop] Stop requested. Running process group will be terminated; partial output will be preserved.")
        else:
            self._append_log("[stop] No active scan.")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "tool_status":
                    self._apply_tool_status(payload)
                elif kind == "tool_status_error":
                    self.toolchain_status.set("Could not check tools")
                    self.status_label.configure(fg=RED)
                    self.toolchain_detail.set(str(payload))
                    self.detail_label.configure(fg=RED)
                    self._append_log("[check error] " + str(payload))
                elif kind == "install_log":
                    self._append_log(str(payload))
                elif kind == "install_done":
                    self.install_button.configure(state="normal")
                    code = int(payload.get("returncode", 1))
                    if code == 0:
                        self.install_state.set("Installation routine finished; checking tools again…")
                        self.install_feedback.configure(fg=GREEN)
                        self._append_log("[install] Installer finished. Re-checking all tool binaries…")
                    elif payload.get("wrong_password"):
                        self.install_state.set("sudo password error — password was rejected")
                        self.install_feedback.configure(fg=RED)
                        self.toolchain_status.set("●  sudo password error")
                        self.status_label.configure(fg=RED)
                        messagebox.showerror("sudo password error", "Linux rejected that sudo password. Check your password and click Download all repositories again.")
                    else:
                        self.install_state.set(f"Install finished with errors (exit {code}); see terminal output.")
                        self.install_feedback.configure(fg=RED)
                        self._append_log("[install error] Installer returned a non-zero exit code.")
                    if not payload.get("wrong_password"):
                        self._refresh_tool_status(silent=True)
                    if code != 0 and payload.get("tail"):
                        for line in payload["tail"][-4:]:
                            self._append_log("[installer] " + line)
                elif kind == "done":
                    self.last_report = Path(payload["report_dir"]) / "report.html"
                    self.status_text.set(f"{payload['status'].upper()} · {payload['run_id']}")
                    self._append_log(f"Scan finished: {payload['status']}")
                    self._append_log(f"HTML report: {self.last_report}")
                    self._append_log(f"JSON report: {self.last_report.with_name('report.json')}")
                    if payload["status"] == "completed":
                        self._append_log("[ok] Selected tools completed or were intentionally skipped. Review raw output before reporting findings.")
                    else:
                        self._append_log("[warning] Some tools failed, timed out or were cancelled. A partial report was still saved.")
                elif kind == "error":
                    self.status_text.set("Error")
                    self._append_log("[error] " + str(payload))
                    messagebox.showerror("Scan error", str(payload))
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _open_report(self) -> None:
        if self.last_report and self.last_report.exists():
            webbrowser.open(self.last_report.resolve().as_uri())
            return
        outputs = Path(__file__).resolve().parent.parent / "outputs"
        candidates = sorted(outputs.glob("*/report.html"), key=lambda p: p.stat().st_mtime, reverse=True) if outputs.exists() else []
        if candidates:
            self.last_report = candidates[0]
            webbrowser.open(self.last_report.resolve().as_uri())
        else:
            messagebox.showinfo("No report yet", "The report will be available after the first scan.")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno("Stop scan?", "A scan is running. Stop it before closing? Partial output will be saved."):
                self.cancel_event.set()
                self.root.after(350, self._close_when_stopped)
            return
        if self.install_worker and self.install_worker.is_alive():
            messagebox.showwarning("Installation running", "Let the tool installation finish before closing the window.")
            return
        self.root.destroy()

    def _close_when_stopped(self) -> None:
        if self.worker and self.worker.is_alive():
            self.root.after(250, self._close_when_stopped)
        else:
            self.root.destroy()


def launch() -> None:
    if platform.system() != "Linux":
        raise SystemExit("This build is Linux-only. Use Kali Linux, Debian, or Ubuntu.")
    root = tk.Tk()
    EchoReconApp(root)
    root.mainloop()
