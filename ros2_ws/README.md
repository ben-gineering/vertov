# PhantomX Reactor ROS 2 Workspace

ROS 2 packages for controlling the PhantomX Reactor robot arm.

---

## Packages

| Package | Description |
|---------|-------------|
| `phantomx_description` | URDF model, meshes, RViz config (based on [Robotnik's official package](https://github.com/RobotnikAutomation/phantomx_reactor_arm)) |
| `phantomx_hardware` | Serial bridge to Arduino, hardware interface |
| `phantomx_bringup` | Launch files for complete system |

### Joint Structure (from official URDF)

```
base_footprint (fixed)
  └─ base_link
      └─ shoulder_yaw_joint (Z-axis rotation, Servo ID 1)
          └─ shoulder_link
              └─ shoulder_pitch_joint (Servo IDs 2,3 dual)
                  └─ bicep_link
                      └─ elbow_pitch_joint (Servo IDs 4,5 dual)
                          └─ forearm_link
                              └─ wrist_pitch_joint (Servo ID 6)
                                  └─ wrist_1_link
                                      └─ wrist_roll_joint (Servo ID 7)
                                          └─ wrist_2_link
                                              └─ gripper_guide_link
                                                  └─ gripper (Servo ID 8)

---

## Prerequisites

### ROS 2 Installation

This workspace targets **ROS 2 Humble Hawksbill** (Ubuntu 22.04).

```bash
# Install ROS 2 Humble (if not already installed)
sudo apt update
sudo apt install ros-humble-desktop
source /opt/ros/humble/setup.bash
```

### Python Dependencies

```bash
pip3 install pyserial
```

---

## Quick Start

### 1. Build the Workspace

```bash
cd ~/src/vertov/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### 2. Upload ROS Bridge Firmware

```bash
cd ~/src/vertov/robotarm/firmware/ros/ros_bridge
arduino-cli compile -b arbotix:avr:arbotix ./ros_bridge
arduino-cli upload -p /dev/ttyUSB0 -b arbotix:avr:arbotix ./ros_bridge
```

### 3. Test Visualization (No Hardware)

```bash
# Launch RViz with joint state GUI
ros2 launch phantomx_description display.launch.py gui:=true
```

You should see the robot model in RViz. Use the Joint State Publisher GUI slider to move joints.

### 4. Test Hardware Interface

```bash
# Connect robot arm via USB, ensure it's powered (12V)

# Launch hardware interface
ros2 launch phantomx_hardware hardware.launch.py

# In another terminal, send joint commands
ros2 topic pub /joint_commands trajectory_msgs/msg/JointTrajectory "{
  joint_names: ['base_joint', 'shoulder_pitch_joint', 'elbow_pitch_joint', 
                'wrist_pitch_joint', 'wrist_roll_joint', 'gripper_joint'],
  points: [{positions: [0.0, 0.5, -0.5, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]
}"
```

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  ROS 2 Layer                         │
├──────────────────────────────────────────────────────┤
│  RViz  │  MoveIt  │  Your App  │  joy_node         │
├──────────────────────────────────────────────────────┤
│          /joint_states    ←→    /joint_commands     │
├──────────────────────────────────────────────────────┤
│        phantomx_hardware (serial_bridge_node)        │
│              Python + pyserial @ 115200              │
└──────────────────────────────────────────────────────┘
                        ↓ USB (/dev/ttyUSB0)
┌──────────────────────────────────────────────────────┤
│               Arduino Layer                          │
├──────────────────────────────────────────────────────┤
│         ros_bridge.ino (custom serial protocol)      │
│  Commands: POS, GET, PING, TORQUE                   │
│  AX-12 communication via Bioloid @ 1Mbps            │
└──────────────────────────────────────────────────────┘
```

---

## Topics

| Topic | Type | Direction | Description |
|-------|------|-----------|-------------|
| `/joint_states` | sensor_msgs/JointState | Publish | Current joint positions |
| `/joint_commands` | trajectory_msgs/JointTrajectory | Subscribe | Goal positions |

---

## Joint Mapping

| Index | Joint Name | Servo IDs | Type | Range (rad) | Range (AX-12 units) |
|-------|------------|-----------|------|-------------|---------------------|
| 0 | `shoulder_yaw_joint` | 1 | Revolute (Z-axis) | ±π | 0-1023 |
| 1 | `shoulder_pitch_joint` | 2, 3 (dual) | Revolute | ±π/2 | 0-1023 |
| 2 | `elbow_pitch_joint` | 4, 5 (dual) | Revolute | ±π/2 | 0-1023 |
| 3 | `wrist_pitch_joint` | 6 | Revolute | -1.7 to 1.9 | 0-1023 |
| 4 | `wrist_roll_joint` | 7 | Revolute | ±π | 0-1023 |
| 5 | `gripper_revolute_joint` | 8 | Revolute | ±π | 0-1023 (effective: 0-512) |

**Notes:**
- Shoulder and elbow use dual servos with mirrored movement (handled in firmware)
- Gripper has a rotating disc mechanism: 0=closed, 256=open, 512=closed
- Joint limits from Robotnik's official URDF

---

## Troubleshooting

### Serial Port Permission Denied

```bash
# Add user to dialout group
sudo usermod -aG dialout $USER
# Log out and back in
```

### No Response from Arduino

1. Check port: `ls -l /dev/ttyUSB0`
2. Verify firmware uploaded: `arduino-cli board list`
3. Test serial manually:
   ```bash
   picocom -b 115200 /dev/ttyUSB0
   # Send: PING
   # Expect: PONG
   ```

### Joints Not Moving

1. Ensure 12V power is connected
2. Check torque enabled: Send `TORQUE 1` via picocom
3. Verify servo IDs match sketch

---

## Next Steps

After basic control works:

1. **MoveIt Integration** - Motion planning with collision avoidance
2. **Joystick Control** - Teleoperation with gamepad
3. **Camera Integration** - Eye-in-hand or eye-to-hand vision
4. **Pick-and-Place Demo** - Complete manipulation task

---

## Development

### Build

```bash
cd ~/src/vertov/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### Run Tests

```bash
colcon test
```

### Lint

```bash
ament_lint
```

---

## License

BSD-3-Clause
