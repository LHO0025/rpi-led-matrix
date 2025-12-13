#!/bin/bash

# LED Matrix System Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Starting LED Matrix System ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo ./start.sh)${NC}"
    exit 1
fi

# Create config if missing
if [ ! -f "config.ini" ]; then
    cat > config.ini << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
fi

# Generate JWT secret if missing
if [ ! -f ".env" ]; then
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > .env
    chmod 600 .env
fi

# Create image folder
mkdir -p matrix_images

echo "Starting LED Matrix Viewer..."
pkill -f viewer.py || true
python3 viewer.py > /var/log/led-matrix-viewer.log 2>&1 &
VIEWER_PID=$!
sleep 2

if ! kill -0 $VIEWER_PID 2>/dev/null; then
    echo -e "${RED}Viewer failed to start${NC}"
    exit 1
fi

echo "Starting Web Server..."
pkill -f server.py || true
python3 server.py > /var/log/led-matrix-server.log 2>&1 &
SERVER_PID=$!
sleep 2

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}Server failed to start${NC}"
    kill $VIEWER_PID 2>/dev/null || true
    exit 1
fi

echo $VIEWER_PID > /tmp/led-matrix-viewer.pid
echo $SERVER_PID > /tmp/led-matrix-server.pid

echo ""
echo -e "${GREEN}System Started${NC}"
echo "Viewer PID: $VIEWER_PID"
echo "Server PID: $SERVER_PID"
echo "Web: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
