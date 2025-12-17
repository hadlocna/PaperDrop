#!/bin/bash
AIRPORT="/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

echo "Scanning for PaperDrop..."
for i in {1..60}; do
    # Check for SSID
    if "$AIRPORT" -s | grep -q "PaperDrop"; then
        echo "FOUND: WiFi Access Point 'PaperDrop_Setup' is visible!"
        exit 0
    fi

    # Check for Local Network Connection
    if ping -c 1 -W 1 raspberrypi.local &> /dev/null; then
        echo "FOUND: Device is online at raspberrypi.local!"
        exit 0
    fi
    
    if ping -c 1 -W 1 paperdrop.local &> /dev/null; then
        echo "FOUND: Device is online at paperdrop.local!"
        exit 0
    fi

    echo -n "."
    sleep 5
done

echo "Timeout: Device not found after 5 minutes."
exit 1
