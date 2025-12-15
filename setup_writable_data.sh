#!/bin/bash
set -euo pipefail

# Persistent /data setup for LED matrix (overlay-safe OS + writable persistent data)
# Usage:
#   sudo ./setup_persistent_data.sh /dev/sda1
#   sudo ./setup_persistent_data.sh /dev/mmcblk0p3
# Optional:
#   sudo ./setup_persistent_data.sh /dev/sda1 --format   # DANGEROUS: formats the partition as ext4

USER_NAME="pi"
GROUP_NAME="pi"
MOUNT_POINT="/data"
DATA_DIR="/data/matrix"

DEVICE="${1:-}"
DO_FORMAT="${2:-}"

if [[ -z "$DEVICE" ]]; then
  echo "Usage: sudo $0 <block-device-partition> [--format]"
  echo "Examples:"
  echo "  sudo $0 /dev/sda1"
  echo "  sudo $0 /dev/mmcblk0p3"
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (use sudo)."
  exit 1
fi

if [[ ! -b "$DEVICE" ]]; then
  echo "ERROR: $DEVICE is not a block device."
  echo "Tip: run 'lsblk -f' to find the right partition (e.g. /dev/sda1, /dev/mmcblk0p3)."
  exit 1
fi

echo "==================================================================="
echo "Persistent /data setup"
echo "==================================================================="
echo "Device:      $DEVICE"
echo "Mount point: $MOUNT_POINT"
echo "Matrix dir:  $DATA_DIR"
echo ""

if [[ "$DO_FORMAT" == "--format" ]]; then
  echo "WARNING: You asked to FORMAT $DEVICE as ext4. This will ERASE all data on it."
  read -p "Type EXACTLY 'FORMAT' to continue: " confirm
  if [[ "$confirm" != "FORMAT" ]]; then
    echo "Aborted."
    exit 1
  fi

  echo "Formatting $DEVICE as ext4..."
  mkfs.ext4 -F "$DEVICE"
else
  echo "No formatting will be performed."
fi

# Ensure mount point exists
mkdir -p "$MOUNT_POINT"

# Remove tmpfs /data entry if present
if grep -qE '^[^#].*\s+/data\s+tmpfs\s+' /etc/fstab; then
  echo "Removing tmpfs /data entry from /etc/fstab..."
  cp /etc/fstab "/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"
  # Comment out any active tmpfs line mounting /data
  sed -i -E 's@^([^#].*\s+/data\s+tmpfs\s+.*)$@# \1@' /etc/fstab
fi

# Get UUID for stable fstab entry
UUID="$(blkid -s UUID -o value "$DEVICE" || true)"
FSTYPE="$(blkid -s TYPE -o value "$DEVICE" || true)"

if [[ -z "$UUID" || -z "$FSTYPE" ]]; then
  echo "ERROR: Could not read UUID/TYPE from $DEVICE."
  echo "If it has no filesystem, rerun with --format, or format it manually."
  exit 1
fi

echo "Detected filesystem: $FSTYPE"
echo "Detected UUID:       $UUID"

if [[ "$FSTYPE" != "ext4" ]]; then
  echo "NOTE: This script expects ext4 for best results."
  echo "      Current type is '$FSTYPE'. It may still work, but ext4 is recommended."
fi

# Add fstab entry if not already present
if grep -qE "UUID=$UUID\s+$MOUNT_POINT\s+" /etc/fstab; then
  echo "/etc/fstab already contains an entry for UUID=$UUID at $MOUNT_POINT"
else
  echo "Adding persistent mount to /etc/fstab..."
  cp /etc/fstab "/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"
  # noatime reduces writes; defaults keeps it simple; add 'nofail' if you use USB and want boot to continue if missing
  echo "UUID=$UUID  $MOUNT_POINT  $FSTYPE  defaults,noatime  0  2" >> /etc/fstab
fi

# Mount it now (unmount if currently something else)
if mountpoint -q "$MOUNT_POINT"; then
  echo "$MOUNT_POINT is currently mounted. Ensuring it's the correct device..."
  CURRENT_SRC="$(findmnt -n -o SOURCE --target "$MOUNT_POINT" || true)"
  if [[ "$CURRENT_SRC" != "$DEVICE" && "$CURRENT_SRC" != "UUID=$UUID" ]]; then
    echo "Unmounting current $MOUNT_POINT mount ($CURRENT_SRC)..."
    umount "$MOUNT_POINT"
  fi
fi

echo "Mounting $MOUNT_POINT..."
mount "$MOUNT_POINT"

# Verify it is a real disk mount (not tmpfs)
MNT_FSTYPE="$(findmnt -n -o FSTYPE --target "$MOUNT_POINT" || true)"
if [[ "$MNT_FSTYPE" == "tmpfs" ]]; then
  echo "ERROR: $MOUNT_POINT is still tmpfs. Check /etc/fstab for leftover tmpfs entries."
  exit 1
fi

echo "Mounted $MOUNT_POINT as: $MNT_FSTYPE"

# Create matrix directories
mkdir -p "$DATA_DIR/images" "$DATA_DIR/config"

# Copy existing data from script directory (if present)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Copying existing images/config if found..."
if [[ -d "$SCRIPT_DIR/matrix_images" ]]; then
  cp -r "$SCRIPT_DIR/matrix_images"/. "$DATA_DIR/images/" 2>/dev/null || true
  echo "  Copied images from $SCRIPT_DIR/matrix_images"
fi

if [[ -f "$SCRIPT_DIR/config.ini" ]]; then
  cp "$SCRIPT_DIR/config.ini" "$DATA_DIR/config/"
  echo "  Copied config.ini"
fi

if [[ -f "$SCRIPT_DIR/.auth" ]]; then
  cp "$SCRIPT_DIR/.auth" "$DATA_DIR/config/"
  echo "  Copied .auth"
fi

# Create order.txt if missing
if [[ ! -f "$DATA_DIR/images/order.txt" ]]; then
  echo "Creating order.txt..."
  (ls "$DATA_DIR"/images/*.{png,jpg,jpeg,gif} 2>/dev/null | xargs -n 1 basename) > /tmp/order.txt || true
  mv /tmp/order.txt "$DATA_DIR/images/order.txt"
fi

# Permissions
chown -R "$USER_NAME:$GROUP_NAME" "$DATA_DIR"
chmod -R 755 "$DATA_DIR"

echo ""
echo "==================================================================="
echo "Done."
echo "==================================================================="
echo "Persistent data is now at: $DATA_DIR"
echo ""
echo "Next steps:"
echo "1) Update your server.py to use:"
echo "   Images: $DATA_DIR/images"
echo "   Config: $DATA_DIR/config"
echo "2) Enable overlay for the OS if you want (root protection):"
echo "   sudo raspi-config nonint do_overlayfs 0"
echo "3) Reboot:"
echo "   sudo reboot"
echo ""
echo "Tip: verify after reboot:"
echo "  mount | grep ' /data '"
echo "  ls -la $DATA_DIR"
