# vertov GUI

Control webinterface for Cinemate camera + Zynthian synthesizer.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Open http://<pi-ip>:8080 in a browser.

## Configuration

All config is set via environment variables (with defaults):

| Variable | Default | Description |
|---|---|---|
| `CINEMATE_REDIS_HOST` | `localhost` | Redis host for Cinemate |
| `CINEMATE_REDIS_PORT` | `6379` | Redis port |
| `CINEMATE_MJPEG_URL` | `http://localhost:8000/stream` | Live preview stream |
| `ZYNTHIAN_HOST` | `10.40.0.10` | Zynthian IP/hostname |
| `ZYNTHIAN_OSC_PORT` | `1370` | Zynthian CUIA OSC port |

## Features

- Camera start/stop recording via Redis
- Zynthian audio start/stop recording via OSC/CUIA
- Live MJPEG camera preview
- Real-time status: FPS, buffer, storage, sensor
