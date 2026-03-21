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

3. **IPC solution chosen**: Implemented an HTTP bridge (`rpicam-httpd`) running on the Pi host using Flask. ROS2 in Docker talks to it via HTTP.

4. **Current state**: Pi has been rebooted, camera detection works, and the HTTP bridge plus ROS2 agent are wired together conceptually. End-to-end tests are next.

## Accomplished

### Completed:
- ✅ Updated `/boot/firmware/config.txt` (reverted to `camera_auto_detect=1`) and rebooted Pi to restore camera detection
- ✅ Created `docker/Dockerfile.vertov-pi` - ROS2 Jazzy base with Python pip support (now includes `requests`)
- ✅ Created `docker/compose-pi.yml` - Docker compose with host network, privileged mode, volume mounts
- ✅ Created `docker/entrypoint-pi.sh` - Entrypoint script for Pi container
- ✅ Created initial `vertov_video/rpicam_agent.py` - ROS2 node for rpicam-vid control
- ✅ Implemented HTTP-based RPICam agent: `vertov_video/rpicam_agent.py` now calls a host HTTP service instead of spawning `rpicam-vid` directly
- ✅ Created `scripts/run_rpicam_agent.sh` - Launch script for rpicam agent (legacy, replaced by HTTP bridge in Docker)
- ✅ Created `scripts/rpicam_vid_wrapper.sh` - Wrapper to call rpicam-vid from container (legacy, not used with HTTP bridge)
- ✅ Created `scripts/rpicam_httpd.py` - Flask-based HTTP daemon on host that starts/stops `rpicam-vid`
- ✅ Added `systemd/rpicam-httpd.service` - systemd unit to run HTTP daemon on boot
- ✅ Updated `setup.py` to include rpicam_agent entry point
- ✅ Updated `docs/quickstart-pi-rpicam.md` - Now documents HTTP bridge, systemd service, and Docker wiring

### In Progress:
- ⏳ **Host tooling**: Ensure Flask is installed correctly on the Pi and `rpicam_httpd.py` runs reliably under systemd
- ⏳ **Validation**: Confirm MP4 output at 720p@30fps behaves as expected with rpicam-vid in this architecture

### Remaining Work:
- ❌ Test rpicam-vid directly at 720p@30 MP4: `rpicam-vid -t 5000 --width 1280 --height 720 --framerate 30 --codec mp4 -o test.mp4`
- ❌ Run `scripts/rpicam_httpd.py` on the Pi and verify HTTP start/stop/status endpoints using curl
- ❌ Build and test the Docker container on the Pi using `docker/compose-pi.yml`
- ❌ Run `rpicam_agent` in the container and test end-to-end recording triggers via ROS2 services

## Relevant Files / Directories

### Configuration Files:
- `/boot/firmware/config.txt` - Pi boot config (reverted to camera_auto_detect=1, needs reboot)
- `/home/pi/.local/src/vertov/docker/compose-pi.yml` - Docker compose for Pi setup
- `/home/pi/.local/src/vertov/docker/Dockerfile.vertov-pi` - Docker image for Pi
- `/home/pi/.local/src/vertov/docker/entrypoint-pi.sh` - Container entrypoint
- `/home/pi/.local/src/vertov/docker/cyclonedds_pc.xml` - DDS configuration
 - `/home/pi/.local/src/vertov/systemd/rpicam-httpd.service` - systemd service for HTTP daemon

### Source Code:
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/vertov_video/rpicam_agent.py` - ROS2 agent node that calls host HTTP daemon
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/vertov_video/video_agent.py` - Original GStreamer agent
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/setup.py` - Package setup (updated with rpicam_agent entry point)
- `/home/pi/.local/src/vertov/ros2_ws/src/vertov_video/srv/StartRecording.srv` - Service definition

### Scripts:
- `/home/pi/.local/src/vertov/scripts/run_rpicam_agent.sh` - Launch rpicam agent
- `/home/pi/.local/src/vertov/scripts/run_video_agent.sh` - Original GStreamer agent launcher
- `/home/pi/.local/src/vertov/scripts/rpicam_vid_wrapper.sh` - Wrapper for calling rpicam-vid
 - `/home/pi/.local/src/vertov/scripts/rpicam_httpd.py` - HTTP daemon for controlling rpicam-vid on host

### Documentation:
- `/home/pi/.local/src/vertov/docs/quickstart-pi-rpicam.md` - Quickstart guide for Pi + rpicam setup
- `/home/pi/.local/src/vertov/PRD.md` - Product requirements (full system specs)
- `/home/pi/.local/src/vertov/docs/raspi-setup.md` - Original Ubuntu Pi setup guide
