# vertov Quickstart

Minimal steps to trigger a recording on a Raspberry Pi 5 video agent from an Arch Linux control node using the current MVP.

## 1. On the Raspberry Pi (video agent)

Prerequisites:
- Repo cloned at `/home/pi/.local/src/vertov`
- ROS2 Jazzy installed

```bash
# ROS 2 environment
source /opt/ros/jazzy/setup.bash

# DDS config (if not already in your shell startup file)
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
export CYCLONEDDS_URI=file:///home/pi/.local/src/vertov/cyclonedds.xml

# Run the video agent (includes GStreamer/libcamera setup)
/home/pi/.local/src/vertov/scripts/run_video_agent.sh
```

Leave this terminal running. You should see logs from the `video_agent` node.

## 2. On the Arch Linux control node (Docker + ROS2)

From the repo root on the Arch machine:

```bash
cd /home/bn/.local/src/vertov

# Start a ROS 2-enabled shell in the dev container
docker compose -f docker/compose.yml run --rm ros2-dev bash
```

Inside the container shell:

```bash
cd /workspace/vertov

# Optional: verify the Pi node is visible
ros2 node list
ros2 service list | grep recording
```

## 3. Start and stop recording

From the container shell, call the services exposed by the Pi video agent:

```bash
# Start recording
ros2 service call /start_recording std_srvs/srv/Trigger "{}"

# Stop recording
ros2 service call /stop_recording std_srvs/srv/Trigger "{}"
```

Recordings are saved on the Pi under:

```bash
/home/pi/Videos/<ISO_timestamp>_cam01.mp4
```
