#!/usr/bin/env bash
#
# Run PhantomX Robot Arm ROS 2 container with RViz (X11 display)
# For Arch Linux with Sway/Wayland (uses XWayland)
#
# Usage:
#   ./run_robotarm_rviz.sh                    # Interactive shell
#   ./run_robotarm_rviz.sh "rviz2"            # Launch RViz directly
#   ./run_robotarm_rviz.sh "bash -c '...'"    # Run custom command
#
# Prerequisites:
#   - Docker installed and running
#   - xorg-xhost installed on host: sudo pacman -S xorg-xhost
#   - XWayland enabled (default in Sway)
#

set -e

# === Configuration ===
IMAGE="phantomx_robotarm:humble"
CONTAINER_NAME="phantomx_robotarm"
WORKSPACE_HOST="$HOME/.local/src/vertov/ros2_ws"
WORKSPACE_CONTAINER="/home/ros/ros2_ws"

# === X11 Setup ===
export DISPLAY=:0

# Allow Docker container to connect to X server
echo "Setting up X11 access..."
if command -v xhost >/dev/null 2>&1; then
    xhost +local:docker >/dev/null 2>&1 && echo "✓ X11 access granted for docker" || \
        echo "⚠ Could not set xhost (may still work)"
else
    echo "⚠ xhost not found. Install with: sudo pacman -S xorg-xhost"
fi
echo ""

# === Check if image exists ===
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building Docker image: $IMAGE"
    echo "This may take a few minutes on first run..."
    echo ""
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    docker build \
        -f "$SCRIPT_DIR/Dockerfile.robotarm" \
        -t "$IMAGE" \
        "$SCRIPT_DIR/.."
    echo ""
    echo "✓ Image built successfully"
    echo ""
fi

# === Remove existing container if present ===
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

# === Command ===
CMD="${@:-bash}"

# === Run container ===
echo "╔════════════════════════════════════════════════════════╗"
echo "║  PhantomX Robot Arm - ROS 2 Humble Container          ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  Display: $DISPLAY"
echo "║  Workspace: $WORKSPACE_HOST"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Run with proper option ordering (image must come before options in some Docker versions)
docker run \
    --rm \
    --name "$CONTAINER_NAME" \
    --network host \
    --privileged \
    -v "$WORKSPACE_HOST:$WORKSPACE_CONTAINER" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -e DISPLAY="$DISPLAY" \
    -e QT_X11_NO_MITSHM=1 \
    -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
    "$IMAGE" \
    $CMD
