#!/bin/bash

# LED Matrix System - Full Deployment Script for Raspberry Pi
# Run this once to set up everything from scratch

set -e

echo "=== LED Matrix System Deployment ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR"
SERVICE_NAME="led-matrix-system"



# Install RGB Matrix library if not already installed
if ! python3 -c "import rgbmatrix" 2>/dev/null; then
    echo "Installing RGB Matrix Python library..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
    cd rpi-rgb-led-matrix/bindings/python
    make build-python PYTHON=$(which python3)
    make install-python PYTHON=$(which python3)
    cd "$INSTALL_DIR"
    rm -rf "$TEMP_DIR"
else
    echo "RGB Matrix library already installed"
fi

echo "[5/7] Building web application..."
if [ -d "$INSTALL_DIR/my-app" ]; then
    cd "$INSTALL_DIR/my-app"
    npm install
    npm run build
    cd "$INSTALL_DIR"
else
    echo "WARNING: my-app directory not found, skipping web build"
fi

echo "[6/7] Setting up configuration files..."
# Create default config if doesn't exist
if [ ! -f "config.ini" ]; then
    cat > config.ini << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
    echo "Created config.ini"
else
    echo "config.ini already exists"
fi

# Generate JWT secret
if [ ! -f ".env" ]; then
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > .env
    chmod 600 .env
    echo "Generated JWT secret key"
else
    echo ".env already exists"
fi

# Create image folder
mkdir -p matrix_images
echo "Created matrix_images directory"

# Make scripts executable
chmod +x start.sh stop.sh deploy.sh
echo "Made scripts executable"

echo "[7/7] Setting up systemd service..."
# Create service file with correct paths
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=LED Matrix System (Viewer + Web Server)
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/start.sh
ExecStop=$INSTALL_DIR/stop.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Set up sudoers for overlay management (passwordless)
if [ ! -f /etc/sudoers.d/led-matrix ]; then
    echo "pi ALL=(ALL) NOPASSWD: /usr/bin/raspi-config" > /etc/sudoers.d/led-matrix
    echo "pi ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/led-matrix
    chmod 440 /etc/sudoers.d/led-matrix
    echo "Created sudoers configuration"
else
    echo "sudoers configuration already exists"
fi

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "The LED Matrix system is now running!"
echo ""
echo "Access the web interface at: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "First-time setup:"
echo "  1. Open the web interface in your browser"
echo "  2. You will be prompted to set a password"
echo "  3. After setting password, you'll be logged in automatically"
echo ""
echo "Useful commands:"
echo "  - Start system:       sudo $INSTALL_DIR/start.sh"
echo "  - Stop system:        sudo $INSTALL_DIR/stop.sh"
echo "  - Service status:     sudo systemctl status $SERVICE_NAME"
echo "  - View logs:          sudo journalctl -u $SERVICE_NAME -f"
echo "  - Viewer logs:        sudo tail -f /var/log/led-matrix-viewer.log"
echo "  - Server logs:        sudo tail -f /var/log/led-matrix-server.log"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""
