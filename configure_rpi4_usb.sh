#!/bin/bash
# RPi 4 USB Gadget Mode Setup Script
# Run this AFTER flashing the raspios.img to the SD card

set -e

BOOT_VOLUME="/Volumes/bootfs"

# Wait for volume to mount
echo "Waiting for boot volume to mount..."
for i in {1..30}; do
    if [ -d "$BOOT_VOLUME" ]; then
        break
    fi
    sleep 1
done

if [ ! -d "$BOOT_VOLUME" ]; then
    echo "ERROR: Boot volume not found at $BOOT_VOLUME"
    exit 1
fi

echo "Boot volume found!"

# 1. Enable USB Gadget Mode in config.txt
echo "Configuring USB Gadget Mode..."
echo "" >> "$BOOT_VOLUME/config.txt"
echo "# Enable USB Gadget Mode (USB Ethernet)" >> "$BOOT_VOLUME/config.txt"
echo "dtoverlay=dwc2" >> "$BOOT_VOLUME/config.txt"

# 2. Add modules to cmdline.txt (must be single line, add before rootwait)
echo "Modifying cmdline.txt..."
CMDLINE=$(cat "$BOOT_VOLUME/cmdline.txt")
# Insert modules-load after rootwait
CMDLINE=$(echo "$CMDLINE" | sed 's/rootwait/rootwait modules-load=dwc2,g_ether/')
echo "$CMDLINE" > "$BOOT_VOLUME/cmdline.txt"

# 3. Create SSH file to enable SSH
echo "Enabling SSH..."
touch "$BOOT_VOLUME/ssh"

# 4. Create userconf.txt for user pi with password 'raspberry'
echo "Creating user configuration..."
# Pre-generated hash for password 'raspberry'
echo 'pi:$6$rBoByrWRKMY1EHFy$S31KRx6/B3w.vk8eeP5B9aQcejkbpg8GafnKjqypbYm1JdHZpSIDMIE/hXQ4tCqLDOJPJrGqGNvPE0VSn4P5M/' > "$BOOT_VOLUME/userconf.txt"

# 5. Create wpa_supplicant.conf for WiFi
echo "Creating WiFi configuration..."
cat > "$BOOT_VOLUME/wpa_supplicant.conf" << 'EOF'
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=PT

network={
#    ssid="fabthan"
#    psk="youarecool"
#    key_mgmt=WPA-PSK
}
EOF

# 6. Set hostname
echo "paperdrop" > "$BOOT_VOLUME/hostname"

echo ""
echo "============================================"
echo "SD Card configured for RPi 4 USB Gadget Mode!"
echo ""
echo "IMPORTANT: For USB gadget mode to work, you must"
echo "connect your Mac to the Pi's USB-C POWER PORT,"
echo "NOT the USB-A ports!"
echo ""
echo "After boot, the Pi should appear as a USB Ethernet"
echo "device and be reachable at 169.254.x.x or via DHCP."
echo "============================================"
