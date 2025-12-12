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
    wireless-tools

# 3. Create Application Directory
echo -e "${GREEN}Setting up /opt/paperdrop...${NC}"
mkdir -p /opt/paperdrop
mkdir -p /etc/paperdrop # Config dir

# 4. Copy Agent Code
echo -e "${GREEN}Copying application files...${NC}"
if [ -d "/tmp/paperdrop_src" ]; then
    cp -r /tmp/paperdrop_src/* /opt/paperdrop/
    # Clean up
    rm -rf /tmp/paperdrop_src
else
    echo "Warning: /tmp/paperdrop_src not found. Assuming files are pre-provisioned or in current dir."
    # Fallback for manual run
    if [ -f "agent.py" ]; then
        cp * /opt/paperdrop/
    fi
fi

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

# 8. Setup Permissions
chown -R root:root /opt/paperdrop
chmod -R 755 /opt/paperdrop

echo -e "${GREEN}Provisioning Complete!${NC}"
