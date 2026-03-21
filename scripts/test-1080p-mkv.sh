#!/bin/bash
# Test 1920x1080 (1080p) resolution at 30fps, recording to MKV

export GST_PLUGIN_PATH=/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0

OUTPUT="/home/pi/Videos/test-1080p.mkv"
echo "Testing 1920x1080@30fps -> $OUTPUT (MKV)"

timeout 2s gst-launch-1.0 libcamerasrc ! \
    "video/x-raw,format=RGB,width=1920,height=1080,framerate=30/1" ! \
    videoconvert ! \
    x264enc tune=zerolatency speed-preset=ultrafast bitrate=4000 ! \
    h264parse ! \
    matroskamux ! \
    filesink location="$OUTPUT"

echo "Done. Checking output..."
ls -lh "$OUTPUT" 2>/dev/null || echo "No output file created"
ffprobe "$OUTPUT" 2>&1 | grep -E 'Stream|Duration|Video' || echo "ffprobe failed or file not valid"
