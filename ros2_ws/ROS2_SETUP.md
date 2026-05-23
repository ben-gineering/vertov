# ROS 2 Setup Guide for PhantomX Reactor

This guide walks through setting up ROS 2 control for the PhantomX Reactor arm.

---

## Repository Structure

```
vertov/
├── robotarm/                    # Arduino firmware (arduino-cli)
│   ├── firmware/
│   │   ├── reactor_test/        # Manual testing sketch
│   │   ├── teach_test/          # Teach & recall sketch
│   │   └── ros/
│   │       └── ros_bridge/      # ROS 2 serial bridge firmware
│   └── README.md, SETUP.md, etc.
│
└── ros2_ws/                     # ROS 2 workspace
    ├── src/
    │   └── vertov_robotarm/
    │       ├── phantomx_description/   # URDF, RViz config
    │       ├── phantomx_hardware/      # Serial bridge node
    │       └── phantomx_bringup/       # System launch files (TODO)
    ├── build/
    ├── install/
    └── README.md
```

---

## Phase 1: Visualization (Current) ✅

**Goal:** See the robot in RViz with manual joint control.

### Steps

1. **Install ROS 2 dependencies:**
   ```bash
   sudo apt update
   sudo apt install ros-humble-xacro ros-humble-joint-state-publisher-gui \
                    ros-humble-robot-state-publisher ros-humble-rviz2
   ```

2. **Build workspace:**
   ```bash
   cd ~/src/vertov/ros2_ws
   colcon build --symlink-install
   source install/setup.bash
   ```

3. **Test visualization:**
   ```bash
   ros2 launch phantomx_description display.launch.py
   ```

**Expected result:** RViz opens with robot model. Use Joint State Publisher GUI sliders to move joints.

---

## Phase 2: Hardware Interface (Next)

**Goal:** Control real hardware via ROS 2 topics.

### Steps

1. **Upload ROS bridge firmware:**
   ```bash
   cd ~/src/vertov/robotarm/firmware/ros/ros_bridge
   arduino-cli compile -b arbotix:avr:arbotix ./ros_bridge
   arduino-cli upload -p /dev/ttyUSB0 -b arbotix:avr:arbotix ./ros_bridge
   ```

2. **Install Python serial:**
   ```bash
   pip3 install pyserial
   ```

3. **Launch hardware interface:**
   ```bash
   ros2 launch phantomx_hardware hardware.launch.py
   ```

4. **Test joint movement:**
   ```bash
   ros2 topic pub /joint_commands trajectory_msgs/msg/JointTrajectory "{
     joint_names: ['base_joint', 'shoulder_pitch_joint', 'elbow_pitch_joint', 
                   'wrist_pitch_joint', 'wrist_roll_joint', 'gripper_joint'],
     points: [{positions: [0.5, 0.3, -0.3, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]
   }"
   ```

**Expected result:** Real arm moves to commanded position.

---

## Phase 3: MoveIt Integration (Future)

**Goal:** Motion planning with collision avoidance.

### TODO Packages
- `phantomx_moveit_config` - MoveIt Setup Assistant output
- `phantomx_bringup` - Complete system launch

### Steps (when ready)
1. Run MoveIt Setup Assistant with URDF
2. Generate SRDF, kinematics.yaml, ompl_planning.yaml
3. Configure ros2_control hardware interface
4. Test motion planning in RViz

---

## Phase 4: Applications (Future)

Potential applications once basic control works:

- **Joystick teleop** - Gamepad control
- **Pick-and-place** - Automated manipulation
- **Camera integration** - Vision-guided grasping
- **Inverse kinematics** - End-effector pose control

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| URDF model | ✅ Created | Basic geometry, all joints defined |
| RViz config | ✅ Created | RobotModel + TF displays |
| Launch files | ✅ Created | display.launch.py, hardware.launch.py |
| Serial bridge (Arduino) | ✅ Created | Custom protocol (POS, GET, PING) |
| Serial bridge (ROS 2) | ✅ Created | Python node with pyserial |
| Joint state publishing | ⏳ Pending | Needs hardware testing |
| Trajectory execution | ⏳ Pending | Needs hardware testing |

---

## Testing Checklist

### Visualization Only
- [ ] RViz launches without errors
- [ ] Robot model displays correctly
- [ ] Joint sliders move the model
- [ ] TF frames show correctly

### Hardware Interface
- [ ] Arduino firmware uploads successfully
- [ ] Serial connection established
- [ ] PING command returns PONG
- [ ] GET command returns valid positions
- [ ] POS command moves servos
- [ ] Joint states publish to /joint_states
- [ ] Trajectory commands execute

---

## Troubleshooting

### XACRO Processing Fails
```bash
# Install xacro
sudo apt install ros-humble-xacro

# Test manually
xacro src/vertov_robotarm/phantomx_description/urdf/phantomx_reactor.urdf.xacro
```

### Import Errors in Python Node
```bash
# Source ROS 2 environment
source /opt/ros/humble/setup.bash
source install/setup.bash

# Install dependencies
pip3 install pyserial
```

### Serial Port Issues
```bash
# Check permissions
ls -l /dev/ttyUSB0

# Add user to dialout group
sudo usermod -aG dialout $USER
# Log out and back in
```

---

## Next Actions

1. **Test visualization** - Verify URDF and RViz work
2. **Upload firmware** - Flash ros_bridge.ino
3. **Test serial comm** - Manual test with picocom
4. **Launch hardware node** - Full integration test

Let me know which step you want to tackle first!
