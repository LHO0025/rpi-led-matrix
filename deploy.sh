#!/bin/bash

# LED Matrix System - Simple Deployment Script
# Run this once to set up the system

set -e

echo "=== LED Matrix System Deployment ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="led-matrix-system"

echo "[1/5] Installing Python dependencies..."
cd "$SCRIPT_DIR"
pip3 install -r requirements.txt

echo "[2/5] Building web application..."
if [ -d "$SCRIPT_DIR/my-app" ]; then
    cd "$SCRIPT_DIR/my-app"
    npm install
    npm run build
    cd "$SCRIPT_DIR"
fi

echo "[3/5] Setting up configuration..."
# Create default config
if [ ! -f "config.ini" ]; then
    cat > config.ini << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
fi

# Generate JWT secret
if [ ! -f ".env" ]; then
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > .env
    chmod 600 .env
fi

# Create image folder
mkdir -p matrix_images

# Make scripts executable
chmod +x start.sh stop.sh deploy.sh

echo "[4/5] Setting up systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=LED Matrix System (Viewer + Web Server)
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/start.sh
ExecStop=$SCRIPT_DIR/stop.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "[5/5] Setting up permissions..."
# Sudoers for overlay management
if [ ! -f /etc/sudoers.d/led-matrix ]; then
    echo "pi ALL=(ALL) NOPASSWD: /usr/bin/raspi-config" > /etc/sudoers.d/led-matrix
    echo "pi ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/led-matrix
    chmod 440 /etc/sudoers.d/led-matrix
fi

# Start service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Web interface: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Commands:"
echo "  sudo $SCRIPT_DIR/start.sh      - Start system"
echo "  sudo $SCRIPT_DIR/stop.sh       - Stop system"
echo "  sudo systemctl status $SERVICE_NAME - Service status"
echo ""
