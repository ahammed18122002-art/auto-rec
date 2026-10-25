# Echo Recon — Linux Edition (echo 2026.10)

A compact, Chrome-inspired Linux-only desktop reconnaissance dashboard with automatic local tool checks, a secure sudo-password entry for installer runs, a large live output panel, sequential scanning, watchdog timeouts, process-group cancellation, and HTML/JSON/Markdown reports.

See `README_BN.md` for Bengali setup instructions and `TOOL_REPOSITORIES.md` / `tool_repositories.json` for official upstream source links.

```bash
chmod +x run.sh install_linux.sh
./run.sh
```

The GUI can run `./install_linux.sh` through sudo, displaying installer output in the Live Terminal. The password is sent to sudo through stdin only; it is not saved to disk or logged. The installer makes a best-effort attempt to install all 14 tools and shows anything that remains missing.

Offline regression suite: `./run.sh --test`
Check installed tools: `./run.sh --check-tools`
Print version: `./run.sh --version`

Only scan systems you own or are explicitly authorized to assess. Tool limits vary; no universal global rate limiter or zero-impact guarantee is claimed.
