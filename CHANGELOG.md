# Changelog

## echo 2026.10
- Replaced busy sidebar layout with a cleaner Chrome-inspired GUI.
- Added required-tool auto-check, green/red readiness status, missing-tool list, and Download all repositories action.
- Added a masked sudo password field; password is sent only to sudo stdin, not command arguments, files, or logs; sudo rejection is reported in the UI.
- Added a larger, scrollable live terminal panel and live installer output.
- Added official repository link registry for all 14 supported tools.
- Installer detects the original GUI user when invoked via sudo; attempts to place locally built binaries under that user's ~/.local/bin rather than only /root.
- Added SHA-256 checking for the official Go SDK download and Feroxbuster release fallback when upstream metadata includes digests.
- Added user-local PATH detection for GUI-launched tools; tightened ProjectDiscovery httpx verification.
- Added installer password-flow regression tests and CLI --version option.
