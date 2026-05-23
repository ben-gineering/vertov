#!/usr/bin/env bash
#
# Run PhantomX Robot Arm ROS 2 container with correct user IDs
# Matches host user to avoid permission issues with mounted volumes
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Get current user's UID and primary GID to match permissions
export USER_ID=$(id -u)
export GROUP_ID=$(id -gn)

echo "Starting container with UID=$USER_ID GID=$GROUP_ID"
echo ""

# Allow X11 access
if command -v xhost >/dev/null 2>&1; then
    xhost +local:docker >/dev/null 2>&1 || true
fi

# Export for docker compose
export DISPLAY=:0

# Start container in background if not running
if ! docker compose -f compose-robotarm.yml ps | grep -q "Up"; then
    echo "Starting container..."
    docker compose -f compose-robotarm.yml up --build -d
    sleep 2
fi

# Execute command or open shell
CMD="${@:-bash}"

docker compose -f compose-robotarm.yml exec \
    -e USER_ID="$USER_ID" \
    -e GROUP_ID="$GROUP_ID" \
    robotarm $CMD
