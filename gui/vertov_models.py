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
        self.status = DeviceStatus.RECORDING if desired_recording else DeviceStatus.STOPPING

    def set_recording(self, active: bool) -> None:
        self.actual_recording = active
        self.status = DeviceStatus.RECORDING if active else DeviceStatus.IDLE
        if active:
            self.started_at = self.started_at or utc_now()
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_device_config(path: str | Path) -> list[DeviceConfig]:
    data = json.loads(Path(path).read_text())
    return [DeviceConfig.from_dict(item) for item in data["devices"]]


def save_manifest(path: str | Path, manifest: TakeManifest) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(manifest.to_json() + "\n")


def save_device_states(path: str | Path, states: dict[str, DeviceState]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({k: v.to_dict() for k, v in states.items()}, indent=2) + "\n")
