#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vertov_models import load_device_config, utc_now

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DEVICE_CONFIG = BASE_DIR / "devices.json"
DEFAULT_INGEST_CONFIG = BASE_DIR / "ingest" / "config.json"
VIDEO_EXTS = {".mp4", ".mov", ".mkv"}
AUDIO_EXTS = {".wav"}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def ssh_target(user: str, host: str) -> str:
    return f"{user}@{host}"


def fetch_remote_file(user: str, host: str, remote_path: str, local_path: Path, dry_run: bool) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-av", f"{ssh_target(user, host)}:{remote_path}", str(local_path)]
    if dry_run:
        print("DRY RUN:", shlex.join(cmd))
        return
    run(cmd)


def fetch_manifest_latest(cfg: dict[str, Any], dest: Path, dry_run: bool) -> Path:
    vh = cfg["vertov_host"]
    remote = vh["active_manifest"]
    if dry_run:
        print("DRY RUN: fetch manifest", remote)
        return dest
    run(["rsync", "-av", f"{ssh_target(vh['ssh_user'], vh['host'])}:{remote}", str(dest)])
    return dest / Path(remote).name


def fetch_manifest_take(cfg: dict[str, Any], take_id: str, dest: Path, dry_run: bool) -> Path:
    vh = cfg["vertov_host"]
    remote = f"{vh['manifest_dir'].rstrip('/')}/{take_id}.json"
    if dry_run:
        print("DRY RUN: fetch manifest", remote)
        return dest / f"{take_id}.json"
    run(["rsync", "-av", f"{ssh_target(vh['ssh_user'], vh['host'])}:{remote}", str(dest)])
    return dest / f"{take_id}.json"


def remote_find_candidates(user: str, host: str, remote_dir: str, exts: set[str]) -> list[dict[str, Any]]:
    ext_args = " -o ".join([f"-name '*{ext}'" for ext in sorted(exts)])
    cmd = (
        f"find {shlex.quote(remote_dir)} -maxdepth 1 -type f \\( {ext_args} \\) "
        "-printf '%T@\t%p\n' | sort -n"
    )
    cp = run(["ssh", ssh_target(user, host), cmd])
    items = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        ts_raw, path = line.split("\t", 1)
        items.append({"ts": float(ts_raw), "path": path})
    return items


def choose_candidates(manifest: dict[str, Any], device: dict[str, Any], device_cfg: dict[str, Any], ingest_cfg: dict[str, Any]) -> list[str]:
    if device.get("output_file"):
        return [device["output_file"]]
    start = parse_ts(device.get("started_at") or manifest.get("started_at"))
    stop = parse_ts(device.get("stopped_at") or manifest.get("stopped_at"))
    if not start or not stop:
        return []
    start_margin = ingest_cfg["matching"]["start_margin_sec"]
    stop_margin = ingest_cfg["matching"]["stop_margin_sec"]
    start_epoch = start.timestamp() - start_margin
    stop_epoch = stop.timestamp() + stop_margin
    remote_dir = device_cfg.get("video_dir") or device_cfg.get("capture_dir")
    if not remote_dir:
        return []
    exts = VIDEO_EXTS if device_cfg["type"] == "cinepi" else AUDIO_EXTS
    candidates = remote_find_candidates(device_cfg["ssh_user"], device_cfg["host"], remote_dir, exts)
    matches = [item["path"] for item in candidates if start_epoch <= item["ts"] <= stop_epoch]
    if ingest_cfg["matching"].get("pull_all_matches", True):
        return matches
    return matches[-1:] if matches else []


def ingest_from_manifest(manifest: dict[str, Any], devices_cfg: dict[str, Any], ingest_cfg: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    root_dir = Path(ingest_cfg["local_storage"]["root_dir"]).expanduser()
    take_dir = root_dir / manifest["take_id"]
    report = {
        "take_id": manifest["take_id"],
        "ingested_at": utc_now(),
        "destination": str(take_dir),
        "dry_run": dry_run,
        "devices": [],
    }
    if not dry_run:
        take_dir.mkdir(parents=True, exist_ok=True)
        (take_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    device_index = {d["id"]: d for d in devices_cfg["devices"]}
    for device in manifest.get("devices", []):
        device_id = device["device_id"]
        entry = {
            "device_id": device_id,
            "status": "skipped",
            "remote_dir": None,
            "remote_files": [],
            "local_files": [],
            "error": None,
        }
        cfg = device_index.get(device_id)
        if not cfg or not device.get("expected", True):
            report["devices"].append(entry)
            continue
        entry["remote_dir"] = cfg.get("video_dir") or cfg.get("capture_dir")
        try:
            remote_files = choose_candidates(manifest, device, cfg, ingest_cfg)
            entry["remote_files"] = remote_files
            for remote_file in remote_files:
                local_name = f"{device_id}_{Path(remote_file).name}"
                local_path = take_dir / local_name
                fetch_remote_file(cfg["ssh_user"], cfg["host"], remote_file, local_path, dry_run)
                entry["local_files"].append(str(local_path))
            entry["status"] = "copied" if remote_files else "no_matches"
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
        report["devices"].append(entry)
    if not dry_run:
        (take_dir / "ingest_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def cmd_latest(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    tmp_dir = Path("/tmp/vertov_pull")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = fetch_manifest_latest(ingest_cfg, tmp_dir, args.dry_run)
    manifest = load_json(manifest_path) if manifest_path.exists() else {"take_id": "dry_run", "devices": []}
    print(json.dumps(ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run), indent=2))


def cmd_take(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    tmp_dir = Path("/tmp/vertov_pull")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = fetch_manifest_take(ingest_cfg, args.take_id, tmp_dir, args.dry_run)
    manifest = load_json(manifest_path) if manifest_path.exists() else {"take_id": args.take_id, "devices": []}
    print(json.dumps(ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run), indent=2))


def cmd_manifest(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    manifest = load_json(Path(args.manifest_path))
    print(json.dumps(ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run), indent=2))


def cmd_report(args):
    print(json.dumps(load_json(Path(args.report_path)), indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--devices-config", default=str(DEFAULT_DEVICE_CONFIG))
    p.add_argument("--ingest-config", default=str(DEFAULT_INGEST_CONFIG))
    sub = p.add_subparsers(dest="command", required=True)

    latest = sub.add_parser("latest")
    latest.add_argument("--dry-run", action="store_true")
    latest.set_defaults(func=cmd_latest)

    take = sub.add_parser("take")
    take.add_argument("take_id")
    take.add_argument("--dry-run", action="store_true")
    take.set_defaults(func=cmd_take)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("manifest_path")
    manifest.add_argument("--dry-run", action="store_true")
    manifest.set_defaults(func=cmd_manifest)

    report = sub.add_parser("report")
    report.add_argument("report_path")
    report.set_defaults(func=cmd_report)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
