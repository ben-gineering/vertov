#!/usr/bin/env bash
#
# Run PhantomX Robot Arm ROS 2 container
# Cleans up old build artifacts and enters as ros user
#
# Use when docker group isn't available or for quick testing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

WORKSPACE_HOST="$HOME/.local/src/vertov/ros2_ws"

# Clean up old build artifacts from host side (before starting container)
echo "Cleaning up old build artifacts..."
sudo rm -rf "$WORKSPACE_HOST/build" "$WORKSPACE_HOST/install" "$WORKSPACE_HOST/log"
echo ""

echo "Starting container..."
echo ""

# Allow X11 access
if command -v xhost >/dev/null 2>&1; then
    xhost +local:docker >/dev/null 2>&1 || true
fi

export DISPLAY=:0

# Stop any existing container to ensure fresh start
sudo docker compose -f compose-robotarm.yml down 2>/dev/null || true

# Start container
echo "Building and starting container..."
sudo docker compose -f compose-robotarm.yml up --build -d
sleep 2

# Enter container as ros user
echo "Entering container..."
echo ""
sudo docker compose -f compose-robotarm.yml exec --user ros robotarm bash
