#!/bin/bash
#
# paperdrop-init.sh
# The "Magic Installer" that runs on first boot (via init= kernel parameter)
# It provisions the system from the /boot partition to the root filesystem.
#

# Mounts
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev

# Mount the root filesystem (read-write)
# We assume /dev/mmcblk0p2 is the root partition on Pi
mount -o rw /dev/mmcblk0p2 /mnt

echo "PaperDrop Installer Started..."

# 1. Copy Scripts
echo "Installing scripts..."
cp /boot/paperdrop-src/paperdrop-first-boot.sh /mnt/usr/local/bin/
cp /boot/paperdrop-src/paperdrop-wifi.sh /mnt/usr/local/bin/
cp /boot/paperdrop-src/paperdrop-reset-wifi.sh /mnt/usr/local/bin/
chmod +x /mnt/usr/local/bin/paperdrop-*.sh

# 2. Install wifi-connect
echo "Installing wifi-connect..."
if [ -f "/boot/offline_assets/wifi-connect.tar.gz" ]; then
    # Extract to temp dir in rootfs
    mkdir -p /mnt/tmp/wc
    tar -xzf /boot/offline_assets/wifi-connect.tar.gz -C /mnt/tmp/wc
    # Find binary
    WC_BIN=$(find /mnt/tmp/wc -name "wifi-connect" -type f | head -n 1)
    if [ -n "$WC_BIN" ]; then
        cp "$WC_BIN" /mnt/usr/local/bin/
        chmod +x /mnt/usr/local/bin/wifi-connect
    fi
    rm -rf /mnt/tmp/wc
fi

# 3. Setup Agent Directory
echo "Setting up agent..."
mkdir -p /mnt/opt/paperdrop
mkdir -p /mnt/etc/paperdrop
mkdir -p /mnt/var/log/paperdrop
cp /boot/paperdrop-src/agent.py /mnt/opt/paperdrop/
cp /boot/paperdrop-src/config.py /mnt/opt/paperdrop/ 2>/dev/null || true
cp /boot/paperdrop-src/requirements.txt /mnt/opt/paperdrop/ 2>/dev/null || true

# 4. Install Python Dependencies (Offline)
# We need to chroot to use pip
echo "Installing Python dependencies..."
# Bind mount /boot to /mnt/boot so chroot can see wheels
mount --bind /boot /mnt/boot

chroot /mnt /bin/bash <<EOF
    python3 -m venv /opt/paperdrop/venv
    source /opt/paperdrop/venv/bin/activate
    if [ -d "/boot/offline_assets/wheels" ]; then
        pip install --no-index --find-links=/boot/offline_assets/wheels -r /opt/paperdrop/requirements.txt
    else
        echo "Warning: No wheels found!"
    fi
EOF

umount /mnt/boot

# 5. Install Systemd Services
echo "Installing services..."
# Create service files directly in /mnt/etc/systemd/system/

# paperdrop-first-boot.service
cat <<EOF > /mnt/etc/systemd/system/paperdrop-first-boot.service
[Unit]
Description=PaperDrop First Boot Initialization
After=local-fs.target
Before=paperdrop-wifi.service
ConditionPathExists=/boot/firmware/paperdrop-first-boot

[Service]
Type=oneshot
ExecStart=/usr/local/bin/paperdrop-first-boot.sh
RemainAfterExit=yes
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF

# paperdrop-wifi.service
cat <<EOF > /mnt/etc/systemd/system/paperdrop-wifi.service
[Unit]
Description=PaperDrop WiFi Provisioning (Access Point)
After=NetworkManager.service paperdrop-first-boot.service
Wants=NetworkManager.service
Before=paperdrop-agent.service

[Service]
Type=simple
ExecStart=/usr/local/bin/paperdrop-wifi.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal+console
StandardError=journal+console

# Don't start until first-boot has run
ExecStartPre=/bin/sh -c 'test ! -f /boot/firmware/paperdrop-first-boot'

[Install]
WantedBy=multi-user.target
EOF

# paperdrop-agent.service
cat <<EOF > /mnt/etc/systemd/system/paperdrop-agent.service
[Unit]
Description=PaperDrop Device Agent
After=network-online.target paperdrop-wifi.service
Wants=network-online.target
# Only start after WiFi is provisioned
ConditionPathExists=/etc/paperdrop/wifi-provisioned

[Service]
Type=simple
ExecStart=/opt/paperdrop/venv/bin/python /opt/paperdrop/agent.py
Restart=always
RestartSec=30
StandardOutput=journal+console
StandardError=journal+console
EnvironmentFile=-/etc/paperdrop/config.env

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable Services (Symlinks)
echo "Enabling services..."
mkdir -p /mnt/etc/systemd/system/multi-user.target.wants
ln -sf /etc/systemd/system/paperdrop-first-boot.service /mnt/etc/systemd/system/multi-user.target.wants/paperdrop-first-boot.service
# Note: wifi and agent services are enabled by first-boot script or manually here?
# The guide says "Enable the wifi-connect service for subsequent boots" in first-boot script.
# But we should probably enable them here to be safe, or let first-boot handle it.
# Let's enable first-boot only, as it orchestrates the rest.

# 7. Create First Boot Flag
touch /mnt/boot/firmware/paperdrop-first-boot
# Also create in /boot (current dir) just in case
touch /boot/paperdrop-first-boot

# 8. Install WiFi Connection (Troubleshooting)
if [ -f "/boot/fabthan2.nmconnection" ]; then
    echo "Installing WiFi profile..."
    cp /boot/fabthan2.nmconnection /mnt/etc/NetworkManager/system-connections/
    chmod 600 /mnt/etc/NetworkManager/system-connections/fabthan2.nmconnection
    chown 0:0 /mnt/etc/NetworkManager/system-connections/fabthan2.nmconnection
fi

# 9. Force Password Reset (Troubleshooting)
echo "Resetting password for user pi..."
# We use chroot to run chpasswd
chroot /mnt /bin/bash -c "echo 'pi:raspberry' | chpasswd"

# 10. Restore cmdline.txt
echo "Restoring boot config..."
# Remove the init= parameter
sed -i 's| init=/boot/paperdrop-init.sh||g' /boot/cmdline.txt

# 10. Sync and Reboot
echo "Installation Complete. Rebooting..."
sync
umount /mnt
reboot -f
