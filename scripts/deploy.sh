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

# Get the project root directory (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="led-matrix-system"

HOSTNAME="ledmatrix"

echo "[1/6] Setting up mDNS hostname..."
# Install avahi for .local mDNS resolution
apt-get install -y avahi-daemon > /dev/null 2>&1 || true
systemctl enable avahi-daemon > /dev/null 2>&1 || true
systemctl start avahi-daemon > /dev/null 2>&1 || true

# Set hostname to "ledmatrix" so the device is reachable at ledmatrix.local
CURRENT_HOSTNAME="$(hostname)"
if [ "$CURRENT_HOSTNAME" != "$HOSTNAME" ]; then
    echo "$HOSTNAME" > /etc/hostname
    sed -i "s/127\.0\.1\.1.*$/127.0.1.1\t$HOSTNAME/" /etc/hosts
    hostnamectl set-hostname "$HOSTNAME" 2>/dev/null || true
    echo "Hostname set to $HOSTNAME (reachable at $HOSTNAME.local)"
else
    echo "Hostname already set to $HOSTNAME"
fi

echo "[2/6] Installing Python dependencies..."
cd "$PROJECT_ROOT"
python3 -m venv --system-site-packages "$PROJECT_ROOT/venv"
"$PROJECT_ROOT/venv/bin/pip" install -r requirements.txt

echo "[3/6] Building web application..."
if [ -d "$PROJECT_ROOT/frontend" ]; then
    cd "$PROJECT_ROOT/frontend"
    npm install
    npm run build
    cd "$PROJECT_ROOT"
fi

echo "[4/6] Setting up configuration..."
# Create default config
if [ ! -f "$PROJECT_ROOT/config.ini" ]; then
    cat > "$PROJECT_ROOT/config.ini" << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
fi

# Generate JWT secret
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > "$PROJECT_ROOT/.env"
    chmod 600 "$PROJECT_ROOT/.env"
fi

# Create image folder
mkdir -p "$PROJECT_ROOT/matrix_images"

# Make scripts executable
chmod +x "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/stop.sh" "$SCRIPT_DIR/deploy.sh"

echo "[5/6] Setting up systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=LED Matrix System (Viewer + Web Server)
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=$PROJECT_ROOT
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

echo "[6/6] Setting up permissions..."
# Sudoers for overlay management — use actual user, not hardcoded "pi"
DEPLOY_USER="${SUDO_USER:-pi}"
if [ ! -f /etc/sudoers.d/led-matrix ]; then
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /usr/bin/raspi-config" > /etc/sudoers.d/led-matrix
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/led-matrix
    chmod 440 /etc/sudoers.d/led-matrix
fi

# Start service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Web interface:"
echo "  http://$HOSTNAME.local:5000  (any device on the same WiFi)"
echo "  http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "To install as an app on iPhone:"
echo "  1. Open http://$HOSTNAME.local:5000 in Safari"
echo "  2. Tap Share > Add to Home Screen"
echo ""
echo "Commands:"
echo "  sudo $SCRIPT_DIR/start.sh       - Start system"
echo "  sudo $SCRIPT_DIR/stop.sh        - Stop system"
echo "  sudo systemctl status $SERVICE_NAME - Service status"
echo ""
