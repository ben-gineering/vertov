#!/usr/bin/env python3
"""
ROS 2 Serial Bridge Node for PhantomX Reactor.

This node communicates with the Arduino via serial port and:
- Subscribes to /joint_commands (trajectory_msgs/JointTrajectory)
- Publishes /joint_states (sensor_msgs/JointState)
- Provides services for torque control, etc.

Protocol matches ros_bridge.ino sketch.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from std_msgs.msg import String
import serial
import time
import threading


class SerialBridgeNode(Node):
    def __init__(self):
        super().__init__('serial_bridge_node')
        
        # Parameters
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('timeout', 1.0)
        
        port = self.get_parameter('port').value
        baud_rate = self.get_parameter('baud_rate').value
        publish_rate = self.get_parameter('publish_rate').value
        timeout = self.get_parameter('timeout').value
        
        # Joint names matching official Robotnik URDF
        self.joint_names = [
            'shoulder_yaw_joint',
            'shoulder_pitch_joint',
            'elbow_pitch_joint',
            'wrist_pitch_joint',
            'wrist_roll_joint',
            'gripper_revolute_joint',
        ]
        
        # Convert position units (0-1023) to radians
        # AX-12: 0-1023 maps to ~300 degrees (0.29 degrees per unit)
        self.POS_TO_RAD = 0.0061359  # (300 * pi/180) / 1024
        self.RAD_TO_POS = 162.97     # 1024 / (300 * pi/180)
        
        # Current state
        self.current_positions = [512.0] * 6  # In position units
        self.current_velocities = [0.0] * 6
        self.current_effort = [0.0] * 6
        
        # Serial connection
        try:
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=baud_rate,
                timeout=timeout
            )
            time.sleep(2.0)  # Wait for Arduino reset
            self.get_logger().info(f'Serial connected to {port} at {baud_rate} baud')
            
            # Clear buffer and wait for READY message
            self.serial_conn.reset_input_buffer()
            self.wait_for_ready()
            
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.serial_conn = None
        
        # Publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        self.joint_state_pub = self.create_publisher(
            JointState, 
            '/joint_states',
            qos_profile
        )
        
        # Subscribers
        self.joint_traj_sub = self.create_subscription(
            JointTrajectory,
            '/joint_commands',
            self.joint_trajectory_callback,
            qos_profile
        )
        
        # Timer for publishing joint states
        self.publish_timer = self.create_timer(
            1.0 / publish_rate,
            self.publish_joint_states
        )
        
        self.get_logger().info('Serial Bridge Node initialized')
    
    def wait_for_ready(self):
        """Wait for Arduino to send READY message."""
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if self.serial_conn.in_waiting > 0:
                line = self.serial_conn.readline().decode('utf-8').strip()
                if line == 'READY':
                    self.get_logger().info('Arduino bridge ready')
                    return
        self.get_logger().warn('Timeout waiting for Arduino READY')
    
    def send_command(self, command: str) -> str:
        """Send command to Arduino and wait for response."""
        if not self.serial_conn:
            return "ERROR: No serial connection"
        
        try:
            self.serial_conn.write((command + '\n').encode())
            self.serial_conn.flush()
            
            # Read response
            start_time = time.time()
            while time.time() - start_time < 1.0:
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.readline().decode('utf-8').strip()
                    return response
            
            return "ERROR: Timeout"
            
        except Exception as e:
            self.get_logger().error(f'Serial error: {e}')
            return f"ERROR: {e}"
    
    def joint_trajectory_callback(self, msg: JointTrajectory):
        """Handle incoming joint trajectory commands."""
        if not msg.points:
            return
        
        # For now, just use the first point (single goal position)
        point = msg.points[0]
        
        # Convert from radians to position units (0-1023)
        positions = []
        for i, pos_rad in enumerate(point.positions):
            pos_units = int(pos_rad * self.RAD_TO_POS + 512)
            # Clamp to valid range
            pos_units = max(0, min(1023, pos_units))
            positions.append(pos_units)
        
        # Build POS command
        # ROS has 6 joints, Arduino maps to 8 servos (dual shoulder/elbow are mirrored)
        # Joint order: shoulder_yaw, shoulder_pitch, elbow_pitch, wrist_pitch, wrist_roll, gripper
        cmd = f"POS {positions[0]} {positions[1]} {positions[1]} {positions[2]} {positions[2]} {positions[3]} {positions[4]} {positions[5]}"
        
        response = self.send_command(cmd)
        
        if response == "OK":
            self.get_logger().debug(f'Moved to {positions}')
        else:
            self.get_logger().error(f'Move failed: {response}')
    
    def publish_joint_states(self):
        """Query current positions and publish joint states."""
        if not self.serial_conn:
            return
        
        response = self.send_command("GET")
        
        if response.startswith("JOINTS"):
            parts = response.split()
            if len(parts) >= 9:
                # Parse positions (skip "JOINTS" keyword)
                positions = []
                for i in range(1, 7):  # Only first 6 joints for URDF
                    try:
                        pos_units = int(parts[i])
                        if pos_units < 0:
                            pos_units = 512  # Default if error
                        # Convert to radians
                        pos_rad = (pos_units - 512) * self.POS_TO_RAD
                        positions.append(pos_rad)
                        self.current_positions[i-1] = pos_units
                    except (ValueError, IndexError):
                        positions.append(0.0)
                
                # Publish
                joint_state_msg = JointState()
                joint_state_msg.header.stamp = self.get_clock().now().to_msg()
                joint_state_msg.name = self.joint_names
                joint_state_msg.position = positions
                joint_state_msg.velocity = self.current_velocities
                joint_state_msg.effort = self.current_effort
                
                self.joint_state_pub.publish(joint_state_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.serial_conn:
            node.serial_conn.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
