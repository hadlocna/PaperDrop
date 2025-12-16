# Raspberry Pi 5 WiFi Provisioning Image Plan

This document describes how we generate a Raspberry Pi 5 image that boots directly into the PaperDrop WiFi provisioning experience. The resulting SD card image can be flashed with `dd`, Raspberry Pi Imager, or Balena Etcher and should bring up the captive portal on first boot.

## Goals
- Use the official Raspberry Pi OS Lite (64‑bit) base image.
- Inject the PaperDrop first-boot installer and WiFi provisioning services so no manual setup is required on the device.
- Keep WiFi credentials empty on the factory image so the agent starts in access-point provisioning mode.

## Build steps
1. Ensure the host has the tooling required to manipulate disk images: `curl`, `xz`, `unzip`, `file`, `losetup`, `partprobe`, `mount`, `rsync`, and `sudo` access.
2. From the repository root run `agent/installer/build_rpi5_image.sh`. The script will:
   - Download the latest Raspberry Pi OS Lite arm64 image (or reuse an existing download).
   - Decompress the image and create a copy named `paperdrop-rpi5-provisioned.img` under `build/rpi5-image/`.
   - Mount the boot and root partitions using a loop device.
   - Place `paperdrop-init.sh`, `setup.sh`, and the PaperDrop installer payload on the boot partition.
   - Enable SSH and replace `cmdline.txt` so the Pi executes the PaperDrop bootstrap on first boot.
   - Unmount and detach the loop device when finished.
3. Flash `build/rpi5-image/paperdrop-rpi5-provisioned.img` to the SD card.

## First-boot sequence on the Pi
1. The modified `cmdline.txt` runs `/boot/paperdrop-init.sh` instead of the standard init process.
2. `paperdrop-init.sh` copies the installer from the boot partition into `/opt/paperdrop_installer` and registers a one-shot systemd unit (`paperdrop-firstboot.service`).
3. On reboot, the first-boot service executes `setup.sh`, which:
   - Installs system dependencies for hostapd/dnsmasq and the PaperDrop Python agent.
   - Configures hostapd, dnsmasq, and the firewall redirect for the captive portal.
   - Leaves `/etc/paperdrop/wifi.json` absent so the agent starts in WiFi setup mode and exposes the setup SSID.
   - Enables the `paperdrop.service` systemd unit to launch the agent on subsequent boots.

## Expected result
- Booting the SD card on an RPi5 should automatically create the `PaperDrop_Setup` access point and captive portal.
- After a user submits WiFi credentials through the portal, the agent applies them and reconnects to the home network without reflashing or manual SSH intervention.
