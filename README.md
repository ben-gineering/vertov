# vertov

vertov is a distributed camera and robotics control system for artistic video production. It enables a single operator to coordinate camera movements across multiple Linux-based recording nodes (ARM/x86 mixed) using ROS2 as the primary orchestration layer, with local storage and post-hoc file aggregation.

## Key Principle

ROS2 acts as the State Machine Master. The Web Interface controls ROS2; ROS2 controls both robot motion and video recording. There is no separate meta-orchestrator.

## System Architecture

vertov follows a hierarchical control pattern:

- **Web UI** - Operator interface (React/Vue) running on Control Node
- **Control Node** - ROS2 Core that orchestrates all operations
- **Video Agents** - Distributed recording nodes (Pi4 + CSI/USB cameras, x86 + USB cameras)
- **Robot Controller** - MoveIt2/Nav2 for motion planning and execution

## Core Features

- **Synchronized Recording** - Coordinated video recording across 2-10 distributed nodes with mixed camera types
- **Robotics Control** - Support for robotic camera movement alongside static cameras
- **Island Mode** - Recording continues during network interruptions
- **Sub-frame Synchronization** - Audio transient method for post-production alignment

## Network Architecture

vertov uses a dual-network approach:

- **Control Plane** (Wired Ethernet) - ROS2/DDS traffic for real-time control
- **Data Sync Plane** (WiFi or Secondary Ethernet) - File transfer between takes

## Recording Format

- **Video:** MP4 (H.264/H.265), 1920x1080@30fps
- **Audio:** WAV (PCM 48kHz/24bit), separate file per camera
- **Metadata:** JSON sidecar with timestamps and sync information

## Software Stack

- **OS:** Ubuntu 22.04 (Pi4/x86)
- **ROS2 Distro:** Iron Irwini
- **DDS:** CycloneDDS
- **GStreamer:** 1.22+ with Python bindings
- **Camera APIs:** libcamera (CSI), V4L2 (USB)
- **Web Backend:** FastAPI or Node.js
- **Frontend:** React or Vue

## Project Structure

- `studio_bringup` - System bringup and launch files
- `studio_video` - Video recording and camera handling
- `studio_robot` - Robot control and motion planning