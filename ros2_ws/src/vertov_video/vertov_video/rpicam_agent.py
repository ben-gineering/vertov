import os
from threading import Lock

import requests
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from std_srvs.srv import Trigger


class RPICamAgent(Node):
    """ROS2 node that controls rpicam-vid via HTTP on the host."""

    def __init__(self):
        super().__init__("rpicam_agent")
        self.get_logger().info("RPICamAgent initializing (HTTP mode)...")

        self.camera_id = os.environ.get("CAMERA_ID", "cam01")
        self.recording_dir = os.environ.get("RECORDING_DIR", "/home/pi/Videos")
        self.resolution = os.environ.get("RESOLUTION", "1280x720")
        self.framerate = int(os.environ.get("FRAMERATE", "30"))
        self.control_url = os.environ.get(
            "RPICAM_CONTROL_URL", "http://127.0.0.1:8080"
        ).rstrip("/")

        self.is_recording = False
        self.current_recording_id = None
        self.current_output_path = None
        self.lock = Lock()

        callback_group = ReentrantCallbackGroup()
        self.start_service = self.create_service(
            Trigger,
            "start_recording",
            self.start_recording_callback,
            callback_group=callback_group,
        )
        self.stop_service = self.create_service(
            Trigger,
            "stop_recording",
            self.stop_recording_callback,
            callback_group=callback_group,
        )

        self.get_logger().info(
            f"RPICamAgent ready (camera_id: {self.camera_id}, resolution: {self.resolution}, "
            f"control_url: {self.control_url})"
        )

    def _http_post(self, path: str, payload: dict) -> dict:
        url = f"{self.control_url}{path}"
        self.get_logger().debug(f"HTTP POST {url} payload={payload}")
        resp = requests.post(url, json=payload, timeout=5.0)
        resp.raise_for_status()
        return resp.json()

    def start_recording_callback(self, request, response):
        self.get_logger().info("Received start recording request")

        with self.lock:
            if self.is_recording:
                response.success = False
                response.message = "Recording already in progress"
                return response

            try:
                width_str, height_str = self.resolution.split("x")
                width = int(width_str)
                height = int(height_str)
            except Exception:
                response.success = False
                response.message = (
                    f"Invalid RESOLUTION '{self.resolution}', expected WxH"
                )
                return response

            payload = {
                "camera_id": self.camera_id,
                "width": width,
                "height": height,
                "framerate": self.framerate,
            }

            try:
                data = self._http_post("/recordings/start", payload)
            except Exception as exc:
                self.get_logger().error(f"HTTP error starting recording: {exc}")
                response.success = False
                response.message = str(exc)
                return response

            if not data.get("success"):
                msg = data.get("message", "Unknown error from rpicam-httpd")
                self.get_logger().error(f"Failed to start recording: {msg}")
                response.success = False
                response.message = msg
                return response

            self.is_recording = True
            self.current_recording_id = data.get("recording_id")
            self.current_output_path = data.get("output_path")

            response.success = True
            response.message = self.current_output_path or "Recording started"
            self.get_logger().info(
                f"Started recording id={self.current_recording_id} path={self.current_output_path}"
            )
            return response

    def stop_recording_callback(self, request, response):
        self.get_logger().info("Received stop recording request")

        with self.lock:
            if not self.is_recording or not self.current_recording_id:
                response.success = False
                response.message = "No active recording"
                return response

            payload = {"recording_id": self.current_recording_id}

            try:
                data = self._http_post("/recordings/stop", payload)
            except Exception as exc:
                self.get_logger().error(f"HTTP error stopping recording: {exc}")
                response.success = False
                response.message = str(exc)
                return response

            if not data.get("success"):
                msg = data.get("message", "Unknown error from rpicam-httpd")
                self.get_logger().error(f"Failed to stop recording: {msg}")
                response.success = False
                response.message = msg
                return response

            output_path = data.get("output_path") or self.current_output_path

            self.is_recording = False
            self.current_recording_id = None
            self.current_output_path = None

            response.success = True
            response.message = output_path or "Stopping recording"
            self.get_logger().info(f"Stopped recording, file: {output_path}")
            return response


def main(args=None):
    rclpy.init(args=args)
    node = RPICamAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
