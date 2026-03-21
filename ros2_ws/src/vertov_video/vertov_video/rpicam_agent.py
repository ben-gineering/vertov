import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_srvs.srv import Trigger
import subprocess
import os
from datetime import datetime
from threading import Thread, Lock

class RPICamAgent(Node):
    """ROS2 node for controlling video recording via rpicam-vid."""

    def __init__(self):
        super().__init__('rpicam_agent')
        self.get_logger().info('RPICamAgent initializing...')

        self.camera_id = os.environ.get('CAMERA_ID', 'cam01')
        self.recording_dir = os.environ.get('RECORDING_DIR', '/home/pi/Videos')
        self.resolution = os.environ.get('RESOLUTION', '1280x720')
        self.framerate = int(os.environ.get('FRAMERATE', '30'))
        
        self.process = None
        self.is_recording = False
        self.lock = Lock()

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

        os.makedirs(self.recording_dir, exist_ok=True)

        self.get_logger().info(f'RPICamAgent ready (camera_id: {self.camera_id}, resolution: {self.resolution})')

    def start_recording_callback(self, request, response):
        self.get_logger().info('Received recording request')

        with self.lock:
            if self.is_recording:
                response.success = False
                response.message = 'Recording already in progress'
                return response

            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')
            filename = f"{timestamp}_{self.camera_id}.mp4"
            output_path = os.path.join(self.recording_dir, filename)

            try:
                width, height = self.resolution.split('x')
                
                cmd = [
                    'rpicam-vid',
                    '--width', width,
                    '--height', height,
                    '--framerate', str(self.framerate),
                    '--codec', 'h264',
                    '--output', output_path,
                    '--timeout', '0',  # Run indefinitely until stopped
                    '--listen',  # Listen for control commands
                ]

                self.get_logger().info(f'Starting rpicam-vid: {" ".join(cmd)}')
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                def monitor_process():
                    self.process.wait()
                    stdout, stderr = self.process.communicate()
                    if stdout:
                        self.get_logger().info(f'rpicam-vid stdout: {stdout.decode()}')
                    if stderr:
                        self.get_logger().info(f'rpicam-vid stderr: {stderr.decode()}')
                    with self.lock:
                        self.is_recording = False
                        self.process = None
                    self.get_logger().info(f'Recording finished: {output_path}')

                Thread(target=monitor_process, daemon=True).start()

                self.is_recording = True
                response.success = True
                response.message = output_path
                self.get_logger().info(f'Started recording: {output_path}')

            except Exception as e:
                response.success = False
                response.message = str(e)
                self.get_logger().error(f'Failed to start recording: {e}')
                with self.lock:
                    self.is_recording = False
                    self.process = None

            return response

    def stop_recording_callback(self, request, response):
        self.get_logger().info('Received stop recording request')

        with self.lock:
            if not self.is_recording or self.process is None:
                response.success = False
                response.message = 'No active recording'
                return response

            try:
                self.get_logger().info('Sending stop signal to rpicam-vid')
                self.process.terminate()
                response.success = True
                response.message = 'Stopping recording'
            except Exception as e:
                self.get_logger().error(f'Failed to stop recording: {e}')
                response.success = False
                response.message = str(e)

            return response


def main(args=None):
    rclpy.init(args=args)
    node = RPICamAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.process:
            node.process.terminate()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
