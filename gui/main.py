#!/usr/bin/env python3
"""vertov control webinterface MVP.

Controls:
  - Cinepi camera via Redis (start/stop recording)
  - Zynthian audio recorder via OSC/CUIA (start/stop recording)
  - Multi-device config, manifest, and per-device state foundations
"""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from pathlib import Path

import liblo
import redis
from nicegui import ui

from vertov_models import (
    CommandStatus,
    DeviceConfig,
    DeviceRole,
    DeviceState,
    DeviceStatus,
    DeviceType,
    TakeManifest,
    load_device_config,
    save_device_states,
    save_manifest,
    utc_now,
)

log = logging.getLogger("vertov.gui")

CINEMATE_REDIS_HOST = os.environ.get("CINEMATE_REDIS_HOST", "localhost")
CINEMATE_REDIS_PORT = int(os.environ.get("CINEMATE_REDIS_PORT", "6379"))
CINEMATE_MJPEG_URL = os.environ.get("CINEMATE_MJPEG_URL", "http://10.0.0.186:8000/stream")
ZYNTHIAN_HOST = os.environ.get("ZYNTHIAN_HOST", "10.40.0.10")
ZYNTHIAN_OSC_PORT = int(os.environ.get("ZYNTHIAN_OSC_PORT", "1370"))
DEVICE_CONFIG_PATH = Path(os.environ.get("VERTOV_DEVICE_CONFIG", str(Path(__file__).with_name("devices.example.json"))))
STATE_DIR = Path(os.environ.get("VERTOV_STATE_DIR", str(Path(__file__).with_name("state"))))
ACTIVE_MANIFEST_PATH = STATE_DIR / "active_take_manifest.json"
DEVICE_STATES_PATH = STATE_DIR / "device_states.json"

ACTIVE_BUTTON_STYLE = "background: #c62828 !important; color: white !important;"
IDLE_BUTTON_STYLE = "background: #757575 !important; color: white !important;"

rdb = redis.Redis(host=CINEMATE_REDIS_HOST, port=CINEMATE_REDIS_PORT, decode_responses=True)

with suppress(Exception):
    device_configs = load_device_config(DEVICE_CONFIG_PATH)
if "device_configs" not in globals():
    device_configs = []

device_configs_by_id: dict[str, DeviceConfig] = {cfg.id: cfg for cfg in device_configs}
device_states: dict[str, DeviceState] = {cfg.id: DeviceState.from_config(cfg) for cfg in device_configs}
osc_addresses: dict[str, liblo.Address] = {}
button_refs: dict[str, ui.button] = {}
status_refs: dict[str, ui.label] = {}
info_refs: dict[str, ui.label] = {}

active_take_manifest: TakeManifest | None = None
master_rec = False


def persist_runtime_state() -> None:
    save_device_states(DEVICE_STATES_PATH, device_states)
    if active_take_manifest is not None:
        save_manifest(ACTIVE_MANIFEST_PATH, active_take_manifest)


def take_entry(device_id: str):
    if active_take_manifest is None:
        return None
    for entry in active_take_manifest.devices:
        if entry.device_id == device_id:
            return entry
    return None


def update_take_entry_from_state(device_id: str) -> None:
    entry = take_entry(device_id)
    state = device_states.get(device_id)
    if entry is None or state is None:
        return
    entry.command_status = state.command_status
    entry.recording_status = state.status
    entry.started_at = state.started_at
    entry.stopped_at = state.stopped_at
    entry.output_file = state.latest_file
    entry.ingest_status = state.ingest_status
    entry.error = state.last_error


def set_button_active(btn: ui.button, active: bool) -> None:
    btn.style(ACTIVE_BUTTON_STYLE if active else IDLE_BUTTON_STYLE)


def update_device_card(device_id: str) -> None:
    state = device_states[device_id]
    cfg = device_configs_by_id[device_id]
    if device_id in button_refs:
        set_button_active(button_refs[device_id], state.actual_recording)
    if device_id in status_refs:
        status_refs[device_id].set_text(state.status.value)
    if device_id in info_refs:
        details = [cfg.type.value, cfg.role.value, cfg.host]
        if state.last_error:
            details.append(f"error: {state.last_error}")
        info_refs[device_id].set_text(" | ".join(details))


def update_master_ui() -> None:
    global master_rec
    master_rec = any(state.actual_recording for state in device_states.values() if state.enabled)
    set_button_active(master_start_btn, master_rec)
    set_button_active(master_stop_btn, False)
    master_status.set_text("RECORDING" if master_rec else "idle")


def update_device_model_ui() -> None:
    if not device_states:
        device_model_status.set_text("No device config loaded")
        return
    lines = []
    for device_id, state in device_states.items():
        lines.append(
            f"{device_id}: status={state.status.value} desired={state.desired_recording} "
            f"actual={state.actual_recording} reachable={state.reachable} command={state.command_status.value}"
        )
    device_model_status.set_text("\n".join(lines))


def update_manifest_ui() -> None:
    if active_take_manifest is None:
        manifest_status.set_text("No active take")
        return
    manifest_status.set_text(active_take_manifest.to_json())


def apply_state(device_id: str, *, reachable: bool | None = None, actual_recording: bool | None = None,
                desired_recording: bool | None = None, status: DeviceStatus | None = None,
                command_status: CommandStatus | None = None, error: str | None = None) -> None:
    state = device_states[device_id]
    if reachable is not None:
        state.reachable = reachable
        if reachable:
            state.last_seen_at = utc_now()
    if desired_recording is not None:
        state.desired_recording = desired_recording
    if actual_recording is not None:
        state.actual_recording = actual_recording
        state.status = DeviceStatus.RECORDING if actual_recording else DeviceStatus.IDLE
    if status is not None:
        state.status = status
    if command_status is not None:
        state.command_status = command_status
    if error is not None:
        state.last_error = error
    update_take_entry_from_state(device_id)
    update_device_card(device_id)
    update_master_ui()
    update_device_model_ui()
    update_manifest_ui()
    persist_runtime_state()


def start_device(device_id: str) -> None:
    cfg = device_configs_by_id[device_id]
    state = device_states[device_id]
    try:
        state.command("start_record", True)
        if cfg.type is DeviceType.CINEPI:
            redis_host = cfg.redis_host or CINEMATE_REDIS_HOST
            redis_port = cfg.redis_port or CINEMATE_REDIS_PORT
            redis.Redis(host=redis_host, port=redis_port, decode_responses=True).set("is_recording", "1")
            redis.Redis(host=redis_host, port=redis_port, decode_responses=True).publish("cp_controls", "is_recording")
            state.mark_seen()
            state.set_recording(True)
        elif cfg.type is DeviceType.ZYNTHIAN:
            addr = osc_addresses.setdefault(device_id, liblo.Address(cfg.host, cfg.osc_port or ZYNTHIAN_OSC_PORT))
            liblo.send(addr, "/CUIA/START_AUDIO_RECORD")
            state.mark_seen()
            state.set_recording(True)
        update_take_entry_from_state(device_id)
        update_device_card(device_id)
        update_master_ui()
        update_device_model_ui()
        update_manifest_ui()
        persist_runtime_state()
    except Exception as exc:
        state.set_error(str(exc))
        update_take_entry_from_state(device_id)
        update_device_card(device_id)
        update_device_model_ui()
        update_manifest_ui()
        persist_runtime_state()
        log.error("start failed for %s: %s", device_id, exc)
        ui.notify(f"{cfg.name} error: {exc}", type="negative")


def stop_device(device_id: str) -> None:
    cfg = device_configs_by_id[device_id]
    state = device_states[device_id]
    try:
        state.command("stop_record", False)
        if cfg.type is DeviceType.CINEPI:
            redis_host = cfg.redis_host or CINEMATE_REDIS_HOST
            redis_port = cfg.redis_port or CINEMATE_REDIS_PORT
            redis.Redis(host=redis_host, port=redis_port, decode_responses=True).set("is_recording", "0")
            redis.Redis(host=redis_host, port=redis_port, decode_responses=True).publish("cp_controls", "is_recording")
            state.mark_seen()
            state.set_recording(False)
        elif cfg.type is DeviceType.ZYNTHIAN:
            addr = osc_addresses.setdefault(device_id, liblo.Address(cfg.host, cfg.osc_port or ZYNTHIAN_OSC_PORT))
            liblo.send(addr, "/CUIA/STOP_AUDIO_RECORD")
            state.mark_seen()
            state.set_recording(False)
        update_take_entry_from_state(device_id)
        update_device_card(device_id)
        update_master_ui()
        update_device_model_ui()
        update_manifest_ui()
        persist_runtime_state()
    except Exception as exc:
        state.set_error(str(exc))
        update_take_entry_from_state(device_id)
        update_device_card(device_id)
        update_device_model_ui()
        update_manifest_ui()
        persist_runtime_state()
        log.error("stop failed for %s: %s", device_id, exc)
        ui.notify(f"{cfg.name} error: {exc}", type="negative")


def start_all() -> None:
    global active_take_manifest
    active_take_manifest = TakeManifest.new(None, device_configs)
    active_take_manifest.status = "recording"
    active_take_manifest.started_at = utc_now()
    for state in device_states.values():
        state.current_take_id = active_take_manifest.take_id
    update_manifest_ui()
    persist_runtime_state()
    for cfg in device_configs:
        if cfg.enabled:
            start_device(cfg.id)


def stop_all() -> None:
    global active_take_manifest
    for cfg in device_configs:
        if cfg.enabled:
            stop_device(cfg.id)
    if active_take_manifest is not None:
        active_take_manifest.status = "stopped"
        active_take_manifest.stopped_at = utc_now()
    update_manifest_ui()
    persist_runtime_state()


def poll_status() -> None:
    for cfg in device_configs:
        state = device_states[cfg.id]
        with suppress(Exception):
            if cfg.type is DeviceType.CINEPI:
                redis_host = cfg.redis_host or CINEMATE_REDIS_HOST
                redis_port = cfg.redis_port or CINEMATE_REDIS_PORT
                rr = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
                is_rec = rr.get("is_recording") == "1"
                state.mark_seen()
                state.actual_recording = is_rec
                state.status = DeviceStatus.RECORDING if is_rec else DeviceStatus.IDLE
                if cfg.id in info_refs:
                    fps = rr.get("fps_actual")
                    buf = rr.get("buffer")
                    space = rr.get("space_left")
                    sensor = rr.get("sensor")
                    parts = [p for p in [sensor and f"sensor: {sensor}", fps and f"fps: {fps}", buf and f"buffer: {buf}", space and f"space: {space}GB"] if p]
                    info_refs[cfg.id].set_text(" | ".join([cfg.type.value, cfg.role.value, cfg.host] + parts))
            elif cfg.type is DeviceType.ZYNTHIAN:
                state.mark_seen()
        update_take_entry_from_state(cfg.id)
        update_device_card(cfg.id)
    update_master_ui()
    update_device_model_ui()
    update_manifest_ui()
    persist_runtime_state()


def build_device_card(cfg: DeviceConfig) -> None:
    with ui.card().classes("w-80"):
        ui.label(cfg.name).classes("text-h6")
        if cfg.type is DeviceType.CINEPI and cfg.mjpeg_url:
            ui.html(f'''
            <div style="position:relative;width:100%;border-radius:8px;overflow:hidden;background:#1e1e1e;min-height:180px;">
              <img src="{cfg.mjpeg_url}"
                   style="width:100%;display:block;"
                   onerror="var m=this.parentElement.querySelector('.reconnect-msg');
                     m.style.display='flex';
                     var self=this;
                     setTimeout(function(){{self.src='{cfg.mjpeg_url}?t='+Date.now();m.style.display='none'}},2000)">
              <div class="reconnect-msg"
                   style="position:absolute;inset:0;display:none;align-items:center;justify-content:center;
                          color:#888;font-size:14px;background:rgba(0,0,0,0.5);">Reconnecting…</div>
            </div>''')
        else:
            ui.space().style("height: 200px")
        status_refs[cfg.id] = ui.label("idle").classes("text-caption text-grey")
        info_refs[cfg.id] = ui.label(f"{cfg.type.value} | {cfg.role.value} | {cfg.host}").classes("text-caption text-grey-6")
        with ui.row().classes("w-full gap-2"):
            rec_label = "CAM REC" if cfg.type is DeviceType.CINEPI else "ZYN REC"
            stop_label = "CAM STOP" if cfg.type is DeviceType.CINEPI else "ZYN STOP"
            button_refs[cfg.id] = ui.button(rec_label, on_click=lambda did=cfg.id: start_device(did)).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)
            ui.button(stop_label, on_click=lambda did=cfg.id: stop_device(did)).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)


@ui.page("/")
def main_page() -> None:
    ui.add_css("body { background: #121212; color: #e0e0e0; }")

    with ui.header().classes("items-center justify-between").style("background: #1a1a1a;"):
        ui.label("vertov").classes("text-h6 font-bold")
        ui.label("control").classes("text-caption text-grey")

    with ui.row().classes("w-full items-start justify-center gap-8 q-mt-md"):
        for cfg in device_configs:
            build_device_card(cfg)

        with ui.card().classes("w-80"):
            ui.label("Master").classes("text-h6")
            ui.space().style("height: 200px")
            global master_status, master_start_btn, master_stop_btn
            master_status = ui.label("idle").classes("text-caption text-grey")
            ui.label("start/stop all enabled devices").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2"):
                master_start_btn = ui.button("START REC", on_click=start_all).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)
                master_stop_btn = ui.button("STOP REC", on_click=stop_all).props("unelevated").classes("w-full").style(IDLE_BUTTON_STYLE)

    with ui.row().classes("w-full items-start gap-4 q-mt-md"):
        with ui.card().classes("w-full"):
            ui.label("Device model").classes("text-subtitle2")
            global device_model_status
            device_model_status = ui.label("").classes("text-caption text-grey-5 whitespace-pre-wrap")
        with ui.card().classes("w-full"):
            ui.label("Active manifest").classes("text-subtitle2")
            global manifest_status
            manifest_status = ui.label("").classes("text-caption text-grey-5 whitespace-pre-wrap")

    update_device_model_ui()
    update_manifest_ui()
    ui.timer(0.5, poll_status)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8080, title="vertov", favicon="🎬", reload=False)
