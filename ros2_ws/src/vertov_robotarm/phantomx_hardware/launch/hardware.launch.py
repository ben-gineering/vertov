#!/usr/bin/env python3
"""
Launch file for PhantomX Reactor hardware interface.

This launches:
- serial_bridge_node: Communicates with Arduino via USB
- robot_state_publisher: Uses URDF for TF transforms

Usage:
  ros2 launch phantomx_hardware hardware.launch.py
  ros2 launch phantomx_hardware hardware.launch.py port:=/dev/ttyUSB0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Arguments
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='/dev/ttyUSB0',
        description='Serial port for Arduino'
    )
    
    baud_arg = DeclareLaunchArgument(
        'baud_rate',
        default_value='115200',
        description='Serial baud rate'
    )
    
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    # Package paths
    pkg_desc = FindPackageShare('phantomx_description')
    urdf_path = PathJoinSubstitution([pkg_desc, 'urdf', 'phantomx_reactor.urdf.xacro'])

    # Read URDF
    with open(urdf_path.perform(None), 'r') as f:
        robot_desc = f.read()

    # Serial bridge node
    serial_bridge_node = Node(
        package='phantomx_hardware',
        executable='serial_bridge_node.py',
        name='serial_bridge_node',
        output='screen',
        parameters=[{
            'port': LaunchConfiguration('port'),
            'baud_rate': LaunchConfiguration('baud_rate'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'robot_description': robot_desc,
        }],
    )

    return LaunchDescription([
        port_arg,
        baud_arg,
        use_sim_time_arg,
        serial_bridge_node,
        robot_state_publisher,
    ])
