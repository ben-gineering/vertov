# vertov GUI

Control webinterface for Cinemate camera + Zynthian synthesizer.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo apt install python3-liblo
ln -sf /usr/lib/python3/dist-packages/liblo.*-linux-gnu.so .venv/lib/python3.11/site-packages/
.venv/bin/python main.py
```

Open http://<pi-ip>:8080 in a browser.

## Configuration

All config is set via environment variables (with defaults):

| Variable | Default | Description |
|---|---|---|
| `CINEMATE_REDIS_HOST` | `localhost` | Redis host for Cinemate |
| `CINEMATE_REDIS_PORT` | `6379` | Redis port |
| `CINEMATE_MJPEG_URL` | `http://10.0.0.186:8000/stream` | Live preview stream |
| `ZYNTHIAN_HOST` | `10.40.0.10` | Zynthian IP/hostname |
| `ZYNTHIAN_OSC_PORT` | `1370` | Zynthian CUIA OSC port |
| `VERTOV_DEVICE_CONFIG` | `gui/devices.example.json` | Multi-device config file |

### Multi-device foundations

The GUI now includes the initial data model for scaling beyond one Cinepi and one Zynthian:

- `gui/devices.example.json` - example device config
- `gui/vertov_models.py` - device config loader, take manifest schema, per-device state model

`main.py` now builds the device cards dynamically from the device config, persists runtime state to `gui/state/`, and uses config-driven device lookup instead of hardcoded `cinepi_main` / `zynthian_main` assumptions.

## Systemd service

A service file is included at `gui/vertov-gui.service`. It starts the GUI on boot after Redis is available.

### Install

```bash
sudo ln -s /home/pi/vertov/gui/vertov-gui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vertov-gui
```

### Manage

```bash
sudo systemctl status vertov-gui
sudo systemctl restart vertov-gui
journalctl -u vertov-gui -f
```

### Override environment

Edit the `Environment=` lines in the service file, or use a systemd override:

```bash
sudo systemctl edit vertov-gui
```

Then add e.g.:

```ini
[Service]
Environment=CINEMATE_MJPEG_URL=http://192.168.1.100:8000/stream
```

## Features

- Camera start/stop recording via Redis
- Zynthian audio start/stop recording via OSC/CUIA
- Live MJPEG camera preview with auto-reconnect
- Real-time status: FPS, buffer, storage, sensor
