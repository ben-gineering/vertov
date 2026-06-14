#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def find_manifest(take_dir: Path) -> Path:
    path = take_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    return path


def find_cinepi_dir(take_dir: Path) -> Path:
    matches = [p for p in take_dir.iterdir() if p.is_dir() and p.name.startswith("cinepi_main_")]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one cinepi directory in {take_dir}, found {len(matches)}")
    return matches[0]


def find_audio_file(take_dir: Path) -> Path:
    matches = [p for p in take_dir.iterdir() if p.is_file() and p.name.startswith("zynthian_main_") and p.suffix.lower() == ".wav"]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one zynthian wav in {take_dir}, found {len(matches)}")
    return matches[0]


def detect_fps(manifest: dict[str, Any]) -> float:
    for device in manifest.get("devices", []):
        if device.get("device_type") == "cinepi":
            fps = device.get("metadata", {}).get("fps")
            if fps is None:
                break
            return float(fps)
    raise RuntimeError("cinepi fps not found in manifest metadata")


def ffprobe_duration(path: Path) -> float:
    cp = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(cp.stdout.strip())


def inspect_take(take_dir: Path) -> dict[str, Any]:
    manifest = load_json(find_manifest(take_dir))
    cinepi_dir = find_cinepi_dir(take_dir)
    audio_file = find_audio_file(take_dir)
    fps = detect_fps(manifest)
    dng_files = sorted(cinepi_dir.glob("*.dng"))
    frame_count = len(dng_files)
    if frame_count == 0:
        raise RuntimeError(f"no dng files found in {cinepi_dir}")
    video_duration = frame_count / fps
    audio_duration = ffprobe_duration(audio_file)
    return {
        "take_id": manifest["take_id"],
        "take_dir": str(take_dir),
        "cinepi_dir": str(cinepi_dir),
        "audio_file": str(audio_file),
        "fps": fps,
        "frame_count": frame_count,
        "video_duration_sec": video_duration,
        "audio_duration_sec": audio_duration,
    }


def ensure_post_dir(take_dir: Path) -> Path:
    post_dir = take_dir / "post"
    post_dir.mkdir(parents=True, exist_ok=True)
    return post_dir


def render_proxy(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    cinepi_dir = Path(info["cinepi_dir"])
    post_dir = ensure_post_dir(take_dir)
    proxy = post_dir / "proxy.mp4"
    run([
        "ffmpeg", "-y",
        "-framerate", str(info["fps"]),
        "-pattern_type", "glob",
        "-i", str(cinepi_dir / "*.dng"),
        "-vf", "scale=1920:-1",
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(proxy),
    ])
    return proxy


def mux_audio(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    post_dir = ensure_post_dir(take_dir)
    proxy = post_dir / "proxy.mp4"
    if not proxy.exists():
        render_proxy(take_dir)
    output = post_dir / "proxy_with_audio.mp4"
    run([
        "ffmpeg", "-y",
        "-i", str(proxy),
        "-i", info["audio_file"],
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output),
    ])
    metadata = info | {
        "proxy": str(proxy),
        "proxy_with_audio": str(output),
        "sync_mode": "align_start",
    }
    (post_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return output


def cmd_inspect(args):
    print(json.dumps(inspect_take(Path(args.take_dir)), indent=2))


def cmd_proxy(args):
    print(render_proxy(Path(args.take_dir)))


def cmd_mux(args):
    print(mux_audio(Path(args.take_dir)))


def cmd_full(args):
    render_proxy(Path(args.take_dir))
    print(mux_audio(Path(args.take_dir)))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name, func in (("inspect", cmd_inspect), ("proxy", cmd_proxy), ("mux", cmd_mux), ("full", cmd_full)):
        sp = sub.add_parser(name)
        sp.add_argument("take_dir")
        sp.set_defaults(func=func)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
