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

INSTALL_DIR="/home/pi/rpi-led-matrix"
SERVICE_NAME="led-matrix-system"

echo "[3/7] Creating Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

echo "[4/7] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install RGB Matrix library if not already installed
if ! python3 -c "import rgbmatrix" 2>/dev/null; then
    echo "Installing RGB Matrix Python library..."
    cd /tmp
    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git || true
    cd rpi-rgb-led-matrix/bindings/python
    make build-python PYTHON=$(which python3)
    make install-python PYTHON=$(which python3)
    cd "$INSTALL_DIR"
fi

echo "[5/7] Building web application..."
cd "$INSTALL_DIR/my-app"
npm install
npm run build
cd "$INSTALL_DIR"

echo "[6/7] Setting up configuration files..."
# Create default config if doesn't exist
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

echo "[7/7] Setting up systemd service..."
# Update service file paths
sed -i "s|/home/pi/rpi-led-matrix|$INSTALL_DIR|g" led-matrix-server.service

# Copy service file
cp led-matrix-server.service /etc/systemd/system/$SERVICE_NAME.service

# Set up sudoers for overlay management (passwordless)
echo "pi ALL=(ALL) NOPASSWD: /usr/bin/raspi-config" > /etc/sudoers.d/led-matrix
echo "pi ALL=(ALL) NOPASSWD: /sbin/reboot" >> /etc/sudoers.d/led-matrix
chmod 440 /etc/sudoers.d/led-matrix

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
echo "  - Start system:       sudo ./start.sh"
echo "  - Stop system:        sudo ./stop.sh"
echo "  - Service status:     sudo systemctl status $SERVICE_NAME"
echo "  - View logs:          sudo journalctl -u $SERVICE_NAME -f"
echo "  - Viewer logs:        sudo tail -f /var/log/led-matrix-viewer.log"
echo "  - Server logs:        sudo tail -f /var/log/led-matrix-server.log"
echo ""
