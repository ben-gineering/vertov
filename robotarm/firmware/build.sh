#!/bin/bash
# PhantomX Reactor - Build & Upload Script
# Usage: ./build.sh [sketch_dir] [port] [upload]
#
# Examples:
#   ./build.sh                          # Compile reactor_test
#   ./build.sh reactor_test             # Compile specific sketch
#   ./build.sh reactor_test /dev/ttyUSB0 upload  # Compile and upload

set -e

SKETCH_DIR="${1:-./reactor_test}"
PORT="${2:-/dev/ttyUSB0}"
DO_UPLOAD="${3:-}"
BOARD="arbotix:avr:arbotix"

echo "======================================"
echo "PhantomX Reactor - Build Script"
echo "======================================"
echo "Sketch: $SKETCH_DIR"
echo "Board:  $BOARD"
echo "Port:   $PORT"
echo "======================================"

# Compile
echo ""
echo "[1/2] Compiling..."
arduino-cli compile -b "$BOARD" "$SKETCH_DIR"

# Upload (if requested)
if [[ "$DO_UPLOAD" == "upload" ]] || [[ "${UPLOAD:-}" == "1" ]]; then
    echo ""
    echo "[2/2] Uploading to $PORT..."
    arduino-cli upload -p "$PORT" -b "$BOARD" "$SKETCH_DIR"
    echo ""
    echo "✓ Upload complete!"
    echo ""
    echo "Connect with:"
    echo "  picocom -b 115200 $PORT"
    echo ""
    echo "Or use: screen $PORT 115200"
fi
