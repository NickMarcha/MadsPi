"""BrainFlow-backed EmotiBit streamer that republishes data to LSL.

This module provides a small class `EmotiBitBrainflowStreamer` which uses BrainFlow
`BoardShim` to read EmotiBit data and republishes it to LSL using `pylsl`.

Notes:
- This is intentionally conservative and pushes per-sample with `local_clock()`.
- Requires `brainflow` and `pylsl` installed in the environment.
"""
from typing import Optional
import time
import threading
import queue

try:
    from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowPresets
    from brainflow.data_filter import DataFilter
    BRAINFLOW_AVAILABLE = True
except Exception:
    BRAINFLOW_AVAILABLE = False

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
    PYLSl_AVAILABLE = True
except Exception:
    PYLSl_AVAILABLE = False


class EmotiBitBrainflowStreamer:
    """Read EmotiBit with BrainFlow and publish to a single multi-channel LSL stream.

    Usage:
        s = EmotiBitBrainflowStreamer(ip_address='192.168.0.255')
        s.start()
        ...
        s.stop()
    """

    def __init__(self, ip_address: Optional[str] = None, nominal_srate: float = 25.0):
        if not BRAINFLOW_AVAILABLE:
            raise RuntimeError('brainflow is not available')
        if not PYLSl_AVAILABLE:
            raise RuntimeError('pylsl is not available')

        self.ip_address = ip_address
        self.nominal_srate = nominal_srate
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._board = None
        self._outlet: Optional[StreamOutlet] = None
        self._started = False
        self._connection_error: Optional[str] = None  # Store connection error message

    def start(self):
        if self._started:
            return
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting BrainFlow EmotiBit streamer (ip_address={self.ip_address})")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name='EmotiBitBrainflowThread', daemon=True)
        self._thread.start()
        self._started = True

    def stop(self, timeout: float = 5.0):
        if not self._started:
            return
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Stopping BrainFlow EmotiBit streamer")
        self._stop_event.set()
        
        # Try to join the thread, but don't wait forever if it's stuck
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                logger.warning(
                    f"BrainFlow thread did not stop within {timeout} seconds. "
                    "The connection attempt may be hanging. The thread will continue in background."
                )
        
        # Cleanup - only try if board was actually created and session prepared
        try:
            if self._board:
                # Check if session was actually prepared before trying to stop
                try:
                    self._board.stop_stream()
                except Exception as e:
                    logger.debug(f"Could not stop stream (may not have started): {e}")
                try:
                    self._board.release_session()
                except Exception as e:
                    logger.debug(f"Could not release session (may not have been prepared): {e}")
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")
        
        self._started = False
        self._board = None
        self._outlet = None

    def _run(self):
        import logging
        logger = logging.getLogger(__name__)
        
        params = BrainFlowInputParams()
        if self.ip_address:
            params.ip_address = self.ip_address
            logger.info(f"Using specified IP address: {self.ip_address}")
        else:
            logger.info("No IP address specified, using auto-discovery (this may take 15-30 seconds)")
            # Increase timeout for auto-discovery (default is often too short)
            # BrainFlow uses timeout in seconds, 0 means default, but we'll try to set a longer one
            try:
                params.timeout = 30  # 30 second timeout for auto-discovery
                logger.info("Set auto-discovery timeout to 30 seconds")
            except AttributeError:
                # Some BrainFlow versions may not support timeout parameter
                logger.debug("Timeout parameter not available in this BrainFlow version")

        board_id = BoardIds.EMOTIBIT_BOARD.value
        board = BoardShim(board_id, params)
        self._board = board
        logger.info("BrainFlow thread started")

        try:
            logger.info("Attempting to prepare BrainFlow board session...")
            logger.info("Note: This may take 10-30 seconds, especially with auto-discovery")
            logger.info("If the device is already in use by another program, this will fail")
            
            # Check if we should stop before attempting connection
            if self._stop_event.is_set():
                logger.info("Stop requested before connection attempt, aborting")
                return
            
            # Try to prepare session with timeout protection
            # Since BrainFlow's prepare_session() can hang indefinitely, we'll use a timeout wrapper
            
            start_time = time.time()
            result_queue = queue.Queue()
            exception_queue = queue.Queue()
            
            def prepare_with_timeout():
                """Run prepare_session in a way that can be monitored."""
                try:
                    board.prepare_session()
                    result_queue.put(True)
                except Exception as e:
                    exception_queue.put(e)
            
            # Run prepare_session in a separate thread so we can timeout
            prep_thread = threading.Thread(target=prepare_with_timeout, daemon=True, name='PrepareSessionThread')
            prep_thread.start()
            
            # Wait for result with timeout (max 45 seconds for auto-discovery)
            max_wait_time = 45.0 if not self.ip_address else 20.0
            prep_thread.join(timeout=max_wait_time)
            
            elapsed = time.time() - start_time
            
            # Check if thread is still running (timed out)
            if prep_thread.is_alive():
                logger.error(
                    f"prepare_session() timed out after {elapsed:.2f} seconds. "
                    "The connection attempt is taking too long or hanging."
                )
                logger.error(
                    "This usually means:\n"
                    "  1. Device is not reachable on the network\n"
                    "  2. Auto-discovery is failing (try specifying IP address)\n"
                    "  3. Network connectivity issues\n"
                    "  4. Device is on a different subnet"
                )
                if not self.ip_address:
                    logger.info("RECOMMENDATION: Try specifying the device IP address (e.g., 10.10.10.10) in LSL Manager")
                
                # Set stop event and return - don't raise exception to avoid crash
                self._stop_event.set()
                self._connection_error = f"Connection timeout after {elapsed:.2f} seconds"
                return
            
            # Check for exception
            if not exception_queue.empty():
                prep_error = exception_queue.get()
                error_str = str(prep_error)
                logger.error(f"prepare_session() failed after {elapsed:.2f} seconds: {error_str}")
                
                # Provide more specific diagnostics
                if "BOARD_NOT_READY_ERROR" in error_str or "7" in error_str:
                    logger.error(
                        "BOARD_NOT_READY_ERROR typically means:\n"
                        "  1. Device is not on the network or not powered on\n"
                        "  2. Device is already in use by another program (e.g., EmotiBit Oscilloscope)\n"
                        "  3. Network connectivity issues (firewall, wrong subnet, etc.)\n"
                        "  4. Auto-discovery timeout (try specifying IP address directly)\n"
                        "  5. Device IP address may have changed"
                    )
                    if not self.ip_address:
                        logger.info("Troubleshooting tip: Try specifying the device IP address in LSL Manager settings")
                
                raise prep_error  # Re-raise the original error
            
            # Check if we got a result
            if not result_queue.empty():
                logger.info(f"BrainFlow board session prepared successfully (took {elapsed:.2f} seconds)")
            else:
                # Shouldn't happen, but handle it
                logger.warning("prepare_session() completed but no result received")
                return
            
            logger.info("Starting BrainFlow stream...")
            board.start_stream()
            logger.info("BrainFlow stream started successfully")

            # quick warmup read
            time.sleep(0.2)
            data = board.get_board_data()
            logger.debug(f"BrainFlow got initial data: {data.shape if hasattr(data, 'shape') else 'None'}")

            # If no data yet, wait a bit
            if data is None or getattr(data, 'size', 0) == 0:
                logger.debug(f"BrainFlow after warmup: {data.shape if hasattr(data, 'shape') else 'None'}")
                time.sleep(0.2)
                data = board.get_board_data()

            # Get channel count and names from BrainFlow
            try:
                n_channels = int(data.shape[0]) if data is not None and getattr(data, 'shape', None) else 16
                
                # Try to get channel names from BrainFlow using presets
                # BrainFlow EmotiBit uses presets: DEFAULT_PRESET, AUXILIARY_PRESET, ANCILLARY_PRESET
                channel_names = []
                
                # Map EmotiBit TypeTags to descriptive names based on documentation
                # EmotiBit TypeTags order (typical): T1, H0, EA, PI, PR, PG, AX, AY, AZ, GX, GY, GZ, MX, MY, MZ
                typetag_to_name = {
                    "T1": "Temperature", "T0": "Temperature", "TH": "Temperature_Thermopile",
                    "H0": "Humidity",
                    "EA": "EDA", "EL": "EDL", "ER": "EDR",
                    "PI": "PPG_IR", "PR": "PPG_Red", "PG": "PPG_Green",
                    "AX": "Accel_X", "AY": "Accel_Y", "AZ": "Accel_Z",
                    "GX": "Gyro_X", "GY": "Gyro_Y", "GZ": "Gyro_Z",
                    "MX": "Mag_X", "MY": "Mag_Y", "MZ": "Mag_Z",
                    "HR": "Heart_Rate", "BI": "Inter_Beat_Interval",
                    "SA": "SCR_Amplitude", "SR": "SCR_Rise_Time", "SF": "SCR_Frequency"
                }
                
                # Standard EmotiBit TypeTag order based on BrainFlow DEFAULT_PRESET
                # This is the typical order for EmotiBit channels
                emotibit_typetags = [
                    "T1",  # Temperature
                    "H0",  # Humidity (if available, may not be present on all devices)
                    "EA",  # EDA - Electrodermal Activity
                    "PI",  # PPG Infrared
                    "PR",  # PPG Red
                    "PG",  # PPG Green
                    "AX",  # Accelerometer X
                    "AY",  # Accelerometer Y
                    "AZ",  # Accelerometer Z
                    "GX",  # Gyroscope X
                    "GY",  # Gyroscope Y
                    "GZ",  # Gyroscope Z
                    "MX",  # Magnetometer X
                    "MY",  # Magnetometer Y
                    "MZ",  # Magnetometer Z
                ]
                
                # Try to map channels using TypeTags
                # Use TypeTag names for the first channels that match the standard order
                for i in range(min(n_channels, len(emotibit_typetags))):
                    typetag = emotibit_typetags[i]
                    channel_names.append(typetag_to_name.get(typetag, f"{typetag}_{i}"))
                
                # If we don't have enough channel names, use default EmotiBit channel names
                # Based on EmotiBit TypeTags from documentation
                if len(channel_names) < n_channels:
                    # Standard EmotiBit channel order based on TypeTags
                    default_names = [
                        "Temperature",      # T1
                        "Humidity",         # H0 (if available)
                        "EDA",              # EA - Electrodermal Activity
                        "PPG_IR",           # PI - PPG Infrared
                        "PPG_Red",          # PR - PPG Red
                        "PPG_Green",        # PG - PPG Green
                        "Accel_X",          # AX
                        "Accel_Y",          # AY
                        "Accel_Z",          # AZ
                        "Gyro_X",           # GX
                        "Gyro_Y",           # GY
                        "Gyro_Z",           # GZ
                        "Mag_X",            # MX
                        "Mag_Y",            # MY
                        "Mag_Z",            # MZ
                    ]
                    # Extend to match channel count
                    while len(channel_names) < n_channels:
                        idx = len(channel_names)
                        if idx < len(default_names):
                            channel_names.append(default_names[idx])
                        else:
                            channel_names.append(f"Channel_{idx}")
                
                logger.info(f"Using {len(channel_names)} channel names for {n_channels} channels: {channel_names[:min(5, len(channel_names))]}...")
            except Exception as e:
                logger.warning(f"Could not determine channel names: {e}")
                n_channels = 16
                channel_names = [f"Channel_{i}" for i in range(n_channels)]
            
            logger.info(f"Creating LSL stream with {n_channels} channels")

            info = StreamInfo('EmotiBit_BrainFlow', 'EmotiBit', n_channels, self.nominal_srate, 'float32', 'emotibit_brainflow_0')
            
            # Add channel labels to LSL stream metadata
            desc = info.desc()
            chns = desc.append_child("channels")
            for i, ch_name in enumerate(channel_names[:n_channels]):
                ch = chns.append_child("channel")
                ch.append_child_value("label", str(ch_name))
                ch.append_child_value("index", str(i))
                ch.append_child_value("type", "EmotiBit")
                
                # Add unit based on EmotiBit TypeTags and documentation
                # Units from EmotiBit documentation: degrees_celsius, percent, microsiemens, raw, g, degrees_per_second, microtesla, bpm, mS
                ch_name_upper = ch_name.upper()
                if "TEMPERATURE" in ch_name_upper or "T1" in ch_name_upper or "T0" in ch_name_upper or "TH" in ch_name_upper:
                    ch.append_child_value("unit", "degrees_celsius")
                elif "HUMIDITY" in ch_name_upper or "H0" in ch_name_upper:
                    ch.append_child_value("unit", "percent")
                elif "EDA" in ch_name_upper or "EA" in ch_name_upper or "EL" in ch_name_upper or "ER" in ch_name_upper:
                    ch.append_child_value("unit", "microsiemens")
                elif "PPG" in ch_name_upper or "PI" in ch_name_upper or "PR" in ch_name_upper or "PG" in ch_name_upper:
                    ch.append_child_value("unit", "raw")
                elif "ACCEL" in ch_name_upper or "AX" in ch_name_upper or "AY" in ch_name_upper or "AZ" in ch_name_upper:
                    ch.append_child_value("unit", "g")
                elif "GYRO" in ch_name_upper or "GX" in ch_name_upper or "GY" in ch_name_upper or "GZ" in ch_name_upper:
                    ch.append_child_value("unit", "degrees_per_second")
                elif "MAG" in ch_name_upper or "MX" in ch_name_upper or "MY" in ch_name_upper or "MZ" in ch_name_upper:
                    ch.append_child_value("unit", "microtesla")  # Correct unit for magnetometer
                elif "HEART_RATE" in ch_name_upper or "HR" in ch_name_upper:
                    ch.append_child_value("unit", "bpm")
                elif "INTER_BEAT" in ch_name_upper or "BI" in ch_name_upper:
                    ch.append_child_value("unit", "mS")
                elif "SCR" in ch_name_upper:
                    if "AMPLITUDE" in ch_name_upper or "SA" in ch_name_upper:
                        ch.append_child_value("unit", "microsiemens")
                    elif "RISE_TIME" in ch_name_upper or "SR" in ch_name_upper:
                        ch.append_child_value("unit", "seconds")
                    elif "FREQUENCY" in ch_name_upper or "SF" in ch_name_upper:
                        ch.append_child_value("unit", "Hz")
            
            # Add additional metadata
            desc.append_child_value("manufacturer", "EmotiBit")
            desc.append_child_value("device_id", getattr(params, 'serial_number', 'unknown'))
            if self.ip_address:
                desc.append_child_value("ip_address", self.ip_address)
            
            outlet = StreamOutlet(info)
            self._outlet = outlet
            logger.info(f"LSL outlet created successfully with {n_channels} labeled channels")

            # Main loop: read and push samples
            while not self._stop_event.is_set():
                data = board.get_board_data()
                if data is None or getattr(data, 'size', 0) == 0:
                    time.sleep(0.01)
                    continue

                n_samples = data.shape[1]
                # push sample-by-sample with current LSL timestamp
                for i in range(n_samples):
                    row = data[:, i].astype(float).tolist()
                    try:
                        outlet.push_sample(row, timestamp=local_clock())
                    except Exception:
                        # swallow occasional LSL errors to keep streaming
                        pass

                # small sleep to avoid busy-loop
                time.sleep(0.001)

        except Exception as e:
            error_msg = str(e)
            # Store error message for checking by session window
            self._connection_error = error_msg
            logger.error(f"BrainFlow error: {error_msg}", exc_info=True)
            
            # Provide helpful error messages for common issues
            if "BOARD_NOT_READY_ERROR" in error_msg or "unable to prepare streaming session" in error_msg:
                logger.error(
                    "EmotiBit device not found or not ready. "
                    "Please ensure:\n"
                    "  1. EmotiBit device is powered on and connected to the network\n"
                    "  2. Device is on the same network as this computer\n"
                    "  3. NO OTHER PROGRAM is using the EmotiBit device (e.g., EmotiBit Oscilloscope, other BrainFlow apps)\n"
                    "     → Close any other programs that might be connected to the device\n"
                    "  4. If using auto-discovery, wait 15-30 seconds and try again\n"
                    "  5. Try specifying the IP address directly in the LSL Manager settings\n"
                    "  6. Check firewall settings - BrainFlow needs UDP port access\n"
                    "  7. Verify device IP hasn't changed (check router or device settings)"
                )
                # Additional diagnostic info
                if not self.ip_address:
                    logger.info("DIAGNOSTIC: Auto-discovery is being used. This can fail if:")
                    logger.info("  - Device is on a different subnet")
                    logger.info("  - Network has multiple interfaces (WiFi + Ethernet)")
                    logger.info("  - Firewall is blocking UDP broadcasts")
                    logger.info("  → Try specifying the device IP address (e.g., 10.10.10.10) in LSL Manager")
            elif "timeout" in error_msg.lower():
                logger.error(
                    "Connection timeout. The EmotiBit device may not be reachable. "
                    "Try specifying the IP address directly."
                )
            
            # ensure resources are released on error
            try:
                if board:
                    board.stop_stream()
                    board.release_session()
            except Exception as e2:
                logger.error(f"Error cleaning up board: {e2}")
                pass
        finally:
            try:
                board.stop_stream()
                board.release_session()
            except Exception:
                pass
            self._board = None
            self._outlet = None
