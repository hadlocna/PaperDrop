#!/usr/bin/env bash
# Run on an arm64 Raspberry Pi OS host against an extracted PaperDrop factory image.
set -Eeuo pipefail

if (( EUID != 0 )) || (( $# != 3 )); then
    echo "Usage: sudo $0 IMAGE.img PUBLIC_KEY HOST_USERNAME" >&2
    exit 2
fi

image=$(realpath -- "$1")
public_key=$(realpath -- "$2")
host_user=$3
target_user=paperdrop

[[ -f "$image" && -f "$public_key" ]] || { echo 'Image or public key is missing' >&2; exit 1; }
[[ "$image" == *.img ]] || { echo 'Expected an extracted .img file' >&2; exit 1; }
[[ "$host_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo 'Invalid host username' >&2; exit 1; }
[[ $(stat -c %s "$image") -eq 7516192768 ]] || { echo 'Unexpected factory image size' >&2; exit 1; }

IFS= read -r key < "$public_key"
[[ "$key" == ssh-ed25519\ * ]] || { echo 'Expected one Ed25519 public key' >&2; exit 1; }
ssh-keygen -lf "$public_key" >/dev/null

host_shadow=$(getent shadow "$host_user")
password_hash=${host_shadow#*:}
password_hash=${password_hash%%:*}
[[ "$password_hash" == \$* ]] || { echo 'Host user has no usable password hash' >&2; exit 1; }

mount_dir=$(mktemp -d)
loop=
cleanup() {
    if mountpoint -q "$mount_dir"; then umount "$mount_dir"; fi
    if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
    rmdir "$mount_dir"
}
trap cleanup EXIT

loop=$(losetup --find --show --partscan "$image")
mount "${loop}p2" "$mount_dir"

[[ -x "$mount_dir/usr/sbin/sshd" ]] || { echo 'Factory image lacks OpenSSH server' >&2; exit 1; }
[[ -e "$mount_dir/etc/passwd" ]] || { echo 'Factory image lacks account database' >&2; exit 1; }
if grep -q "^${target_user}:" "$mount_dir/etc/passwd"; then
    echo "Factory image already has user $target_user" >&2
    exit 1
fi
grep -q '^Include /etc/ssh/sshd_config.d/\*.conf' "$mount_dir/etc/ssh/sshd_config" || {
    echo 'Factory image does not load SSH config snippets' >&2
    exit 1
}

chroot "$mount_dir" /usr/sbin/useradd -m -s /bin/bash -G sudo,adm "$target_user"
chroot "$mount_dir" /usr/sbin/usermod -p "$password_hash" "$target_user"
uid=$(awk -F: -v name="$target_user" '$1 == name {print $3}' "$mount_dir/etc/passwd")
gid=$(awk -F: -v name="$target_user" '$1 == name {print $4}' "$mount_dir/etc/passwd")
install -d -m 700 "$mount_dir/home/$target_user/.ssh"
printf '%s\n' "$key" > "$mount_dir/home/$target_user/.ssh/authorized_keys"
chmod 600 "$mount_dir/home/$target_user/.ssh/authorized_keys"
chown -R "$uid:$gid" "$mount_dir/home/$target_user/.ssh"

install -d -m 755 "$mount_dir/etc/ssh/sshd_config.d"
cat > "$mount_dir/etc/ssh/sshd_config.d/10-paperdrop-debug.conf" <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
chroot "$mount_dir" /usr/bin/ssh-keygen -A
install -d -m 755 "$mount_dir/run/sshd"
chroot "$mount_dir" /usr/sbin/sshd -t
systemctl --root="$mount_dir" enable ssh.service

sync
echo "Personalized $image for $target_user with key-only SSH"
