#!/bin/bash
set -e

echo "=== PaperDrop Agent Installation Script ==="
echo ""

# Update system
echo "[1/6] Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install dependencies
echo "[2/6] Installing dependencies..."
sudo apt install -y python3 python3-pip git cups

# Install Python packages
echo "[3/6] Installing Python dependencies..."
pip3 install requests websocket-client pillow --break-system-packages

# Clone the PaperDrop repository
echo "[4/6] Cloning PaperDrop repository..."
cd ~
if [ -d "PaperDrop" ]; then
    echo "PaperDrop directory exists, pulling latest..."
    cd PaperDrop
    git pull
else
    git clone https://github.com/hadlocna/PaperDrop.git
    cd PaperDrop
fi

# Set up the agent
echo "[5/6] Setting up agent configuration..."
cd agent
mkdir -p /home/paperdrop/.config/paperdrop

# Create systemd service
echo "[6/6] Creating systemd service..."
sudo tee /etc/systemd/system/paperdrop.service > /dev/null <<EOF
[Unit]
Description=PaperDrop Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=paperdrop
WorkingDirectory=/home/paperdrop/PaperDrop/agent
ExecStart=/usr/bin/python3 /home/paperdrop/PaperDrop/agent/src/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable paperdrop.service
sudo systemctl start paperdrop.service

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Service status:"
sudo systemctl status paperdrop.service --no-pager

echo ""
echo "To view logs:"
echo "  sudo journalctl -u paperdrop.service -f"
