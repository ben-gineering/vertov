# vertov Quickstart - Pi with rpicam-apps (Host) + ROS2 (Docker)

This guide shows how to run rpicam-apps natively on Raspberry Pi while running ROS2 in a Docker container.

## Architecture

- **Host (Pi)**: rpicam-apps for camera control, MP4 recording
- **Host (Pi)**: `rpicam-httpd` Flask service that starts/stops `rpicam-vid`
- **Docker Container**: ROS2 Jazzy for orchestration and service calls
- **Communication**: ROS2 services in the container call the host over HTTP

## 1. Prerequisites on Pi

```bash
# Verify rpicam-apps is installed
rpicam-hello --list-cameras

# Should show your camera. If not, check CSI cable connection

# Install Python + Flask for the HTTP daemon
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install --user flask
```

## 2. Start the rpicam HTTP Daemon on Pi (Host)

This daemon exposes `/recordings/start`, `/recordings/stop`, and `/recordings/status` on `http://127.0.0.1:8080` and starts `rpicam-vid` on the host.

```bash
cd /home/pi/.local/src/vertov

export RPICAM_RECORDING_DIR=/home/pi/Videos
export RPICAM_PORT=8080
export RPICAM_DEFAULT_WIDTH=1280
export RPICAM_DEFAULT_HEIGHT=720
export RPICAM_DEFAULT_FRAMERATE=30
export CAMERA_ID=cam01

python3 scripts/rpicam_httpd.py
```

Leave this terminal running. In another terminal you can test it directly:

```bash
curl -X POST http://127.0.0.1:8080/recordings/start \
  -H 'Content-Type: application/json' \
  -d '{"width":1280,"height":720,"framerate":30}'

sleep 5

curl -X POST http://127.0.0.1:8080/recordings/stop \
  -H 'Content-Type: application/json' \
  -d '{}'

curl http://127.0.0.1:8080/recordings/status
```

### Optional: Run rpicam-httpd as a systemd service

A unit file is provided at `systemd/rpicam-httpd.service`. To install it on the Pi:

```bash
sudo cp /home/pi/.local/src/vertov/systemd/rpicam-httpd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rpicam-httpd.service

sudo systemctl status rpicam-httpd.service
```

This will start the HTTP daemon automatically on boot.

## 3. Start the Docker Container on Pi

```bash
cd /home/pi/.local/src/vertov

# Build the container
docker compose -f docker/compose-pi.yml build

# Run the container
docker compose -f docker/compose-pi.yml run --rm vertov-pi bash
```

`docker/compose-pi.yml` uses `network_mode: host` so the container can reach `http://127.0.0.1:8080` on the Pi.

Inside the container:

```bash
cd /workspace/vertov/ros2_ws

# Build vertov_video if needed
colcon build --packages-select vertov_video
source install/setup.bash

# Verify the rpicam_agent node is available after you start it
ros2 run vertov_video rpicam_agent
```

In another shell inside the same container you can check:

```bash
ros2 node list
ros2 service list | grep recording
```

## 4. Start and Stop Recording via ROS2

With `rpicam_httpd` running on the host and `rpicam_agent` running in the container:

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

If you bind-mount the directory in `docker/compose-pi.yml` as:

```yaml
volumes:
  - /home/pi/Videos:/recordings
```

then the same files will be visible inside the container under `/recordings`.

## 5. Configuration

Environment variables for the host HTTP daemon (`rpicam_httpd.py`):

- `RPICAM_RECORDING_DIR`: Output directory (default: `/home/pi/Videos`)
- `RPICAM_PORT`: HTTP port (default: `8080`)
- `RPICAM_DEFAULT_WIDTH`: Default width (default: `1280`)
- `RPICAM_DEFAULT_HEIGHT`: Default height (default: `720`)
- `RPICAM_DEFAULT_FRAMERATE`: Default FPS (default: `30`)
- `CAMERA_ID`: Camera identifier (default: `cam01`)

Environment variables for the ROS2 agent in the container (`rpicam_agent.py`):

- `CAMERA_ID`: Camera identifier (default: `cam01`)
- `RECORDING_DIR`: Output directory as seen from the container (e.g. `/recordings`)
- `RESOLUTION`: Video resolution (default: `1280x720`)
- `FRAMERATE`: Frames per second (default: `30`)
- `RPICAM_CONTROL_URL`: HTTP base URL for the host daemon (default: `http://127.0.0.1:8080`)

Example Docker environment snippet:

```yaml
environment:
  - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  - ROS_DOMAIN_ID=0
  - CYCLONEDDS_URI=file:///workspace/vertov/docker/cyclonedds_pc.xml
  - CAMERA_ID=cam01
  - RECORDING_DIR=/recordings
  - RESOLUTION=1280x720
  - FRAMERATE=30
  - RPICAM_CONTROL_URL=http://127.0.0.1:8080
```

## 6. Testing Camera Directly

Before using ROS2, test rpicam-vid directly on the host:

```bash
# Test 5 second recording at 720p30
rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec h264 -o test.h264

# For MP4 container (requires clean shutdown)
rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec mp4 -o test.mp4

# Verify the file
ffprobe test.mp4
```

## 7. Troubleshooting

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
