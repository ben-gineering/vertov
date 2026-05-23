# PhantomX Reactor Robot Arm

## Overview

The **PhantomX Reactor** is a research-grade robotic arm from Interbotix Labs, designed for entry-level research and university use. It offers high features at an affordable price point, making it ideal for educational institutions, robotics research, and hobbyist projects.

---

## Key Specifications

| Parameter | Value |
|-----------|-------|
| **Weight** | 1.36 kg (1.43 kg with wrist rotate) |
| **Vertical Reach** | 51 cm (55.5 cm with wrist rotate) |
| **Horizontal Reach** | 38 cm (43 cm with wrist rotate) |
| **Payload** | 600g @ 10cm, 400g @ 20cm, 200g @ 30cm |
| **Gripper Strength** | 500g holding |
| **Wrist Lift Strength** | 250g (150g with wrist rotate) |
| **Degrees of Freedom** | 4-5 DOF + gripper |

---

## Hardware Components

### Actuators
- **8x AX-12A Dynamixel Servos**
  - 300° range of motion per joint (0-1023 position units)
  - Real-time feedback (temperature, position, voltage, load)
  - User-adjustable compliance and torque settings
  - Dual servos on shoulder and elbow for increased torque

### Controller
- **ArbotiX Robocontroller**
  - ATMega644p microprocessor
  - 8 Analog & 8 Digital IOs
  - USB, XBee wireless, or TTL serial connectivity
  - Arduino IDE compatible
  - ROS ready

### Construction
- Solid Delrin, acrylic, and metal frame
- 14cm ball bearing rotational base
- Custom parallel gripper
- Mounting brackets for cameras & sensors

---

## Degrees of Freedom (Joints)

| Joint | Name | Type | Servo IDs |
|-------|------|------|----------|
| 1 | Base | Rotation | ID 1 |
| 2 | Shoulder Left | Pitch | ID 2 |
| 3 | Shoulder Right | Pitch (mirrored) | ID 3 |
| 4 | Elbow Left | Pitch | ID 4 |
| 5 | Elbow Right | Pitch (mirrored) | ID 5 |
| 6 | Wrist Tilt | Pitch | ID 6 |
| 7 | Wrist Rotation | Roll | ID 7 |
| 8 | Gripper | Open/close | ID 8 |

**Note:** Shoulder and elbow use dual servos (mirrored movement) for increased torque.

**Position Range:** 0-1023 (0.29° resolution, ~300° total)
**Gripper Special:** Rotating disc mechanism (0=closed, 256=open, 512=closed)

---

## Control Options

1. **Arbotix-M Controller** - Upload custom firmware via Arduino IDE
2. **USB2Dynamixel** - Direct ROS control
3. **ROS Topics** - Command via `/joint_name/command` (std_msgs/Float64)
4. **MoveIt!** - Motion planning and trajectory execution

---

## Official Links

### Product Pages
- [Interbotix PhantomX Reactor](https://www.interbotix.com/p/phantomx-ax-12-reactor-robot-arm.aspx)
- [Robosklep Product Page](https://robosklep.com/en/robotic-arms/171-phantomx-reactor.html)

### Documentation & Wikis
- [UPM Robolabo Wiki](https://wiki.robolabo.etsit.upm.es/index.php/PhantomX_Reactor_Robot)
- [ROS Wiki - phantomx_reactor_arm](https://wiki.ros.org/phantomx_reactor_arm)

### GitHub Repositories
- [RobotnikAutomation/phantomx_reactor_arm](https://github.com/RobotnikAutomation/phantomx_reactor_arm) - Original ROS package (Arbotix-M + USB2Dynamixel)
- [I-Quotient-Robotics/phantomx_reactor_arm_v2](https://github.com/I-Quotient-Robotics/phantomx_reactor_arm_v2) - Version 2 (USB2Dynamixel only)

### Getting Started Guides
- ArbotiX Getting Started Guide
- DYNAMIXEL ID Guide
- Arm Assembly Guide
- Build Check / Test Program

---

## ROS Package Structure

```
phantomx_reactor_arm/
├── phantomx_reactor_arm_description/   # URDF models, meshes
├── phantomx_reactor_arm_controller/    # Controller configurations
└── phantomx_reactor_arm_moveit_config/ # MoveIt! configuration
```

---

## Quick Start (ROS)

### Launch with Arbotix-M (with wrist)
```bash
roslaunch phantomx_reactor_arm_controller arbotix_phantomx_reactor_arm_wrist.launch
```

### Launch with USB2Dynamixel
```bash
roslaunch phantomx_reactor_arm_controller dynamixel_phantomx_reactor_arm_wrist.launch
```

### Run MoveIt! Demo (fake controllers)
```bash
roslaunch phantomx_reactor_arm_moveit_config demo.launch
```

### Run MoveIt! with Real Controllers
```bash
roslaunch phantomx_reactor_arm_moveit_config demo_real.launch
```

### Command Joints via Topics
```bash
rostopic pub /shoulder_yaw_joint/command std_msgs/Float64 "data: 0.0"
rostopic pub /shoulder_pitch_joint/command std_msgs/Float64 "data: 0.0"
rostopic pub /elbow_pitch_joint/command std_msgs/Float64 "data: 0.0"
rostopic pub /wrist_pitch_joint/command std_msgs/Float64 "data: 0.0"
rostopic pub /wrist_roll_joint/command std_msgs/Float64 "data: 0.0"
```

---

## Applications

- Educational robotics and STEM programs
- Pick-and-place tasks with small objects
- Computer vision integration (camera mounting)
- Inverse kinematics research
- Manipulation research and prototyping

---

## Notes

- Gripper may require sanding for smooth operation (see assembly guide)
- Be careful with dependency between joints j2-j3 and j4-j5 when using Arbotix-M
- udev rules must be configured for proper USB device access
