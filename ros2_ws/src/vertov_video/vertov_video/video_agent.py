import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_srvs.srv import Trigger
import gi
import os
from datetime import datetime
from threading import Thread

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

class VideoAgent(Node):
    """ROS2 node for controlling video recording via GStreamer."""

    def __init__(self):
        super().__init__('video_agent')
        self.get_logger().info('VideoAgent initializing...')

        self.camera_id = os.environ.get('CAMERA_ID', 'cam01')
        self.recording_dir = os.environ.get('RECORDING_DIR', '/home/pi/Videos')
        self.pipeline = None
        self.is_recording = False

        callback_group = ReentrantCallbackGroup()
        self.start_service = self.create_service(
            Trigger,
            'start_recording',
            self.start_recording_callback,
            callback_group=callback_group
        )

        self.stop_service = self.create_service(
            Trigger,
            'stop_recording',
            self.stop_recording_callback,
            callback_group=callback_group
        )

        self.get_logger().info(f'VideoAgent ready (camera_id: {self.camera_id})')
        self.get_logger().info('Services available at: /start_recording, /stop_recording')

    def create_pipeline(self, output_path):
        """Create GStreamer recording pipeline (H.264 in MKV container)."""
        pipeline_str = (
            "libcamerasrc ! "
            "video/x-raw,format=RGB,width=1920,height=1080,framerate=30/1 ! "
            "videoconvert ! "
            "x264enc tune=zerolatency speed-preset=ultrafast bitrate=4000 ! "
            "h264parse ! "
            f"matroskamux ! filesink location={output_path}"
        )
        self.get_logger().info(f'Pipeline: {pipeline_str}')
        return Gst.parse_launch(pipeline_str)

    def start_recording_callback(self, request, response):
        """Handle StartRecording service calls."""
        self.get_logger().info('Received recording request')

        if self.is_recording:
            response.success = False
            response.message = 'Recording already in progress'
            return response

        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S-%f')[:-3] + 'Z'
        # Use MKV container for robustness against EOS/finalization issues
        filename = f"{timestamp}_{self.camera_id}.mkv"
        output_path = os.path.join(self.recording_dir, filename)

        try:
            self.pipeline = self.create_pipeline(output_path)
            bus = self.pipeline.get_bus()
            self.pipeline.set_state(Gst.State.PLAYING)

            def monitor_bus():
                msg = bus.timed_pop_filtered(
                    Gst.CLOCK_TIME_NONE,
                    Gst.MessageType.ERROR | Gst.MessageType.EOS
                )
                if msg:
                    if msg.type == Gst.MessageType.ERROR:
                        self.get_logger().error(f'Pipeline error: {msg.parse_error()}')
                    elif msg.type == Gst.MessageType.EOS:
                        self.get_logger().info('Recording complete')
                    self.is_recording = False
                    if self.pipeline:
                        self.pipeline.set_state(Gst.State.NULL)

            Thread(target=monitor_bus, daemon=True).start()

            self.is_recording = True
            response.success = True
            response.message = output_path
            self.get_logger().info(f'Started recording: {output_path}')

        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f'Failed to start recording: {e}')

        return response

    def stop_recording_callback(self, request, response):
        """Handle StopRecording service calls by sending EOS to the pipeline."""
        self.get_logger().info('Received stop recording request')

        if not self.is_recording or self.pipeline is None:
            response.success = False
            response.message = 'No active recording'
            return response

        try:
            self.get_logger().info('Sending EOS event to pipeline')
            # This will cause the monitor thread to observe EOS, log
            # completion, and tear down the pipeline cleanly.
            self.pipeline.send_event(Gst.Event.new_eos())
            response.success = True
            response.message = 'Stopping recording'
        except Exception as e:
            self.get_logger().error(f'Failed to stop recording: {e}')
            response.success = False
            response.message = str(e)

        return response

def main(args=None):
    rclpy.init(args=args)
    node = VideoAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
