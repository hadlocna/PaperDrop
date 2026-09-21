#!/bin/bash
set -Eeuo pipefail
mount --make-rprivate /
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends fdisk e2fsprogs xz-utils curl unzip ca-certificates
cd /workspace
image=/workspace/artifacts/image-build/paperdrop-2.0.0-20260921.img
loop=$(losetup --find --show --partscan "$image")
root=$(mktemp -d)
cleanup() {
    umount "$root/boot/firmware" 2>/dev/null || true
    umount "$root" 2>/dev/null || true
    losetup -d "$loop" 2>/dev/null || true
    rmdir "$root" 2>/dev/null || true
}
trap cleanup EXIT
for part in 1 2; do
 node="${loop}p${part}"
 if [ ! -b "$node" ]; then
  dev=$(cat "/sys/class/block/$(basename "$loop")/$(basename "$node")/dev")
  mknod "$node" b "${dev%:*}" "${dev#*:}"
 fi
done
mount "${loop}p2" "$root"
mount "${loop}p1" "$root/boot/firmware"
tar -xzf artifacts/firmware/paperdrop-2.0.0-20260921.tar.gz -C "$root/opt/paperdrop/releases/2.0.0-20260921"
cp agent/src/auto_update.py agent/src/update_guard.py "$root/usr/local/lib/paperdrop/"
cp agent/factory/first_boot.py agent/factory/wifi_portal.py "$root/usr/local/lib/paperdrop/"
cp agent/factory/paperdrop-*.service agent/factory/paperdrop-*.timer "$root/etc/systemd/system/"
# Include the offline wake model for devices without a button pad.
if [ ! -d "$root/opt/paperdrop-models/vosk-model-small-en-us-0.15" ]; then
 curl -fL --retry 2 https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -o artifacts/image-build/vosk.zip
 mkdir -p "$root/opt/paperdrop-models"
 unzip -q artifacts/image-build/vosk.zip -d "$root/opt/paperdrop-models"
fi
chroot "$root" /opt/paperdrop/current/venv/bin/python -c 'import websockets, PIL, StreamDeck, cairosvg, escpos, vosk, audioop; print("Image runtime imports: OK")'
chroot "$root" /opt/paperdrop/current/venv/bin/pip freeze > artifacts/image-build/installed-requirements.txt
chroot "$root" /usr/bin/python3 -m compileall -q /usr/local/lib/paperdrop /opt/paperdrop/current/src /opt/paperdrop/current/streamdeck
chroot "$root" systemd-analyze verify /etc/systemd/system/paperdrop-runtime.service /etc/systemd/system/paperdrop-update.service /etc/systemd/system/paperdrop-update.timer /etc/systemd/system/paperdrop-enroll.service /etc/systemd/system/paperdrop-setup.service
for path in /etc/paperdrop/device.json /etc/paperdrop/device-id /etc/paperdrop/enrollment.json; do
 test ! -e "$root$path"
done
# No default account/password or host SSH keys are distributed.
test -z "$(find "$root/etc/ssh" -name 'ssh_host_*' -print -quit)"
find "$root/etc/NetworkManager/system-connections" -type f -print > artifacts/image-build/network-profile-check.txt
test ! -s artifacts/image-build/network-profile-check.txt
printf 'Image imports, Python compilation, systemd units, identity and Wi-Fi checks passed.\n' > artifacts/image-build/verification.txt
sync
cleanup
trap - EXIT
xz -T2 -3 -f -k "$image"
sha256sum "$image.xz" > "$image.xz.sha256"
echo 'Factory image finalized and verified.'
