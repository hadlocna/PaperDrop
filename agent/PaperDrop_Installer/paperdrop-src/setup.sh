#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PaperDrop Agent Provisioning...${NC}"

# 1. Update System
echo -e "${GREEN}Updating system packages...${NC}"
apt-get update
# apt-get upgrade -y # Optional: can be slow

# 2. Install System Dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    hostapd \
    dnsmasq \
    libjpeg-dev \
    zlib1g-dev \
    libopenjp2-7 \
    libtiff5 \
    rfkill \
    wireless-tools \
    libusb-1.0-0-dev

# 3. Create Application Directory
echo -e "${GREEN}Setting up /opt/paperdrop...${NC}"
mkdir -p /opt/paperdrop
mkdir -p /etc/paperdrop # Config dir

# 4. Copy Agent Code
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

# 5. Setup Python Environment
echo -e "${GREEN}Setting up Python venv...${NC}"
cd /opt/paperdrop
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Setup Systemd Service
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

# 7. Enable Services
echo -e "${GREEN}Enabling services...${NC}"
systemctl daemon-reload
systemctl enable paperdrop.service

# Disable hostapd/dnsmasq by default (agent controls them)
systemctl disable hostapd
systemctl disable dnsmasq

# 8. Configure Hostapd (WiFi Hotspot)
echo -e "${GREEN}Configuring hostapd...${NC}"
cat <<EOF > /etc/hostapd/hostapd.conf
country_code=US
interface=wlan0
driver=nl80211
ssid=PaperDrop_Setup
hw_mode=g
channel=7
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
ieee80211n=1
ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]
EOF

# Point daemon to config
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

# 9. Configure Dnsmasq (DHCP)
echo -e "${GREEN}Configuring dnsmasq...${NC}"
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null || true
cat <<EOF > /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=paperdrop.local
address=/#/192.168.4.1
EOF

# 10. Configure Static IP for AP Mode (dhcpcd)
echo -e "${GREEN}Configuring static IP for wlan0...${NC}"
# Append to end of dhcpcd.conf
cat <<EOF >> /etc/dhcpcd.conf

interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

# 11. Setup Permissions
chown -R root:root /opt/paperdrop
chmod -R 755 /opt/paperdrop

# 12. Configure Captive Portal Redirect (iptables)
echo -e "${GREEN}Configuring firewall redirect...${NC}"
# Apply immediately
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
# Save for persistence (simple method via rc.local)
if ! grep -q "iptables -t nat -A PREROUTING" /etc/rc.local; then
    sed -i '$i iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080\n' /etc/rc.local
fi

# 12. Pre-configure WiFi (Troubleshooting Mode)
echo -e "${GREEN}Pre-configuring WiFi (fabthan2)...${NC}"
cat <<EOF > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="Ya Mama"
    psk="youarecool"
    key_mgmt=WPA-PSK
}
EOF

# Pre-seed Agent Config so it knows to connect
mkdir -p /etc/paperdrop
cat <<EOF > /etc/paperdrop/wifi.json
{
  "ssid": "Ya Mama",
  "password": "youarecool"
}
EOF
chmod 600 /etc/paperdrop/wifi.json

cleanup_installer
echo -e "${GREEN}Provisioning Complete! Starting Agent...${NC}"
systemctl start paperdrop.service
