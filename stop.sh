#!/bin/bash

# LED Matrix System Stop Script

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping LED Matrix System${NC}"

STOPPED=0

# Stop viewer
if [ -f /tmp/led-matrix-viewer.pid ]; then
    VIEWER_PID=$(cat /tmp/led-matrix-viewer.pid)
    if kill -0 $VIEWER_PID 2>/dev/null; then
        kill $VIEWER_PID
        STOPPED=1
    fi
    rm -f /tmp/led-matrix-viewer.pid
fi

# Stop server
if [ -f /tmp/led-matrix-server.pid ]; then
    SERVER_PID=$(cat /tmp/led-matrix-server.pid)
    if kill -0 $SERVER_PID 2>/dev/null; then
        kill $SERVER_PID
        STOPPED=1
    fi
    rm -f /tmp/led-matrix-server.pid
fi

# Kill any remaining processes
pkill -f viewer.py && STOPPED=1
pkill -f server.py && STOPPED=1

if [ $STOPPED -eq 1 ]; then
    echo -e "${GREEN}System stopped${NC}"
else
    echo -e "${YELLOW}No running processes found${NC}"
fi
