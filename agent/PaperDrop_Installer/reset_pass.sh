#!/bin/bash
mount -o remount,rw /
echo "pi:paperdrop" | chpasswd
echo "Password reset to paperdrop" > /boot/password_reset.log
# Restore original cmdline to prevent loop
cat /boot/cmdline.bak > /boot/cmdline.txt
# Continue boot
exec /sbin/init
