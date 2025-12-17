#!/bin/bash
#
# provision.sh
# Master Installer for PaperDrop (Runs on First Boot of Factory Image)
# This script transforms a stock Raspberry Pi OS into the PaperDrop Factory Image.
#

set -e

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Starting PaperDrop Factory Provisioning...${NC}"

# 1. Install System Dependencies (Offline)
echo -e "${GREEN}Installing system dependencies (Offline)...${NC}"
if [ -d "/boot/offline_assets" ]; then
    # Install libnl dependencies first
    dpkg -i /boot/offline_assets/libnl-3-200.deb || true
    dpkg -i /boot/offline_assets/libnl-genl-3-200.deb || true
    dpkg -i /boot/offline_assets/libnl-route-3-200.deb || true
    
    # Install libusb (needed for pyusb)
    dpkg -i /boot/offline_assets/libusb-1.0-0.deb || true

    # Install rfkill (needed for wifi_setup.py)
    dpkg -i /boot/offline_assets/rfkill.deb || true

    # Install wireless tools (iw, iwconfig)
    dpkg -i /boot/offline_assets/libiw30.deb || true
    dpkg -i /boot/offline_assets/wireless-tools.deb || true
    dpkg -i /boot/offline_assets/iw.deb || true
    
    # Install dnsmasq
    dpkg -i /boot/offline_assets/dnsmasq-base.deb || true
    dpkg -i /boot/offline_assets/dnsmasq.deb || true
    
    # Install hostapd
    dpkg -i /boot/offline_assets/hostapd.deb || true
    
    # Fix broken dependencies if any (might fail without net, but worth a shot)
    apt-get install -f -y || true
else
    echo "Error: offline_assets not found!"
fi

# 2. Install wifi-connect
echo -e "${GREEN}Installing wifi-connect...${NC}"
if [ -f "/boot/offline_assets/wifi-connect.tar.gz" ]; then
    tar -xzf /boot/offline_assets/wifi-connect.tar.gz -C /usr/local/sbin/
    # Handle folder extraction if necessary
    if [ -f "/usr/local/sbin/wifi-connect-aarch64-unknown-linux-gnu/wifi-connect" ]; then
        mv /usr/local/sbin/wifi-connect-aarch64-unknown-linux-gnu/wifi-connect /usr/local/sbin/wifi-connect
        rm -rf /usr/local/sbin/wifi-connect-aarch64-unknown-linux-gnu
    fi
    chmod +x /usr/local/sbin/wifi-connect
else
    echo "Warning: wifi-connect tarball not found!"
fi

# 3. Setup Directories
echo -e "${GREEN}Setting up directories...${NC}"
mkdir -p /opt/paperdrop/{logs,scripts}
mkdir -p /etc/paperdrop
mkdir -p /var/log/paperdrop

# 4. Copy Runtime Scripts
echo -e "${GREEN}Copying runtime scripts...${NC}"
cp /boot/paperdrop-src/paperdrop-first-boot.sh /usr/local/bin/
chmod +x /usr/local/bin/paperdrop-first-boot.sh

cp /boot/paperdrop-src/paperdrop-wifi.sh /usr/local/bin/
chmod +x /usr/local/bin/paperdrop-wifi.sh

cp /boot/paperdrop-src/paperdrop-reset-wifi.sh /usr/local/bin/
chmod +x /usr/local/bin/paperdrop-reset-wifi.sh

cp /boot/paperdrop-src/ota-update.sh /opt/paperdrop/scripts/
chmod +x /opt/paperdrop/scripts/ota-update.sh

# 5. Copy Agent Code
echo -e "${GREEN}Copying agent code...${NC}"
cp -r /boot/paperdrop-src/* /opt/paperdrop/
# Clean up source files from opt (keep only what's needed)
rm /opt/paperdrop/*.sh

# 6. Setup Python Environment
echo -e "${GREEN}Setting up Python venv...${NC}"
cd /opt/paperdrop
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}Installing Python dependencies...${NC}"
if [ -d "/boot/offline_assets/wheels" ]; then
    pip install --no-index --find-links=/boot/offline_assets/wheels -r requirements.txt
else
    pip install -r requirements.txt
fi

# 7. Create Systemd Services

# First Boot Service (Runtime)
cat <<EOF > /etc/systemd/system/paperdrop-first-boot.service
[Unit]
Description=PaperDrop First Boot Initialization
After=local-fs.target
Before=paperdrop-wifi.service
ConditionPathExists=!/etc/paperdrop/device-id

[Service]
Type=oneshot
ExecStart=/usr/local/bin/paperdrop-first-boot.sh
RemainAfterExit=yes
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF

# WiFi Provisioning Service
cat <<EOF > /etc/systemd/system/paperdrop-wifi.service
[Unit]
Description=PaperDrop WiFi Provisioning (Access Point)
After=NetworkManager.service paperdrop-first-boot.service
Wants=NetworkManager.service
Before=paperdrop.service

[Service]
Type=simple
ExecStart=/usr/local/bin/paperdrop-wifi.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF

# Device Agent Service (WebSocket)
cat <<EOF > /etc/systemd/system/paperdrop-ws-agent.service
[Unit]
Description=PaperDrop WebSocket Agent
After=network-online.target paperdrop-wifi.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/paperdrop
ExecStart=/opt/paperdrop/venv/bin/python /opt/paperdrop/ws_agent.py
Restart=always
RestartSec=10
Environment=PAPERDROP_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# 8. Enable Services
echo -e "${GREEN}Enabling services...${NC}"
systemctl daemon-reload
systemctl enable paperdrop-first-boot.service
systemctl enable paperdrop-wifi.service
systemctl enable paperdrop-ws-agent.service

# Ensure NetworkManager is enabled
systemctl enable NetworkManager
systemctl start NetworkManager

# Disable dhcpcd (conflict)
systemctl disable dhcpcd 2>/dev/null || true
systemctl stop dhcpcd 2>/dev/null || true

echo -e "${GREEN}Provisioning Complete! Rebooting in 5 seconds...${NC}"
sleep 5
reboot
