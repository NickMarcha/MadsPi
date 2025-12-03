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
        
        # Enable BrainFlow's board logger for detailed connection diagnostics
        # This will show what IPs are being tried and connection attempts
        try:
            BoardShim.enable_dev_board_logger()
            logger.debug("Enabled BrainFlow board logger for connection diagnostics")
        except Exception as e:
            logger.debug(f"Could not enable board logger: {e}")
        
        params = BrainFlowInputParams()
        if self.ip_address:
            params.ip_address = self.ip_address
            logger.info(f"Using specified IP address: {self.ip_address}")
            # Note: If this is a broadcast address (e.g., .254, .255), it won't work
            # The device needs its actual IP address (e.g., 10.10.10.10)
        else:
            logger.info("No IP address specified, using auto-discovery (this may take 15-30 seconds)")
            logger.info("Auto-discovery will try multiple broadcast addresses on your network")
            # Increase timeout for auto-discovery (default is often too short)
            # BrainFlow uses timeout in seconds, 0 means default, but we'll try to set a longer one
            try:
                params.timeout = 30  # 30 second timeout for auto-discovery
                logger.info("Set auto-discovery timeout to 30 seconds")
            except AttributeError:
                # Some BrainFlow versions may not support timeout parameter
                logger.debug("Timeout parameter not available in this BrainFlow version")
        
        # Note: BrainFlow doesn't expose many other connection parameters for EmotiBit
        # The main settings are ip_address and timeout

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
                    logger.info("HOW TO FIND DEVICE IP:")
                    logger.info("  - Check EmotiBit Oscilloscope: The device IP is shown when connected")
                    logger.info("  - Use Arduino Serial Monitor: Press 'i' to print device info with IP address")
                    logger.info("  - Check your router's connected devices list")
                    logger.info("  - The IP should be in the 10.10.10.x range (NOT .254 or .255 - those are broadcast addresses)")
                else:
                    logger.warning(f"WARNING: The IP address '{self.ip_address}' might not be correct.")
                    logger.warning("  - .254 and .255 are typically broadcast/gateway addresses, not device IPs")
                    logger.warning("  - Device IPs are usually in the range 10.10.10.1-253")
                    logger.info("HOW TO FIND CORRECT DEVICE IP:")
                    logger.info("  - Check EmotiBit Oscilloscope: The device IP is shown when connected")
                    logger.info("  - Use Arduino Serial Monitor: Press 'i' to print device info with IP address")
                    logger.info("  - Check your router's connected devices list")
                
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
                # Try to get board description to understand channel layout
                try:
                    board_descr = BoardShim.get_board_descr(board_id)
                    logger.info(f"BrainFlow board description: {board_descr}")
                    # Log specific channel information if available
                    if 'temperature_channels' in board_descr:
                        logger.info(f"Temperature channels: {board_descr['temperature_channels']}")
                    if 'eda_channels' in board_descr:
                        logger.info(f"EDA channels: {board_descr['eda_channels']}")
                    if 'ppg_channels' in board_descr:
                        logger.info(f"PPG channels: {board_descr['ppg_channels']}")
                    if 'accel_channels' in board_descr:
                        logger.info(f"Accelerometer channels: {board_descr['accel_channels']}")
                except Exception as e:
                    logger.debug(f"Could not get board description: {e}")
                
                # Determine channel structure from all presets
                # Based on log analysis:
                # - ANCILLARY_PRESET (6 channels): package_num(0), EDA(1), temperature(2), temperature2(3), timestamp(4), marker(5)
                # - AUXILIARY_PRESET (6 channels): package_num(0), PPG_IR(1), PPG_Red(2), PPG_Green(3), timestamp(4), marker(5)
                # - DEFAULT_PRESET (12 channels): package_num(0), accel(1-3), gyro(4-6), mag(7-9), timestamp(10), marker(11)
                
                # Wait a bit for data to accumulate in all presets
                time.sleep(0.5)
                
                # Try to get data from each preset to determine structure
                data_anc = None
                data_aux = None
                data_default = None
                
                try:
                    data_anc = board.get_current_board_data(1, BrainFlowPresets.ANCILLARY_PRESET)
                except Exception:
                    pass
                
                try:
                    data_aux = board.get_current_board_data(1, BrainFlowPresets.AUXILIARY_PRESET)
                except Exception:
                    pass
                
                try:
                    data_default = board.get_current_board_data(1, BrainFlowPresets.DEFAULT_PRESET)
                except Exception:
                    pass
                
                # Build combined channel list in order: ANCILLARY, AUXILIARY, DEFAULT
                channel_names = []
                
                # ANCILLARY_PRESET: channels 1-3 (skip package_num, timestamp, marker)
                # Based on logs and user feedback: channel 1 = EDA, channel 2 = Temperature, channel 3 = Temperature2
                if data_anc is not None and data_anc.size > 0 and data_anc.shape[0] >= 4:
                    channel_names.extend(["EDA", "Temperature", "Temperature2"])
                
                # AUXILIARY_PRESET: channels 1-3 (skip package_num, timestamp, marker)
                # Based on logs: channels 1-3 are PPG_IR, PPG_Red, PPG_Green
                if data_aux is not None and data_aux.size > 0 and data_aux.shape[0] >= 4:
                    channel_names.extend(["PPG_IR", "PPG_Red", "PPG_Green"])
                
                # DEFAULT_PRESET: channels 1-9 (skip package_num, timestamp, marker)
                # Motion sensors: accel (1-3), gyro (4-6), mag (7-9)
                if data_default is not None and data_default.size > 0 and data_default.shape[0] >= 10:
                    channel_names.extend(["Accel_X", "Accel_Y", "Accel_Z", 
                                        "Gyro_X", "Gyro_Y", "Gyro_Z",
                                        "Mag_X", "Mag_Y", "Mag_Z"])
                
                n_channels = len(channel_names)
                
                # Fallback if no data available yet
                if n_channels == 0:
                    # Use expected structure based on documentation
                    channel_names = ["EDA", "Temperature", "Temperature2", 
                                   "PPG_IR", "PPG_Red", "PPG_Green",
                                   "Accel_X", "Accel_Y", "Accel_Z", 
                                   "Gyro_X", "Gyro_Y", "Gyro_Z",
                                   "Mag_X", "Mag_Y", "Mag_Z"]
                    n_channels = len(channel_names)
                
                logger.info(f"Using {len(channel_names)} channel names: {channel_names}")
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

            # Check available presets and log data from each
            # Wait a bit for data to accumulate before checking
            time.sleep(1.0)
            try:
                available_presets = BoardShim.get_board_presets(board_id)
                logger.info(f"Available BrainFlow presets for EmotiBit: {available_presets}")
                logger.info(f"Preset mapping: 0=DEFAULT_PRESET, 1=AUXILIARY_PRESET, 2=ANCILLARY_PRESET")
                
                # Try to get data from each preset to understand the structure
                # Use get_current_board_data() which reads recent data without clearing the buffer
                try:
                    data_default = board.get_current_board_data(10, BrainFlowPresets.DEFAULT_PRESET)
                    if data_default is not None and data_default.size > 0:
                        logger.info(f"DEFAULT_PRESET: shape={data_default.shape}, first sample (all channels): {data_default[:, 0].tolist() if data_default.shape[1] > 0 else 'no data'}")
                    else:
                        logger.info(f"DEFAULT_PRESET: No data available yet (shape: {data_default.shape if data_default is not None else 'None'})")
                except Exception as e:
                    logger.warning(f"Could not read DEFAULT_PRESET: {e}")
                
                try:
                    data_aux = board.get_current_board_data(10, BrainFlowPresets.AUXILIARY_PRESET)
                    if data_aux is not None and data_aux.size > 0:
                        logger.info(f"AUXILIARY_PRESET: shape={data_aux.shape}, first sample (all channels): {data_aux[:, 0].tolist() if data_aux.shape[1] > 0 else 'no data'}")
                        # Log which channels have non-zero data (PPG should be in specific channels)
                        non_zero_channels = [i for i in range(data_aux.shape[0]) if data_aux.shape[1] > 0 and abs(data_aux[i, 0]) > 0.001]
                        logger.info(f"AUXILIARY_PRESET: Channels with data: {non_zero_channels}")
                    else:
                        logger.info(f"AUXILIARY_PRESET: No data available yet (shape: {data_aux.shape if data_aux is not None else 'None'})")
                except Exception as e:
                    logger.warning(f"Could not read AUXILIARY_PRESET: {e}")
                
                try:
                    data_anc = board.get_current_board_data(10, BrainFlowPresets.ANCILLARY_PRESET)
                    if data_anc is not None and data_anc.size > 0:
                        logger.info(f"ANCILLARY_PRESET: shape={data_anc.shape}, first sample (all channels): {data_anc[:, 0].tolist() if data_anc.shape[1] > 0 else 'no data'}")
                        # Log which channels have non-zero data (Temperature/EDA should be in specific channels)
                        non_zero_channels = [i for i in range(data_anc.shape[0]) if data_anc.shape[1] > 0 and abs(data_anc[i, 0]) > 0.001]
                        logger.info(f"ANCILLARY_PRESET: Channels with data: {non_zero_channels}")
                    else:
                        logger.info(f"ANCILLARY_PRESET: No data available yet (shape: {data_anc.shape if data_anc is not None else 'None'})")
                except Exception as e:
                    logger.warning(f"Could not read ANCILLARY_PRESET: {e}")
            except Exception as e:
                logger.warning(f"Could not check presets: {e}")

            # Main loop: read from all three presets and combine into single stream
            # - ANCILLARY_PRESET: EDA, temperature, temperature2
            # - AUXILIARY_PRESET: PPG (IR, Red, Green)
            # - DEFAULT_PRESET: motion sensors (accel, gyro, mag)
            first_sample_logged = False
            last_anc_data = None
            last_aux_data = None
            last_default_data = None
            
            while not self._stop_event.is_set():
                # Read from all three presets
                data_anc = None
                data_aux = None
                data_default = None
                
                try:
                    data_anc = board.get_current_board_data(1, BrainFlowPresets.ANCILLARY_PRESET)
                    if data_anc is not None and data_anc.size > 0 and data_anc.shape[1] > 0:
                        last_anc_data = data_anc[:, -1]  # Get most recent sample
                except Exception as e:
                    logger.debug(f"Could not read ANCILLARY_PRESET: {e}")
                
                try:
                    data_aux = board.get_current_board_data(1, BrainFlowPresets.AUXILIARY_PRESET)
                    if data_aux is not None and data_aux.size > 0 and data_aux.shape[1] > 0:
                        last_aux_data = data_aux[:, -1]  # Get most recent sample
                except Exception as e:
                    logger.debug(f"Could not read AUXILIARY_PRESET: {e}")
                
                try:
                    data_default = board.get_current_board_data(1, BrainFlowPresets.DEFAULT_PRESET)
                    if data_default is not None and data_default.size > 0 and data_default.shape[1] > 0:
                        last_default_data = data_default[:, -1]  # Get most recent sample
                except Exception as e:
                    logger.debug(f"Could not read DEFAULT_PRESET: {e}")
                
                # Combine data from all presets into single sample
                # Order: ANCILLARY (EDA, temperature, temperature2), AUXILIARY (PPG), DEFAULT (motion)
                combined_sample = []
                
                # ANCILLARY_PRESET: channels 1, 2, 3 (EDA, temperature, temperature2)
                if last_anc_data is not None and len(last_anc_data) >= 4:
                    combined_sample.extend([
                        float(last_anc_data[1]),  # EDA
                        float(last_anc_data[2]),  # Temperature
                        float(last_anc_data[3])   # Temperature2
                    ])
                else:
                    # Use zeros if no data available
                    combined_sample.extend([0.0, 0.0, 0.0])
                
                # AUXILIARY_PRESET: channels 1, 2, 3 (PPG_IR, PPG_Red, PPG_Green)
                if last_aux_data is not None and len(last_aux_data) >= 4:
                    combined_sample.extend([
                        float(last_aux_data[1]),  # PPG_IR
                        float(last_aux_data[2]),  # PPG_Red
                        float(last_aux_data[3])   # PPG_Green
                    ])
                else:
                    # Use zeros if no data available
                    combined_sample.extend([0.0, 0.0, 0.0])
                
                # DEFAULT_PRESET: channels 1-9 (accel, gyro, mag)
                if last_default_data is not None and len(last_default_data) >= 10:
                    combined_sample.extend([
                        float(last_default_data[1]),  # Accel_X
                        float(last_default_data[2]),  # Accel_Y
                        float(last_default_data[3]),  # Accel_Z
                        float(last_default_data[4]),  # Gyro_X
                        float(last_default_data[5]),  # Gyro_Y
                        float(last_default_data[6]),  # Gyro_Z
                        float(last_default_data[7]),  # Mag_X
                        float(last_default_data[8]),  # Mag_Y
                        float(last_default_data[9])   # Mag_Z
                    ])
                else:
                    # Use zeros if no data available
                    combined_sample.extend([0.0] * 9)
                
                # Log first combined sample
                if not first_sample_logged:
                    logger.info(f"First combined sample: {combined_sample}")
                    first_sample_logged = True
                
                # Push combined sample to LSL
                try:
                    outlet.push_sample(combined_sample, timestamp=local_clock())
                except Exception as e:
                    logger.debug(f"LSL push error: {e}")
                    pass

                # Small sleep to avoid busy-loop
                time.sleep(0.04)  # ~25 Hz (matching EmotiBit sampling rate)

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
                    logger.info("HOW TO FIND DEVICE IP:")
                    logger.info("  - Check EmotiBit Oscilloscope: The device IP is shown when connected")
                    logger.info("  - Use Arduino Serial Monitor: Press 'i' to print device info with IP address")
                    logger.info("  - Check your router's connected devices list")
                else:
                    logger.warning(f"WARNING: The IP address '{self.ip_address}' might not be correct.")
                    logger.warning("  - .254 and .255 are typically broadcast/gateway addresses, not device IPs")
                    logger.warning("  - Device IPs are usually in the range 10.10.10.1-253")
                    logger.info("HOW TO FIND CORRECT DEVICE IP:")
                    logger.info("  - Check EmotiBit Oscilloscope: The device IP is shown when connected")
                    logger.info("  - Use Arduino Serial Monitor: Press 'i' to print device info with IP address")
                    logger.info("  - Check your router's connected devices list")
                    logger.info("  → Try specifying the device IP address (e.g., 10.10.10.10) in LSL Manager")
            elif "timeout" in error_msg.lower():
                logger.error(
                    "Connection timeout. The EmotiBit device may not be reachable. "
                    "Try specifying the IP address directly."
                )
                if self.ip_address:
                    logger.warning(f"WARNING: The IP address '{self.ip_address}' might not be correct.")
                    logger.warning("  - .254 and .255 are typically broadcast/gateway addresses, not device IPs")
                    logger.warning("  - Device IPs are usually in the range 10.10.10.1-253")
                logger.info("HOW TO FIND DEVICE IP:")
                logger.info("  - Check EmotiBit Oscilloscope: The device IP is shown when connected")
                logger.info("  - Use Arduino Serial Monitor: Press 'i' to print device info with IP address")
                logger.info("  - Check your router's connected devices list")
            
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
