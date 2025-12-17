#!/bin/bash
#
# check-wifi.sh
# Checks internet connectivity and launches wifi-connect AP if offline
# Adapted for PaperDrop
#

# Configuration
PORTAL_SSID="${PORTAL_SSID:-PaperDrop_Setup}"
PORTAL_GATEWAY="192.168.42.1"
PORTAL_DHCP_RANGE="192.168.42.2,192.168.42.254"
PORTAL_INTERFACE="wlan0"
CONNECTIVITY_CHECK_URL="http://connectivity.raspberrypi.com/generate_204"
CONNECTIVITY_CHECK_TIMEOUT=5
MAX_RETRIES=3

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a /var/log/wifi-connect.log
}

# Check if we have internet connectivity
check_connectivity() {
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s --head --connect-timeout $CONNECTIVITY_CHECK_TIMEOUT "$CONNECTIVITY_CHECK_URL" | head -n 1 | grep -q "204"; then
            return 0
        fi
        # Also try pinging Google DNS as backup
        if ping -c 1 -W $CONNECTIVITY_CHECK_TIMEOUT 8.8.8.8 > /dev/null 2>&1; then
            return 0
        fi
        log "Connectivity check attempt $i failed, retrying..."
        sleep 2
    done
    return 1
}

# Get device serial for unique SSID suffix
get_device_serial() {
    if [ -f /sys/firmware/devicetree/base/serial-number ]; then
        cat /sys/firmware/devicetree/base/serial-number | tail -c 5 | tr -d '\0'
    else
        hostname | tail -c 5
    fi
}

# Main logic
main() {
    log "Starting connectivity check..."
    
    # Wait for NetworkManager to be fully ready
    sleep 5
    
    if check_connectivity; then
        log "Internet connectivity confirmed. No action needed."
        exit 0
    fi
    
    log "No internet connectivity. Starting wifi-connect portal..."
    
    # Generate unique SSID
    DEVICE_SUFFIX=$(get_device_serial)
    UNIQUE_SSID="${PORTAL_SSID}_${DEVICE_SUFFIX}"
    
    log "Launching AP with SSID: $UNIQUE_SSID"
    
    # Launch wifi-connect
    # The --clear flag removes any existing connection attempts first
    /usr/local/sbin/wifi-connect \
        --portal-ssid "$UNIQUE_SSID" \
        --portal-gateway "$PORTAL_GATEWAY" \
        --portal-dhcp-range "$PORTAL_DHCP_RANGE" \
        --portal-interface "$PORTAL_INTERFACE" \
        --activity-timeout 600
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log "wifi-connect completed successfully. Credentials received."
        # Optional: Restart agent to pick up new network immediately if needed
        systemctl restart paperdrop.service
    else
        log "wifi-connect exited with code $EXIT_CODE"
    fi
}

main "$@"
