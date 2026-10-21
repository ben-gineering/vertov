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


def find_cinepi_dir(take_dir: Path) -> Path | None:
    """Subset takes: video leg may be absent (audio-only take) — return None then."""
    matches = [p for p in take_dir.iterdir() if p.is_dir() and p.name.startswith("cinepi_main_")]
    if len(matches) > 1:
        raise RuntimeError(f"expected at most one cinepi directory in {take_dir}, found {len(matches)}")
    if not matches:
        return None
    cinepi_dir = matches[0]
    if not any(cinepi_dir.glob("*.dng")):
        nested = [p for p in cinepi_dir.iterdir() if p.is_dir()]
        if len(nested) == 1 and any(nested[0].glob("*.dng")):
            cinepi_dir = nested[0]
    return cinepi_dir


def find_audio_file(take_dir: Path) -> Path | None:
    """Subset takes: audio leg may be absent (video-only take) — return None then."""
    matches = [p for p in take_dir.iterdir() if p.is_file() and p.name.startswith("zynthian_main_") and p.suffix.lower() == ".wav"]
    if len(matches) > 1:
        raise RuntimeError(f"expected at most one zynthian wav in {take_dir}, found {len(matches)}")
    return matches[0] if matches else None


def detect_fps(manifest: dict[str, Any]) -> float | None:
    fps = None
    for device in manifest.get("devices", []):
        if device.get("device_type") == "cinepi":
            fps = device.get("metadata", {}).get("fps")
            break
    return float(fps) if fps is not None else None


def manifest_span(manifest: dict[str, Any]) -> float | None:
    """Fallback rolling span: stopped_at minus the rewritten started_at (= first kept frame)."""
    try:
        start = manifest.get("started_at")
        stop = manifest.get("stopped_at")
        if not start or not stop:
            return None
        from datetime import datetime
        t0 = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(stop).replace("Z", "+00:00"))
        span = (t1 - t0).total_seconds()
        return span if span > 0 else None
    except (ValueError, TypeError):
        return None


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
    if cinepi_dir is None and audio_file is None:
        raise RuntimeError("take has neither a video nor an audio leg")
    entry = next((d for d in manifest.get("devices", []) if d.get("device_type") == "cinepi"), None)
    mode = (entry or {}).get("capture_mode", "normal")
    params = (entry or {}).get("mode_params") or {}
    fps = detect_fps(manifest)
    dng_files = sorted(cinepi_dir.glob("*.dng")) if cinepi_dir is not None else []
    frame_count = len(dng_files)
    if cinepi_dir is not None and frame_count == 0:
        raise RuntimeError(f"no dng files found in {cinepi_dir}")
    audio_duration = ffprobe_duration(audio_file) if audio_file is not None else None

    if mode == "timelapse":
        # Interval-clocked video: audio is recorded real-time alongside and is
        # NOT the sync master here — the capture fps comes from the manifest.
        capture_fps = float(params.get("capture_fps") or 0.0) or (1.0 / float(params.get("interval_s") or 1.0))
        effective_fps = capture_fps
        video_duration = frame_count / effective_fps if effective_fps > 0 else 0.0
        sync_mode = "align_start"
    elif mode == "rolling":
        # Video covers only the kept tail; audio covers the whole session.
        span = float(params.get("video_span_s") or 0.0) or manifest_span(manifest) or 0.0
        if span <= 0:
            raise RuntimeError("rolling take: no video_span_s in manifest and no span derivable")
        effective_fps = frame_count / span
        video_duration = span
        sync_mode = "tail"
    else:
        # The audio clock is the sync master: derive the encoded frame rate from
        # frame count and audio duration so the rendered video lasts exactly as
        # long as the recorded audio. Manifest fps metadata can be wrong (e.g.
        # cinemate stamps fps_actual=24 while the sensor captured 25.0) and frame
        # pacing jitters mid-take, so any fixed fps label drifts against the audio.
        effective_fps = frame_count / audio_duration if (audio_duration and audio_duration > 0) else fps
        video_duration = frame_count / effective_fps if effective_fps and effective_fps > 0 else 0.0
        sync_mode = "align_start"

    if cinepi_dir is not None and (not effective_fps or effective_fps <= 0):
        raise RuntimeError("cannot determine frame rate for rendering")

    audio_offset = 0.0
    if mode == "rolling" and audio_duration and video_duration:
        audio_offset = max(0.0, audio_duration - video_duration)

    return {
        "take_id": manifest["take_id"],
        "take_dir": str(take_dir),
        "cinepi_dir": str(cinepi_dir) if cinepi_dir else None,
        "audio_file": str(audio_file) if audio_file else None,
        "capture_mode": mode,
        "mode_params": params,
        "sync_mode": sync_mode,
        "fps": fps,
        "effective_fps": round(effective_fps, 6) if effective_fps and effective_fps > 0 else None,
        "frame_count": frame_count,
        "video_duration_sec": video_duration,
        "audio_duration_sec": audio_duration,
        "audio_offset_sec": round(audio_offset, 3),
    }


def ensure_post_dir(take_dir: Path) -> Path:
    post_dir = take_dir / "post"
    post_dir.mkdir(parents=True, exist_ok=True)
    return post_dir


def render_proxy(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    if not info["cinepi_dir"]:
        raise RuntimeError("no video leg in this take (audio-only)")
    cinepi_dir = Path(info["cinepi_dir"])
    post_dir = ensure_post_dir(take_dir)
    proxy = post_dir / "proxy.mp4"
    run([
        "ffmpeg", "-y",
        "-framerate", f"{info['effective_fps']:.6f}",
        "-pattern_type", "glob",
        "-i", str(cinepi_dir / "*.dng"),
        "-vf", "scale=1920:-2",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(proxy),
    ])
    return proxy


def render_lossless(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    if not info["cinepi_dir"]:
        raise RuntimeError("no video leg in this take (audio-only)")
    cinepi_dir = Path(info["cinepi_dir"])
    post_dir = ensure_post_dir(take_dir)
    lossless = post_dir / "lossless.mkv"
    run([
        "ffmpeg", "-y",
        "-framerate", f"{info['effective_fps']:.6f}",
        "-pattern_type", "glob",
        "-i", str(cinepi_dir / "*.dng"),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-qp", "0",
        "-pix_fmt", "yuv420p",
        str(lossless),
    ])
    return lossless


def mux_audio(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    post_dir = ensure_post_dir(take_dir)
    audio_file = info["audio_file"]
    if not info["cinepi_dir"]:
        # audio-only take: nothing to mux; carry the wav into post/
        output = post_dir / "audio_only.wav"
        if audio_file:
            run(["cp", str(audio_file), str(output)])
        metadata = info | {"audio_only": str(output) if audio_file else None, "sync_mode": "audio_only"}
        (post_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        return output
    proxy = post_dir / "proxy.mp4"
    if not proxy.exists():
        render_proxy(take_dir)
    output = post_dir / "proxy_with_audio.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(proxy)]
    if audio_file:
        # rolling/tail sync: trim the audio front so it ends with the kept video tail
        if info["audio_offset_sec"] > 0.05:
            cmd += ["-ss", f"{info['audio_offset_sec']:.3f}", "-i", str(audio_file)]
        else:
            cmd += ["-i", str(audio_file)]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-shortest"]
    else:
        output = post_dir / "proxy_video_only.mp4"
        cmd += ["-c:v", "copy"]
    cmd += [str(output)]
    run(cmd)
    metadata = info | {
        "proxy": str(proxy),
        "proxy_with_audio": str(output),
        "sync_mode": info["sync_mode"],
    }
    (post_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return output


def mux_audio_lossless(take_dir: Path) -> Path:
    info = inspect_take(take_dir)
    post_dir = ensure_post_dir(take_dir)
    if not info["cinepi_dir"]:
        raise RuntimeError("no video leg in this take (audio-only)")
    lossless = post_dir / "lossless.mkv"
    if not lossless.exists():
        render_lossless(take_dir)
    output = post_dir / "lossless_with_audio.mkv"
    cmd = ["ffmpeg", "-y", "-i", str(lossless)]
    if info["audio_file"]:
        if info["audio_offset_sec"] > 0.05:
            cmd += ["-ss", f"{info['audio_offset_sec']:.3f}", "-i", str(info["audio_file"])]
        else:
            cmd += ["-i", str(info["audio_file"])]
        cmd += ["-c:v", "copy", "-c:a", "flac", "-shortest"]
    else:
        output = post_dir / "lossless_video_only.mkv"
        cmd += ["-c:v", "copy"]
    cmd += [str(output)]
    run(cmd)
    metadata_path = post_dir / "metadata.json"
    metadata = load_json(metadata_path) if metadata_path.exists() else info
    metadata.update({
        "lossless": str(lossless),
        "lossless_with_audio": str(output),
        "sync_mode": info["sync_mode"],
    })
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return output


def cmd_inspect(args):
    print(json.dumps(inspect_take(Path(args.take_dir)), indent=2))


def cmd_proxy(args):
    print(render_proxy(Path(args.take_dir)))


def cmd_mux(args):
    print(mux_audio(Path(args.take_dir)))


def cmd_full(args):
    take_dir = Path(args.take_dir)
    info = inspect_take(take_dir)
    if info["cinepi_dir"]:
        render_proxy(take_dir)
    print(mux_audio(take_dir))


def cmd_lossless(args):
    render_lossless(Path(args.take_dir))
    print(mux_audio_lossless(Path(args.take_dir)))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name, func in (("inspect", cmd_inspect), ("proxy", cmd_proxy), ("mux", cmd_mux), ("full", cmd_full), ("lossless", cmd_lossless)):
        sp = sub.add_parser(name)
        sp.add_argument("take_dir")
        sp.set_defaults(func=func)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
