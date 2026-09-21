#!/bin/bash
# Runs only inside an arm64 Linux build container. Never writes a physical disk.
set -Eeuo pipefail
cd /workspace
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends xz-utils fdisk e2fsprogs parted rsync ca-certificates curl
work=/workspace/artifacts/image-build
expected=$(awk '{print $1}' "$work/base.sha256")
echo "$expected  $work/base.img.xz" | sha256sum -c -
image="$work/paperdrop-2.0.0-20260921.img"
xz -dc "$work/base.img.xz" > "$image"
truncate -s 7G "$image"
parted -s "$image" resizepart 2 100%
loop=$(losetup --find --show --partscan "$image")
root=$(mktemp -d)
cleanup() {
    umount "$root/dev/pts" "$root/dev" "$root/proc" "$root/sys" "$root/boot/firmware" 2>/dev/null || true
    umount "$root" 2>/dev/null || true
    losetup -d "$loop" 2>/dev/null || true
    rmdir "$root" 2>/dev/null || true
}
trap cleanup EXIT
sleep 1
# Docker Desktop exposes loop devices but does not run udev for partition nodes.
for part in 1 2; do
    node="${loop}p${part}"
    if [ ! -b "$node" ]; then
        dev=$(cat "/sys/class/block/$(basename "$loop")/$(basename "$node")/dev")
        mknod "$node" b "${dev%:*}" "${dev#*:}"
    fi
done
e2fsck -fy "${loop}p2" || test "$?" -eq 1
resize2fs "${loop}p2"
mount "${loop}p2" "$root"
mount "${loop}p1" "$root/boot/firmware"
mount --bind /dev "$root/dev"
mount -t devpts devpts "$root/dev/pts"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
cp -L /etc/resolv.conf "$root/etc/resolv.conf.build"
# Preserve the OS resolver symlink for the final image.
cp -a "$root/etc/resolv.conf" "$root/etc/resolv.conf.original"
rm "$root/etc/resolv.conf"
cp "$root/etc/resolv.conf.build" "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod +x "$root/usr/sbin/policy-rc.d"
chroot "$root" apt-get update -qq
chroot "$root" apt-get install -y -qq --no-install-recommends python3-venv python3-dbus bluez bluez-alsa-utils libasound2-plugin-bluez alsa-utils libhidapi-libusb0 libcairo2 fonts-dejavu-core libusb-1.0-0 network-manager dnsmasq-base openssh-server curl ca-certificates
mkdir -p "$root/opt/paperdrop/releases/2.0.0-20260921" "$root/var/lib/paperdrop/streamdeck" "$root/var/log/paperdrop" "$root/etc/paperdrop" "$root/usr/local/lib/paperdrop"
tar -xzf artifacts/firmware/paperdrop-2.0.0-20260921.tar.gz -C "$root/opt/paperdrop/releases/2.0.0-20260921"
ln -s releases/2.0.0-20260921 "$root/opt/paperdrop/current"
chroot "$root" python3 -m venv /opt/paperdrop/releases/2.0.0-20260921/venv
chroot "$root" /opt/paperdrop/current/venv/bin/pip install --disable-pip-version-check -r /opt/paperdrop/current/requirements.txt
mkdir -p "$root/opt/paperdrop/wheels"
chroot "$root" /opt/paperdrop/current/venv/bin/pip download -r /opt/paperdrop/current/requirements.txt -d /opt/paperdrop/wheels
cp agent/src/auto_update.py agent/src/update_guard.py "$root/usr/local/lib/paperdrop/"
cp agent/factory/paperdrop-*.service agent/factory/paperdrop-*.timer "$root/etc/systemd/system/"
cp agent/factory/first_boot.py agent/factory/wifi_portal.py "$root/usr/local/lib/paperdrop/"
mkdir -p "$root/etc/systemd/system/bluealsa.service.d"
cat > "$root/etc/systemd/system/bluealsa.service.d/paperdrop.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa -S -p a2dp-source --io-rt-priority=10 --keep-alive=3
RestrictRealtime=no
LimitRTPRIO=10
EOF
chroot "$root" systemctl enable paperdrop-runtime.service paperdrop-update.timer paperdrop-enroll.service paperdrop-setup.service bluetooth.service bluealsa.service NetworkManager.service
# A factory image never contains laptop keys, Wi-Fi passwords or a device identity.
rm -f "$root/etc/paperdrop/device.json" "$root/etc/paperdrop/device-id" "$root/etc/ssh/ssh_host_"* "$root/etc/machine-id" "$root/var/lib/dbus/machine-id"
touch "$root/etc/machine-id"
rm -f "$root/usr/sbin/policy-rc.d" "$root/etc/resolv.conf"
mv "$root/etc/resolv.conf.original" "$root/etc/resolv.conf"
rm -f "$root/etc/resolv.conf.build"
chroot "$root" apt-get clean
rm -rf "$root/root/.cache/pip"
# Disable stock first-login wizard; our setup service owns onboarding.
chroot "$root" systemctl mask userconfig.service 2>/dev/null || true
cat > "$root/boot/firmware/PAPERDROP-START-HERE.txt" <<'EOF'
PaperDrop automatic-update image
Power off your Pi before swapping cards. Use Ethernet for the simplest first start.
For Wi-Fi, join the PaperDrop-Setup network (password: paperdrop-setup) from a phone and open http://10.42.0.1:8080.
Once online, PaperDrop checks the published stable release automatically.
Use the PaperDrop app to claim a new device and connect its Bluetooth speaker.
A house-specific enrollment file can restore an existing device before first boot.
EOF
sync
cleanup
trap - EXIT
xz -T2 -3 -k "$image"
sha256sum "$image.xz" > "$image.xz.sha256"
echo "Image built: $image.xz"
