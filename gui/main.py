#!/usr/bin/env python3
"""vertov control webinterface MVP.

Controls:
  - Cinemate camera via local Redis (start/stop recording)
  - Zynthian synth via OSC/CUIA (start/stop audio recording)

Requires: nicegui, redis, liblo
"""

import logging
import os
from contextlib import suppress

import liblo
import redis
from nicegui import app, ui

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
zynthian_osc_addr = liblo.Address(ZYNTHIAN_HOST, ZYNTHIAN_OSC_PORT)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
camera_rec = False
zynthian_rec = False
master_rec = False  # Track combined recording state

ACTIVE_BUTTON_STYLE = "background: #c62828 !important; color: white !important;"
IDLE_BUTTON_STYLE = "background: #757575 !important; color: white !important;"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def start_camera() -> None:
    global camera_rec
    try:
        rdb.set("is_recording", "1")
        rdb.publish("cp_controls", "is_recording")
        camera_rec = True
        log.info("Camera START requested")
        update_camera_ui()
    except Exception as exc:
        log.error("camera start failed: %s", exc)
        ui.notify(f"Camera error: {exc}", type="negative")


def stop_camera() -> None:
    global camera_rec
    try:
        rdb.set("is_recording", "0")
        rdb.publish("cp_controls", "is_recording")
        camera_rec = False
        log.info("Camera STOP requested")
        update_camera_ui()
    except Exception as exc:
        log.error("camera stop failed: %s", exc)
        ui.notify(f"Camera error: {exc}", type="negative")


def start_all() -> None:
    start_camera()
    start_zynthian()


def stop_all() -> None:
    stop_camera()
    stop_zynthian()


def start_zynthian() -> None:
    global zynthian_rec
    try:
        liblo.send(zynthian_osc_addr, "/CUIA/START_AUDIO_RECORD")
        zynthian_rec = True
        log.info("Zynthian START requested")
        update_zynthian_ui()
    except Exception as exc:
        log.error("zynthian start failed: %s", exc)
        ui.notify(f"Zynthian error: {exc}", type="negative")


def stop_zynthian() -> None:
    global zynthian_rec
    try:
        liblo.send(zynthian_osc_addr, "/CUIA/STOP_AUDIO_RECORD")
        zynthian_rec = False
        log.info("Zynthian STOP requested")
        update_zynthian_ui()
    except Exception as exc:
        log.error("zynthian stop failed: %s", exc)
        ui.notify(f"Zynthian error: {exc}", type="negative")


# ---------------------------------------------------------------------------
# UI Updates
# ---------------------------------------------------------------------------
def set_button_active(btn, active: bool) -> None:
    btn.style(ACTIVE_BUTTON_STYLE if active else IDLE_BUTTON_STYLE)


def update_camera_ui_direct(is_rec: bool) -> None:
    """Update Camera UI directly from polled value (used by poll_status)."""
    global cam_start_btn, cam_stop_btn, cam_status
    set_button_active(cam_start_btn, is_rec)
    set_button_active(cam_stop_btn, False)
    cam_status.set_text("RECORDING" if is_rec else "idle")


def update_camera_ui() -> None:
    update_camera_ui_direct(camera_rec)


def update_zynthian_ui() -> None:
    """Update Zynthian button colors and status based on local state."""
    global zyn_start_btn, zyn_stop_btn, zyn_status
    set_button_active(zyn_start_btn, zynthian_rec)
    set_button_active(zyn_stop_btn, False)
    zyn_status.set_text("RECORDING" if zynthian_rec else "idle")


def update_master_ui() -> None:
    """Update Master panel button colors and status."""
    global master_start_btn, master_stop_btn, master_status
    set_button_active(master_start_btn, master_rec)
    set_button_active(master_stop_btn, False)
    master_status.set_text("RECORDING" if master_rec else "idle")


# ---------------------------------------------------------------------------
# Live status polling
# ---------------------------------------------------------------------------
def poll_status() -> None:
    """Poll recording states and update UI."""
    global master_rec
    with suppress(Exception):
        # Camera: poll actual state from Redis (source of truth)
        # Don't use local variable to avoid race condition with user actions
        cam_val = rdb.get("is_recording")
        cam_is_rec = cam_val == "1"
        update_camera_ui_direct(cam_is_rec)

        # Zynthian: use locally tracked state (no OSC query available)
        update_zynthian_ui()

        # Master: derived from camera + zynthian state
        master_rec = cam_is_rec or zynthian_rec
        update_master_ui()

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
            global cam_status, cam_info, cam_start_btn, cam_stop_btn
            cam_status = ui.label("idle").classes("text-caption text-grey")
            cam_info = ui.label("").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2"):
                cam_start_btn = ui.button(
                    "CAM REC", on_click=start_camera
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)
                cam_stop_btn = ui.button(
                    "CAM STOP", on_click=stop_camera
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)

        # -- Zynthian panel --
        with ui.card().classes("w-80"):
            ui.label("Zynthian").classes("text-h6")
            ui.space().style("height: 200px")
            global zyn_status, zyn_start_btn, zyn_stop_btn
            zyn_status = ui.label("idle").classes("text-caption text-grey")
            ui.label("").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2"):
                zyn_start_btn = ui.button(
                    "ZYN REC", on_click=start_zynthian
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)
                zyn_stop_btn = ui.button(
                    "ZYN STOP", on_click=stop_zynthian
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)

        # -- Master panel --
        with ui.card().classes("w-80"):
            ui.label("Master").classes("text-h6")
            ui.space().style("height: 200px")
            global master_status, master_start_btn, master_stop_btn
            master_status = ui.label("idle").classes("text-caption text-grey")
            ui.label("").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2"):
                master_start_btn = ui.button(
                    "START REC", on_click=start_all
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)
                master_stop_btn = ui.button(
                    "STOP REC", on_click=stop_all
                ).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)

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
