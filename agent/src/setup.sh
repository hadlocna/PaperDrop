#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PaperDrop Agent Provisioning...${NC}"

# 1. Install System Dependencies (Offline)
echo -e "${GREEN}Installing system dependencies (Offline)...${NC}"
if [ -d "/boot/offline_assets" ]; then
    # Install libnl dependencies first
    dpkg -i /boot/offline_assets/libnl-3-200.deb
    dpkg -i /boot/offline_assets/libnl-genl-3-200.deb
    dpkg -i /boot/offline_assets/libnl-route-3-200.deb
    
    # Install libusb (needed for pyusb)
    dpkg -i /boot/offline_assets/libusb-1.0-0.deb

    # Install rfkill (needed for wifi_setup.py)
    dpkg -i /boot/offline_assets/rfkill.deb

    # Install wireless tools (iw, iwconfig)
    dpkg -i /boot/offline_assets/libiw30.deb
    dpkg -i /boot/offline_assets/wireless-tools.deb
    dpkg -i /boot/offline_assets/iw.deb
    
    # Install dnsmasq
    dpkg -i /boot/offline_assets/dnsmasq-base.deb
    dpkg -i /boot/offline_assets/dnsmasq.deb
    
    # Install hostapd
    dpkg -i /boot/offline_assets/hostapd.deb
    
    # Fix broken dependencies if any (might fail without net, but worth a shot)
    apt-get install -f -y || true
else
    echo "Error: offline_assets not found!"
fi

# 2. Create Application Directory
echo -e "${GREEN}Setting up /opt/paperdrop...${NC}"
mkdir -p /opt/paperdrop
mkdir -p /etc/paperdrop # Config dir

# 3. Copy Agent Code
echo -e "${GREEN}Copying application files...${NC}"

# Find where this script is running from
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SOURCE_DIR="$SCRIPT_DIR"

if [ -d "$SCRIPT_DIR/paperdrop-src" ]; then
    SOURCE_DIR="$SCRIPT_DIR/paperdrop-src"
fi

if [ -f "$SOURCE_DIR/agent.py" ]; then
    echo "Files found in $SOURCE_DIR, copying to /opt/paperdrop..."
    cp -r "$SOURCE_DIR"/* /opt/paperdrop/
else
    echo "Error: agent.py not found in $SOURCE_DIR"
    exit 1
fi

# Cleanup self (PaperDrop Installer) to prevent re-run
# We do this later after success, but let's define the function
cleanup_installer() {
    echo "Disabling First Boot Installer..."
    systemctl disable paperdrop-firstboot.service || true
    rm -f /etc/systemd/system/multi-user.target.wants/paperdrop-firstboot.service
    rm -f /etc/systemd/system/paperdrop-firstboot.service
    # Optional: remove installer files
    # rm -rf /opt/paperdrop_installer
}

# 4. Setup Python Environment (Offline)
echo -e "${GREEN}Setting up Python venv...${NC}"
cd /opt/paperdrop
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}Installing Python dependencies from offline wheels...${NC}"
if [ -d "/boot/offline_assets/wheels" ]; then
    pip install --no-index --find-links=/boot/offline_assets/wheels -r requirements.txt
else
    echo "Warning: Offline wheels not found. Attempting online install (likely to fail)..."
    pip install -r requirements.txt
fi

# 5. Setup Systemd Service
echo -e "${GREEN}Creating systemd service...${NC}"
cat <<EOF > /etc/systemd/system/paperdrop.service
[Unit]
Description=PaperDrop Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/paperdrop
Environment=PAPERDROP_ENV=production
# Point to the venv python
ExecStart=/opt/paperdrop/venv/bin/python agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable Services
echo -e "${GREEN}Enabling services...${NC}"
systemctl daemon-reload
systemctl enable paperdrop.service

# Ensure NetworkManager is running (required for wifi-connect)
# systemctl enable NetworkManager
# systemctl start NetworkManager

# 7. Pre-configure WiFi (Troubleshooting Mode)
echo -e "${GREEN}Pre-configuring WiFi (fathan2)...${NC}"
cat <<EOF > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="fathan2"
    psk="youarecool"
    key_mgmt=WPA-PSK
}
EOF

# Pre-seed Agent Config so it knows to connect
mkdir -p /etc/paperdrop
cat <<EOF > /etc/paperdrop/wifi.json
{
  "ssid": "fathan2",
  "password": "youarecool"
}
EOF
chmod 600 /etc/paperdrop/wifi.json

# 8. Setup Permissions
chown -R root:root /opt/paperdrop
chmod -R 755 /opt/paperdrop

# 9. Cleanup Installer
cleanup_installer
echo -e "${GREEN}Provisioning Complete! Starting Agent...${NC}"
systemctl start paperdrop.service
