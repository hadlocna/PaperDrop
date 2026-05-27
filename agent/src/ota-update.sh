#!/bin/bash
#
# OTA update script for the PaperDrop Raspberry Pi agent.
#
# Usage:
#   ota-update.sh [archive_url] [version] [sha256]
#
# archive_url may point at a tar.gz created from this repo or from agent/src.
# If archive_url is empty, the script falls back to cloning REPO_URL.

set -euo pipefail

LOG_FILE="/var/log/paperdrop/ota.log"
REPO_URL="${PAPERDROP_REPO_URL:-https://github.com/hadlocna/PaperDrop.git}"
INSTALL_DIR="${PAPERDROP_INSTALL_DIR:-/opt/paperdrop}"
ARCHIVE_URL="${1:-${PAPERDROP_UPDATE_URL:-}}"
VERSION="${2:-${PAPERDROP_UPDATE_VERSION:-latest}}"
EXPECTED_SHA256="${3:-${PAPERDROP_UPDATE_SHA256:-}}"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

detect_service() {
    for service in paperdrop-ws-agent.service paperdrop-agent.service paperdrop.service; do
        if systemctl is-enabled "$service" >/dev/null 2>&1 || systemctl is-active "$service" >/dev/null 2>&1; then
            echo "$service"
            return 0
        fi
    done
    echo "paperdrop-ws-agent.service"
}

download_archive() {
    local url="$1"
    local target="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -fL --connect-timeout 20 --retry 3 --output "$target" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$target" "$url"
    else
        python3 - "$url" "$target" <<'PY'
import sys
import urllib.request

url, target = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(url, timeout=60) as response:
    with open(target, "wb") as handle:
        handle.write(response.read())
PY
    fi
}

find_agent_source() {
    local root="$1"

    if [ -d "$root/agent/src" ]; then
        echo "$root/agent/src"
    elif [ -d "$root/src" ] && [ -f "$root/src/ws_agent.py" ]; then
        echo "$root/src"
    elif [ -f "$root/ws_agent.py" ]; then
        echo "$root"
    else
        find "$root" -maxdepth 4 -type f -name ws_agent.py -print -quit | xargs dirname
    fi
}

log "Starting OTA update to version $VERSION"

if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: OTA update must run as root"
    exit 1
fi

if [ ! -d "$INSTALL_DIR" ]; then
    log "ERROR: install directory not found: $INSTALL_DIR"
    exit 1
fi

SERVICE="$(detect_service)"
BACKUP_DIR="/opt/paperdrop-backup-$(date +%Y%m%d%H%M%S)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

log "Using service: $SERVICE"
log "Creating backup at $BACKUP_DIR"
cp -a "$INSTALL_DIR" "$BACKUP_DIR"

if [ -n "$ARCHIVE_URL" ]; then
    ARCHIVE_PATH="$WORK_DIR/update.tar.gz"
    log "Downloading update archive from $ARCHIVE_URL"
    download_archive "$ARCHIVE_URL" "$ARCHIVE_PATH"

    if [ -n "$EXPECTED_SHA256" ]; then
        ACTUAL_SHA256="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
        if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
            log "ERROR: SHA256 mismatch. Expected $EXPECTED_SHA256, got $ACTUAL_SHA256"
            exit 1
        fi
        log "SHA256 verified"
    fi

    mkdir -p "$WORK_DIR/extracted"
    tar -xzf "$ARCHIVE_PATH" -C "$WORK_DIR/extracted"
    SOURCE_DIR="$(find_agent_source "$WORK_DIR/extracted")"
else
    log "No archive URL supplied; cloning $REPO_URL"
    git clone --depth 1 "$REPO_URL" "$WORK_DIR/repo"
    SOURCE_DIR="$(find_agent_source "$WORK_DIR/repo")"
fi

if [ -z "${SOURCE_DIR:-}" ] || [ ! -f "$SOURCE_DIR/ws_agent.py" ]; then
    log "ERROR: update package does not contain ws_agent.py"
    exit 1
fi

log "Installing agent files from $SOURCE_DIR"
find "$SOURCE_DIR" -maxdepth 1 -type f -print0 | while IFS= read -r -d '' file; do
    cp -a "$file" "$INSTALL_DIR/"
done

if [ -d "$SOURCE_DIR/configs" ]; then
    mkdir -p "$INSTALL_DIR/configs"
    cp -a "$SOURCE_DIR/configs/." "$INSTALL_DIR/configs/"
fi

chmod +x "$INSTALL_DIR/ota-update.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/"*.sh 2>/dev/null || true

if [ -f "$INSTALL_DIR/requirements.txt" ] && [ -x "$INSTALL_DIR/venv/bin/pip" ]; then
    log "Updating Python dependencies"
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" || log "WARNING: dependency update failed"
fi

if [ -n "$VERSION" ] && [ "$VERSION" != "latest" ]; then
    echo "$VERSION" > /etc/paperdrop/firmware-version
fi

log "Restarting $SERVICE"
systemctl daemon-reload
systemctl restart "$SERVICE"

ls -dt /opt/paperdrop-backup-* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null || true

log "OTA update completed successfully"
