#!/usr/bin/env bash

set -euo pipefail

# IP address or hostname of the Pi running the video agent
PI_HOST="192.168.1.50"

# Source directory on the Pi to copy from (e.g. recording folder)
PI_SOURCE_DIR="/home/pi/Videos"

# Destination directory on the local desktop machine
LOCAL_DEST_DIR="$HOME/vertov-import/pi-videos"

mkdir -p "$LOCAL_DEST_DIR"

echo "Copying from ${PI_HOST}:${PI_SOURCE_DIR} to ${LOCAL_DEST_DIR}..."

rsync -av --progress "${PI_HOST}:${PI_SOURCE_DIR}/" "$LOCAL_DEST_DIR/"

echo "Done."
