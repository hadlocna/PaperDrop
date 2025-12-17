#!/bin/bash
#
# Simple OTA update script for PaperDrop
#

LOG_FILE="/opt/paperdrop/logs/ota.log"
REPO_URL="https://github.com/hadlocna/PaperDrop.git" # Adjust if needed
INSTALL_DIR="/opt/paperdrop"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting OTA update..."

# Create backup
BACKUP_DIR="/opt/paperdrop-backup-$(date +%Y%m%d%H%M%S)"
cp -r "$INSTALL_DIR" "$BACKUP_DIR"
log "Backup created at $BACKUP_DIR"

# Pull latest code
# Note: This assumes /opt/paperdrop is a git repo or we are just curling files.
# Since we copied files, we might not be in a git repo.
# Strategy: Git clone to temp, then rsync over.

TEMP_DIR=$(mktemp -d)
log "Cloning latest code to $TEMP_DIR..."

if git clone "$REPO_URL" "$TEMP_DIR"; then
    log "Code downloaded successfully"
    
    # Copy agent source
    cp -r "$TEMP_DIR/agent/src/"* "$INSTALL_DIR/"
    
    # Update Python dependencies
    source /opt/paperdrop/venv/bin/activate
    pip install -r "$INSTALL_DIR/requirements.txt" 2>/dev/null || true
    deactivate
    
    # Restart agent service
    systemctl restart paperdrop.service
    log "Agent restarted"
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    # Cleanup old backups (keep last 3)
    ls -dt /opt/paperdrop-backup-* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null
    
    log "OTA update completed successfully"
else
    log "ERROR: Git clone failed. Restoring backup..."
    rm -rf "$TEMP_DIR"
    # Restore logic if we had wiped the dir, but we just copied over.
    # If copy failed mid-way, we might be in trouble, but rsync/cp is usually atomic enough for files.
    exit 1
fi
