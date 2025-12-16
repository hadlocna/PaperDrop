#!/usr/bin/env bash
set -euo pipefail

# Build a Raspberry Pi 5 SD card image that boots directly into PaperDrop's
# WiFi provisioning flow.

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo)." >&2
  exit 1
fi

for bin in curl xz unzip file losetup partprobe mount rsync; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing required tool: $bin" >&2
    exit 1
  fi
done

REPO_ROOT="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$REPO_ROOT/build/rpi5-image"
DOWNLOAD_URL="${OS_IMAGE_URL:-https://downloads.raspberrypi.com/raspios_lite_arm64_latest}"
DOWNLOAD_TARGET="$BUILD_DIR/raspios-lite-arm64.download"
IMAGE_XZ="$BUILD_DIR/raspios-lite-arm64.img.xz"
IMAGE_RAW="$BUILD_DIR/raspios-lite-arm64.img"
OUTPUT_IMAGE="$BUILD_DIR/paperdrop-rpi5-provisioned.img"

mkdir -p "$BUILD_DIR"

if [[ ! -f "$IMAGE_RAW" && ! -f "$IMAGE_XZ" ]]; then
  echo "Downloading Raspberry Pi OS Lite (arm64)..."
  curl -L "$DOWNLOAD_URL" -o "$DOWNLOAD_TARGET"

  MIME_TYPE=$(file --brief --mime-type "$DOWNLOAD_TARGET")
  case "$MIME_TYPE" in
    application/zip)
      echo "Extracting .img.xz from zip payload..."
      unzip -p "$DOWNLOAD_TARGET" '*.img.xz' > "$IMAGE_XZ"
      ;;
    application/x-xz|application/xz)
      mv "$DOWNLOAD_TARGET" "$IMAGE_XZ"
      ;;
    *)
      echo "Unexpected download MIME type: $MIME_TYPE" >&2
      exit 1
      ;;
  esac
else
  echo "Reusing existing download artifacts in $BUILD_DIR"
fi

if [[ ! -f "$IMAGE_RAW" ]]; then
  echo "Decompressing base image..."
  xz -dk "$IMAGE_XZ"
fi

cp "$IMAGE_RAW" "$OUTPUT_IMAGE"
echo "Prepared working image at $OUTPUT_IMAGE"

cleanup() {
  set +e
  if mountpoint -q "$BOOT_MNT"; then umount "$BOOT_MNT"; fi
  if mountpoint -q "$ROOT_MNT"; then umount "$ROOT_MNT"; fi
  if [[ -n "${LOOP_DEV:-}" ]]; then losetup -d "$LOOP_DEV" 2>/dev/null; fi
}
trap cleanup EXIT

BOOT_MNT=$(mktemp -d)
ROOT_MNT=$(mktemp -d)

LOOP_DEV=$(losetup --find --show --partscan "$OUTPUT_IMAGE")
partprobe "$LOOP_DEV"

mount "${LOOP_DEV}p1" "$BOOT_MNT"
mount "${LOOP_DEV}p2" "$ROOT_MNT"

echo "Injecting PaperDrop first-boot assets..."
install -m 755 "$REPO_ROOT/agent/installer/paperdrop-init.sh" "$BOOT_MNT/paperdrop-init.sh"
install -m 644 "$REPO_ROOT/agent/installer/cmdline.txt" "$BOOT_MNT/cmdline.txt"
install -m 644 "$REPO_ROOT/agent/PaperDrop_Installer/setup.sh" "$BOOT_MNT/setup.sh"
rsync -a "$REPO_ROOT/agent/PaperDrop_Installer/paperdrop-src/" "$BOOT_MNT/paperdrop-src/"

touch "$BOOT_MNT/ssh"

echo "PaperDrop installer staged. Syncing and cleaning up..."
sync
umount "$BOOT_MNT"
umount "$ROOT_MNT"
losetup -d "$LOOP_DEV"
trap - EXIT

rm -rf "$BOOT_MNT" "$ROOT_MNT"

echo "Image ready: $OUTPUT_IMAGE"
echo "Flash this file to the SD card for an RPi5 provisioning image."
