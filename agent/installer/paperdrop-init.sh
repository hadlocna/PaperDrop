#!/bin/bash
# paperdrop-init.sh
# This script runs INSTEAD of /sbin/init on the first boot.
# It sets up a one-time systemd service to install PaperDrop, then restores standard boot.

mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t tmpfs tmp /run

# Remount root as RW
mount -o remount,rw /

# Find the boot partition (usually mounted at /boot, but in early init strictly might need finding)
# In RPi OS, the kernel mounts the rootfs. We are on rootfs.
# But /boot might not be mounted yet.
mkdir -p /boot
mount /dev/mmcblk0p1 /boot

# 1. Copy Installer Files to /opt
echo "Staging PaperDrop Installer..."
mkdir -p /opt/paperdrop_installer
cp -r /boot/paperdrop-src/* /opt/paperdrop_installer/
cp /boot/setup.sh /opt/paperdrop_installer/
chmod +x /opt/paperdrop_installer/setup.sh

# 2. Create One-Shot Systemd Service for Installation
# This ensures installation happens in a proper systemd environment (network, apt, etc)
cat <<EOF > /etc/systemd/system/paperdrop-firstboot.service
[Unit]
Description=PaperDrop First Boot Setup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/paperdrop_installer/setup.sh
RemainAfterExit=yes
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
EOF

# 3. Enable the service
ln -s /etc/systemd/system/paperdrop-firstboot.service /etc/systemd/system/multi-user.target.wants/paperdrop-firstboot.service

# 4. Restore cmdline.txt (Remove init=/boot/paperdrop-init.sh)
# We assume the original cmdline works if we just strip the init= part.
sed -i 's| init=/boot/paperdrop-init.sh||g' /boot/cmdline.txt

# 5. Sync and Reboot to start real systemd
sync
umount /boot
mount -o remount,ro /
echo "Bootstrap complete. Rebooting into installer..."
/sbin/reboot -f
