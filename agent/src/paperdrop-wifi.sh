#!/bin/bash
#
# paperdrop-wifi.sh
# Modified to use specific AP interface
#

LOG_FILE="/var/log/paperdrop-wifi.log"
IDENTITY_FILE="/etc/paperdrop/device-id"
AP_IFACE_FILE="/etc/paperdrop/ap-interface"
PROVISIONED_FLAG="/etc/paperdrop/wifi-provisioned"
WIFI_CONNECT_BIN="/usr/local/bin/wifi-connect"

AP_GATEWAY="192.168.42.1"
AP_DHCP_RANGE="192.168.42.2,192.168.42.254"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WIFI] $1" | tee -a "$LOG_FILE"
}

get_device_suffix() {
    if [ -f "$IDENTITY_FILE" ]; then
        cat "$IDENTITY_FILE" | tail -c 5
    else
        hostname | tail -c 5
    fi
}

get_ap_interface() {
    if [ -f "$AP_IFACE_FILE" ]; then
        cat "$AP_IFACE_FILE"
    else
        echo "wlan0"
    fi
}

start_ap_mode() {
    local suffix=$(get_device_suffix)
    local ssid="PaperDrop_${suffix}"
    local iface=$(get_ap_interface)
    
    log "Starting Access Point on $iface: $ssid"
    
    "$WIFI_CONNECT_BIN" \
        --portal-ssid "$ssid" \
        --portal-gateway "$AP_GATEWAY" \
        --portal-dhcp-range "$AP_DHCP_RANGE" \
        --portal-interface "$iface" \
        --portal-listening-port 80 \
        --activity-timeout 0
    
    if [ $? -eq 0 ]; then
        log "Credentials received."
        touch "$PROVISIONED_FLAG"
        return 0
    else
        log "wifi-connect failed/exited."
        return 1
    fi
}

main() {
    log "PaperDrop WiFi Service (Dual-Interface)"
    
    # Wait for NM
    sleep 10
    
    # In Dual-Interface mode, we ALWAYS run the AP on the secondary interface
    # regardless of whether the primary is connected or not.
    # This allows provisioning even if the device is already online via Ethernet/wlan0.
    
    while true; do
        start_ap_mode
        sleep 5
    done
}

main "$@"
