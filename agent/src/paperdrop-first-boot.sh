#!/bin/bash
#
# paperdrop-first-boot.sh
# Modified for Dual-Interface Troubleshooting
#

set -e

LOG_FILE="/var/log/paperdrop-first-boot.log"
FLAG_FILE="/boot/firmware/paperdrop-first-boot"
FLAG_FILE_ALT="/boot/paperdrop-first-boot"
IDENTITY_FILE="/etc/paperdrop/device-id"
AP_IFACE_FILE="/etc/paperdrop/ap-interface"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [FIRST-BOOT] $1" | tee -a "$LOG_FILE"
}

generate_device_id() {
    local serial=$(cat /sys/firmware/devicetree/base/serial-number 2>/dev/null | tr -d '\0')
    if [ -z "$serial" ]; then
        serial=$(cat /proc/cpuinfo | grep Serial | awk '{print $3}')
    fi
    if [ -z "$serial" ] || [ "$serial" = "0000000000000000" ]; then
         serial=$(cat /proc/sys/kernel/random/uuid | cut -d- -f1)
    fi
    echo "PD-${serial: -8}"
}

main() {
    log "========================================="
    log "PaperDrop First Boot (Dual-Interface Mode)"
    log "========================================="
    
    if [ ! -f "$FLAG_FILE" ] && [ ! -f "$FLAG_FILE_ALT" ]; then
        log "Not first boot. Exiting."
        exit 0
    fi
    
    # 1. Generate Identity
    mkdir -p /etc/paperdrop
    DEVICE_ID=$(generate_device_id)
    echo "$DEVICE_ID" > "$IDENTITY_FILE"
    log "Device ID: $DEVICE_ID"
    
    # 2. Set Hostname
    hostnamectl set-hostname "paperdrop-${DEVICE_ID: -4}"
    sed -i "s/127.0.1.1.*raspberrypi/127.0.1.1\tpaperdrop-${DEVICE_ID: -4}/g" /etc/hosts
    
    # 3. Detect Interfaces
    # We assume wlan0 is the onboard WiFi connected to Home Network (via wpa_supplicant)
    # We look for a SECOND wireless interface for the AP
    
    log "Detecting wireless interfaces..."
    # List all wireless interfaces
    INTERFACES=$(nmcli -t -f DEVICE,TYPE device | grep ":wifi" | cut -d: -f1)
    
    PRIMARY_IFACE="wlan0"
    SECONDARY_IFACE=""
    
    for iface in $INTERFACES; do
        if [ "$iface" != "$PRIMARY_IFACE" ]; then
            SECONDARY_IFACE="$iface"
            break
        fi
    done
    
    if [ -n "$SECONDARY_IFACE" ]; then
        log "Found secondary interface for AP: $SECONDARY_IFACE"
        echo "$SECONDARY_IFACE" > "$AP_IFACE_FILE"
    else
        log "WARNING: No secondary interface found! Falling back to $PRIMARY_IFACE for AP (might conflict)"
        echo "$PRIMARY_IFACE" > "$AP_IFACE_FILE"
        # If we fallback, we might break the SSH connection if we start AP on wlan0
        # But for now, we assume the user attached the USB dongle.
    fi
    
    # 4. Preserve Existing Connections (Do NOT delete them)
    log "Preserving existing WiFi connections for troubleshooting..."
    
    # 5. Cleanup Flags
    rm -f "$FLAG_FILE"
    rm -f "$FLAG_FILE_ALT"
    
    # 6. Enable & Start AP Service
    systemctl enable paperdrop-wifi.service
    systemctl start paperdrop-wifi.service
    
    log "Initialization complete."
}

main "$@"
