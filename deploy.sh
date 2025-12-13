#!/bin/bash

# LED Matrix Server Deployment Script for Raspberry Pi
# Run this script on your Raspberry Pi to set up the server

set -e

echo "=== LED Matrix Server Deployment ==="

# Variables
INSTALL_DIR="/home/pi/rpi-led-matrix"
SERVICE_NAME="led-matrix-server"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

echo "[1/6] Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv

echo "[2/6] Creating virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

echo "[3/6] Installing Python dependencies..."
pip install -r requirements.txt

echo "[4/6] Building web app (if npm is available)..."
if command -v npm &> /dev/null; then
    cd "$INSTALL_DIR/my-app"
    npm install
    npm run build
    cd "$INSTALL_DIR"
else
    echo "npm not found - skipping web app build. Make sure dist/ folder exists."
fi

echo "[5/6] Setting up systemd service..."
cp "$INSTALL_DIR/led-matrix-server.service" /etc/systemd/system/
# Update the service to use the virtual environment
sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$INSTALL_DIR/venv/bin/python3|g" /etc/systemd/system/led-matrix-server.service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "[6/6] Setting up sudoers for overlay management..."
# Allow the service to run raspi-config without password
echo "pi ALL=(ALL) NOPASSWD: /usr/bin/raspi-config" > /etc/sudoers.d/led-matrix
echo "pi ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/led-matrix
chmod 440 /etc/sudoers.d/led-matrix

echo ""
echo "=== Deployment Complete ==="
echo "Service status:"
systemctl status $SERVICE_NAME --no-pager

echo ""
echo "The server is running at: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Useful commands:"
echo "  - View logs:     sudo journalctl -u $SERVICE_NAME -f"
echo "  - Restart:       sudo systemctl restart $SERVICE_NAME"
echo "  - Stop:          sudo systemctl stop $SERVICE_NAME"
echo "  - Status:        sudo systemctl status $SERVICE_NAME"
