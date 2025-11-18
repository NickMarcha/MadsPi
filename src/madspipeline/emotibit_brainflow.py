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
                import logging
                logger = logging.getLogger(__name__)
                logger.info("Stopping BrainFlow EmotiBit streamer")
            return
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
        params = BrainFlowInputParams()
        if self.ip_address:
            params.ip_address = self.ip_address

        board_id = BoardIds.EMOTIBIT_BOARD.value
        board = BoardShim(board_id, params)
        self._board = board
    import logging
    logger = logging.getLogger(__name__)
    logger.info("BrainFlow thread started")

        try:
            board.prepare_session()
                logger.info("BrainFlow board session prepared")
            board.start_stream()
    logger.info("BrainFlow stream started")

            # quick warmup read
            time.sleep(0.2)
            data = board.get_board_data()
    logger.debug(f"BrainFlow got initial data: {data.shape if hasattr(data, 'shape') else 'None'}")

            # If no data yet, wait a bit
            if data is None or getattr(data, 'size', 0) == 0:
                            logger.debug(f"BrainFlow after warmup: {data.shape if hasattr(data, 'shape') else 'None'}")
                time.sleep(0.2)
                data = board.get_board_data()

            # Fallback channel count
            try:
                n_channels = int(data.shape[0]) if data is not None and getattr(data, 'shape', None) else 16
            except Exception:
                n_channels = 16
    logger.info(f"Creating LSL stream with {n_channels} channels")

            info = StreamInfo('EmotiBit_BrainFlow', 'EmotiBit', n_channels, self.nominal_srate, 'float32', 'emotibit_brainflow_0')
            outlet = StreamOutlet(info)
            self._outlet = outlet
    logger.info("LSL outlet created successfully")

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
            logger.error(f"BrainFlow error: {e}", exc_info=True)
            # ensure resources are released on error
            try:
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
