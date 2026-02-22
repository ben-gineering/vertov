**Product Requirements Document: Studio Robotics Recording System (vertov)**

**Version:** 0.1  
**Date:** 2026-02-08
**Status:** Draft for Review  

---

## 1. Executive Summary

vertov is a distributed camera and robotics control system for artistic video production. It enables a single operator to coordinate camera movements across multiple Linux-based recording nodes (ARM/x86 mixed) using ROS2 as the primary orchestration layer, with local storage and post-hoc file aggregation.

**Key Principle:** ROS2 acts as the State Machine Master. The Web Interface controls ROS2; ROS2 controls both robot motion and video recording. There is no separate meta-orchestrator.

---

## 2. Goals & Success Criteria

**Primary Goals:**
- Enable synchronized video recording across 2-10 distributed nodes with mixed camera types (CSI/USB)
- Coordinate robotic camera movement and static cameras simultaneously
- Ensure recording continuity during network interruptions ("island mode")
- Provide sub-frame synchronization via audio transient method for post-production alignment

**Non-Goals:**
- Real-time video streaming to Control Node (preview only, not recording)
- RAW video recording (H.264/H.265 hardware encoding only)
- Collaborative robot safety features (system assumes small, low-power robots)
- In-camera frame-level synchronization (genlock)

**Success Metrics:**
- Zero lost takes due to network failure (island mode verification)
- <200ms latency from "Record" button press to recording start across all nodes
- successful alignment of video/audio tracks in Blender via audio transient detection

---

## 3. System Architecture

### 3.1 Control Hierarchy (ROS-Master Pattern)

```
[Operator] 
    │
    ▼ HTTP/WebSocket
[Web UI] (React/Vue)
    │
    ▼ ROS2 Actions/Services (DDS)
[Control Node - ROS2 Core]
    ├──► [Robot Controller] (MoveIt2/Nav2)
    │         └── Physical Robot Arm/Base
    │
    ├──► [Video Agent 1] (Pi4 + CSI) ──┐
    ├──► [Video Agent 2] (Pi4 + USB) ──┤── Local Storage (USB3 SSD)
    ├──► [Video Agent 3] (x86 + USB) ──┘   (Island Mode capable)
    │
    └──► [Post-Production Trigger]
              └── File Sync (rsync) when idle
```

**Authority Flow:**
1. **Temporal Master:** PTP-synchronized system clocks (all nodes)
2. **State Machine Master:** ROS2 Control Node (owns the "Take" lifecycle)
3. **Execution:** 
   - Motion planning via ROS2 Action `ExecuteMotion`
   - Recording via ROS2 Service `StartRecording`/`StopRecording`
   - Video agents are ROS2 nodes wrapping GStreamer pipelines

### 3.2 Recording Lifecycle (Atomic Take)

```python
# ROS2 Action: ExecuteTake
1. PREPARE_PHASE
   - robot.plan_trajectory()  # MoveIt planning
   - video_agent.prewarm()    # GStreamer PAUSED, buffers allocated
   
2. ARMED_PHASE  
   - Wait for "READY" from all participants
   - Robot holds position (pre-positioned)
   
3. EXECUTE_PHASE (Atomic)
   - timestamp = now() + 200ms
   - video_agent.start_at(timestamp)  # GStreamer PLAYING
   - robot.execute_at(timestamp)      # Motion begins
   
4. COMPLETION_PHASE
   - Robot reaches final pose OR operator aborts
   - video_agent.stop()
   - Publish /take_complete with metadata
```

### 3.3 Network Segregation Strategy

**Dual-Network Architecture:**
- **ROS2 Control Plane:** Wired Ethernet preferred (VLAN 10)
  - DDS traffic (CycloneDDS default, unicast for WiFi segments)
  - Real-time priorities (SCHED_FIFO for robot control)
  - Bandwidth: <10 Mbps (lightweight)

- **Data Sync Plane:** WiFi or Secondary Ethernet (VLAN 20)  
  - **Time Division Multiplexing:** Active only during IDLE state (between takes)
  - rclone/rsync of completed takes to central storage
  - No sync during RECORDING or ARMED states

**Mixed Network Handling:**
- **Static nodes:** Wired Ethernet + PTP hardware timestamping
- **Mobile nodes:** WiFi (5GHz) + Chrony NTP (sufficient for loose sync)
- **Fallback:** If network partition occurs during recording, nodes continue in island mode; sync resumes when reconnected.

---

## 4. Functional Requirements

### 4.1 Video Recording (FR-VIdeo)

**FR-VIDEO-01:** Local Storage Recording
- Each node records to locally attached USB3 SSD (3-5 hour capacity)
- Filename format: `<PTP_ISO_timestamp>_<camera_id>.mp4`
- Container: MP4 with faststart (moov atom at front for streaming later)

**FR-VIDEO-02:** Mixed Camera API Support
- **CSI Cameras (Pi):** libcamera pipeline with hardware H.264 encoding (VideoCore)
- **USB Cameras:** V4L2 pipeline with hardware encoding (VA-API on x86, V4L2 on ARM)
- Configuration via node-specific YAML: `camera_type: [csi|usb|ip]`

**FR-VIDEO-03:** Frame Drop Resilience
- Recording continues regardless of frame drops ("continue regardless" policy)
- Frame drops logged to sidecar JSON: `{"frame_drops": [123, 456], "total_frames": 9000}`
- GStreamer pipeline uses leaky queues to prevent pipeline stall on slow storage

**FR-VIDEO-04:** Audio Recording
- Each node records local audio (USB mic or camera module audio) to separate WAV file
- Sample rate: 48kHz/24-bit (Blender VSE compatible)
- Audio transient sync mark recorded at take start (see FR-SYNC-01)

### 4.2 Robotics Control (FR-ROBOT)

**FR-ROBOT-01:** Independent Robot Coordination
- Support for 1 active robot + N static cameras initially
- Simultaneous robot support (TF namespace isolation: `robot_01/`, `robot_02/`)
- No collision avoidance required between robots (assume physical separation)

**FR-ROBOT-02:** Motion Types
- **Preset execution:** Named trajectories stored as ROS2 action goals
- **Manual jog:** Web UI joystick control (velocity commands) with deadman switch
- **Blender import:** Execute trajectories defined in Blender (optional/TBD)

**FR-ROBOT-03:** Safety (Small Robot Assumption)
- System assumes robots are intrinsically safe (small, low-mass, low-speed)
- Emergency stop via standard ROS2 `/emergency_stop` topic (software level)
- Hardware e-stop bypasses ROS2 (local to robot hardware, not integrated into recording logic)

### 4.3 Synchronization (FR-SYNC)

**FR-SYNC-01:** Audio Transient Method
- At take start, each node generates audio transient (clap/beep) within 50ms of recording start
- Transient detection frequency: 1kHz (configurable)
- Hardware: TBD (GPIO buzzer, servo clap, or USB speaker) - see TBD-03

**FR-SYNC-02:** Timestamp Metadata
- Rosbag2 records `/tf`, `/joint_states` with PTP-synchronized timestamps
- Video sidecar JSON maps frame numbers to approximate ROS timestamps (nearest 33ms)
- Post-production script correlates audio transient with visual waveform and ROS pose data

**FR-SYNC-03:** Time Synchronization Backend
- **Wired nodes:** PTP (IEEE 1588) with hardware timestamping
- **WiFi nodes:** Chrony NTP (sufficient for 10-50ms alignment)

### 4.4 Orchestration (FR-ORCH)

**FR-ORCH-01:** Take Management
- Take defined as: Motion execution + synchronized video recording
- Metadata per take: UUID, start_time, robot_preset (if applicable), camera_list, operator_notes
- Atomic failure: If any camera fails to start, abort take before robot moves

**FR-ORCH-02:** State Machine
System states: IDLE → ARMING → RECORDING → STOPPING → SYNCING → IDLE
- SYNCING state: File transfer from agents to central storage (only in IDLE)
- No file transfer during ARMING or RECORDING

**FR-ORCH-03:** Web Interface
- Single-page application (React/Vue) served by Control Node
- Real-time status: Recording state, disk space per node, robot pose preview
- Trigger methods: Web UI button, physical GPIO button on Control Node (TBD), optional wireless remote (TBD)

---

## 5. Non-Functional Requirements

### 5.1 Performance

**NFR-PERF-01:** Startup Latency
- <200ms from "Start Take" command to first frame recorded across all nodes
- Robot pre-positioning occurs during ARMING phase (before recording starts)

**NFR-PERF-02:** Recording Reliability
- Zero dropped frames due to ROS2 CPU contention (CPU isolation: GStreamer on cores 0-2, ROS2 on core 3)
- Continuous recording duration: 5 minutes standard, 60 minutes maximum per take

### 5.2 Reliability

**NFR-REL-01:** Island Mode Operation
- Network disconnection during recording does not stop recording or robot motion
- Upon reconnection, nodes report status and transfer files
- Operator can abort take locally via robot hardware e-stop (recording stops via local agent logic)

**NFR-REL-02:** Storage Management
- Auto-stop recording if <5GB remaining on local SSD
- Pre-recording disk space check during ARMING phase

### 5.3 Maintainability

**NFR-MAINT-01:** Hardware Abstraction
- Camera pipelines abstracted behind `VideoAgent` ROS2 node interface
- Robot types abstracted behind `RobotController` interface (MoveIt vs. simple servo)

---

## 6. Technical Specifications

### 6.1 Software Stack

| Component | Version/Type | Notes |
|-----------|--------------|-------|
| **OS** | Ubuntu 22.04 (Pi4/5 agents); Linux host (e.g. Arch) + Ubuntu 24.04-based Docker image for control node | ROS2 runs natively on agents and in containers on x86 where needed |
| **ROS2 Distro** | Jazzy Jalisco | Current target; future upgrades TBD |
| **DDS** | CycloneDDS (`rmw_cyclonedds_cpp`) | Minimal config for now; production config for WiFi/dual-network resilience TBD |
| **GStreamer** | 1.22+ | Python GI bindings for agent nodes |
| **Camera APIs** | libcamera (CSI), V4L2 (USB) | Hardware encoding mandatory |
| **Web Backend** | FastAPI (Python) or Node.js | Bridges HTTP/WebSocket to ROS2 |
| **Frontend** | React or Vue | ROS2 connection via rosbridge_suite or direct MQTT |

### 6.2 Hardware per Node

**Video Agent (Pi 4/5):**
- Raspberry Pi 4 (4GB+) or Pi 5
- USB3 SSD 500GB+ (Samsung T7 or equivalent)
- CSI Camera Module 3 (Wide) OR USB webcam (Logitech C920/C930e)
- Optional: GPIO piezo buzzer (for audio sync)
- Cooling: Passive heatsink minimum (no fan noise during recording)

**Control Node (x86):**
- Intel NUC or similar (i5+, 16GB RAM)
- Ethernet + WiFi
- Optional: Audio interface for monitoring

**Robot Node:**
- TBD: Dynamixel servos / Stepper controller / Commercial arm
- Microcontroller: Pi Pico (Micro-ROS) or direct Pi GPIO (if Pi not overloaded)
- Connection: USB serial or CAN bus to Control Node

### 6.3 Network Requirements

- **Control Plane:** 100Mbps Ethernet minimum, IGMP snooping enabled for DDS
- **Sync Plane:** WiFi 5GHz (802.11ac) or Gigabit Ethernet
- **Time Sync:** PTP Grandmaster (Control Node) or GPS-disciplined oscillator for outdoor

### 6.4 Current Test Rigs

The following setups are currently available and used for early MVP testing. They are a subset of the target hardware described above and may evolve over time.

- **Video Agent Rig A:** Raspberry Pi 5 + Raspberry Pi High Quality Camera, USB SSD for local recording
- **Control/Test Rig B:** x86 machine (Arch Linux) with USB webcam
- **Mobile Base:** TurtleBot 3 (no camera mounted yet)
- **Robot Arm:** PhantomX Reactor (no camera mounted yet)
- **Operator Interface:** Android tablet/phone used as primary web interface client

---

## 7. Interfaces & APIs

### 7.1 ROS2 Interfaces

**Action:** `ExecuteTake`
```
ExecuteTake.action
---
# Goal
string take_id
string robot_preset  # Empty for manual/static shots
string[] camera_ids
uint32 duration_sec  # 0 for manual stop
---
# Result
bool success
string[] recorded_files
string error_message
---
# Feedback
uint8 state  # 0=ARMING, 1=RECORDING, 2=STOPPING
float32 progress
string status_message
```

**Service:** `StartRecording` (per camera agent)
```
# Request
string take_id
builtin_interfaces/Time start_time  # Future timestamp for sync
---
# Response
bool success
string filename
string error
```

**Topic:** `/studio/take_status` (latched)
```
std_msgs/Header header
bool is_recording
string current_take_id
string[] active_cameras
string robot_status
```

### 7.2 File Formats

**Video:** MP4 (H.264/H.265), 1920x1080@30fps baseline
**Audio:** WAV (PCM 48kHz/24bit), separate file per camera
**Metadata:** JSON sidecar per take:
```json
{
  "take_id": "uuid",
  "start_time_ptp": "2024-01-15T14:30:00.000Z",
  "cameras": {
    "cam_01": {
      "video_file": "...mp4",
      "audio_file": "...wav",
      "frame_drops": 0,
      "sync_transient_frame": 15
    }
  },
  "ros_bag": "take_001.bag",
  "robot_preset": "crane_up_slow"
}
```

---

## 8. Open Questions (TBD)

| ID | Question | Impact | Priority |
|----|----------|--------|----------|
| **TBD-01** | Robot hardware specs (servo vs. stepper vs. arm)? | Determines ros2_control configuration | **HIGH** |
| **TBD-02** | Web UI paradigm (preset library vs. direct control)? | Affects ROS2 action design | **HIGH** |
| **TBD-03** | Audio transient hardware implementation? | BOM and wiring | Low |
| **TBD-04** | Pi OS vs. Ubuntu on agents? | Driver availability (libcamera) | Medium |

---

## 9. Appendix: Post-Production Workflow

1. **Collection:** Operator runs `./collect_take.sh <take_id>` which rsyncs from all agents to editing workstation
2. **Sync Detection:** Blender Python script detects audio transient in each WAV file
3. **Alignment:** Video strips aligned to audio transient (frame-accurate relative to each other)
4. **Robot Data:** Rosbag imported as camera tracking data (empty objects animated via TF data)
5. **Proxy Editing:** Low-res proxies generated for Blender VSE editing; relink to full-res for render

---

**Next Steps:**
0. MVP: Remote-triggered video-only recording from control node to a single Pi 5 agent (no robotics, no audio, no multi-node sync yet)
1. Resolve TBD-01 (Robot hardware selection)
2. Define ROS2 package structure (`vertov_bringup`, `vertov_video`, `vertov_robot`)
3. Prototype single-node recording (GStreamer + ROS2 service)

**Approval Required From:** [Product Owner/Technical Lead]
