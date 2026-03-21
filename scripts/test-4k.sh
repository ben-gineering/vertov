#!/bin/bash
# Test 3840x2160 (4K) resolution at 15fps

export GST_PLUGIN_PATH=/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0

OUTPUT="/home/pi/Videos/test-4k.mp4"
echo "Testing 3840x2160@15fps -> $OUTPUT"

timeout 2s gst-launch-1.0 libcamerasrc ! \
    "video/x-raw,format=RGB,width=3840,height=2160,framerate=15/1" ! \
    videoconvert ! \
    x264enc tune=zerolatency speed-preset=ultrafast bitrate=8000 ! \
    h264parse ! \
    mp4mux ! \
    filesink location="$OUTPUT"

echo "Done. Checking output..."
ls -lh "$OUTPUT"
ffprobe "$OUTPUT" 2>&1 | grep -E 'Stream|Duration|Video'