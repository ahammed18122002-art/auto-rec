# Echo Recon 2026.10 — Official Tool Repositories

This list identifies the upstream repositories used by the Linux installer. Installing a tool does not imply that its repository code is cloned locally; Go tools are built using official Go module paths, apt tools come from the configured distribution repositories, Arjun uses pipx when available, and Feroxbuster uses an official release only after SHA-256 verification.

| Tool | Official upstream | Installer path |
|---|---|---|
| DNSRecon | https://github.com/darkoperator/dnsrecon | apt, if available |
| Subfinder | https://github.com/projectdiscovery/subfinder | `go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` |
| dnsx | https://github.com/projectdiscovery/dnsx | `go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest` |
| ProjectDiscovery httpx | https://github.com/projectdiscovery/httpx | `go install github.com/projectdiscovery/httpx/cmd/httpx@latest` |
| Katana | https://github.com/projectdiscovery/katana | `go install github.com/projectdiscovery/katana/cmd/katana@latest` |
| Nmap | https://github.com/nmap/nmap | apt; GitHub repository is a source mirror |
| Naabu | https://github.com/projectdiscovery/naabu | `go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest` |
| Nuclei | https://github.com/projectdiscovery/nuclei | `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` |
| ffuf | https://github.com/ffuf/ffuf | apt or `go install github.com/ffuf/ffuf/v2@latest` |
| Feroxbuster | https://github.com/epi052/feroxbuster | apt or checksum-verified official release |
| Gobuster | https://github.com/OJ/gobuster | apt or `go install github.com/OJ/gobuster/v3@latest` |
| Nikto | https://github.com/sullo/nikto | apt or shallow clone |
| Arjun | https://github.com/s0md3v/arjun | apt or `pipx install arjun` |
| sqlmap | https://github.com/sqlmapproject/sqlmap | apt or shallow clone |

Installer requirements depend on Linux distribution repositories, CPU architecture, network access, current upstream tool versions, and the installed Go version. Check the in-app tool status after installation; the installer must not be assumed to have installed every tool just because it completed.
