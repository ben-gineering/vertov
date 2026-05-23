# PhantomX Reactor - Arduino CLI Setup Guide

This guide walks you through setting up the PhantomX Reactor robot arm using `arduino-cli` and command-line tools (no Arduino IDE required).

---

## Prerequisites Installed ✓

- [x] `arduino-cli` (v1.4.1)
- [x] AVR toolchain (`avr-gcc`, `avrdude`, etc.)
- [x] ArbotiX hardware support files
- [x] Bioloid library for Dynamixel control

---

## Step 1: USB Permissions (Required)

**Add your user to the `uucp` group:**
```bash
sudo usermod -aG uucp $USER
```
⚠️ **Log out and log back in** for this to take effect.

**Create udev rule for persistent access:**
```bash
cat << 'EOF' | sudo tee /etc/udev/rules.d/99-ftdi.rules > /dev/null
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", GROUP="uucp", SYMLINK+="arbotix"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## Step 2: Connect the Robot Arm

1. Connect the ArbotiX controller to your computer via USB
2. Power on the robot arm (12V 5A power supply)

**Verify connection:**
```bash
arduino-cli board list
```

You should see something like:
```
/dev/ttyUSB0    arbotix:avr:ArbotiX    arbotix:avr
```

Note the port (e.g., `/dev/ttyUSB0`).

---

## Step 3: Build & Upload Firmware

**Navigate to firmware directory:**
```bash
cd /home/bn/.local/src/vertov/robotarm/firmware
```

**Compile the test sketch:**
```bash
./build.sh reactor_test
```

**Upload to the board:**
```bash
./build.sh reactor_test /dev/ttyUSB0 upload
```

Or manually:
```bash
arduino-cli compile -b arbotix:avr:arbotix ./reactor_test
arduino-cli upload -p /dev/ttyUSB0 -b arbotix:avr:arbotix ./reactor_test
```

---

## Step 4: Test Communication

**Open serial monitor:**
```bash
picocom -b 115200 /dev/ttyUSB0
# Exit with Ctrl+A, then Ctrl+X
```

Or using screen:
```bash
screen /dev/ttyUSB0 115200
# Exit with Ctrl+A, then K, then Y
```

**Available commands:**
```
Commands:
  0 - Relax servos (power off)
  1 - Hold servos (power on)
  2 - Get joint positions
  3 - Gripper close
  4 - Gripper open
  5 - Test movement sequence
  h/? - Show this menu
```

**Test sequence:**
1. Type `1` → Powers on all servos (you'll feel them engage)
2. Type `2` → Shows current joint positions
3. Type `5` → Runs a test movement sequence
4. Type `0` → Relaxes servos (power off)

---

## File Structure

```
robotarm/
├── README.md                    # Robot overview & links
├── SETUP.md                     # This file
├── arbotix-hardware/            # Cloned ArbotiX source repo
│   ├── hardware/arbotix/        # Board definitions
│   └── libraries/               # Libraries
└── firmware/
    ├── build.sh                 # Build/upload script
    └── reactor_test/
        └── reactor_test.ino     # Test sketch
```

---

## Configuration Files

### Board Definition
Location: `/home/bn/Arduino/hardware/arbotix/avr/`

| File | Purpose |
|------|---------|
| `boards.txt` | Board configurations (ArbotiX, ArbotiX w/ RX Shield) |
| `platform.txt` | Compiler and upload tool settings |
| `cores/arbotix/` | Arduino core for ArbotiX |
| `variants/` | Board variant pinouts |

### Libraries
Location: `/home/bn/Arduino/libraries/`

| Library | Purpose |
|---------|---------|
| `Bioloid` | AX-12 Dynamixel communication |
| `ArmLink` | ArbotiX Arm Link protocol |
| `Commander` | Wireless commander support |

---

## Troubleshooting

### Permission Denied on /dev/ttyUSB0
```bash
# Check group membership
groups

# If not in uucp, add yourself and re-login
sudo usermod -aG uucp $USER
```

### Board Not Detected
```bash
# Check USB connection
lsusb | grep FTDI

# List all boards
arduino-cli board list

# Verify ArbotiX platform is installed
arduino-cli board listall | grep arbotix
```

### Compilation Errors
- Ensure `platform.txt` has correct compiler paths
- Check that `build.board` is defined in `boards.txt`
- Verify libraries are in `/home/bn/Arduino/libraries/`

### Upload Fails
- Check correct port with `arduino-cli board list`
- Try different USB cable
- Ensure ArbotiX is powered (12V supply connected)
- Reset the board (press reset button) before upload

### Servos Don't Move
- Check power supply (12V 5A required)
- Verify servo IDs match sketch (default: 1-5)
- Check AX-12 baud rate (1Mbps = 1000000)
- Listen for error beeps from servos

---

## Custom Sketches

To create your own sketch:

1. Create a new directory in `firmware/`:
   ```bash
   mkdir firmware/my_project
   ```

2. Create `.ino` file with same name as directory:
   ```bash
   touch firmware/my_project/my_project.ino
   ```

3. Build and upload:
   ```bash
   ./build.sh my_project /dev/ttyUSB0 upload
   ```

---

## Next Steps

Once basic control is working:

1. **Calibrate servos** - Find center positions for each joint
2. **Learn inverse kinematics** - Calculate joint angles for end-effector position
3. **Try ROS integration** - When ready for advanced features
4. **Add sensors** - Camera, force sensors, etc.

---

## Reference Links

- [PhantomX Reactor Product Page](https://www.interbotix.com/p/phantomx-ax-12-reactor-robot-arm.aspx)
- [ROS Wiki](https://wiki.ros.org/phantomx_reactor_arm)
- [ArbotiX GitHub](https://github.com/trossenrobotics/arbotix)
- [AX-12 Datasheet](https://emanual.robotis.com/docs/en/dxl/ax/ax-12a/)
