#!/bin/bash
# Export files, never raw free space or a physical disk. Run as a transient root service.
set -Eeuo pipefail
test "$(id -u)" = 0
work=/run/paperdrop-image
mkdir -p "$work"
chmod 755 "$work"
rm -f "$work/result"
fifo="$work/export.fifo"
test ! -e "$fifo"
mkfifo -m 600 "$fifo"
chown paperdrop:paperdrop "$fifo"
was_active=no
cleanup() {
    result=$?
    if [ "$was_active" = yes ]; then
        systemctl start paperdrop-runtime.service || result=1
    fi
    printf '%s\n' "$result" > "$work/result"
    chmod 644 "$work/result"
    rm -f "$fifo"
}
trap cleanup EXIT
trap 'exit 130' TERM INT
# Wait for the reader before interrupting the working runtime.
exec 3>"$fifo"
if systemctl is-active --quiet paperdrop-runtime.service; then
    was_active=yes
    systemctl stop paperdrop-runtime.service
fi
tar --create --file=- --numeric-owner --acls --xattrs --one-file-system \
    --exclude='./dev' --exclude='./proc' --exclude='./sys' \
    --exclude='./run' --exclude='./tmp' --exclude='./mnt' --exclude='./media' \
    --exclude='./home/*' --exclude='./root/*' \
    --exclude='./etc/paperdrop' --exclude='./etc/netplan/*' \
    --exclude='./etc/NetworkManager/system-connections/*' \
    --exclude='./etc/ssh/ssh_host_*' --exclude='./etc/shadow*' --exclude='./etc/gshadow*' \
    --exclude='./etc/machine-id' --exclude='./etc/wpa_supplicant/*' \
    --exclude='./etc/ssl/private/*' \
    --exclude='./var/log/*' --exclude='./var/tmp/*' --exclude='./var/cache/*' \
    --exclude='./var/spool/*' --exclude='./var/lib/paperdrop/*' \
    --exclude='./var/lib/bluetooth/*' --exclude='./var/lib/NetworkManager/*' \
    --exclude='./var/lib/cloud/*' --exclude='./var/lib/dbus/machine-id' \
    --exclude='./var/lib/systemd/random-seed' --exclude='./var/lib/dhcpcd/*' \
    --exclude='./var/lib/systemd/credential.secret' --exclude='./var/lib/systemd/pstore/*' \
    --exclude='./var/lib/lightdm/*' --exclude='./var/lib/AccountsService/*' \
    --exclude='./swapfile' --exclude='./var/swap*' \
    --exclude='*/paperdrop-enrollment.json' --exclude='*/firstrun.sh' \
    --exclude='*/userconf*' --exclude='*/user-data' --exclude='*/network-config' \
    --exclude='*/meta-data' --exclude='./boot/firmware/ssh' --exclude='boot/firmware/ssh' \
    --exclude='./boot/firmware/ssh.txt' --exclude='boot/firmware/ssh.txt' \
    --exclude='*/.ssh' --exclude='*/.env' \
    --exclude='*/System Volume Information' \
    -C / . boot/firmware >&3
