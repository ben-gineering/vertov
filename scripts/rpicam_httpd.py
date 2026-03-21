#!/usr/bin/env python3
import os
import subprocess
import threading
from datetime import datetime

from flask import Flask, request, jsonify


app = Flask(__name__)


RECORDING_DIR = os.environ.get("RPICAM_RECORDING_DIR", "/home/pi/Videos")
DEFAULT_WIDTH = int(os.environ.get("RPICAM_DEFAULT_WIDTH", "1280"))
DEFAULT_HEIGHT = int(os.environ.get("RPICAM_DEFAULT_HEIGHT", "720"))
DEFAULT_FRAMERATE = int(os.environ.get("RPICAM_DEFAULT_FRAMERATE", "30"))
CAMERA_ID = os.environ.get("CAMERA_ID", "cam01")


lock = threading.Lock()
current_process = None
current_meta = None


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _build_output_path(camera_id: str) -> (str, str):
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    recording_id = f"{timestamp}_{camera_id}"
    filename = f"{recording_id}.mp4"
    return recording_id, os.path.join(RECORDING_DIR, filename)


def _start_rpicam(
    width: int, height: int, framerate: int, output_path: str
) -> subprocess.Popen:
    # NOTE: Adjust codec/container flags here if direct MP4 needs tuning.
    cmd = [
        "rpicam-vid",
        "--width",
        str(width),
        "--height",
        str(height),
        "--framerate",
        str(framerate),
        "--codec",
        "h264",
        "--output",
        output_path,
        "--timeout",
        "0",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _monitor_process(
    proc: subprocess.Popen, recording_id: str, output_path: str
) -> None:
    global current_process, current_meta
    stdout, stderr = proc.communicate()
    if stdout:
        print(f"[rpicam-vid:{recording_id}] stdout:\n{stdout.decode(errors='ignore')}")
    if stderr:
        print(f"[rpicam-vid:{recording_id}] stderr:\n{stderr.decode(errors='ignore')}")
    with lock:
        if current_process is proc:
            current_process = None
            current_meta = None
    print(f"[rpicam-vid:{recording_id}] finished, file: {output_path}")


@app.route("/recordings/start", methods=["POST"])
def start_recording():
    global current_process, current_meta
    data = request.get_json(silent=True) or {}

    width = int(data.get("width", DEFAULT_WIDTH))
    height = int(data.get("height", DEFAULT_HEIGHT))
    framerate = int(data.get("framerate", DEFAULT_FRAMERATE))
    camera_id = data.get("camera_id", CAMERA_ID)

    with lock:
        if current_process is not None and current_process.poll() is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Recording already in progress",
                }
            )

        _ensure_dir(RECORDING_DIR)
        recording_id, output_path = _build_output_path(camera_id)

        try:
            proc = _start_rpicam(width, height, framerate, output_path)
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to start rpicam-vid: {exc}",
                }
            )

        current_process = proc
        current_meta = {
            "recording_id": recording_id,
            "output_path": output_path,
            "camera_id": camera_id,
            "width": width,
            "height": height,
            "framerate": framerate,
        }

        threading.Thread(
            target=_monitor_process,
            args=(proc, recording_id, output_path),
            daemon=True,
        ).start()

        return jsonify(
            {
                "success": True,
                "message": "Recording started",
                "recording_id": recording_id,
                "output_path": output_path,
            }
        )


@app.route("/recordings/stop", methods=["POST"])
def stop_recording():
    global current_process, current_meta
    data = request.get_json(silent=True) or {}
    requested_id = data.get("recording_id")

    with lock:
        if current_process is None or current_process.poll() is not None:
            return jsonify(
                {
                    "success": False,
                    "message": "No active recording",
                }
            )

        active_id = current_meta.get("recording_id") if current_meta else None
        if requested_id and requested_id != active_id:
            return jsonify(
                {
                    "success": False,
                    "message": "Recording ID does not match active recording",
                }
            )

        output_path = current_meta.get("output_path") if current_meta else None

        try:
            current_process.terminate()
        except Exception as exc:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to stop rpicam-vid: {exc}",
                }
            )

        return jsonify(
            {
                "success": True,
                "message": "Stopping recording",
                "output_path": output_path,
            }
        )


@app.route("/recordings/status", methods=["GET"])
def status():
    with lock:
        is_recording = current_process is not None and current_process.poll() is None
        meta = current_meta if is_recording else None
    return jsonify(
        {
            "is_recording": is_recording,
            "recording": meta,
        }
    )


def main() -> None:
    port = int(os.environ.get("RPICAM_PORT", "8080"))
    host = os.environ.get("RPICAM_HOST", "127.0.0.1")
    print(f"Starting rpicam-httpd on {host}:{port}, dir={RECORDING_DIR}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
