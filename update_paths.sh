#!/bin/bash

# Quick update script to apply /data/matrix path changes
# Run this after setup_writable_data.sh

echo "Updating server.py and viewer.py to use /data/matrix paths..."

# Note: The paths have already been updated in the Python files
# This script is just for documentation

echo ""
echo "Path changes applied:"
echo "  - Images: /data/matrix/images"
echo "  - Config: /data/matrix/config/config.ini"
echo "  - Auth: /data/matrix/config/.auth"
echo ""
echo "The code will automatically fall back to local directories"
echo "if /data/matrix doesn't exist."
echo ""
echo "Next steps:"
echo "1. Run setup_writable_data.sh to create /data/matrix"
echo "2. Enable overlay filesystem for system protection"
echo "3. Reboot"
echo ""
