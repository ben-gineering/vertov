# PhantomX Robot Arm - Docker Setup

ROS 2 Humble container with RViz support for Arch Linux + Sway (Wayland/XWayland).

---

## Quick Start

### 1. Install Prerequisites

```bash
# X11 forwarding support
sudo pacman -S xorg-xhost

# Add user to docker group (one-time setup)
sudo usermod -aG docker $USER

# Log out and back in for group change to take effect
# OR use newgrp docker for current session
```

### 2. Start Container (Choose One Method)

#### Method A: Using Helper Script (Recommended)

```bash
cd ~/src/vertov/docker

# If you have docker group access:
./run_robotarm.sh

# If not, or for quick testing (uses sudo):
./run_robotarm_sudo.sh
```

#### Method B: Manual Docker Commands

```bash
cd ~/src/vertov/docker

# Allow X11 access
xhost +local:docker

# Start container
docker compose -f compose-robotarm.yml up --build -d

# Enter container
docker compose -f compose-robotarm.yml exec robotarm bash
```

### 3. Build ROS 2 Workspace

```bash
# Inside container
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### 4. Test RViz

```bash
# Inside container
ros2 launch phantomx_description display.launch.py
```

RViz window should appear on your Sway desktop!

---

## Docker Compose Commands

| Command | Description |
|---------|-------------|
| `docker compose -f compose-robotarm.yml up --build -d` | Build and start in background |
| `docker compose -f compose-robotarm.yml exec robotarm bash` | Get shell in running container |
| `docker compose -f compose-robotarm.yml exec robotarm <cmd>` | Run specific command |
| `docker compose -f compose-robotarm.yml logs -f` | View container logs |
| `docker compose -f compose-robotarm.yml down` | Stop and remove container |
| `docker compose -f compose-robotarm.yml restart` | Restart container |

---

## Example Workflows

### Test Visualization Only

```bash
cd ~/src/vertov/docker
docker compose -f compose-robotarm.yml up --build -d
docker compose -f compose-robotarm.yml exec robotarm \
    bash -c "source /opt/ros/humble/setup.bash && \
             cd ~/ros2_ws && colcon build && \
             source install/setup.bash && \
             ros2 launch phantomx_description display.launch.py"
```

### Development Session

```bash
# Terminal 1: Start container
docker compose -f compose-robotarm.yml up -d

# Terminal 2: Work inside container
docker compose -f compose-robotarm.yml exec robotarm bash
# Now you can edit code, build, test, etc.

# When done: stop container
docker compose -f compose-robotarm.yml down
```

### Run RViz Directly

```bash
docker compose -f compose-robotarm.yml up -d
docker compose -f compose-robotarm.yml exec robotarm \
    ros2 launch phantomx_description display.launch.py
```

---

## USB Serial Access (for Hardware)

To access the Arduino via `/dev/ttyUSB0`:

### Option A: Privileged Mode (easiest)
Already enabled in `compose-robotarm.yml` with `privileged: true`

### Option B: Specific Device (more secure)
Edit `compose-robotarm.yml`:
```yaml
# Remove or comment out:
# privileged: true

# Add instead:
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

Then upload firmware from inside container:
```bash
docker compose -f compose-robotarm.yml exec robotarm bash
arduino-cli upload -p /dev/ttyUSB0 -b arbotix:avr:arbotix \
    ~/ros2_ws/../robotarm/firmware/ros/ros_bridge
```

---

## Troubleshooting

### RViz Window Doesn't Appear

1. Check X11 access:
   ```bash
   # On host
   xhost +local:docker
   ```

2. Verify DISPLAY variable in container:
   ```bash
   docker compose -f compose-robotarm.yml exec robotarm echo $DISPLAY
   # Should show :0
   ```

3. Test with simple X11 app:
   ```bash
   docker compose -f compose-robotarm.yml exec robotarm xclock
   ```

### Permission Denied on /dev/ttyUSB0

```bash
# On host, check permissions
ls -l /dev/ttyUSB0

# Add your user to uucp group (Arch-specific for FTDI)
sudo usermod -aG uucp $USER
# Log out and back in

# Or use privileged mode (already set in compose file)
```

### Colcon Build Fails

```bash
# Make sure ROS 2 is sourced
source /opt/ros/humble/setup.bash

# Clean build
rm -rf build/ install/ log/
colcon build --symlink-install

# Check dependencies
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

### Container Won't Start

```bash
# Check what's running
docker ps -a

# Remove old container
docker rm -f phantomx_robotarm

# Rebuild
docker compose -f compose-robotarm.yml up --build -d
```

---

## XWayland on Sway

Verify XWayland is active:

```bash
# Check if XWayland is running
ps aux | grep Xwayland

# Test X11 apps work
xclock  # Should open on your Sway desktop
```

If XWayland isn't running, add to your Sway config (`~/.config/sway/config`):

```
# Enable XWayland
exec swayidle -w timeout 300 'swaylock -f -c 000000'
```

(Actually, XWayland should be automatic when you run any X11 app)

---

## Notes

- **Image size:** ~2GB (ROS 2 Humble + GUI libs)
- **First build:** Takes 5-10 minutes depending on connection
- **Subsequent builds:** Fast (uses cached layers)
- **Workspace persistence:** Your code is mounted from host, so edits persist
- **Build artifacts:** `build/`, `install/`, `log/` are inside container but backed by host filesystem

---

## Cleanup

```bash
# Stop and remove container
docker compose -f compose-robotarm.yml down

# Remove image (free ~2GB)
docker rmi phantomx_robotarm:humble

# Remove all dangling images
docker image prune
```
