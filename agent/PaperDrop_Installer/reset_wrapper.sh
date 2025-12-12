#!/bin/sh
# PaperDrop Rescue Script
# 1. Mount filesystems
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -o remount,rw /

# 2. Reset Password (The "Fix")
echo "Reseting password to 'paperdrop'..."
echo "pi:paperdrop" | chpasswd

# 3. Ensure SSH is enabled
touch /boot/ssh
systemctl enable ssh

# 4. Restore original boot config (Stop the loop)
# We copy back the clean backup we made
if [ -f /boot/cmdline.bak ]; then
    cp /boot/cmdline.bak /boot/cmdline.txt
else
    # Fallback to hardcoded standard if backup missing (Safety net)
    echo "console=serial0,115200 console=tty1 root=PARTUUID=efa1509d-02 rootfstype=ext4 fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles" > /boot/cmdline.txt
fi

# 5. Sync and Boot
sync
exec /sbin/init
