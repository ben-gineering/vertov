#!/bin/bash
set -e

source /opt/ros/jazzy/setup.bash

if [ -f "/workspace/vertov/ros2_ws/install/setup.bash" ]; then
    source /workspace/vertov/ros2_ws/install/setup.bash
fi

exec "$@"