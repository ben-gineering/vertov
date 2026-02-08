# ROS2 Development Environment (Docker)

This document describes how to set up and use the ROS2 development environment for vertov using Docker on Arch Linux.

## Prerequisites

- Docker and Docker Compose plugin installed on Arch Linux
- Raspberry Pi 5 on the same network with ROS2 Jazzy installed natively
- Network connectivity between machines (same LAN)

## Building the Container

```bash
cd /path/to/vertov
docker compose -f docker/compose.yml build
```

## Running the Container

### Interactive Shell

```bash
docker compose -f docker/compose.yml run --rm ros2-dev
```

This drops you into a bash shell inside the container with ROS2 sourced.

### Running Commands Directly

```bash
docker compose -f docker/compose.yml run --rm ros2-dev ros2 topic list
docker compose -f docker/compose.yml run --rm ros2-dev ros2 node list
```

## Environment Variables

The container uses these environment variables:

- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` - Use CycloneDDS middleware
- `ROS_DOMAIN_ID=0` - ROS2 domain ID for communication
- `CYCLONEDDS_URI` - Path to CycloneDDS configuration file

Override these at runtime if needed:

```bash
ROS_DOMAIN_ID=1 docker compose -f docker/compose.yml run --rm ros2-dev
```

## Workspace

The ROS2 workspace is in `ros2_ws/` at the repository root. To build packages:

```bash
cd /workspace/vertov
docker compose -f docker/compose.yml run --rm ros2-dev bash
colcon build
```

After building, source the workspace overlay:

```bash
source ros2_ws/install/setup.bash
```

## Testing Connectivity with Pi

1. On the Pi, start a simple talker:

```bash
ros2 run demo_nodes_cpp talker
```

2. In the Docker container:

```bash
docker compose -f docker/compose.yml run --rm ros2-dev bash
ros2 topic list  # Should show /chatter
ros2 topic echo /chatter std_msgs/msg/String
```

## Common Issues

### Nodes Not Discovering Each Other

- Ensure both machines are on the same network
- Check `ROS_DOMAIN_ID` matches on both machines
- Verify Docker is using `network_mode: host`
- Check firewall settings allow multicast traffic

### CycloneDDS Configuration

The config file is at `docker/cyclonedds_pc.xml`. If you experience discovery issues, you may need to:
- Specify specific network interfaces
- Adjust multicast settings
- Add peer addresses explicitly

## Next Steps

Once the Docker environment is working:
1. Implement recording service on the Pi
2. Create trigger client in `ros2_ws/src/`
3. Test end-to-end recording trigger