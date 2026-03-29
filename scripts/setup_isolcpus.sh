#!/bin/bash
# Setup script to add isolcpus=3 to /boot/cmdline.txt
# This improves display update performance by reserving CPU core 3 for the viewer

CMDLINE_FILE="/boot/cmdline.txt"
FIRMWARE_CMDLINE="/boot/firmware/cmdline.txt"

# Check which file exists (different Pi OS versions use different paths)
if [ -f "$FIRMWARE_CMDLINE" ]; then
    CMDLINE_FILE="$FIRMWARE_CMDLINE"
fi

echo "Checking $CMDLINE_FILE for isolcpus setting..."

# Check if isolcpus is already set
if grep -q "isolcpus=" "$CMDLINE_FILE"; then
    echo "isolcpus is already configured in $CMDLINE_FILE"
    grep "isolcpus" "$CMDLINE_FILE"
    echo ""
    echo "If you want to change it, manually edit the file:"
    echo "  sudo nano $CMDLINE_FILE"
    exit 0
fi

# Create backup
echo "Creating backup of $CMDLINE_FILE..."
sudo cp "$CMDLINE_FILE" "${CMDLINE_FILE}.backup"

# Add isolcpus=3 to the end of the line (cmdline.txt is a single line)
echo "Adding isolcpus=3 to $CMDLINE_FILE..."
sudo sed -i 's/$/ isolcpus=3/' "$CMDLINE_FILE"

# Verify the change was applied
if ! grep -q "isolcpus=3" "$CMDLINE_FILE"; then
    echo "ERROR: Failed to add isolcpus=3 to $CMDLINE_FILE"
    exit 1
fi

echo ""
echo "Done! New contents of $CMDLINE_FILE:"
cat "$CMDLINE_FILE"
echo ""
echo "================================================"
echo "IMPORTANT: You must reboot for changes to take effect!"
echo "Run: sudo reboot"
echo "================================================"
echo ""
echo "After reboot, verify with: cat /sys/devices/system/cpu/isolated"
echo "Should show: 3"
