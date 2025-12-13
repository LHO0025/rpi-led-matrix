#!/bin/bash

# LED Matrix System Startup Script
# This script starts both the viewer and the web server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== LED Matrix System Startup ===${NC}"

# Check if running as root (required for viewer to access GPIO)
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (sudo ./start.sh)${NC}"
    exit 1
fi

# Find the actual user (when using sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo "[1/4] Checking Python environment..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    sudo -u $ACTUAL_USER python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "[2/4] Checking configuration..."

# Create config file if it doesn't exist
if [ ! -f "config.ini" ]; then
    echo -e "${YELLOW}Creating default config.ini...${NC}"
    cat > config.ini << EOF
[display]
brightness = 75
hold_seconds = 20
EOF
fi

# Create matrix_images directory if it doesn't exist
mkdir -p matrix_images

# Generate JWT secret key if not exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Generating JWT secret key...${NC}"
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" > .env
    chmod 600 .env
fi

echo "[3/4] Starting LED Matrix Viewer..."

# Kill any existing viewer processes
pkill -f viewer.py || true

# Start viewer in background
python3 viewer.py > /var/log/led-matrix-viewer.log 2>&1 &
VIEWER_PID=$!
echo "Viewer started (PID: $VIEWER_PID)"

# Wait a moment for viewer to initialize
sleep 2

# Check if viewer is still running
if ! kill -0 $VIEWER_PID 2>/dev/null; then
    echo -e "${RED}Error: Viewer failed to start. Check /var/log/led-matrix-viewer.log${NC}"
    exit 1
fi

echo "[4/4] Starting Web Server..."

# Kill any existing server processes
pkill -f server.py || true

# Start server in background
python3 server.py > /var/log/led-matrix-server.log 2>&1 &
SERVER_PID=$!
echo "Server started (PID: $SERVER_PID)"

# Wait a moment for server to initialize
sleep 2

# Check if server is still running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${RED}Error: Server failed to start. Check /var/log/led-matrix-server.log${NC}"
    kill $VIEWER_PID 2>/dev/null || true
    exit 1
fi

# Save PIDs for stop script
echo $VIEWER_PID > /tmp/led-matrix-viewer.pid
echo $SERVER_PID > /tmp/led-matrix-server.pid

echo ""
echo -e "${GREEN}=== System Started Successfully ===${NC}"
echo ""
echo "Services running:"
echo "  - LED Viewer (PID: $VIEWER_PID)"
echo "  - Web Server (PID: $SERVER_PID)"
echo ""
echo "Access the web interface at: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Logs:"
echo "  - Viewer: /var/log/led-matrix-viewer.log"
echo "  - Server: /var/log/led-matrix-server.log"
echo ""
echo "To stop the system, run: sudo ./stop.sh"
echo "To view logs: sudo tail -f /var/log/led-matrix-*.log"
echo ""
