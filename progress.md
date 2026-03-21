# Progress Summary

## Goal

Set up a Raspberry Pi 3+ with Raspberry Pi OS to run the vertov distributed camera system, where:
- **rpicam-apps** runs natively on the Pi host (for reliable camera hardware access)
- **ROS2 Jazzy** runs in a Docker container (since ROS2 is not natively installed on Pi OS)
- Camera records to **MP4 at 720p@30fps**
- The system should allow triggering recordings via ROS2 services from the Docker container

## Instructions

- Use **Option A architecture**: rpicam-apps on host, ROS2 in Docker container
- **HTTP bridge approach** for IPC: Flask server on host, ROS2 node makes HTTP calls from container
- Recording format: **MP4 container** with H.264 codec
- Resolution: **720p@30fps** for initial tests (1280x720)
- Do NOT modify `/boot/firmware/config.txt` - use `camera_auto_detect=1` setting
- Camera is **HQ Camera Module (imx477)** connected via CSI interface
- Pi 3+ hardware (not Pi 5)
- Use `network_mode: host` in Docker compose so container can reach `http://127.0.0.1:8080`

## Discoveries

1. **Camera detection**: The HQ Camera works with `camera_auto_detect=1` in config.txt. Avoid specific dtoverlays like `imx219`.

2. **Architecture decision**: HTTP bridge (Flask) was chosen over ROS2 pip on host or native ROS2 install. This provides clean separation between ROS2 orchestration and camera control.

3. **HTTP daemon test passed**: Successfully tested rpicam_httpd.py in isolation:
   - All endpoints respond correctly (start, stop, status)
   - 6-second test recording created valid 3.6MB MP4 file
   - Camera runs stable at 30fps
   - HQ Camera (imx477) auto-configured correctly by libcamera

4. **Python version**: Pi runs Python 3.13.5, Flask 3.1.1 already installed

5. **Minor fix applied**: Changed `datetime.utcnow()` to `datetime.now()` to fix deprecation warning

6. **Docker connectivity verified**: Container with `network_mode: host` can reach HTTP daemon on host at `127.0.0.1:8080`

7. **Package import fix**: Removed unconditional `video_agent` import from `__init__.py` to prevent GStreamer dependency requirement for `rpicam_agent` (which only uses HTTP)

## Accomplished

### Completed:
- ✅ Created `scripts/rpicam_httpd.py` - Flask server controlling rpicam-vid on host
- ✅ Updated `vertov_video/rpicam_agent.py` - ROS2 node that calls HTTP endpoints
- ✅ Created `systemd/rpicam-httpd.service` - systemd unit for auto-start on boot
- ✅ Created `docker/Dockerfile.vertov-pi` - ROS2 Jazzy with requests pip package
- ✅ Created `docker/compose-pi.yml` - Docker compose with host network, volume mounts
- ✅ Created `docker/entrypoint-pi.sh` - Container entrypoint script
- ✅ Updated `docs/quickstart-pi-rpicam.md` - Comprehensive documentation
- ✅ Created `scripts/run_rpicam_agent.sh` - Launch script for rpicam agent
- ✅ Updated `setup.py` - Added rpicam_agent entry point
- ✅ Created `progress.md` - Progress summary (committed to git)
- ✅ **HTTP daemon tested successfully** - End-to-end recording via curl works
- ✅ **Docker container built** - ROS2 Jazzy base with requests package
- ✅ **Container → host connectivity verified** - HTTP calls from container work
- ✅ **Fixed package imports** - Removed GStreamer dependency from rpicam_agent

### In Progress:
- ⏳ **ROS2 + Docker integration test** - HTTP daemon works, container built, need to test full ROS2 service flow

### Remaining Work:
- ❌ Start rpicam-httpd as systemd service (or run in background)
- ❌ Rebuild container after import fix and start fresh
- ❌ Source ROS2 workspace and start rpicam_agent node from container
- ❌ Test `/start_recording` and `/stop_recording` ROS2 services
- ❌ Verify recordings appear in `/home/pi/Videos/`
- ❌ Consider production hardening (WSGI server, error handling, logging)

## Relevant Files / Directories

### Configuration Files:
- `/boot/firmware/config.txt` - Pi boot config (reverted to camera_auto_detect=1, needs reboot)
- `/home/pi/.local/src/vertov/docker/compose-pi.yml` - Docker compose for Pi setup
- `/home/pi/.local/src/vertov/docker/Dockerfile.vertov-pi` - Docker image for Pi
- `/home/pi/.local/src/vertov/docker/entrypoint-pi.sh` - Container entrypoint
- `/home/pi/.local/src/vertov/docker/cyclonedds_pc.xml` - DDS configuration

### Source Code:
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/vertov_video/rpicam_agent.py` - ROS2 agent node (needs IPC fix)
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/vertov_video/video_agent.py` - Original GStreamer agent
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/setup.py` - Package setup (updated with rpicam_agent entry point)
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/srv/StartRecording.srv` - Service definition

### Scripts:
- `/home/pi/.local/src/vertov/scripts/run_rpicam_agent.sh` - Launch rpicam agent
- `/home/pi/.local/src/vertov/scripts/run_video_agent.sh` - Original GStreamer agent launcher
- `/home/pi/.local/src/vertov/scripts/rpicam_vid_wrapper.sh` - Wrapper for calling rpicam-vid

### Documentation:
- `/home/pi/.local/src/vertov/docs/quickstart-pi-rpicam.md` - Quickstart guide for Pi + rpicam setup
- `/home/pi/.local/src/vertov/PRD.md` - Product requirements (full system specs)
- `/home/pi/.local/src/vertov/docs/raspi-setup.md` - Original Ubuntu Pi setup guide
