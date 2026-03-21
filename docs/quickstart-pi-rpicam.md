# vertov Quickstart - Pi with rpicam-apps (Host) + ROS2 (Docker)

This guide shows how to run rpicam-apps natively on Raspberry Pi while running ROS2 in a Docker container.

## Architecture

- **Host (Pi)**: rpicam-apps for camera control, MP4 recording
- **Docker Container**: ROS2 Jazzy for orchestration and service calls
- **Communication**: ROS2 services over host network

## 1. Prerequisites on Pi

```bash
# Verify rpicam-apps is installed
rpicam-hello --list-cameras

# Should show your camera. If not, check CSI cable connection
```

## 2. Start the rpicam Agent on Pi (Host)

```bash
# ROS 2 environment (for running the agent initially - will move to Docker)
source /opt/ros/jazzy/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
export CYCLONEDDS_URI=file:///home/pi/.local/src/vertov/docker/cyclonedds_pc.xml

# Build the workspace
cd /home/pi/.local/src/vertov/ros2_ws
colcon build --packages-select vertov_video
source install/setup.bash

# Run the rpicam agent
/home/pi/.local/src/vertov/scripts/run_rpicam_agent.sh
```

Leave this terminal running. You should see logs from `rpicam_agent`.

## 3. Start the Docker Container (on Pi or Arch Control Node)

```bash
cd /home/pi/.local/src/vertov

# Build the container
docker compose -f docker/compose-pi.yml build

# Run the container
docker compose -f docker/compose-pi.yml run --rm vertov-pi bash
```

Inside the container:

```bash
cd /workspace/vertov/ros2_ws

# Build (if not already built on host)
colcon build --packages-select vertov_video
source install/setup.bash

# Verify the Pi agent is visible
ros2 node list
ros2 service list | grep recording
```

## 4. Start and Stop Recording

From the Docker container:

```bash
# Start recording (720p@30fps to MP4)
ros2 service call /start_recording std_srvs/srv/Trigger "{}"

# Stop recording
ros2 service call /stop_recording std_srvs/srv/Trigger "{}"
```

Recordings are saved on the Pi host at:

```bash
/home/pi/Videos/<ISO_timestamp>_cam01.mp4
```

## Configuration

Environment variables for the rpicam agent:

- `CAMERA_ID`: Camera identifier (default: `cam01`)
- `RECORDING_DIR`: Output directory (default: `/home/pi/Videos`)
- `RESOLUTION`: Video resolution (default: `1280x720`)
- `FRAMERATE`: Frames per second (default: `30`)

Example with custom settings:

```bash
export CAMERA_ID=pi3_cam1
export RESOLUTION=1280x720
export FRAMERATE=30
/home/pi/.local/src/vertov/scripts/run_rpicam_agent.sh
```

## Testing Camera Directly

Before using ROS2, test rpicam-vid directly:

```bash
# Test 5 second recording at 720p30
rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec h264 -o test.h264

# For MP4 container (requires clean shutdown)
rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec mp4 -o test.mp4

# Verify the file
ffprobe test.mp4
```

## Troubleshooting

### Camera not detected

```bash
# Check config.txt has camera detection enabled
cat /boot/firmware/config.txt | grep camera

# Should show: camera_auto_detect=1

# Reboot if you changed config.txt
sudo reboot

# After reboot, verify
rpicam-hello --list-cameras
```

### ROS2 nodes not discovering each other

- Ensure both container and host use same `ROS_DOMAIN_ID`
- Check `network_mode: host` in compose file
- Verify CycloneDDS config matches

### Recording file issues

```bash
# Check file was created
ls -lh /home/pi/Videos/

# Verify codec/container
ffprobe /home/pi/Videos/*.mp4
```
