#!/bin/bash
# Test 1024x768 resolution

export GST_PLUGIN_PATH=/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0

OUTPUT="/home/pi/Videos/test-1024.mp4"
echo "Testing 1024x768@30fps -> $OUTPUT"

timeout 2s gst-launch-1.0 libcamerasrc ! \
    "video/x-raw,format=RGB,width=1024,height=768,framerate=30/1" ! \
    videoconvert ! \
    x264enc tune=zerolatency speed-preset=ultrafast bitrate=4000 ! \
    h264parse ! \
    mp4mux ! \
    filesink location="$OUTPUT"

echo "Done. Checking output..."
ls -lh "$OUTPUT"
ffprobe "$OUTPUT" 2>&1 | grep -E 'Stream|Duration|Video'