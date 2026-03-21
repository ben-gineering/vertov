#!/bin/bash
# Wrapper script to run rpicam-vid from Docker container
# This script runs on the Pi host and is called from inside Docker

set -e

# Parse arguments from Docker call
WIDTH=${1:-1280}
HEIGHT=${2:-720}
FRAMERATE=${3:-30}
OUTPUT=${4:-/home/pi/Videos/test.mp4}
TIMEOUT=${5:-0}

# Run rpicam-vid with hardware H.264 encoding
# Using mp4 container as requested
rpicam-vid \
    --width "$WIDTH" \
    --height "$HEIGHT" \
    --framerate "$FRAMERATE" \
    --codec h264 \
    --output "$OUTPUT" \
    --timeout "$TIMEOUT"
