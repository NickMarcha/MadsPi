"""Screen recording functionality using mss and opencv-python."""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable
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

# Try to import LSL for timestamp synchronization
try:
    from pylsl import local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False

# Windows-specific imports for accurate window capture
if platform.system() == 'Windows':
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_API_AVAILABLE = True
    except ImportError:
        WINDOWS_API_AVAILABLE = False
else:
    WINDOWS_API_AVAILABLE = False

from .models import ScreenRecordingConfig


class ScreenRecorder:
    """Records screen during a session using mss for capture and opencv for encoding."""
    
    def __init__(self, session_id: str, config: ScreenRecordingConfig, output_dir: Path, window=None, 
                 on_recording_started: Optional[Callable[[Dict[str, Any]], None]] = None):
        """Initialize screen recorder.
        
        Args:
            session_id: Session ID for file naming
            config: Screen recording configuration
            output_dir: Directory to save the recording
            window: Optional QWidget/QWindow to record (if None, records full screen)
            on_recording_started: Optional callback to invoke when recording starts.
                                  Will be called with sync event data containing:
                                  - type: 'video_recording_started'
                                  - lsl_timestamp: LSL synchronized timestamp
                                  - wall_clock: ISO format wall clock time
                                  - session_id: Session ID
        """
        if not RECORDING_AVAILABLE:
            raise RuntimeError(f"Screen recording dependencies not available: {IMPORT_ERROR}")
        
        self.session_id = session_id
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.window = window  # Window to record (None = full screen)
        self.on_recording_started = on_recording_started  # Callback for sync event
        
        self.is_recording = False
        self.frames: queue.Queue = queue.Queue()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.lsl_start_time: Optional[float] = None  # LSL timestamp when recording started
        
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
            # Get window geometry - we want to record the entire window including frame
            # On Windows, we'll use Windows API to get accurate physical pixel coordinates
            if platform.system() == 'Windows' and WINDOWS_API_AVAILABLE:
                # Use Windows API to get window rect in physical pixels
                try:
                    hwnd = int(self.window.winId())
                    rect = wintypes.RECT()
                    # GetWindowRect returns coordinates in physical pixels
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    self.record_x = rect.left
                    self.record_y = rect.top
                    self.record_width = rect.right - rect.left
                    self.record_height = rect.bottom - rect.top
                    self.dpr = 1.0  # Windows API already returns physical pixels
                    print(f"[ScreenRecorder] Window rect from Windows API: {self.record_x}, {self.record_y}, {self.record_width}x{self.record_height}")
                except Exception as e:
                    print(f"[ScreenRecorder] Failed to get window rect from Windows API: {e}, falling back to Qt")
                    # Fallback to Qt method
                    self._init_window_geometry_qt()
            else:
                # Use Qt geometry (may have DPI scaling issues on Windows)
                self._init_window_geometry_qt()
        else:
            # Full screen
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                self.record_x = monitor['left']
                self.record_y = monitor['top']
                self.record_width = monitor['width']
                self.record_height = monitor['height']
                self.dpr = 1.0
        
        # Apply resolution override if specified (scales the output)
        if self.config.resolution:
            self.output_width, self.output_height = self.config.resolution
        else:
            # Use captured dimensions, but ensure they're even (required by most codecs)
            self.output_width = self.record_width
            self.output_height = self.record_height
        
        # Ensure output dimensions are even (required by most video codecs like H.264)
        # Many codecs require dimensions to be divisible by 2 (some require 4, 8, or 16)
        # We'll make them divisible by 2 at minimum
        if self.output_width % 2 != 0:
            self.output_width += 1
        if self.output_height % 2 != 0:
            self.output_height += 1
    
    def _init_window_geometry_qt(self):
        """Initialize window geometry using Qt methods (fallback)."""
        # Get window geometry - we want to record the entire window including frame
        # frameGeometry() includes window decorations and is in screen coordinates (logical pixels)
        frame_geom = self.window.frameGeometry()
        
        # Get the screen that contains this window
        screen = self.window.screen()
        if screen:
            # Get device pixel ratio for DPI scaling
            # On Windows with DPI scaling, Qt uses logical pixels but mss needs physical pixels
            dpr = screen.devicePixelRatio()
            
            # Convert Qt logical pixels to physical pixels for mss
            # frameGeometry() returns logical pixels, but we need physical pixels
            logical_x = frame_geom.x()
            logical_y = frame_geom.y()
            logical_width = frame_geom.width()
            logical_height = frame_geom.height()
            
            # Store logical coordinates - we'll convert in capture_loop where we have mss monitor info
            self.record_x = logical_x
            self.record_y = logical_y
            self.record_width = logical_width
            self.record_height = logical_height
            self.dpr = dpr
            print(f"[ScreenRecorder] Window geometry from Qt: {self.record_x}, {self.record_y}, {self.record_width}x{self.record_height} (DPR: {self.dpr})")
        else:
            # Fallback: use frame geometry without DPI scaling
            self.record_x = frame_geom.x()
            self.record_y = frame_geom.y()
            self.record_width = frame_geom.width()
            self.record_height = frame_geom.height()
            self.dpr = 1.0
    
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
        
        # Capture LSL timestamp for sync event (if available)
        if LSL_AVAILABLE:
            self.lsl_start_time = local_clock()
        
        # Send sync event to indicate video recording has started
        # Build event using the same shape as bridge events so LSLRecorder parsing is consistent.
        if self.on_recording_started:
            # Primary event (immediate)
            sync_event = {
                'data': {
                    'lsl_timestamp': self.lsl_start_time if (LSL_AVAILABLE and self.lsl_start_time is not None) else None,
                    'session_id': self.session_id
                },
                'timestamp': self.lsl_start_time if (LSL_AVAILABLE and self.lsl_start_time is not None) else datetime.now().timestamp(),
                'type': 'video_recording_started',
                'wall_clock': datetime.now().isoformat()
            }

            def _send_sync(event):
                try:
                    self.on_recording_started(event)
                    print(f"[ScreenRecorder] Sent video_recording_started sync event: {event}")
                except Exception as e:
                    print(f"[ScreenRecorder] Error sending sync event: {e}")

            # Send immediately
            _send_sync(sync_event)

            # Also resend after a short delay to ensure the LSL recorder/inlets have time to capture it
            try:
                import threading
                resend_timer = threading.Timer(0.5, _send_sync, args=(sync_event,))
                resend_timer.daemon = True
                resend_timer.start()
            except Exception:
                # If timer fails for any reason, ignore (best-effort)
                pass
        
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
                # Will be updated each frame
                capture_region = None
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
                            # Get all monitors from mss (in physical pixels)
                            monitors = sct.monitors
                            capture_region = None
                            
                            # Check if we're using Windows API (coordinates already in physical pixels)
                            if platform.system() == 'Windows' and WINDOWS_API_AVAILABLE and self.dpr == 1.0:
                                # Try to use Windows API for accurate coordinates
                                try:
                                    hwnd = int(self.window.winId())
                                    rect = wintypes.RECT()
                                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                                    window_x = rect.left
                                    window_y = rect.top
                                    window_width = rect.right - rect.left
                                    window_height = rect.bottom - rect.top
                                    
                                    # Find which monitor contains the window center
                                    window_center_x = window_x + window_width // 2
                                    window_center_y = window_y + window_height // 2
                                    
                                    target_monitor = None
                                    for i in range(1, len(monitors)):
                                        mon = monitors[i]
                                        if (mon['left'] <= window_center_x <= mon['left'] + mon['width'] and
                                            mon['top'] <= window_center_y <= mon['top'] + mon['height']):
                                            target_monitor = mon
                                            break
                                    
                                    if target_monitor:
                                        # Calculate position relative to monitor (already in physical pixels)
                                        capture_region = {
                                            'top': window_y - target_monitor['top'],
                                            'left': window_x - target_monitor['left'],
                                            'width': window_width,
                                            'height': window_height
                                        }
                                        
                                        # Ensure capture region is within monitor bounds
                                        capture_region['top'] = max(0, capture_region['top'])
                                        capture_region['left'] = max(0, capture_region['left'])
                                        capture_region['width'] = min(capture_region['width'], target_monitor['width'] - capture_region['left'])
                                        capture_region['height'] = min(capture_region['height'], target_monitor['height'] - capture_region['top'])
                                    else:
                                        # Fallback: use primary monitor
                                        primary_monitor = monitors[1]
                                        capture_region = {
                                            'top': max(0, window_y - primary_monitor['top']),
                                            'left': max(0, window_x - primary_monitor['left']),
                                            'width': window_width,
                                            'height': window_height
                                        }
                                except Exception:
                                    # Fallback to Qt method if Windows API fails
                                    capture_region = None
                            
                            # If Windows API failed or not available, use Qt method with DPI conversion
                            if capture_region is None:
                                # Get current window frame geometry (includes decorations)
                                # This returns logical pixels on Windows with DPI scaling
                                frame_geom = self.window.frameGeometry()
                                logical_x = frame_geom.x()
                                logical_y = frame_geom.y()
                                logical_width = frame_geom.width()
                                logical_height = frame_geom.height()
                                
                                # Convert Qt logical pixels to physical pixels
                                # DPR tells us the scaling factor (e.g., 1.5 for 150% DPI scaling)
                                physical_width = int(logical_width * self.dpr)
                                physical_height = int(logical_height * self.dpr)
                                
                                # Find which monitor contains the window center (in logical pixels)
                                window_center_x = logical_x + logical_width // 2
                                window_center_y = logical_y + logical_height // 2
                                
                                # Find the target monitor by checking which monitor contains the window center
                                target_monitor = None
                                for i in range(1, len(monitors)):
                                    mon = monitors[i]
                                    # Convert monitor bounds to logical pixels for comparison
                                    mon_logical_left = int(mon['left'] / self.dpr)
                                    mon_logical_top = int(mon['top'] / self.dpr)
                                    mon_logical_width = int(mon['width'] / self.dpr)
                                    mon_logical_height = int(mon['height'] / self.dpr)
                                    
                                    if (mon_logical_left <= window_center_x <= mon_logical_left + mon_logical_width and
                                        mon_logical_top <= window_center_y <= mon_logical_top + mon_logical_height):
                                        target_monitor = mon
                                        break
                                
                                # If we found a target monitor, use it
                                if target_monitor:
                                    # Convert window position to physical pixels
                                    physical_x = int(logical_x * self.dpr)
                                    physical_y = int(logical_y * self.dpr)
                                    
                                    # Calculate position relative to monitor (in physical pixels)
                                    capture_region = {
                                        'top': physical_y - target_monitor['top'],
                                        'left': physical_x - target_monitor['left'],
                                        'width': physical_width,
                                        'height': physical_height
                                    }
                                    
                                    # Ensure capture region is within monitor bounds
                                    capture_region['top'] = max(0, capture_region['top'])
                                    capture_region['left'] = max(0, capture_region['left'])
                                    capture_region['width'] = min(capture_region['width'], target_monitor['width'] - capture_region['left'])
                                    capture_region['height'] = min(capture_region['height'], target_monitor['height'] - capture_region['top'])
                                else:
                                    # Fallback: use primary monitor
                                    primary_monitor = monitors[1]
                                    physical_x = int(logical_x * self.dpr)
                                    physical_y = int(logical_y * self.dpr)
                                    
                                    capture_region = {
                                        'top': max(0, physical_y - primary_monitor['top']),
                                        'left': max(0, physical_x - primary_monitor['left']),
                                        'width': physical_width,
                                        'height': physical_height
                                    }
                        
                        # Capture screen region (must be valid)
                        if capture_region and capture_region['width'] > 0 and capture_region['height'] > 0:
                            screenshot = sct.grab(capture_region)
                            
                            # Convert to numpy array
                            img = np.array(screenshot)
                            
                            # Convert BGRA to BGR (opencv uses BGR)
                            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                            
                            # Get actual captured dimensions
                            captured_height, captured_width = img_bgr.shape[:2]
                            
                            # Resize if output resolution differs from capture resolution
                            if self.output_width != captured_width or self.output_height != captured_height:
                                img_bgr = cv2.resize(img_bgr, (self.output_width, self.output_height), interpolation=cv2.INTER_LINEAR)
                            
                            # Write frame to video
                            if self.video_writer and self.video_writer.isOpened():
                                self.video_writer.write(img_bgr)
                        else:
                            print(f"Warning: Invalid capture region: {capture_region}")
                        
                        last_capture_time = current_time
                        
                    except Exception as e:
                        print(f"Error capturing frame: {e}")
                        import traceback
                        traceback.print_exc()
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
            Dictionary with recording metadata including sync time for event alignment
        """
        info = {
            'is_recording': self.is_recording,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'video_path': str(self.video_path) if self.video_path else None,
            'resolution': (self.output_width, self.output_height),
            'capture_region': (self.record_x, self.record_y, self.record_width, self.record_height),
            'fps': self.config.fps,
            'quality': self.config.recording_quality,
            # LSL sync information for event alignment
            'lsl_recording_start_time': self.lsl_start_time  # Use this to offset event timestamps
        }
        
        if self.start_time and self.end_time:
            info['duration'] = (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            info['duration'] = (datetime.now() - self.start_time).total_seconds()
        else:
            info['duration'] = 0.0
        
        return info

