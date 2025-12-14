#!/bin/bash
set -e

# Setup script for PaperDrop Agent (Manual Install)
echo "Installing PaperDrop Agent..."

# Create directories
sudo mkdir -p /opt/paperdrop
sudo mkdir -p /etc/paperdrop

# Copy source manually from /boot (if available) or rely on what we copy over
# For this run, we assume we are running this on the device and files are local or handling via scp/paste

# Dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv hostapd dnsmasq libjpeg-dev zlib1g-dev libopenjp2-7 libtiff5 rfkill wireless-tools

# Setup Python
cd /opt/paperdrop
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r /boot/paperdrop-src/requirements.txt || echo "Requirements not found in /boot, assuming local..."

# Enable service
echo "Service setup..."
# (Assuming service file is created in next step via copy)

echo "Done."
