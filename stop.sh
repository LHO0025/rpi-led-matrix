#!/bin/bash

# LED Matrix System Stop Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Stopping LED Matrix System ===${NC}"

STOPPED_ANY=0

# Stop viewer
if [ -f /tmp/led-matrix-viewer.pid ]; then
    VIEWER_PID=$(cat /tmp/led-matrix-viewer.pid)
    if kill -0 $VIEWER_PID 2>/dev/null; then
        echo "Stopping viewer (PID: $VIEWER_PID)..."
        kill $VIEWER_PID
        STOPPED_ANY=1
    fi
    rm -f /tmp/led-matrix-viewer.pid
fi

# Stop server
if [ -f /tmp/led-matrix-server.pid ]; then
    SERVER_PID=$(cat /tmp/led-matrix-server.pid)
    if kill -0 $SERVER_PID 2>/dev/null; then
        echo "Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID
        STOPPED_ANY=1
    fi
    rm -f /tmp/led-matrix-server.pid
fi

# Kill any remaining processes
pkill -f viewer.py && STOPPED_ANY=1
pkill -f server.py && STOPPED_ANY=1

if [ $STOPPED_ANY -eq 1 ]; then
    echo -e "${GREEN}System stopped successfully${NC}"
else
    echo -e "${YELLOW}No running processes found${NC}"
fi
