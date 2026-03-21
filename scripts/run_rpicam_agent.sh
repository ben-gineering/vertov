#!/usr/bin/env bash

set -eo pipefail

REPO_ROOT="/home/pi/.local/src/vertov"

cd "$REPO_ROOT/ros2_ws"

source install/setup.bash

ros2 run vertov_video rpicam_agent
