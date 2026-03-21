# Progress Summary

## Goal

Set up a Raspberry Pi 3+ with Raspberry Pi OS to run the vertov distributed camera system, where:
- **rpicam-apps** runs natively on the Pi host (for reliable camera hardware access)
- **ROS2 Jazzy** runs in a Docker container (since ROS2 is not natively installed on Pi OS)
- Camera records to **MP4 at 720p@30fps**
- The system should allow triggering recordings via ROS2 services from the Docker container

## Instructions

- Use **Option A architecture**: rpicam-apps on host, ROS2 in Docker container
- Recording format: **MP4 container** (user switched from H.264 due to previous issues, but still wants MP4)
- Resolution: **720p@30fps** for initial tests
- Do NOT modify `/boot/firmware/config.txt` further - the original `camera_auto_detect=1` setting worked before
- Camera is **HQ Camera Module connected via CSI** interface
- Pi 3+ hardware (not Pi 5)
- User clarified: ROS2 is NOT installed natively on Pi OS (that's the whole reason for Docker)

## Discoveries

1. **Camera detection issue**: The `dtoverlay=imx219` overlay was incorrect for the HQ Camera. The original `camera_auto_detect=1` setting worked before the reboot. Need to keep that setting.

2. **Architecture challenge**: Docker containers cannot directly execute host binaries. Need an IPC mechanism between Docker (ROS2) and host (rpicam-vid).

3. **Three possible approaches identified**:
   - **Approach 1**: ROS2 Python pip package on host + rpicam-vid (may have compatibility issues)
   - **Approach 2**: HTTP bridge (Flask/FastAPI on host, HTTP calls from Docker)
   - **Approach 3**: Install ROS2 Jazzy natively on Pi OS (actually supported on Debian Bookworm base)

4. **Current state**: Camera config was reverted but Pi hasn't been rebooted yet to restore camera detection.

## Accomplished

### Completed:
- ✅ Updated `/boot/firmware/config.txt` (reverted to `camera_auto_detect=1`)
- ✅ Created `docker/Dockerfile.vertov-pi` - ROS2 Jazzy base with Python pip support
- ✅ Created `docker/compose-pi.yml` - Docker compose with host network, privileged mode, volume mounts
- ✅ Created `docker/entrypoint-pi.sh` - Entrypoint script for Pi container
- ✅ Created `vertov_video/rpicam_agent.py` - ROS2 node that wraps rpicam-vid (needs architecture fix)
- ✅ Created `scripts/run_rpicam_agent.sh` - Launch script for rpicam agent
- ✅ Created `scripts/rpicam_vid_wrapper.sh` - Wrapper to call rpicam-vid from container
- ✅ Updated `setup.py` to include rpicam_agent entry point
- ✅ Created `docs/quickstart-pi-rpicam.md` - Documentation for the Pi + rpicam setup

### In Progress:
- ⏳ **Architecture decision pending**: Need to choose between HTTP bridge, ROS2 pip on host, or native ROS2 install
- ⏳ **Camera not detection**: Pi needs reboot to restore camera detection after config revert

### Remaining Work:
- ❌ Decide and implement IPC mechanism between Docker and host
- ❌ Reboot Pi and verify camera detection works
- ❌ Test rpicam-vid directly: `rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec mp4 -o test.mp4`
- ❌ Build and test the Docker container
- ❌ Test end-to-end recording trigger from Docker container

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
