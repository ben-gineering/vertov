#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vertov_models import utc_now

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DEVICE_CONFIG = BASE_DIR / "devices.json"
DEFAULT_INGEST_CONFIG = BASE_DIR / "ingest" / "config.json"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".dng"}
AUDIO_EXTS = {".wav"}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def run_stream(cmd: list[str]) -> None:
    """Like run(), but lets output flow straight to the terminal (rsync --info=progress2)."""
    subprocess.run(cmd, check=True, text=True)


def ssh_target(user: str, host: str) -> str:
    return f"{user}@{host}"


def fetch_remote_path(user: str, host: str, remote_path: str, local_path: Path, dry_run: bool, stream: bool = False) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_spec = f"{ssh_target(user, host)}:{remote_path}"
    if stream:
        cmd = ["rsync", "-a", "--info=progress2", remote_spec, str(local_path)]
    else:
        cmd = ["rsync", "-av", remote_spec, str(local_path)]
    if dry_run:
        print("DRY RUN:", shlex.join(cmd))
        return
    if stream:
        run_stream(cmd)
    else:
        run(cmd)


def fetch_manifest_latest(cfg: dict[str, Any], dest: Path, dry_run: bool) -> Path:
    # manifests are tiny read-only metadata — fetched even on --dry-run so the summary works
    vh = cfg["vertov_host"]
    remote = vh["active_manifest"]
    local_path = dest / Path(remote).name
    run(["rsync", "-av", f"{ssh_target(vh['ssh_user'], vh['host'])}:{remote}", str(dest)])
    return local_path


def fetch_manifest_take(cfg: dict[str, Any], take_id: str, dest: Path, dry_run: bool) -> Path:
    vh = cfg["vertov_host"]
    remote = f"{vh['manifest_dir'].rstrip('/')}/{take_id}.json"
    local_path = dest / f"{take_id}.json"
    run(["rsync", "-av", f"{ssh_target(vh['ssh_user'], vh['host'])}:{remote}", str(dest)])
    return local_path


def remote_find_file_candidates(user: str, host: str, remote_dir: str, exts: set[str]) -> list[dict[str, Any]]:
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


def remote_find_dir_candidates(user: str, host: str, remote_dir: str) -> list[dict[str, Any]]:
    cmd = (
        f"find {shlex.quote(remote_dir)} -mindepth 1 -maxdepth 1 -type d "
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
    if device_cfg["type"] == "cinepi":
        candidates = remote_find_dir_candidates(device_cfg["ssh_user"], device_cfg["host"], remote_dir)
    else:
        candidates = remote_find_file_candidates(device_cfg["ssh_user"], device_cfg["host"], remote_dir, AUDIO_EXTS)
    matches = [item["path"] for item in candidates if start_epoch <= item["ts"] <= stop_epoch]
    if ingest_cfg["matching"].get("pull_all_matches", True):
        return matches
    return matches[-1:] if matches else []


def remote_size(user: str, host: str, remote_path: str) -> int | None:
    """Byte size of a remote dir/file (du -sb); None if unreachable."""
    try:
        cp = run(["ssh", ssh_target(user, host), f"du -sb -- {shlex.quote(remote_path)}"])
        return int(cp.stdout.split()[0])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return None


def human_size(n: int | None) -> str:
    if n is None:
        return "n/a"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{n} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "n/a"


def print_take_summary(manifest: dict[str, Any], devices_cfg: dict[str, Any], ingest_cfg: dict[str, Any], dry_run: bool) -> None:
    print(f"take:     {manifest.get('take_id')}")
    print(f"status:   {manifest.get('status')}")
    print(f"notes:    {manifest.get('notes') or '-'}")
    print(f"window:   {manifest.get('started_at')} -> {manifest.get('stopped_at')}")
    device_index = {d["id"]: d for d in devices_cfg["devices"]}
    total = 0
    for device in manifest.get("devices", []):
        device_id = device["device_id"]
        cfg = device_index.get(device_id)
        if not cfg or not device.get("expected", True):
            print(f"  - {device_id}: not expected / no config -> skipped")
            continue
        mode = device.get("capture_mode", "normal")
        params = device.get("mode_params") or {}
        param_str = " ".join(f"{k}={v}" for k, v in params.items())
        print(f"  - {device_id} [{cfg['type']}] mode={mode} {param_str}")
        try:
            for cand in choose_candidates(manifest, device, cfg, ingest_cfg):
                size = remote_size(cfg["ssh_user"], cfg["host"], cand)
                if size is not None:
                    total += size
                print(f"      {cand}  ({human_size(size)})")
        except subprocess.CalledProcessError as exc:
            print(f"      (unreachable: {exc.returncode})")
    print(f"total:    {human_size(total)}")


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
                if cfg["type"] == "cinepi":
                    local_path.mkdir(parents=True, exist_ok=True) if not dry_run else None
                    fetch_remote_path(cfg["ssh_user"], cfg["host"], remote_file.rstrip("/") + "/", local_path, dry_run, stream=True)
                else:
                    fetch_remote_path(cfg["ssh_user"], cfg["host"], remote_file, local_path, dry_run, stream=True)
                entry["local_files"].append(str(local_path))
            entry["status"] = "copied" if remote_files else "no_matches"
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
        report["devices"].append(entry)
    if not dry_run:
        (take_dir / "ingest_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def maybe_run_post(report: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    take_dir = report.get("destination")
    if not take_dir:
        return
    reply = input("Run vertov_post.py full on this take? [Y/n] ").strip().lower()
    if reply in {"", "y", "yes"}:
        subprocess.run(["python3", str(BASE_DIR / "vertov_post.py"), "full", take_dir], check=False)


def cmd_latest(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    tmp_dir = Path("/tmp/vertov_pull")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = fetch_manifest_latest(ingest_cfg, tmp_dir, args.dry_run)
    manifest = load_json(manifest_path) if manifest_path.exists() else {"take_id": "dry_run", "devices": []}
    print_take_summary(manifest, devices_cfg, ingest_cfg, args.dry_run)
    report = ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run)
    print(json.dumps(report, indent=2))
    maybe_run_post(report, args.dry_run)


def cmd_take(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    tmp_dir = Path("/tmp/vertov_pull")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = fetch_manifest_take(ingest_cfg, args.take_id, tmp_dir, args.dry_run)
    manifest = load_json(manifest_path) if manifest_path.exists() else {"take_id": args.take_id, "devices": []}
    print_take_summary(manifest, devices_cfg, ingest_cfg, args.dry_run)
    report = ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run)
    print(json.dumps(report, indent=2))
    maybe_run_post(report, args.dry_run)


def cmd_manifest(args):
    ingest_cfg = load_json(Path(args.ingest_config))
    devices_cfg = load_json(Path(args.devices_config))
    manifest = load_json(Path(args.manifest_path))
    print_take_summary(manifest, devices_cfg, ingest_cfg, args.dry_run)
    report = ingest_from_manifest(manifest, devices_cfg, ingest_cfg, args.dry_run)
    print(json.dumps(report, indent=2))
    maybe_run_post(report, args.dry_run)


def cmd_takes(args):
    """List all manifests from the Pi: id | date | status | duration | devices."""
    ingest_cfg = load_json(Path(args.ingest_config))
    vh = ingest_cfg["vertov_host"]
    dest = Path("/tmp/vertov_pull/manifests")
    dest.mkdir(parents=True, exist_ok=True)
    run(["rsync", "-a", f"{ssh_target(vh['ssh_user'], vh['host'])}:{vh['manifest_dir'].rstrip('/')}/*", str(dest)])
    count = 0
    for p in sorted(dest.glob("*.json")):
        try:
            m = load_json(p)
        except ValueError:
            continue
        count += 1
        start = parse_ts(m.get("started_at"))
        stop = parse_ts(m.get("stopped_at"))
        dur = f"{(stop - start).total_seconds():.0f}s" if start and stop else "-"
        devices = " ".join(f"{d['device_id']}[{d.get('capture_mode', 'normal')}]" for d in m.get("devices", []))
        print(f"{m.get('take_id', p.stem):<34} {str(m.get('created_at'))[:10]:<11} {str(m.get('status')):<9} {dur:>8}  {devices}")
    print(f"{count} takes")


def cmd_report(args):
    print(json.dumps(load_json(Path(args.report_path)), indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pull vertov takes from the Pi and optionally run post.")
    p.add_argument("--devices-config", default=str(DEFAULT_DEVICE_CONFIG))
    p.add_argument("--ingest-config", default=str(DEFAULT_INGEST_CONFIG))
    sub = p.add_subparsers(dest="command")

    latest = sub.add_parser("latest", help="pull the newest take (active manifest)")
    latest.add_argument("--dry-run", action="store_true")
    latest.set_defaults(func=cmd_latest)

    take = sub.add_parser("take", help="pull a take by id (see 'takes')")
    take.add_argument("take_id")
    take.add_argument("--dry-run", action="store_true")
    take.set_defaults(func=cmd_take)

    manifest = sub.add_parser("manifest", help="pull from a local manifest json")
    manifest.add_argument("manifest_path")
    manifest.add_argument("--dry-run", action="store_true")
    manifest.set_defaults(func=cmd_manifest)

    sub.add_parser("takes", help="list all takes/manifests on the Pi").set_defaults(func=cmd_takes)

    report = sub.add_parser("report")
    report.add_argument("report_path")
    report.set_defaults(func=cmd_report)
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        args.func(args)
