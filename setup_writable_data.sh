#!/bin/bash

# Setup script to create a writable data partition for LED matrix uploads
# This allows the system to run with overlay filesystem protection while
# still accepting real-time uploads and config changes.

set -e

echo "==================================================================="
echo "LED Matrix - Writable Data Partition Setup"
echo "==================================================================="
echo ""
echo "This script will:"
echo "1. Create a writable directory at /data/matrix"
echo "2. Move existing images and config to /data/matrix"
echo "3. Update server.py paths to use /data/matrix"
echo "4. Set up proper permissions"
echo "5. Enable overlay filesystem for system protection"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# 1. Create writable data directory
echo ""
echo "Creating /data/matrix directory..."
sudo mkdir -p /data/matrix
sudo mkdir -p /data/matrix/images
sudo mkdir -p /data/matrix/config

# 2. Move existing data
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo "Moving existing images..."
if [ -d "$SCRIPT_DIR/matrix_images" ]; then
    sudo cp -r "$SCRIPT_DIR/matrix_images"/* /data/matrix/images/ 2>/dev/null || true
    echo "Images copied from $SCRIPT_DIR/matrix_images"
fi

echo "Moving config files..."
if [ -f "$SCRIPT_DIR/config.ini" ]; then
    sudo cp "$SCRIPT_DIR/config.ini" /data/matrix/config/
    echo "config.ini copied"
fi

if [ -f "$SCRIPT_DIR/.auth" ]; then
    sudo cp "$SCRIPT_DIR/.auth" /data/matrix/config/
    echo ".auth copied"
fi

# 3. Set permissions (allow pi user to write)
echo ""
echo "Setting permissions..."
sudo chown -R pi:pi /data/matrix
sudo chmod -R 755 /data/matrix

# 4. Create order.txt if it doesn't exist
if [ ! -f "/data/matrix/images/order.txt" ]; then
    echo "Creating order.txt..."
    ls /data/matrix/images/*.{png,jpg,jpeg,gif} 2>/dev/null | xargs -n 1 basename > /tmp/order.txt || true
    sudo mv /tmp/order.txt /data/matrix/images/order.txt
    sudo chown pi:pi /data/matrix/images/order.txt
fi

# 5. Add /data to fstab for explicit write mounting (if not already there)
echo ""
echo "Checking /etc/fstab..."
if ! grep -q "/data" /etc/fstab; then
    echo "Adding /data mount to /etc/fstab..."
    echo "tmpfs /data tmpfs defaults,noatime,mode=1777 0 0" | sudo tee -a /etc/fstab
    echo "Note: /data is mounted as tmpfs (RAM). For persistent storage across reboots,"
    echo "      you may want to use a separate partition or USB drive instead."
else
    echo "/data already in /etc/fstab"
fi

# 6. Mount /data
echo ""
echo "Mounting /data..."
sudo mount -a 2>/dev/null || true

# Re-copy data after mount (in case /data was just mounted)
sudo mkdir -p /data/matrix/images /data/matrix/config
if [ -d "$SCRIPT_DIR/matrix_images" ]; then
    sudo cp -r "$SCRIPT_DIR/matrix_images"/* /data/matrix/images/ 2>/dev/null || true
fi
if [ -f "$SCRIPT_DIR/config.ini" ]; then
    sudo cp "$SCRIPT_DIR/config.ini" /data/matrix/config/
fi
if [ -f "$SCRIPT_DIR/.auth" ]; then
    sudo cp "$SCRIPT_DIR/.auth" /data/matrix/config/
fi
sudo chown -R pi:pi /data/matrix
sudo chmod -R 755 /data/matrix

echo ""
echo "==================================================================="
echo "Setup complete!"
echo "==================================================================="
echo ""
echo "Next steps:"
echo "1. Update server.py to use /data/matrix paths (or run the update script)"
echo "2. Enable overlay filesystem: sudo raspi-config nonint do_overlayfs 0"
echo "3. Reboot: sudo reboot"
echo ""
echo "After reboot, your system will be protected but uploads will still work!"
echo ""
