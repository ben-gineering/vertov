#!/usr/bin/env bash
#
# Run PhantomX Robot Arm ROS 2 container as root
# Then fix workspace permissions from inside
#
# Use when docker group isn't available or for quick testing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

WORKSPACE_HOST="$HOME/.local/src/vertov/ros2_ws"

echo "Starting container..."
echo ""

# Allow X11 access
if command -v xhost >/dev/null 2>&1; then
    xhost +local:docker >/dev/null 2>&1 || true
fi

export DISPLAY=:0

# Start if not running
if ! sudo docker compose -f compose-robotarm.yml ps 2>/dev/null | grep -q "Up"; then
    echo "Building and starting container..."
    sudo docker compose -f compose-robotarm.yml up --build -d
    sleep 2
fi

echo "Entering container as root..."
echo ""

# Clean up old build artifacts (created by wrong user)
echo "Cleaning up old build artifacts..."
sudo rm -rf "$WORKSPACE_HOST/build" "$WORKSPACE_HOST/install" "$WORKSPACE_HOST/log"

# Enter container as ros user (no password needed with -s)
echo "Entering container..."
echo ""
sudo docker compose -f compose-robotarm.yml exec --user ros robotarm bash
