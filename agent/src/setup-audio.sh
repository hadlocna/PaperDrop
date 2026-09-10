#!/bin/bash
# Headless Bluetooth audio output; safe to re-run during OTA.
set -euo pipefail
packages=(bluez bluez-alsa-utils libasound2-plugin-bluez alsa-utils python3-dbus)
missing=()
for package in "${packages[@]}"; do
    if [ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != 'install ok installed' ]; then
        missing+=("$package")
    fi
done
if [ "${#missing[@]}" -gt 0 ]; then
    apt-get -o DPkg::Lock::Timeout=60 update
    DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=60 install -y --no-install-recommends "${missing[@]}"
fi
mkdir -p /etc/systemd/system/bluealsa.service.d
override=/etc/systemd/system/bluealsa.service.d/paperdrop.conf
contents='[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa -S -p a2dp-source -p hfp-ag -p hsp-ag --io-rt-priority=10 --keep-alive=3
RestrictRealtime=no
LimitRTPRIO=10
CapabilityBoundingSet=CAP_NET_RAW CAP_SYS_NICE
AmbientCapabilities=CAP_NET_RAW CAP_SYS_NICE
SystemCallFilter=@resources'
changed=0
if [ ! -f "$override" ] || [ "$(cat "$override")" != "$contents" ]; then
    printf '%s\n' "$contents" > "$override"
    changed=1
fi
systemctl daemon-reload
systemctl enable --now bluetooth.service bluealsa.service
if [ "$changed" -eq 1 ]; then
    systemctl restart bluealsa.service
fi

# Small offline English recognizer: audio never leaves the device for wake detection.
model_dir=/opt/paperdrop-models/vosk-model-small-en-us-0.15
if [ ! -d "$model_dir" ]; then
    model_archive="$(mktemp)"
    curl -fL --retry 2 --max-time 180 https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -o "$model_archive"
    mkdir -p /opt/paperdrop-models
    python3 -m zipfile -e "$model_archive" /opt/paperdrop-models
    rm -f "$model_archive"
fi
