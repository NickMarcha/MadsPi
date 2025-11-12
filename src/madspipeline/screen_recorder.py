"""Screen recording functionality using mss and opencv-python."""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import queue
import platform

try:
    import mss
    import numpy as np
    import cv2
    RECORDING_AVAILABLE = True
except ImportError as e:
    RECORDING_AVAILABLE = False
    IMPORT_ERROR = str(e)

from .models import ScreenRecordingConfig


class ScreenRecorder:
    """Records screen during a session using mss for capture and opencv for encoding."""
    
    def __init__(self, session_id: str, config: ScreenRecordingConfig, output_dir: Path, window=None):
        """Initialize screen recorder.
        
        Args:
            session_id: Session ID for file naming
            config: Screen recording configuration
            output_dir: Directory to save the recording
            window: Optional QWidget/QWindow to record (if None, records full screen)
        """
        if not RECORDING_AVAILABLE:
            raise RuntimeError(f"Screen recording dependencies not available: {IMPORT_ERROR}")
        
        self.session_id = session_id
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.window = window  # Window to record (None = full screen)
        
        self.is_recording = False
        self.frames: queue.Queue = queue.Queue()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # Threading
        self.capture_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Video writer
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.video_path: Optional[Path] = None
        
        # Calculate frame interval based on FPS
        self.frame_interval = 1.0 / config.fps
        
        # Determine recording region
        if self.window:
            # Get window geometry
            geometry = self.window.geometry()
            self.record_x = geometry.x()
            self.record_y = geometry.y()
            self.record_width = geometry.width()
            self.record_height = geometry.height()
        else:
            # Full screen
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                self.record_x = monitor['left']
                self.record_y = monitor['top']
                self.record_width = monitor['width']
                self.record_height = monitor['height']
        
        # Apply resolution override if specified (scales the output)
        if config.resolution:
            self.output_width, self.output_height = config.resolution
        else:
            self.output_width = self.record_width
            self.output_height = self.record_height
    
    def start_recording(self):
        """Start screen recording."""
        if self.is_recording:
            print("Warning: Recording already in progress")
            return
        
        self.is_recording = True
        self.start_time = datetime.now()
        self.stop_event.clear()
        
        # Set up video writer
        self.video_path = self.output_dir / f"screen_recording_{self.session_id}.mp4"
        
        # Determine codec - try H264 first, fallback to XVID, then mp4v
        # H264 is better quality and widely supported
        codecs_to_try = [
            ('H264', cv2.VideoWriter_fourcc(*'H264')),
            ('XVID', cv2.VideoWriter_fourcc(*'XVID')),
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
        ]
        
        codec = None
        codec_name = None
        for name, fourcc in codecs_to_try:
            # Test if codec is available by trying to create a writer
            test_writer = cv2.VideoWriter(
                str(self.video_path.parent / f"_test_{self.session_id}.mp4"),
                fourcc,
                self.config.fps,
                (self.output_width, self.output_height)
            )
            if test_writer.isOpened():
                test_writer.release()
                # Clean up test file
                test_file = self.video_path.parent / f"_test_{self.session_id}.mp4"
                if test_file.exists():
                    test_file.unlink()
                codec = fourcc
                codec_name = name
                break
        
        if codec is None:
            raise RuntimeError("No suitable video codec found. Please ensure OpenCV is built with codec support.")
        
        print(f"Using codec: {codec_name}")
        
        self.video_writer = cv2.VideoWriter(
            str(self.video_path),
            codec,
            self.config.fps,
            (self.output_width, self.output_height)
        )
        
        if not self.video_writer.isOpened():
            raise RuntimeError(f"Failed to open video writer for {self.video_path}")
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        print(f"Screen recording started: {self.video_path}")
    
    def _capture_loop(self):
        """Capture screen frames in a separate thread."""
        last_capture_time = time.time()
        
        with mss.mss() as sct:
            # Determine capture region
            if self.window:
                # Update window geometry in case it moved/resized
                geometry = self.window.geometry()
                capture_region = {
                    'top': geometry.y(),
                    'left': geometry.x(),
                    'width': geometry.width(),
                    'height': geometry.height()
                }
            else:
                # Full screen - use primary monitor
                monitor = sct.monitors[1]
                capture_region = {
                    'top': monitor['top'],
                    'left': monitor['left'],
                    'width': monitor['width'],
                    'height': monitor['height']
                }
            
            while not self.stop_event.is_set():
                current_time = time.time()
                
                # Check if it's time to capture a frame (based on FPS)
                if current_time - last_capture_time >= self.frame_interval:
                    try:
                        # Update window geometry if recording window
                        if self.window:
                            geometry = self.window.geometry()
                            capture_region = {
                                'top': geometry.y(),
                                'left': geometry.x(),
                                'width': geometry.width(),
                                'height': geometry.height()
                            }
                        
                        # Capture screen region
                        screenshot = sct.grab(capture_region)
                        
                        # Convert to numpy array
                        img = np.array(screenshot)
                        
                        # Convert BGRA to BGR (opencv uses BGR)
                        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                        
                        # Resize if output resolution differs from capture resolution
                        if self.output_width != capture_region['width'] or self.output_height != capture_region['height']:
                            img_bgr = cv2.resize(img_bgr, (self.output_width, self.output_height))
                        
                        # Write frame to video
                        if self.video_writer and self.video_writer.isOpened():
                            self.video_writer.write(img_bgr)
                        
                        last_capture_time = current_time
                        
                    except Exception as e:
                        print(f"Error capturing frame: {e}")
                        # Continue trying to capture
                
                # Small sleep to avoid busy waiting
                time.sleep(0.001)  # 1ms
    
    def stop_recording(self) -> Optional[Path]:
        """Stop screen recording and save video file.
        
        Returns:
            Path to the saved video file, or None if recording failed
        """
        if not self.is_recording:
            print("Warning: Not recording")
            return None
        
        self.is_recording = False
        self.end_time = datetime.now()
        
        # Signal capture thread to stop
        self.stop_event.set()
        
        # Wait for capture thread to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        # Release video writer
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        
        # Calculate duration
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"Screen recording stopped. Duration: {duration:.2f}s")
        
        # Return video path if file exists
        if self.video_path and self.video_path.exists():
            file_size = self.video_path.stat().st_size / (1024 * 1024)  # MB
            print(f"Screen recording saved: {self.video_path} ({file_size:.2f} MB)")
            return self.video_path
        else:
            print(f"Warning: Screen recording file not found: {self.video_path}")
            return None
    
    def get_recording_info(self) -> Dict[str, Any]:
        """Get information about the current recording.
        
        Returns:
            Dictionary with recording metadata
        """
        info = {
            'is_recording': self.is_recording,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'video_path': str(self.video_path) if self.video_path else None,
            'resolution': (self.output_width, self.output_height),
            'capture_region': (self.record_x, self.record_y, self.record_width, self.record_height),
            'fps': self.config.fps,
            'quality': self.config.recording_quality
        }
        
        if self.start_time and self.end_time:
            info['duration'] = (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            info['duration'] = (datetime.now() - self.start_time).total_seconds()
        else:
            info['duration'] = 0.0
        
        return info

