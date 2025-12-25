#!/bin/bash
#
# install.sh - One-command installer for PaperDrop on a fresh Raspberry Pi
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}    PaperDrop Device Setup Utility       ${NC}"
echo -e "${BLUE}=========================================${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# 1. System Updates & Prerequisites
echo -e "${GREEN}[1/6] Updating system and installing dependencies...${NC}"
apt-get update
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-dbus \
    python3-gi \
    git \
    libusb-1.0-0-dev \
    libudev-dev \
    network-manager \
    libjpeg-dev \
    zlib1g-dev \
    libopenjp2-7 \
    libtiff6 \
    rfkill \
    wireless-tools

# Ensure NetworkManager is active (needed for the agent to report WiFi stats)
systemctl enable NetworkManager
systemctl start NetworkManager

# 2. Setup Directories
echo -e "${GREEN}[2/6] Setting up /opt/paperdrop...${NC}"
mkdir -p /opt/paperdrop
mkdir -p /etc/paperdrop
mkdir -p /var/log/paperdrop

# 3. Copy Application Files
echo -e "${GREEN}[3/6] Copying application files...${NC}"
cp -r agent/src/* /opt/paperdrop/

# 4. Setup Python Environment
echo -e "${GREEN}[4/6] Setting up Python virtual environment...${NC}"
cd /opt/paperdrop
python3 -m venv --system-site-packages venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 5. Generate Device Identity
echo -e "${GREEN}[5/6] Generating unique device identity...${NC}"
if [ ! -f "/etc/paperdrop/device-id" ]; then
    SERIAL=$(cat /sys/firmware/devicetree/base/serial-number 2>/dev/null | tr -d '\0' || echo "")
    if [ -z "$SERIAL" ] || [ "$SERIAL" = "0000000000000000" ]; then
        SERIAL=$(cat /proc/sys/kernel/random/uuid | cut -d- -f1)
    fi
    DEVICE_ID="PD-${SERIAL: -8}"
    echo "$DEVICE_ID" > /etc/paperdrop/device-id
    echo -e "Device ID generated: ${GREEN}$DEVICE_ID${NC}"
else
    echo "Existing Device ID found: $(cat /etc/paperdrop/device-id)"
fi

# 6. Install Systemd Services
echo -e "${GREEN}[6/6] Installing systemd services...${NC}"

# BLE Service
cat <<EOF > /etc/systemd/system/paperdrop-ble.service
[Unit]
Description=PaperDrop BLE Provisioning
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=simple
WorkingDirectory=/opt/paperdrop
ExecStart=/opt/paperdrop/venv/bin/python3 ble_provisioning.py
Restart=always
User=root
Environment=PYTHONPATH=/opt/paperdrop

[Install]
WantedBy=multi-user.target
EOF

# WebSocket Agent Service
cat <<EOF > /etc/systemd/system/paperdrop-agent.service
[Unit]
Description=PaperDrop WebSocket Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/paperdrop
ExecStart=/opt/paperdrop/venv/bin/python3 ws_agent.py
Restart=always
RestartSec=10
Environment=PAPERDROP_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# Reload and Start
systemctl daemon-reload
systemctl enable paperdrop-ble.service
systemctl enable paperdrop-agent.service

systemctl start paperdrop-ble.service
systemctl start paperdrop-agent.service

echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}    PaperDrop Setup Complete!           ${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "Your Device ID is: ${GREEN}$(cat /etc/paperdrop/device-id)${NC}"
echo -e "You can now see this device in your dashboard and claim it."
echo -e "Check status with: ${BLUE}sudo systemctl status paperdrop-agent${NC}"
echo -e "========================================="
