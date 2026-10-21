#!/usr/bin/env python3
"""vertov control webinterface MVP.

Controls:
  - Cinepi camera via Redis (start/stop recording)
  - Zynthian audio recorder via OSC/CUIA (start/stop recording)
  - Multi-device config, manifest, and per-device state foundations
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.request
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

import liblo
import redis
from nicegui import ui, app
from starlette.responses import PlainTextResponse, StreamingResponse

from vertov_models import (
    CaptureMode,
    CommandStatus,
    DeviceConfig,
    DeviceRole,
    DeviceState,
    DeviceStatus,
    DeviceType,
    TakeManifest,
    load_device_config,
    load_device_states,
    save_device_states,
    save_manifest,
    utc_now,
)

log = logging.getLogger("vertov.gui")

CINEMATE_REDIS_HOST = os.environ.get("CINEMATE_REDIS_HOST", "localhost")
CINEMATE_REDIS_PORT = int(os.environ.get("CINEMATE_REDIS_PORT", "6379"))
CINEMATE_MJPEG_URL = os.environ.get("CINEMATE_MJPEG_URL", "http://127.0.0.1:8000/stream")
ZYNTHIAN_HOST = os.environ.get("ZYNTHIAN_HOST", "10.40.0.10")
ZYNTHIAN_OSC_PORT = int(os.environ.get("ZYNTHIAN_OSC_PORT", "1370"))
DEVICE_CONFIG_PATH = Path(os.environ.get("VERTOV_DEVICE_CONFIG", str(Path(__file__).with_name("devices.json"))))
STATE_DIR = Path(os.environ.get("VERTOV_STATE_DIR", str(Path(__file__).with_name("state"))))
TAKES_DIR = STATE_DIR / "takes"
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
# restore armed/mode prefs from the last run (armed set itself is frozen per take at REC start)
for _did, _raw in load_device_states(DEVICE_STATES_PATH).items():
    _st = device_states.get(_did)
    if _st is None:
        continue
    _st.armed_video = bool(_raw.get("armed_video", False))
    _st.armed_audio = bool(_raw.get("armed_audio", False))
    with suppress(ValueError):
        _st.capture_mode = CaptureMode(str(_raw.get("capture_mode", "normal")))
    with suppress(TypeError, ValueError):
        _st.mode_param = float(_raw.get("mode_param", 600.0))
osc_addresses: dict[str, liblo.Address] = {}
button_refs: dict[str, ui.button] = {}
status_refs: dict[str, ui.label] = {}
info_refs: dict[str, ui.label] = {}
param_input_refs: dict[str, ui.number] = {}
param_label_refs: dict[str, ui.label] = {}
sweeper_tasks: dict[str, asyncio.Task] = {}
tl_prev_fps: dict[str, str | None] = {}
rolling_take_meta: dict[str, dict] = {}

active_take_manifest: TakeManifest | None = None
master_rec = False


def _cinepi_redis(cfg: DeviceConfig) -> redis.Redis:
    return redis.Redis(
        host=cfg.redis_host or CINEMATE_REDIS_HOST,
        port=cfg.redis_port or CINEMATE_REDIS_PORT,
        decode_responses=True,
    )


def _iso_from_epoch(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _newest_dng_dir(cfg: DeviceConfig) -> Path | None:
    base = Path(cfg.video_dir or "/media/RAW")
    try:
        dirs = [p for p in base.iterdir() if p.is_dir()]
    except OSError:
        return None
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def _param_label(mode: CaptureMode) -> str:
    if mode is CaptureMode.TIMELAPSE:
        return "interval s"
    if mode is CaptureMode.ROLLING:
        return "window s"
    return "n/a"


def _mjpeg_proxy(request):
    """Browser-facing MJPEG proxy.

    The <img> in the device card uses a relative URL, so the browser only ever
    talks to the GUI origin. The GUI fetches the upstream stream (e.g.
    cinemate on 127.0.0.1) server-side and relays the bytes.
    """
    device_id = request.path_params["device_id"]
    cfg = device_configs_by_id.get(device_id)
    upstream_url = (cfg.mjpeg_url if cfg else None) or CINEMATE_MJPEG_URL
    if not upstream_url:
        return PlainTextResponse(f"no stream configured for {device_id}", status_code=404)
    try:
        upstream = urllib.request.urlopen(upstream_url, timeout=10)
    except Exception as exc:
        log.warning("stream proxy upstream error for %s: %s", device_id, exc)
        return PlainTextResponse(f"stream upstream unavailable: {exc}", status_code=502)

    content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame")

    def _relay():
        try:
            while True:
                chunk = upstream.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            with suppress(Exception):
                upstream.close()

    return StreamingResponse(_relay(), media_type=content_type)


app.add_route("/media/stream/{device_id}", _mjpeg_proxy, methods=["GET"])


def persist_runtime_state() -> None:
    save_device_states(DEVICE_STATES_PATH, device_states)
    if active_take_manifest is not None:
        save_manifest(ACTIVE_MANIFEST_PATH, active_take_manifest)
        save_manifest(TAKES_DIR / f"{active_take_manifest.take_id}.json", active_take_manifest)


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
    entry.metadata = dict(state.telemetry)


def set_button_active(btn: ui.button, active: bool) -> None:
    btn.style(ACTIVE_BUTTON_STYLE if active else IDLE_BUTTON_STYLE)


def set_arm(device_id: str, which: str, value: bool) -> None:
    state = device_states.get(device_id)
    if state is None:
        return
    if which == "video":
        state.armed_video = bool(value)
    else:
        state.armed_audio = bool(value)
    persist_runtime_state()
    update_device_model_ui()


def set_mode(device_id: str, mode_value: str) -> None:
    state = device_states.get(device_id)
    if state is None:
        return
    try:
        state.capture_mode = CaptureMode(mode_value)
    except ValueError:
        state.capture_mode = CaptureMode.NORMAL
    pin = param_input_refs.get(device_id)
    if pin is not None:
        (pin.disable if state.capture_mode is CaptureMode.NORMAL else pin.enable)()
    plab = param_label_refs.get(device_id)
    if plab is not None:
        plab.set_text(_param_label(state.capture_mode))
    persist_runtime_state()
    update_device_model_ui()


def set_mode_param(device_id: str, value: float) -> None:
    state = device_states.get(device_id)
    if state is None:
        return
    with suppress(TypeError, ValueError):
        state.mode_param = float(value or 0.0)
    persist_runtime_state()


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
            f"actual={state.actual_recording} reachable={state.reachable} command={state.command_status.value} "
            f"armed V={state.armed_video} A={state.armed_audio} mode={state.capture_mode.value}({state.mode_param})"
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


def _sweep_once(folder: Path, window_s: float) -> int:
    """Delete DNGs older than the rolling window. Never touches other files (e.g. cam0.wav)."""
    cutoff = time.time() - window_s
    removed = 0
    try:
        for p in folder.iterdir():
            try:
                if p.suffix.lower() == ".dng" and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:
                pass
    except OSError:
        pass
    return removed


async def _rolling_sweeper(device_id: str, folder: Path, window_s: float) -> None:
    log.info("rolling sweeper %s on %s (window %.0fs)", device_id, folder, window_s)
    try:
        while True:
            removed = await asyncio.to_thread(_sweep_once, folder, window_s)
            if removed:
                log.info("sweeper %s: removed %d DNGs", device_id, removed)
            await asyncio.sleep(30.0)
    except asyncio.CancelledError:
        raise


async def _resolve_rec_folder(cfg: DeviceConfig, before_newest: str | None, timeout: float = 6.0) -> Path | None:
    """Wait for cinemate to create the new recording folder (name differs from the pre-start newest)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cand = _newest_dng_dir(cfg)
        if cand is not None and (before_newest is None or cand.name != before_newest):
            return cand
        await asyncio.sleep(0.25)
    return _newest_dng_dir(cfg)


async def start_device(device_id: str, *, want_video: bool | None = None, want_audio: bool | None = None) -> None:
    cfg = device_configs_by_id[device_id]
    state = device_states[device_id]
    if want_video is None:
        want_video = cfg.role in (DeviceRole.VIDEO, DeviceRole.HYBRID)
    if want_audio is None:
        want_audio = cfg.role in (DeviceRole.AUDIO, DeviceRole.HYBRID)
    try:
        state.command("start_record", True)
        if cfg.type is DeviceType.CINEPI and want_video:
            rr = _cinepi_redis(cfg)
            mode = state.capture_mode
            if mode is CaptureMode.TIMELAPSE:
                interval = max(0.2, float(state.mode_param or 1.0))
                tl_prev_fps[device_id] = rr.get("fps")
                rr.set("fps", f"{1.0 / interval:.6f}")
                rr.publish("cp_controls", "fps")
            rr.set("is_recording", "1")
            rr.publish("cp_controls", "is_recording")
            state.mark_seen()
            state.set_recording(True)
            if mode is CaptureMode.ROLLING:
                before_newest = _newest_dng_dir(cfg)
                before_newest = before_newest.name if before_newest else None
                folder = await _resolve_rec_folder(cfg, before_newest)
                if folder is None:
                    raise RuntimeError("rolling mode: no DNG folder appeared under video_dir")
                window_s = max(10.0, float(state.mode_param or 600.0))
                rolling_take_meta[device_id] = {"folder": str(folder), "window_s": window_s}
                old = sweeper_tasks.get(device_id)
                if old is not None and not old.done():
                    old.cancel()
                sweeper_tasks[device_id] = asyncio.create_task(
                    _rolling_sweeper(device_id, folder, window_s), name=f"sweeper-{device_id}"
                )
        elif cfg.type is DeviceType.ZYNTHIAN and want_audio:
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


async def stop_device(device_id: str, *, want_video: bool | None = None, want_audio: bool | None = None) -> None:
    cfg = device_configs_by_id[device_id]
    state = device_states[device_id]
    if want_video is None:
        want_video = cfg.role in (DeviceRole.VIDEO, DeviceRole.HYBRID)
    if want_audio is None:
        want_audio = cfg.role in (DeviceRole.AUDIO, DeviceRole.HYBRID)
    try:
        state.command("stop_record", False)
        if cfg.type is DeviceType.CINEPI and want_video:
            rr = _cinepi_redis(cfg)
            rr.set("is_recording", "0")
            rr.publish("cp_controls", "is_recording")
            state.mark_seen()
            state.set_recording(False)
            mode = state.capture_mode
            if mode is CaptureMode.TIMELAPSE and device_id in tl_prev_fps:
                prev = tl_prev_fps.pop(device_id)
                if prev is not None:
                    rr.set("fps", prev)
                    rr.publish("cp_controls", "fps")
            if mode is CaptureMode.ROLLING:
                task = sweeper_tasks.pop(device_id, None)
                if task is not None:
                    task.cancel()
        elif cfg.type is DeviceType.ZYNTHIAN and want_audio:
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


def _armed_snapshot() -> list[tuple[DeviceConfig, bool, bool, CaptureMode, float]]:
    """The armed set, frozen at REC start. Arm/mode changes during a take apply to the next take."""
    armed = []
    for cfg in device_configs:
        state = device_states[cfg.id]
        if not cfg.enabled:
            continue
        av = state.armed_video and cfg.role in (DeviceRole.VIDEO, DeviceRole.HYBRID)
        aa = state.armed_audio and cfg.role in (DeviceRole.AUDIO, DeviceRole.HYBRID)
        if av or aa:
            armed.append((cfg, av, aa, state.capture_mode, state.mode_param))
    return armed


def _finalize_rolling_manifest() -> None:
    """Rolling takes: measure the kept window from surviving DNG mtimes and rewrite started_at."""
    if active_take_manifest is None:
        return
    for entry in active_take_manifest.devices:
        if entry.capture_mode != "rolling":
            continue
        meta = rolling_take_meta.get(entry.device_id) or {}
        folder = Path(meta["folder"]) if meta.get("folder") else None
        if folder is None or not folder.is_dir():
            entry.error = "rolling finalize: rec folder not found"
            continue
        try:
            mtimes = sorted(p.stat().st_mtime for p in folder.iterdir() if p.suffix.lower() == ".dng")
        except OSError as exc:
            entry.error = f"rolling finalize: {exc}"
            continue
        if len(mtimes) < 2:
            entry.error = "rolling finalize: fewer than 2 frames kept"
            entry.mode_params["kept_frames"] = len(mtimes)
            continue
        span = mtimes[-1] - mtimes[0]
        entry.mode_params.update({
            "kept_frames": len(mtimes),
            "video_span_s": round(span, 3),
            "first_frame_ts": _iso_from_epoch(mtimes[0]),
            "last_frame_ts": _iso_from_epoch(mtimes[-1]),
            "window_s": meta.get("window_s", entry.mode_params.get("window_s")),
        })
        if active_take_manifest.metadata.get("session_started_at") is None:
            active_take_manifest.metadata["session_started_at"] = active_take_manifest.started_at
        active_take_manifest.started_at = _iso_from_epoch(mtimes[0])
        entry.metadata["rolling"] = {"kept_frames": len(mtimes), "video_span_s": round(span, 3)}


async def start_all() -> None:
    global active_take_manifest
    armed = _armed_snapshot()
    if not armed:
        ui.notify("no armed devices — arm A/V on a device card first", type="warning")
        return
    active_take_manifest = TakeManifest.new_armed(None, armed)
    active_take_manifest.status = "recording"
    active_take_manifest.started_at = utc_now()
    for cfg, av, aa, _mode, _param in armed:
        state = device_states[cfg.id]
        state.current_take_id = active_take_manifest.take_id
        await start_device(cfg.id, want_video=av, want_audio=aa)
    update_manifest_ui()
    persist_runtime_state()


async def stop_all() -> None:
    global active_take_manifest
    for cfg in device_configs:
        if cfg.enabled:
            await stop_device(cfg.id)
    await asyncio.sleep(0.5)
    if active_take_manifest is not None:
        active_take_manifest.status = "stopped"
        active_take_manifest.stopped_at = utc_now()
        _finalize_rolling_manifest()
    rolling_take_meta.clear()
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
                    state.telemetry.update({
                        "sensor": sensor,
                        "fps": fps,
                        "buffer": buf,
                        "space_left_gb": space,
                    })
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
    state = device_states[cfg.id]
    with ui.card().classes("w-80"):
        ui.label(cfg.name).classes("text-h6")
        if cfg.type is DeviceType.CINEPI and cfg.mjpeg_url:
            ui.html(f'''
            <div style="position:relative;width:100%;border-radius:8px;overflow:hidden;background:#1e1e1e;min-height:180px;">
            <img src="/media/stream/{cfg.id}"
                 style="width:100%;display:block;"
                 onerror="var m=this.parentElement.querySelector('.reconnect-msg');
                   m.style.display='flex';
                   var self=this;
                   setTimeout(function(){{self.src='/media/stream/{cfg.id}?t='+Date.now();m.style.display='none'}},2000)">
              <div class="reconnect-msg"
                   style="position:absolute;inset:0;display:none;align-items:center;justify-content:center;
                          color:#888;font-size:14px;background:rgba(0,0,0,0.5);">Reconnecting…</div>
            </div>''')
        else:
            ui.space().style("height: 200px")
        status_refs[cfg.id] = ui.label("idle").classes("text-caption text-grey")
        info_refs[cfg.id] = ui.label(f"{cfg.type.value} | {cfg.role.value} | {cfg.host}").classes("text-caption text-grey-6")
        with ui.row().classes("w-full items-center gap-2"):
            ui.toggle("ARM V", value=state.armed_video,
                      on_change=lambda e, did=cfg.id: set_arm(did, "video", e.value)).props("dense")
            ui.toggle("ARM A", value=state.armed_audio,
                      on_change=lambda e, did=cfg.id: set_arm(did, "audio", e.value)).props("dense")
        if cfg.role in (DeviceRole.VIDEO, DeviceRole.HYBRID):
            with ui.row().classes("w-full items-center gap-2"):
                ui.select(["normal", "timelapse", "rolling"], value=state.capture_mode.value,
                          on_change=lambda e, did=cfg.id: set_mode(did, e.value)).props("dense").classes("w-40")
                param_label_refs[cfg.id] = ui.label(_param_label(state.capture_mode)).classes("text-caption text-grey-5")
                param_input_refs[cfg.id] = ui.number(value=state.mode_param, format="%.0f",
                                                     on_change=lambda e, did=cfg.id: set_mode_param(did, e.value)
                                                     ).props("dense").classes("w-24")
                if state.capture_mode is CaptureMode.NORMAL:
                    param_input_refs[cfg.id].disable()
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
