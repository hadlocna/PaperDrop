#!/bin/bash
#
# device-identity.sh
# Generates or retrieves persistent device identity
#

IDENTITY_FILE="/etc/paperdrop/device-id"
IDENTITY_DIR="/etc/paperdrop"

# Ensure directory exists
mkdir -p "$IDENTITY_DIR"

generate_device_id() {
    # Use Pi serial number as base, add random suffix for uniqueness
    PI_SERIAL=$(cat /sys/firmware/devicetree/base/serial-number 2>/dev/null | tr -d '\0')
    
    if [ -z "$PI_SERIAL" ]; then
        # Fallback: generate random UUID
        DEVICE_ID=$(cat /proc/sys/kernel/random/uuid)
    else
        # Use serial + timestamp hash for uniqueness
        DEVICE_ID="${PI_SERIAL}-$(date +%s | sha256sum | head -c 8)"
    fi
    
    echo "$DEVICE_ID"
}

get_device_id() {
    if [ -f "$IDENTITY_FILE" ]; then
        cat "$IDENTITY_FILE"
    else
        DEVICE_ID=$(generate_device_id)
        echo "$DEVICE_ID" > "$IDENTITY_FILE"
        chmod 600 "$IDENTITY_FILE"
        echo "$DEVICE_ID"
    fi
}

# If called directly, output device ID
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    get_device_id
fi
