#!/usr/bin/env python3
"""
Launch file for PhantomX Reactor visualization in RViz.

This launches:
- robot_state_publisher: Publishes TF transforms from URDF
- joint_state_publisher_gui: Interactive joint sliders
- rviz2: 3D visualization

Usage:
  ros2 launch phantomx_description display.launch.py
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation clock'
    )

    # Get package paths
    pkg_share = FindPackageShare('phantomx_description')
    urdf_path = PathJoinSubstitution([pkg_share, 'robots', 'phantomx_reactor.urdf.xacro'])
    rviz_config = PathJoinSubstitution([pkg_share, 'config', 'phantomx.rviz'])

    # Robot state publisher (processes XACRO automatically)
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'robot_description': ParameterValue(Command(['xacro ', urdf_path]), value_type=str),
        }],
    )

    # Joint state publisher GUI (interactive sliders)
    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    # RViz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    return LaunchDescription([
        use_sim_time_arg,
        robot_state_publisher_node,
        joint_state_publisher_gui_node,
        rviz_node,
    ])
