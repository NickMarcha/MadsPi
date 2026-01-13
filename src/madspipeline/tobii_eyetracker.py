"""
Tobii Eye Tracker integration for MadsPipeline.
Handles connection to Tobii eye tracker and streams gaze data to LSL.
"""
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tobii_research as tr
    TOBII_AVAILABLE = True
except ImportError:
    TOBII_AVAILABLE = False
    logger.warning("tobii_research not available. Tobii eye tracker integration will be disabled.")
    tr = None

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
    PYLSL_AVAILABLE = True
except ImportError:
    PYLSL_AVAILABLE = False
    logger.warning("pylsl not available. Cannot create LSL stream for Tobii.")
    StreamInfo = None
    StreamOutlet = None
    local_clock = None


class TobiiEyetrackerStreamer:
    """Streams Tobii eye tracker gaze data to LSL.
    
    Usage:
        s = TobiiEyetrackerStreamer()
        s.start()
        ...
        s.stop()
    """
    
    def __init__(self, eyetracker_address: Optional[str] = None, nominal_srate: float = 60.0):
        """Initialize Tobii eye tracker streamer.
        
        Args:
            eyetracker_address: Optional address/URI of specific eye tracker (None = auto-detect first)
            nominal_srate: Nominal sampling rate for LSL stream (Hz)
        """
        if not TOBII_AVAILABLE:
            raise RuntimeError("tobii_research is not available")
        if not PYLSL_AVAILABLE:
            raise RuntimeError("pylsl is not available")
        
        self.eyetracker_address = eyetracker_address
        self.nominal_srate = nominal_srate
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._eyetracker: Optional[tr.EyeTracker] = None
        self._outlet: Optional[StreamOutlet] = None
        self._started = False
        self._connection_error: Optional[str] = None
    
    def start(self):
        """Start the eye tracker streamer."""
        if self._started:
            return
        
        logger.info("Starting Tobii eye tracker streamer")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="TobiiEyetrackerThread", daemon=True)
        self._thread.start()
        self._started = True
    
    def stop(self, timeout: float = 5.0):
        """Stop the eye tracker streamer."""
        if not self._started:
            return
        
        logger.info("Stopping Tobii eye tracker streamer")
        self._stop_event.set()
        
        # Try to unsubscribe immediately if we have the eyetracker
        # This helps ensure cleanup happens even if thread.join hangs
        if self._eyetracker:
            try:
                # The callback is defined in _run, so we can't unsubscribe here directly
                # But we can at least log that we're trying to stop
                logger.debug("Eye tracker connection exists, thread will handle unsubscribe")
            except Exception as e:
                logger.debug(f"Error during stop preparation: {e}")
        
        if self._thread:
            logger.debug(f"Waiting for Tobii thread to stop (timeout: {timeout}s)...")
            self._thread.join(timeout)
            if self._thread.is_alive():
                logger.warning(f"Tobii thread did not stop within {timeout} seconds - continuing anyway")
            else:
                logger.debug("Tobii thread stopped successfully")
        
        self._started = False
        self._eyetracker = None
        self._outlet = None
        logger.info("Tobii eye tracker streamer stopped")
    
    def _run(self):
        """Main thread function for streaming gaze data."""
        try:
            # Find eye tracker
            logger.info("Searching for Tobii eye tracker...")
            found_eyetrackers = tr.find_all_eyetrackers()
            
            if not found_eyetrackers:
                error_msg = "No Tobii eye tracker found"
                logger.error(error_msg)
                self._connection_error = error_msg
                return
            
            # Select eye tracker
            if self.eyetracker_address:
                # Find by address
                self._eyetracker = None
                for et in found_eyetrackers:
                    if et.address == self.eyetracker_address:
                        self._eyetracker = et
                        break
                if not self._eyetracker:
                    error_msg = f"Eye tracker with address {self.eyetracker_address} not found"
                    logger.error(error_msg)
                    self._connection_error = error_msg
                    return
            else:
                # Use first available
                self._eyetracker = found_eyetrackers[0]
            
            logger.info(f"Found Tobii eye tracker: {self._eyetracker.model} at {self._eyetracker.address}")
            logger.info(f"Device name: {self._eyetracker.device_name}")
            logger.info(f"Serial number: {self._eyetracker.serial_number}")
            
            # Create LSL stream
            # Stream gaze data in screen space coordinates
            # Channels: left_gaze_x, left_gaze_y, right_gaze_x, right_gaze_y, 
            #          left_validity, right_validity, left_pupil_diameter, right_pupil_diameter
            n_channels = 8
            info = StreamInfo(
                'Tobii_Eyetracker',
                'ET',  # Eye Tracker type
                n_channels,
                self.nominal_srate,
                'float32',
                self._eyetracker.address
            )
            
            # Add channel labels
            desc = info.desc()
            chns = desc.append_child("channels")
            channel_names = [
                "left_gaze_x", "left_gaze_y",
                "right_gaze_x", "right_gaze_y",
                "left_validity", "right_validity",
                "left_pupil_diameter", "right_pupil_diameter"
            ]
            for i, ch_name in enumerate(channel_names):
                ch = chns.append_child("channel")
                ch.append_child_value("label", ch_name)
                ch.append_child_value("index", str(i))
                ch.append_child_value("type", "ET")
                if "gaze" in ch_name:
                    ch.append_child_value("unit", "normalized")  # Normalized screen coordinates (0-1)
                elif "validity" in ch_name:
                    ch.append_child_value("unit", "boolean")  # 0 or 1
                elif "pupil" in ch_name:
                    ch.append_child_value("unit", "mm")
            
            # Add metadata
            desc.append_child_value("manufacturer", "Tobii")
            desc.append_child_value("device_id", self._eyetracker.serial_number)
            desc.append_child_value("device_name", self._eyetracker.device_name or "Unknown")
            desc.append_child_value("model", self._eyetracker.model)
            desc.append_child_value("address", self._eyetracker.address)
            desc.append_child_value("coordinate_system", "screen_space_normalized")  # 0-1 normalized coordinates
            
            outlet = StreamOutlet(info)
            self._outlet = outlet
            logger.info("LSL outlet created successfully for Tobii eye tracker")
            
            # Define gaze data callback
            def gaze_data_callback(gaze_data):
                """Callback function for gaze data."""
                if self._stop_event.is_set() or not self._outlet:
                    return
                
                try:
                    # Extract gaze data in screen space coordinates (normalized 0-1)
                    # left_gaze_point_on_display_area and right_gaze_point_on_display_area
                    left_gaze = gaze_data.get('left_gaze_point_on_display_area', (float('nan'), float('nan')))
                    right_gaze = gaze_data.get('right_gaze_point_on_display_area', (float('nan'), float('nan')))
                    
                    # Extract validity
                    left_validity = gaze_data.get('left_gaze_point_validity', 0)
                    right_validity = gaze_data.get('right_gaze_point_validity', 0)
                    
                    # Extract pupil diameter
                    left_pupil = gaze_data.get('left_pupil_diameter', float('nan'))
                    right_pupil = gaze_data.get('right_pupil_diameter', float('nan'))
                    
                    # Build sample: [left_x, left_y, right_x, right_y, left_validity, right_validity, left_pupil, right_pupil]
                    sample = [
                        float(left_gaze[0]) if isinstance(left_gaze, (tuple, list)) and len(left_gaze) >= 1 else float('nan'),
                        float(left_gaze[1]) if isinstance(left_gaze, (tuple, list)) and len(left_gaze) >= 2 else float('nan'),
                        float(right_gaze[0]) if isinstance(right_gaze, (tuple, list)) and len(right_gaze) >= 1 else float('nan'),
                        float(right_gaze[1]) if isinstance(right_gaze, (tuple, list)) and len(right_gaze) >= 2 else float('nan'),
                        float(left_validity),
                        float(right_validity),
                        float(left_pupil) if left_pupil is not None else float('nan'),
                        float(right_pupil) if right_pupil is not None else float('nan')
                    ]
                    
                    # Use system timestamp from gaze data (in microseconds, convert to seconds)
                    system_timestamp = gaze_data.get('system_time_stamp', 0) / 1000000.0
                    if system_timestamp == 0:
                        system_timestamp = local_clock()
                    
                    # Push to LSL
                    self._outlet.push_sample(sample, system_timestamp)
                    
                except Exception as e:
                    logger.debug(f"Error processing gaze data: {e}")
            
            # Subscribe to gaze data
            self._eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
            logger.info("Subscribed to Tobii gaze data")
            
            # Keep running until stopped
            while not self._stop_event.is_set():
                time.sleep(0.1)
            
            # Unsubscribe before exiting
            try:
                self._eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)
                logger.info("Unsubscribed from Tobii gaze data")
            except Exception as e:
                logger.debug(f"Error unsubscribing: {e}")
        
        except Exception as e:
            error_msg = str(e)
            self._connection_error = error_msg
            logger.error(f"Tobii eye tracker error: {error_msg}", exc_info=True)
        finally:
            self._eyetracker = None
            self._outlet = None

