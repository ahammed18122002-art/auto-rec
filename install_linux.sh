#!/usr/bin/env bash
# Linux-only installer. The GUI starts this script through sudo so that the
# password is passed directly to sudo's stdin, never stored in a file or argv.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[ERROR] Echo Recon installer supports Linux only." >&2
  exit 2
fi
if [[ "$EUID" -ne 0 ]]; then
  echo "[ERROR] Run this installer through the Echo Recon GUI or with sudo." >&2
  exit 2
fi
command -v apt-get >/dev/null 2>&1 || {
  echo "[ERROR] apt-get was not found. Kali/Debian/Ubuntu are supported by this installer." >&2
  exit 2
}

TARGET_USER="${SUDO_USER:-root}"
if ! getent passwd "$TARGET_USER" >/dev/null 2>&1; then TARGET_USER="root"; fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
TARGET_GROUP="$(id -gn "$TARGET_USER" 2>/dev/null || echo root)"
LOCAL_BIN="$TARGET_HOME/.local/bin"
TOOLS_DIR="$TARGET_HOME/.local/share/echo-recon-tools"
mkdir -p "$LOCAL_BIN" "$TOOLS_DIR"
chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN" "$TOOLS_DIR" 2>/dev/null || true
export PATH="$LOCAL_BIN:/usr/local/go/bin:$TARGET_HOME/go/bin:/usr/local/bin:/usr/bin:/bin"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
warn() { log "WARN: $*"; }

log "Echo Recon 2026.10 · Linux dependency installation"
log "Installing system packages through the configured Linux package repositories."
if ! apt-get update; then
  warn "apt-get update failed; check internet access and your configured repositories."
  exit 1
fi

packages=(python3 python3-tk python3-venv python3-pip pipx git curl ca-certificates unzip perl golang-go dnsrecon nmap ffuf gobuster nikto sqlmap seclists feroxbuster)
available=()
for pkg in "${packages[@]}"; do
  if apt-cache show "$pkg" >/dev/null 2>&1; then
    available+=("$pkg")
  else
    log "Package not present in current apt repositories: $pkg (fallback/manual check may apply)"
  fi
done
if ((${#available[@]})); then
  if ! apt-get install -y --no-install-recommends "${available[@]}"; then
    warn "Some apt packages failed to install; the remaining steps will still be attempted."
  fi
fi

# Check Go compatibility. If the system Go is too old or missing, install a
# stable Go SDK in the user's local tool directory after checking Google's SHA-256.
GO_BIN="$(command -v go || true)"
GO_VERSION=""
if [[ -n "$GO_BIN" ]]; then GO_VERSION="$("$GO_BIN" version 2>/dev/null | sed -nE 's/.*go([0-9]+\.[0-9]+(\.[0-9]+)?).*/\1/p')"; fi
GO_ROOT="$TOOLS_DIR/go-sdk"
GO_MIN="1.26.10"
version_ge() { [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" == "$2" ]]; }
# Reuse a previously downloaded verified SDK instead of fetching it on every install click.
if [[ -x "$GO_ROOT/bin/go" ]]; then
  LOCAL_GO_VERSION="$("$GO_ROOT/bin/go" version 2>/dev/null | sed -nE 's/.*go([0-9]+\.[0-9]+(\.[0-9]+)?).*/\1/p')"
  if [[ -n "$LOCAL_GO_VERSION" ]] && version_ge "$LOCAL_GO_VERSION" "$GO_MIN"; then
    GO_BIN="$GO_ROOT/bin/go"
    GO_VERSION="$LOCAL_GO_VERSION"
  fi
fi

if [[ -z "$GO_VERSION" ]] || ! version_ge "$GO_VERSION" "$GO_MIN"; then
  log "System Go is missing/older than ${GO_MIN}; trying a verified user-local stable Go SDK."
  case "$(uname -m)" in
    x86_64) GO_ARCH="amd64" ;;
    aarch64|arm64) GO_ARCH="arm64" ;;
    armv6l|armv7l) GO_ARCH="armv6l" ;;
    i386|i686) GO_ARCH="386" ;;
    *) GO_ARCH="" ;;
  esac
  if [[ -n "$GO_ARCH" ]]; then
    META_FILE="$(mktemp)"
    if curl -fsSL 'https://go.dev/dl/?mode=json' -o "$META_FILE"; then
      read -r GO_FILE GO_SHA < <(python3 - "$GO_ARCH" "$META_FILE" <<'PY'
import json, sys
arch, path = sys.argv[1:]
try:
    releases = json.load(open(path, encoding='utf-8'))
    for release in releases:
        if not release.get('stable'):
            continue
        for item in release.get('files', []):
            if item.get('os') == 'linux' and item.get('arch') == arch and item.get('kind') == 'archive' and item.get('filename', '').endswith('.linux-' + arch + '.tar.gz'):
                print(item['filename'], item['sha256'])
                raise SystemExit(0)
except Exception:
    pass
raise SystemExit(1)
PY
      ) || true
      if [[ -n "${GO_FILE:-}" && -n "${GO_SHA:-}" ]]; then
        TMP_GO="$(mktemp -d)"
        if curl -fL "https://go.dev/dl/$GO_FILE" -o "$TMP_GO/$GO_FILE" && \
           echo "$GO_SHA  $TMP_GO/$GO_FILE" | sha256sum -c -; then
          tar -xzf "$TMP_GO/$GO_FILE" -C "$TMP_GO"
          rm -rf "$GO_ROOT"
          mv "$TMP_GO/go" "$GO_ROOT"
          GO_BIN="$GO_ROOT/bin/go"
          chown -R "$TARGET_USER:$TARGET_GROUP" "$GO_ROOT" 2>/dev/null || true
          log "Installed verified Go SDK $GO_FILE to $GO_ROOT"
        else
          warn "Could not download/verify Go; the Go-based tools may remain missing."
        fi
        rm -rf "$TMP_GO"
      else
        warn "Could not locate a verified Go SDK for architecture $(uname -m)."
      fi
    else
      warn "Could not retrieve official Go release metadata."
    fi
    rm -f "$META_FILE"
  else
    warn "Unsupported architecture for automatic Go SDK setup: $(uname -m)"
  fi
fi

GO_PATH=""
if [[ -x "$GO_ROOT/bin/go" ]]; then
  GO_PATH="$GO_ROOT/bin/go"
elif [[ -n "$GO_BIN" && -x "$GO_BIN" ]]; then
  GO_PATH="$GO_BIN"
fi

install_go_tool() {
  local label="$1" module="$2" binary="$3"
  if [[ -z "$GO_PATH" ]]; then
    warn "$label skipped: no compatible Go compiler was found."
    return 1
  fi
  log "Installing/updating $label from its official Go module: $module"
  local go_root_env=""
  if [[ "$GO_PATH" == "$GO_ROOT/bin/go" ]]; then go_root_env="$GO_ROOT"; fi
  if GOROOT="$go_root_env" GOBIN="$LOCAL_BIN" GOPATH="$TOOLS_DIR/gopath" GOCACHE="$TOOLS_DIR/gocache" \
       "$GO_PATH" install "$module"@latest; then
    if [[ -f "$LOCAL_BIN/$binary" ]]; then chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN/$binary" 2>/dev/null || true; fi
    log "[OK] $label installed"
    return 0
  fi
  warn "$label installation failed; see Go version/network errors above."
  return 1
}

log "Downloading/building ProjectDiscovery tools from official repositories."
install_go_tool "Subfinder" "github.com/projectdiscovery/subfinder/v2/cmd/subfinder" "subfinder" || true
install_go_tool "dnsx" "github.com/projectdiscovery/dnsx/cmd/dnsx" "dnsx" || true
install_go_tool "ProjectDiscovery httpx" "github.com/projectdiscovery/httpx/cmd/httpx" "httpx" || true
install_go_tool "Katana" "github.com/projectdiscovery/katana/cmd/katana" "katana" || true
install_go_tool "Naabu" "github.com/projectdiscovery/naabu/v2/cmd/naabu" "naabu" || true
install_go_tool "Nuclei" "github.com/projectdiscovery/nuclei/v3/cmd/nuclei" "nuclei" || true

# If apt does not supply selected tools, try the upstream Go install paths.
command -v ffuf >/dev/null 2>&1 || install_go_tool "ffuf" "github.com/ffuf/ffuf/v2" "ffuf" || true
command -v gobuster >/dev/null 2>&1 || install_go_tool "Gobuster" "github.com/OJ/gobuster/v3" "gobuster" || true

# Arjun recommends pipx. Run pipx as the target user, not as root.
if ! command -v arjun >/dev/null 2>&1; then
  if command -v pipx >/dev/null 2>&1 && command -v runuser >/dev/null 2>&1; then
    log "Trying Arjun's recommended pipx install for $TARGET_USER."
    runuser -u "$TARGET_USER" -- env HOME="$TARGET_HOME" PATH="$LOCAL_BIN:$TARGET_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" pipx install arjun || warn "Arjun pipx install failed."
  else
    warn "Arjun missing; install pipx or use the official source listed in TOOL_REPOSITORIES.md."
  fi
fi

# Official feroxbuster release fallback, requiring the release API's SHA-256 digest.
if ! command -v feroxbuster >/dev/null 2>&1; then
  case "$(uname -m)" in
    x86_64) FEROX_ASSET="x86_64-linux-feroxbuster.zip" ;;
    aarch64|arm64) FEROX_ASSET="aarch64-linux-feroxbuster.zip" ;;
    armv7l|armv6l) FEROX_ASSET="armv7-linux-feroxbuster.zip" ;;
    i386|i686) FEROX_ASSET="x86-linux-feroxbuster.zip" ;;
    *) FEROX_ASSET="" ;;
  esac
  if [[ -n "$FEROX_ASSET" ]]; then
    log "Trying official Feroxbuster release fallback with SHA-256 verification."
    META="$(mktemp)"; TMP_F="$(mktemp -d)"
    if curl -fsSL 'https://api.github.com/repos/epi052/feroxbuster/releases/latest' -o "$META"; then
      FEROX_SHA="$(python3 - "$FEROX_ASSET" "$META" <<'PY'
import json, sys
name, path = sys.argv[1:]
try:
    data=json.load(open(path, encoding='utf-8'))
    for asset in data.get('assets', []):
        if asset.get('name') == name and (asset.get('digest') or '').startswith('sha256:'):
            print(asset['digest'].split(':',1)[1]); raise SystemExit(0)
except Exception: pass
raise SystemExit(1)
PY
      )" || FEROX_SHA=""
      if [[ -n "$FEROX_SHA" ]] && curl -fL "https://github.com/epi052/feroxbuster/releases/latest/download/$FEROX_ASSET" -o "$TMP_F/$FEROX_ASSET" && \
           echo "$FEROX_SHA  $TMP_F/$FEROX_ASSET" | sha256sum -c - && unzip -oq "$TMP_F/$FEROX_ASSET" -d "$TMP_F"; then
        FEROX_BIN="$(find "$TMP_F" -maxdepth 3 -type f -name feroxbuster -print -quit)"
        if [[ -n "$FEROX_BIN" ]]; then install -m 0755 "$FEROX_BIN" "$LOCAL_BIN/feroxbuster"; chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN/feroxbuster" 2>/dev/null || true; log "[OK] Feroxbuster installed from verified release"; else warn "Feroxbuster binary not found in verified release archive."; fi
      else
        warn "Feroxbuster fallback skipped: official asset checksum unavailable or validation failed."
      fi
    else warn "Could not fetch Feroxbuster release metadata."; fi
    rm -rf "$TMP_F" "$META"
  fi
fi

# Source-based fallbacks for tools commonly packaged by Kali/Debian.
if ! command -v nikto >/dev/null 2>&1 && command -v git >/dev/null 2>&1; then
  log "Trying Nikto official repository fallback."
  if [[ ! -d "$TOOLS_DIR/nikto/.git" ]]; then git clone --depth 1 https://github.com/sullo/nikto.git "$TOOLS_DIR/nikto" || true; fi
  if [[ -f "$TOOLS_DIR/nikto/program/nikto.pl" ]]; then
    cat > "$LOCAL_BIN/nikto" <<EOF
#!/usr/bin/env bash
exec perl "$TOOLS_DIR/nikto/program/nikto.pl" "\$@"
EOF
    chmod 0755 "$LOCAL_BIN/nikto"; chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN/nikto" "$TOOLS_DIR/nikto" 2>/dev/null || true
  fi
fi
if ! command -v sqlmap >/dev/null 2>&1 && command -v git >/dev/null 2>&1; then
  log "Trying sqlmap official repository fallback."
  if [[ ! -d "$TOOLS_DIR/sqlmap/.git" ]]; then git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git "$TOOLS_DIR/sqlmap" || true; fi
  if [[ -f "$TOOLS_DIR/sqlmap/sqlmap.py" ]]; then
    cat > "$LOCAL_BIN/sqlmap" <<EOF
#!/usr/bin/env bash
exec python3 "$TOOLS_DIR/sqlmap/sqlmap.py" "\$@"
EOF
    chmod 0755 "$LOCAL_BIN/sqlmap"; chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN/sqlmap" "$TOOLS_DIR/sqlmap" 2>/dev/null || true
  fi
fi

# Ensure user-local binaries and source repositories are owned by the desktop user.
chown -R "$TARGET_USER:$TARGET_GROUP" "$TOOLS_DIR" 2>/dev/null || true
chown "$TARGET_USER:$TARGET_GROUP" "$LOCAL_BIN" 2>/dev/null || true

log "Checking tool availability for the desktop user."
missing_count=0
for tool in dnsrecon subfinder dnsx httpx katana nmap naabu nuclei ffuf feroxbuster gobuster nikto arjun sqlmap; do
  if runuser -u "$TARGET_USER" -- env HOME="$TARGET_HOME" PATH="$LOCAL_BIN:$TARGET_HOME/go/bin:$PATH" sh -c 'command -v "$1" >/dev/null 2>&1' sh "$tool"; then
    log "[OK] $tool"
  else
    warn "$tool is still missing; see TOOL_REPOSITORIES.md for its official upstream source."
    missing_count=$((missing_count + 1))
  fi
done

if ((missing_count > 0)); then
  log "Installation attempted but $missing_count of 14 tools remain missing. Review warnings above."
  log "Tool source URLs: TOOL_REPOSITORIES.md and tool_repositories.json"
  exit 1
fi
log "All 14 tool commands were detected for $TARGET_USER. Reopen/refresh Echo Recon."
log "Tool source URLs: TOOL_REPOSITORIES.md and tool_repositories.json"
