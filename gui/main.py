#!/usr/bin/env python3
"""vertov control webinterface MVP.

Controls:
  - Cinemate camera via local Redis (start/stop recording)
  - Zynthian synth via OSC/CUIA (start/stop audio recording)

Requires: nicegui, redis, python-osc
"""

import logging
import os
from contextlib import suppress

import redis
from nicegui import app, ui
from pythonosc import udp_client

log = logging.getLogger("vertov.gui")

# ---------------------------------------------------------------------------
# Configuration (override via env or edit here)
# ---------------------------------------------------------------------------
CINEMATE_REDIS_HOST = os.environ.get("CINEMATE_REDIS_HOST", "localhost")
CINEMATE_REDIS_PORT = int(os.environ.get("CINEMATE_REDIS_PORT", "6379"))
CINEMATE_MJPEG_URL = os.environ.get("CINEMATE_MJPEG_URL", "http://10.0.0.186:8000/stream")

ZYNTHIAN_HOST = os.environ.get("ZYNTHIAN_HOST", "10.40.0.10")
ZYNTHIAN_OSC_PORT = int(os.environ.get("ZYNTHIAN_OSC_PORT", "1370"))

# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------
rdb = redis.Redis(host=CINEMATE_REDIS_HOST, port=CINEMATE_REDIS_PORT, decode_responses=True)
zynthian_osc = udp_client.SimpleUDPClient(ZYNTHIAN_HOST, ZYNTHIAN_OSC_PORT)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
camera_rec = False
zynthian_rec = False


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def toggle_camera() -> None:
    global camera_rec
    try:
        current = rdb.get("is_recording")
        new_val = "0" if current == "1" else "1"
        rdb.set("is_recording", new_val)
        rdb.publish("cp_controls", "is_recording")
        camera_rec = new_val == "1"
        cam_btn.props(f'color={"red" if camera_rec else "grey-7"}')
        cam_btn.props(f'label={"CAM STOP" if camera_rec else "CAM REC"}')
        cam_status.set_text("RECORDING" if camera_rec else "idle")
    except Exception as exc:
        log.error("camera toggle failed: %s", exc)
        ui.notify(f"Camera error: {exc}", type="negative")


def toggle_zynthian() -> None:
    global zynthian_rec
    try:
        action = "STOP_AUDIO_RECORD" if zynthian_rec else "START_AUDIO_RECORD"
        zynthian_osc.send_message(f"/cuia/{action}")
        zynthian_rec = not zynthian_rec
        zyn_btn.props(f'color={"blue" if zynthian_rec else "grey-7"}')
        zyn_btn.props(f'label={"ZYN STOP" if zynthian_rec else "ZYN REC"}')
        zyn_status.set_text("RECORDING" if zynthian_rec else "idle")
    except Exception as exc:
        log.error("zynthian toggle failed: %s", exc)
        ui.notify(f"Zynthian error: {exc}", type="negative")


# ---------------------------------------------------------------------------
# Live status polling
# ---------------------------------------------------------------------------
def poll_status() -> None:
    global camera_rec, zynthian_rec
    with suppress(Exception):
        val = rdb.get("is_recording")
        camera_rec = val == "1"
        cam_btn.props(f'color={"red" if camera_rec else "grey-7"}')
        cam_btn.props(f'label={"CAM STOP" if camera_rec else "CAM REC"}')
        cam_status.set_text("RECORDING" if camera_rec else "idle")

        # FPS / buffer / storage info
        with suppress(Exception):
            fps = rdb.get("fps_actual")
            buf = rdb.get("buffer")
            space = rdb.get("space_left")
            sensor = rdb.get("sensor")
            info_parts = []
            if sensor:
                info_parts.append(f"sensor: {sensor}")
            if fps:
                info_parts.append(f"fps: {fps}")
            if buf:
                info_parts.append(f"buffer: {buf}")
            if space:
                info_parts.append(f"space: {space}GB")
            cam_info.set_text(" | ".join(info_parts) if info_parts else "")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
@ui.page("/")
def main_page() -> None:
    ui.add_css("body { background: #121212; color: #e0e0e0; }")

    with ui.header().classes("items-center justify-between").style("background: #1a1a1a;"):
        ui.label("vertov").classes("text-h6 font-bold")
        ui.label("control").classes("text-caption text-grey")

    with ui.row().classes("w-full items-start justify-center gap-8 q-mt-md"):
        # -- Camera panel --
        with ui.card().classes("w-80"):
            ui.label("Camera").classes("text-h6")
            ui.html(f'''
            <div style="position:relative;width:100%;border-radius:8px;overflow:hidden;background:#1e1e1e;min-height:180px;">
              <img src="{CINEMATE_MJPEG_URL}"
                   style="width:100%;display:block;"
                   onerror="var m=this.parentElement.querySelector('.reconnect-msg');
                     m.style.display='flex';
                     var self=this;
                     setTimeout(function(){{self.src='{CINEMATE_MJPEG_URL}?t='+Date.now();m.style.display='none'}},2000)">
              <div class="reconnect-msg"
                   style="position:absolute;inset:0;display:none;align-items:center;justify-content:center;
                          color:#888;font-size:14px;background:rgba(0,0,0,0.5);">Reconnecting\u2026</div>
            </div>''')
            global cam_status, cam_info, cam_btn
            cam_status = ui.label("idle").classes("text-caption text-grey")
            cam_info = ui.label("").classes("text-caption text-grey-6")
            cam_btn = ui.button(
                "CAM REC", on_click=toggle_camera
            ).props("color=grey-7 unelevated").classes("w-full")

        # -- Zynthian panel --
        with ui.card().classes("w-80"):
            ui.label("Zynthian").classes("text-h6")
            ui.space().style("height: 200px")
            global zyn_status, zyn_btn
            zyn_status = ui.label("idle").classes("text-caption text-grey")
            ui.label("").classes("text-caption text-grey-6")
            zyn_btn = ui.button(
                "ZYN REC", on_click=toggle_zynthian
            ).props("color=grey-7 unelevated").classes("w-full")

    # Poll every 500ms for live status
    ui.timer(0.5, poll_status)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8080,
        title="vertov",
        favicon="🎬",
        reload=False,
    )
