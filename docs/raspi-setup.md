# Raspberry Pi 5 Setup Guide

This document covers the setup of the vertov distributed camera system on Raspberry Pi 5 running Ubuntu 24.04.

## Hardware

- **Device**: Raspberry Pi 5 (4GB+ recommended)
- **OS**: Ubuntu 24.04.3 LTS (Noble Numbat)
- **Camera**: Raspberry Pi Camera Module 3 (CSI interface)
- **Storage**: Local SSD or SD card for recordings (`/home/pi/Videos/`)

## Network

- **Control**: WiFi (wlan0) - 10.0.0.x subnet
- **Arch Linux Control Node**: Wired ethernet on same network
- **ROS2 Domain**: ID 0

## Software Stack

- **ROS2 Distro**: Jazzy Jackal
- **DDS**: CycloneDDS
- **Camera API**: libcamera (via GStreamer)
- **Video Encoder**: v4l2h264enc (hardware H.264)
- **Recording Format (on Pi)**: MKV (H.264), 1920x1080@30fps

## Installation Steps

### 1. Install ROS2 Jazzy

```bash
# Add ROS2 repository
sudo apt update && sudo apt install -y curl gnupg lsb-release software-properties-common
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2
sudo apt update
sudo apt install -y ros-jazzy-ros-base ros-jazzy-rmw-cyclonedds-cpp python3-colcon-common-extensions ros-dev-tools
```

### 2. Configure Environment

Add to `~/.bashrc`:

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
export CYCLONEDDS_URI=file:///home/pi/.local/src/vertov/cyclonedds.xml
```

### 3. Configure CycloneDDS for WiFi

Create `/home/pi/.local/src/vertov/cyclonedds.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CycloneDDS>
  <Domain>
    <General>
      <AllowMulticast>true</AllowMulticast>
      <MaxMessageSize>65500B</MaxMessageSize>
    </General>
    <Discovery>
      <ParticipantIndex>auto</ParticipantIndex>
      <MaxAutoParticipantIndex>100</MaxAutoParticipantIndex>
    </Discovery>
  </Domain>
</CycloneDDS>
```

### 4. Install GStreamer and Camera Tools

GStreamer 1.24 and libcamera are pre-installed on Ubuntu 24.04:

```bash
# Verify installation
dpkg -l | grep -E "(gstreamer|libcamera)"

# Test libcamera
libcamera-hello --list-cameras
```

### 5. Build the vertov_video Package

```bash
# Source ROS2 environment
source /opt/ros/jazzy/setup.bash

# Navigate to workspace
cd /home/pi/.local/src/vertov/ros2_ws

# Build the package
colcon build --packages-select vertov_video

# Source the workspace
source install/setup.bash
```

## Verifying the Setup

### Test ROS2 Installation

```bash
source /opt/ros/jazzy/setup.bash
ros2 node list
ros2 topic list
ros2 service list
```

### Test Camera (GStreamer)

```bash
# Quick camera preview (requires display or X forwarding)
gst-launch-1.0 libcamerasrc ! videoconvert ! autovideosink
```

### Test Cross-Machine Discovery

On both Pi and Arch Linux control node:

```bash
# Should show nodes from both machines
ros2 node list
```

## Package Structure

```
/home/pi/.local/src/vertov/
├── cyclonedds.xml          # DDS configuration
├── ros2_ws/                # ROS2 workspace
│   └── src/
│       └── vertov_video/   # Video recording agent package
│           ├── vertov_video/
│           │   ├── __init__.py
│           │   └── video_agent.py
│           ├── srv/
│           │   └── StartRecording.srv
│           ├── package.xml
│           ├── setup.py
│           └── setup.cfg
└── Videos/                 # Recording directory
    └── (MKV files saved here)
```

## Recording Workflow

### Start Recording Service

```bash
# Terminal 1: Run the video agent
ros2 run vertov_video video_agent

# Terminal 2: Trigger recording
ros2 service call /start_recording vertov_video/srv/StartRecording \
  "{take_id: 'test_001', start_time: {sec: 0, nanosec: 0}}"
```

### Expected Output

- Recording files: `/home/pi/Videos/{ISO_timestamp}_cam01.mkv`
- Service response: `success: true`, `filename: "...mkv"`

## Troubleshooting

### ROS2 Not Found

```bash
source /opt/ros/jazzy/setup.bash
```

### Camera Not Detected

```bash
# Check video devices
ls /dev/video*

# Test libcamera
libcamera-hello --list-cameras
```

### Cross-Machine Discovery Failed

1. Verify both machines are on the same network
2. Check ROS_DOMAIN_ID is consistent
3. Check firewall allows UDP ports 7400-7410
4. Review CycloneDDS configuration

### GStreamer Pipeline Errors

```bash
# Test GStreamer elements
gst-inspect-1.0 libcamerasrc
gst-inspect-1.0 v4l2h264enc
gst-inspect-1.0 mp4mux
```

### 1080p MP4 Files Missing `moov` Atom

On Pi 5 with the IMX477 camera and the current libcamera + GStreamer stack, the
following behavior has been observed:

- Pipelines using `libcamerasrc` at 1920x1080 feeding `x264enc ! h264parse ! mp4mux`
  can hang on EOS and produce MP4 files without a `moov` atom (`ffprobe` reports
  `moov atom not found`).
- The same encoder/mux chain at 1920x1080 using `videotestsrc` instead of
  `libcamerasrc` produces valid MP4 files.

This suggests an EOS/teardown issue specific to `libcamerasrc` at 1080p on this
platform, rather than a general problem with `x264enc` or `mp4mux`.

Workarounds and current recommendation:

- Use a lower resolution pipeline (e.g. 640x480) that is known to shut down
  cleanly and produce valid MP4 files.
- Prefer using `matroskamux` instead of `mp4mux` to record `.mkv` files on the
  Pi, which has proven more robust to imperfect EOS handling at 1080p. The
  `vertov_video` ROS node records 1080p H.264 into MKV by default.
- If you require MP4 for downstream tools, convert off-device (for example on
  the Arch Linux control node) using a stream copy remux:

  ```bash
  ffmpeg -i input.mkv -c copy output.mp4
  ```

The 1080p + `libcamerasrc` + MP4 behavior should be revisited after future
libcamera/GStreamer updates.
