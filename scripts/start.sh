#!/bin/bash

# LED Matrix System Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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
if [ ! -f "$PROJECT_ROOT/config.ini" ]; then
    cat > "$PROJECT_ROOT/config.ini" << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
fi

# Generate JWT secret if missing
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > "$PROJECT_ROOT/.env"
    chmod 600 "$PROJECT_ROOT/.env"
fi

# Create image folder
mkdir -p "$PROJECT_ROOT/matrix_images"

echo "Starting LED Matrix Viewer..."
pkill -f "python3.*viewer.py" || true
python3 "$PROJECT_ROOT/backend/viewer.py" > /var/log/led-matrix-viewer.log 2>&1 &
VIEWER_PID=$!
echo $VIEWER_PID > /tmp/led-matrix-viewer.pid
sleep 2

if ! kill -0 $VIEWER_PID 2>/dev/null; then
    echo -e "${RED}Viewer failed to start${NC}"
    rm -f /tmp/led-matrix-viewer.pid
    exit 1
fi

echo "Starting Web Server..."
pkill -f "python3.*server.py" || true
python3 "$PROJECT_ROOT/backend/server.py" > /var/log/led-matrix-server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > /tmp/led-matrix-server.pid
sleep 2

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}Server failed to start${NC}"
    rm -f /tmp/led-matrix-server.pid
    kill $VIEWER_PID 2>/dev/null || true
    rm -f /tmp/led-matrix-viewer.pid
    exit 1
fi

echo ""
echo -e "${GREEN}System Started${NC}"
echo "Viewer PID: $VIEWER_PID"
echo "Server PID: $SERVER_PID"
echo "Web: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
