#!/bin/bash
#
# paperdrop-reset-wifi.sh
# Clears WiFi credentials and returns device to AP mode
# Can be triggered via RPC or physical button
#

LOG_FILE="/var/log/paperdrop-wifi.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [RESET] $1" | tee -a "$LOG_FILE"
}

log "WiFi reset initiated"

# Stop the agent
systemctl stop paperdrop-agent.service 2>/dev/null || true

# Remove provisioned flag
rm -f /etc/paperdrop/wifi-provisioned

# Delete all WiFi connections
nmcli -t -f NAME,TYPE connection show | grep ':802-11-wireless$' | cut -d: -f1 | while read conn; do
    log "Removing connection: $conn"
    nmcli connection delete "$conn" 2>/dev/null || true
done

log "WiFi credentials cleared"

# Restart WiFi provisioning service
systemctl restart paperdrop-wifi.service

log "AP mode restarted"
