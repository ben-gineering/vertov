#!/usr/bin/env bash

# Use -e and -o pipefail but avoid -u because
# ROS 2's generated setup scripts reference COLCON_TRACE
# without guaranteeing it is defined.
set -eo pipefail

# Root of the vertov repo
REPO_ROOT="/home/pi/.local/src/vertov"

cd "$REPO_ROOT/ros2_ws"

# ROS 2 environment
source install/setup.bash

# Ensure GStreamer can see the libcamera plugin we installed under /usr/local
export GST_PLUGIN_PATH="/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0:${GST_PLUGIN_PATH-}"

ros2 run vertov_video video_agent
