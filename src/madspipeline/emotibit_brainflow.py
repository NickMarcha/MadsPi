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

try:
    from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
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
        if self._thread:
            self._thread.join(timeout)
        # cleanup
        try:
            if self._board:
                self._board.stop_stream()
                self._board.release_session()
        except Exception:
            pass
        self._started = False

    def _run(self):
        import logging
        logger = logging.getLogger(__name__)
        
        params = BrainFlowInputParams()
        if self.ip_address:
            params.ip_address = self.ip_address
            logger.info(f"Using specified IP address: {self.ip_address}")
        else:
            logger.info("No IP address specified, using auto-discovery (this may take longer)")

        board_id = BoardIds.EMOTIBIT_BOARD.value
        board = BoardShim(board_id, params)
        self._board = board
        logger.info("BrainFlow thread started")

        try:
            logger.info("Attempting to prepare BrainFlow board session...")
            board.prepare_session()
            logger.info("BrainFlow board session prepared successfully")
            
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
                # Try to get channel names from BrainFlow
                # BrainFlow uses get_eeg_channels, get_emg_channels, etc. but for EmotiBit we need to check what's available
                channel_names = []
                try:
                    # Try to get channel names - BrainFlow may have different methods
                    if hasattr(BoardShim, 'get_eeg_channels'):
                        eeg_ch = BoardShim.get_eeg_channels(board_id)
                        if eeg_ch:
                            channel_names.extend([f"EEG_{i}" for i in range(len(eeg_ch))])
                except:
                    pass
                
                # If we don't have channel names, use default EmotiBit channel names
                # Based on typical EmotiBit data: Temperature, Humidity, EDA, PPG (IR, Red, Green), 
                # Accelerometer (X,Y,Z), Gyroscope (X,Y,Z), Magnetometer (X,Y,Z), etc.
                if len(channel_names) < n_channels:
                    default_names = [
                        "Temperature", "Humidity", "EDA", 
                        "PPG_IR", "PPG_Red", "PPG_Green",
                        "Accel_X", "Accel_Y", "Accel_Z",
                        "Gyro_X", "Gyro_Y", "Gyro_Z"
                    ]
                    # Extend to match channel count
                    while len(channel_names) < n_channels:
                        idx = len(channel_names)
                        if idx < len(default_names):
                            channel_names.append(default_names[idx])
                        else:
                            channel_names.append(f"Channel_{idx}")
                
                logger.info(f"Using {len(channel_names)} channel names for {n_channels} channels")
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
            logger.error(f"BrainFlow error: {error_msg}", exc_info=True)
            
            # Provide helpful error messages for common issues
            if "BOARD_NOT_READY_ERROR" in error_msg or "unable to prepare streaming session" in error_msg:
                logger.error(
                    "EmotiBit device not found or not ready. "
                    "Please ensure:\n"
                    "  1. EmotiBit device is powered on and connected to the network\n"
                    "  2. Device is on the same network as this computer\n"
                    "  3. If using auto-discovery, wait a few seconds and try again\n"
                    "  4. Try specifying the IP address in the LSL Manager settings"
                )
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
