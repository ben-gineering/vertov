from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any
import uuid


class DeviceType(str, Enum):
    CINEPI = "cinepi"
    ZYNTHIAN = "zynthian"


class DeviceRole(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    HYBRID = "hybrid"


class CaptureMode(str, Enum):
    NORMAL = "normal"
    TIMELAPSE = "timelapse"
    ROLLING = "rolling"


class DeviceStatus(str, Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"
    ARMING = "arming"
    RECORDING = "recording"
    STOPPING = "stopping"
    ERROR = "error"
    OFFLINE = "offline"


class CommandStatus(str, Enum):
    IDLE = "idle"
    SENT = "sent"
    ACKED = "acked"
    FAILED = "failed"


class IngestStatus(str, Enum):
    NOT_READY = "not_ready"
    PENDING = "pending"
    COPIED = "copied"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(slots=True)
class DeviceConfig:
    id: str
    name: str
    type: DeviceType
    role: DeviceRole
    host: str
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    redis_host: str | None = None
    redis_port: int | None = None
    mjpeg_url: str | None = None
    osc_port: int | None = None
    ssh_user: str | None = None
    capture_dir: str | None = None
    video_dir: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceConfig":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            type=DeviceType(data["type"]),
            role=DeviceRole(data.get("role", data["type"])),
            host=data["host"],
            enabled=data.get("enabled", True),
            tags=list(data.get("tags", [])),
            redis_host=data.get("redis_host"),
            redis_port=data.get("redis_port"),
            mjpeg_url=data.get("mjpeg_url"),
            osc_port=data.get("osc_port"),
            ssh_user=data.get("ssh_user"),
            capture_dir=data.get("capture_dir"),
            video_dir=data.get("video_dir"),
            notes=data.get("notes"),
        )


@dataclass(slots=True)
class DeviceState:
    device_id: str
    reachable: bool = False
    enabled: bool = True
    status: DeviceStatus = DeviceStatus.UNKNOWN
    desired_recording: bool = False
    actual_recording: bool = False
    armed_video: bool = False
    armed_audio: bool = False
    capture_mode: CaptureMode = CaptureMode.NORMAL
    mode_param: float = 600.0
    command_status: CommandStatus = CommandStatus.IDLE
    last_command: str | None = None
    last_command_at: str | None = None
    last_seen_at: str | None = None
    last_error: str | None = None
    current_take_id: str | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    latest_file: str | None = None
    ingest_status: IngestStatus = IngestStatus.NOT_READY
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_config(cls, config: DeviceConfig) -> "DeviceState":
        return cls(device_id=config.id, enabled=config.enabled)

    def mark_seen(self) -> None:
        self.last_seen_at = utc_now()
        self.reachable = True

    def command(self, name: str, desired_recording: bool) -> None:
        self.last_command = name
        self.last_command_at = utc_now()
        self.command_status = CommandStatus.SENT
        self.desired_recording = desired_recording
        if desired_recording:
            self.started_at = utc_now()
            self.stopped_at = None
        self.status = DeviceStatus.RECORDING if desired_recording else DeviceStatus.STOPPING

    def set_recording(self, active: bool) -> None:
        self.actual_recording = active
        self.status = DeviceStatus.RECORDING if active else DeviceStatus.IDLE
        if active:
            self.started_at = utc_now()
            self.stopped_at = None
        else:
            self.stopped_at = utc_now()
        self.command_status = CommandStatus.ACKED
        self.last_error = None

    def set_error(self, message: str) -> None:
        self.last_error = message
        self.status = DeviceStatus.ERROR
        self.command_status = CommandStatus.FAILED


@dataclass(slots=True)
class ManifestDeviceEntry:
    device_id: str
    device_type: DeviceType
    role: DeviceRole
    host: str
    expected: bool = True
    armed_video: bool = True
    armed_audio: bool = False
    capture_mode: str = "normal"
    mode_params: dict[str, Any] = field(default_factory=dict)
    command_status: CommandStatus = CommandStatus.IDLE
    recording_status: DeviceStatus = DeviceStatus.UNKNOWN
    started_at: str | None = None
    stopped_at: str | None = None
    output_file: str | None = None
    ingest_status: IngestStatus = IngestStatus.NOT_READY
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TakeManifest:
    schema_version: str
    take_id: str
    created_at: str
    started_at: str | None = None
    stopped_at: str | None = None
    status: str = "idle"
    scene: str | None = None
    shot: str | None = None
    notes: str | None = None
    devices: list[ManifestDeviceEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, take_id: str | None, devices: list[DeviceConfig]) -> "TakeManifest":
        return cls(
            schema_version="1.0",
            take_id=take_id or f"take_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}",
            created_at=utc_now(),
            devices=[
                ManifestDeviceEntry(
                    device_id=device.id,
                    device_type=device.type,
                    role=device.role,
                    host=device.host,
                    expected=device.enabled,
                )
                for device in devices
            ],
        )

    @classmethod
    def new_armed(cls, take_id: str | None, armed: list[tuple[DeviceConfig, bool, bool, "CaptureMode", float]]) -> "TakeManifest":
        """Manifest over only the armed devices (schema 1.1).

        `armed` items: (config, armed_video, armed_audio, capture_mode, mode_param).
        """
        return cls(
            schema_version="1.1",
            take_id=take_id or f"take_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}",
            created_at=utc_now(),
            devices=[
                ManifestDeviceEntry(
                    device_id=cfg.id,
                    device_type=cfg.type,
                    role=cfg.role,
                    host=cfg.host,
                    expected=True,
                    armed_video=armed_video,
                    armed_audio=armed_audio,
                    capture_mode=mode.value,
                    mode_params=mode_params_for(mode, param),
                )
                for cfg, armed_video, armed_audio, mode, param in armed
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def mode_params_for(mode: CaptureMode, param: float) -> dict[str, Any]:
    if mode is CaptureMode.TIMELAPSE:
        interval = max(0.2, float(param or 1.0))
        return {"interval_s": interval, "capture_fps": round(1.0 / interval, 6), "playback_fps": 25}
    if mode is CaptureMode.ROLLING:
        return {"window_s": max(10.0, float(param or 600.0))}
    return {}


def load_device_config(path: str | Path) -> list[DeviceConfig]:
    data = json.loads(Path(path).read_text())
    return [DeviceConfig.from_dict(item) for item in data["devices"]]


def save_manifest(path: str | Path, manifest: TakeManifest) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(manifest.to_json() + "\n")


def save_device_states(path: str | Path, states: dict[str, DeviceState]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({k: v.to_dict() for k, v in states.items()}, indent=2) + "\n")


def load_device_states(path: str | Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
