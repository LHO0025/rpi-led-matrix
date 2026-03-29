#!/bin/bash

# LED Matrix System Stop Script

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping LED Matrix System${NC}"

STOPPED=0

# Helper: stop a process by PID file with graceful timeout
stop_by_pid() {
    local pid_file="$1"
    local name="$2"

    if [ ! -f "$pid_file" ]; then
        return 1
    fi

    local pid
    pid=$(cat "$pid_file")
    rm -f "$pid_file"

    if ! kill -0 "$pid" 2>/dev/null; then
        return 1
    fi

    echo "Stopping $name (PID $pid)..."
    kill -TERM "$pid" 2>/dev/null

    # Wait up to 5 seconds for graceful shutdown
    for i in {1..10}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        sleep 0.5
    done

    # Force kill if still running
    echo "Force-killing $name (PID $pid)..."
    kill -KILL "$pid" 2>/dev/null
    return 0
}

# Stop viewer
if stop_by_pid /tmp/led-matrix-viewer.pid "viewer"; then
    STOPPED=1
fi

# Stop server
if stop_by_pid /tmp/led-matrix-server.pid "server"; then
    STOPPED=1
fi

# Kill any remaining processes by name
pkill -f "python3.*viewer.py" 2>/dev/null && STOPPED=1
pkill -f "python3.*server.py" 2>/dev/null && STOPPED=1

# Clean up socket
rm -f /tmp/ledctl.sock

if [ $STOPPED -eq 1 ]; then
    echo -e "${GREEN}System stopped${NC}"
else
    echo -e "${YELLOW}No running processes found${NC}"
fi
