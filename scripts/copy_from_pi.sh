#!/usr/bin/env bash

set -euo pipefail

# IP address or hostname of the Pi running the video agent
PI_HOST="10.0.0.187"

# SSH user on the Pi
PI_USER="pi"

# Source directory on the Pi to copy from (e.g. recording folder)
PI_SOURCE_DIR="/home/pi/Videos"

# Destination directory on the local desktop machine
LOCAL_DEST_DIR="tmp/pi-videos"

mkdir -p "$LOCAL_DEST_DIR"

echo "Copying from ${PI_USER}@${PI_HOST}:${PI_SOURCE_DIR} to ${LOCAL_DEST_DIR}..."

rsync -av --progress "${PI_USER}@${PI_HOST}:${PI_SOURCE_DIR}/" "$LOCAL_DEST_DIR/"

echo "Done."
