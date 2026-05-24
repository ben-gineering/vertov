#!/usr/bin/env python3
"""
Nudge the PhantomX arm by a small amount from its current position.

Usage:
  ros2 run phantomx_hardware nudge.py --ros-args -p joint:=shoulder_yaw_joint -p delta:=0.1
  ros2 run phantomx_hardware nudge.py --ros-args -p joint:gripper_revolute_joint -p delta:=-0.2

Parameters:
  joint: Which joint to move (default: shoulder_yaw_joint)
  delta: How much to move in radians (default: 0.1)
  time: Duration of movement in seconds (default: 3.0)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
import sys


class NudgeNode(Node):
    def __init__(self):
        super().__init__('nudge_node')
        
        self.joint_names = [
            'shoulder_yaw_joint',
            'shoulder_pitch_joint', 
            'elbow_pitch_joint',
            'wrist_pitch_joint',
            'wrist_roll_joint',
            'gripper_revolute_joint',
        ]
        
        self.current_positions = None
        
        # Parameters
        self.target_joint = self.declare_parameter('joint', 'shoulder_yaw_joint').value
        self.delta = self.declare_parameter('delta', 0.1).value
        self.duration = self.declare_parameter('time', 3.0).value
        
        self.cmd_pub = self.create_publisher(JointTrajectory, '/joint_commands', 10)
        self.state_sub = self.create_subscription(
            JointState, 
            '/joint_states', 
            self.state_callback, 
            10
        )
        
        self.get_logger().info(f'Waiting for current joint state...')
        
    def state_callback(self, msg):
        if self.current_positions is None:
            self.current_positions = list(msg.position)
            self.get_logger().info(f'Got current state: {self.current_positions}')
            self.execute_nudge()
    
    def execute_nudge(self):
        # Find joint index
        try:
            idx = self.joint_names.index(self.target_joint)
        except ValueError:
            self.get_logger().error(f'Unknown joint: {self.target_joint}')
            self.get_logger().info(f'Valid joints: {self.joint_names}')
            rclpy.shutdown()
            return
        
        # Calculate new position
        new_positions = self.current_positions.copy()
        old_val = new_positions[idx]
        new_positions[idx] = old_val + self.delta
        
        # Clamp to reasonable limits (in radians, roughly ±3 rad = ±512 units)
        new_positions[idx] = max(-3.0, min(3.0, new_positions[idx]))
        
        self.get_logger().info(
            f'Moving {self.target_joint}: {old_val:.3f} → {new_positions[idx]:.3f} '
            f'(Δ={self.delta:+.3f}) over {self.duration}s'
        )
        
        # Build trajectory message
        traj = JointTrajectory()
        traj.joint_names = self.joint_names
        
        point = JointTrajectoryPoint()
        point.positions = new_positions
        point.time_from_start.sec = int(self.duration)
        point.time_from_start.nanosec = int((self.duration % 1) * 1e9)
        
        traj.points.append(point)
        
        # Publish
        self.cmd_pub.publish(traj)
        self.get_logger().info('Command published!')
        
        # Shutdown after publishing
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = NudgeNode()
    rclpy.spin(node)
    node.destroy_node()


if __name__ == '__main__':
    main()
