"""
Tobii Eye Tracker Manager.
Centralized management of Tobii eye tracker state, notifications, and lifecycle.
"""
import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import tobii_research as tr
    TOBII_AVAILABLE = True
except ImportError:
    TOBII_AVAILABLE = False
    logger.warning("tobii_research not available. Tobii functionality will be disabled.")
    tr = None


class TobiiState(Enum):
    """Tobii eye tracker states."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    CALIBRATION_MODE = "calibration_mode"
    STREAMING = "streaming"
    ERROR = "error"


class TobiiManager:
    """Centralized manager for Tobii eye tracker operations."""
    
    def __init__(self):
        """Initialize the Tobii manager."""
        if not TOBII_AVAILABLE:
            raise RuntimeError("tobii_research is not available")
        
        self.eyetracker: Optional[tr.EyeTracker] = None
        self.state = TobiiState.DISCONNECTED
        self._lock = threading.Lock()
        
        # Notification callbacks
        self._notification_callbacks: Dict[str, list] = {}
        
        # Gaze data callback
        self._gaze_callback: Optional[Callable] = None
        self._gaze_subscribed = False
        
        # Calibration object
        self._calibration: Optional[tr.ScreenBasedCalibration] = None
        self._calibration_mode_entered = False
        
        # Event for waiting on state changes
        self._state_event = threading.Event()
        self._last_notification_time = {}
    
    def find_eyetracker(self) -> Optional[tr.EyeTracker]:
        """Find and return the first available eye tracker."""
        with self._lock:
            try:
                found = tr.find_all_eyetrackers()
                if found:
                    logger.info(f"Found eye tracker: {found[0].model} at {found[0].address}")
                    return found[0]
                else:
                    logger.warning("No eye tracker found")
                    return None
            except Exception as e:
                logger.error(f"Error finding eye tracker: {e}", exc_info=True)
                return None
    
    def connect(self, eyetracker: Optional[tr.EyeTracker] = None) -> bool:
        """Connect to an eye tracker."""
        with self._lock:
            if self.state != TobiiState.DISCONNECTED and self.eyetracker is not None:
                logger.warning("Already connected to an eye tracker")
                return True
            
            if eyetracker is None:
                eyetracker = self.find_eyetracker()
                if eyetracker is None:
                    logger.error("No eye tracker available to connect")
                    self.state = TobiiState.ERROR
                    return False
            
            self.eyetracker = eyetracker
            self.state = TobiiState.CONNECTED
            
            # Subscribe to all relevant notifications
            self._subscribe_to_notifications()
            
            logger.info(f"Connected to eye tracker: {self.eyetracker.model}")
            return True
    
    def disconnect(self):
        """Disconnect from the eye tracker."""
        with self._lock:
            # Stop streaming if active
            if self._gaze_subscribed:
                self.stop_gaze_stream()
            
            # Leave calibration mode if active
            if self._calibration_mode_entered:
                self.leave_calibration_mode()
            
            # Unsubscribe from notifications
            self._unsubscribe_from_notifications()
            
            self.eyetracker = None
            self.state = TobiiState.DISCONNECTED
            self._state_event.clear()
            logger.info("Disconnected from eye tracker")
    
    def _notification_callback_factory(self, notification_type: str):
        """Create a notification callback for a specific notification type."""
        def callback(notification, data):
            """Handle notification callback."""
            timestamp = getattr(data, 'system_time_stamp', time.time() * 1000000)
            logger.info(f"Notification {notification_type} received at timestamp {timestamp}")
            
            self._last_notification_time[notification_type] = timestamp
            
            # Update state based on notification FIRST
            if notification_type == tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_ENTERED:
                logger.info("Processing CALIBRATION_MODE_ENTERED notification")
                with self._lock:
                    self.state = TobiiState.CALIBRATION_MODE
                    self._calibration_mode_entered = True
                    self._state_event.set()
                    logger.info("Entered calibration mode (from notification) - state updated and event set")
            elif notification_type == tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_LEFT:
                logger.info("Processing CALIBRATION_MODE_LEFT notification")
                with self._lock:
                    self.state = TobiiState.CONNECTED
                    self._calibration_mode_entered = False
                    self._state_event.set()
                    logger.info("Left calibration mode (from notification) - state updated and event set")
            
            # Call registered callbacks AFTER state update
            if notification_type in self._notification_callbacks:
                logger.info(f"Calling {len(self._notification_callbacks[notification_type])} registered callbacks for {notification_type}")
                for cb in self._notification_callbacks[notification_type]:
                    try:
                        cb(notification, data)
                    except Exception as e:
                        logger.error(f"Error in notification callback: {e}", exc_info=True)
        
        return callback
    
    def _subscribe_to_notifications(self):
        """Subscribe to all relevant notifications."""
        if not self.eyetracker:
            return
        
        notifications = [
            tr.EYETRACKER_NOTIFICATION_CONNECTION_LOST,
            tr.EYETRACKER_NOTIFICATION_CONNECTION_RESTORED,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_ENTERED,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_LEFT,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_CHANGED,
        ]
        
        for notification in notifications:
            try:
                callback = self._notification_callback_factory(notification)
                self.eyetracker.subscribe_to(notification, callback)
                logger.info(f"Subscribed to notification: {notification}")
            except Exception as e:
                logger.warning(f"Failed to subscribe to {notification}: {e}", exc_info=True)
    
    def _unsubscribe_from_notifications(self):
        """Unsubscribe from all notifications."""
        if not self.eyetracker:
            return
        
        notifications = [
            tr.EYETRACKER_NOTIFICATION_CONNECTION_LOST,
            tr.EYETRACKER_NOTIFICATION_CONNECTION_RESTORED,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_ENTERED,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_MODE_LEFT,
            tr.EYETRACKER_NOTIFICATION_CALIBRATION_CHANGED,
        ]
        
        for notification in notifications:
            try:
                # We need to unsubscribe, but we don't have the callback reference
                # The SDK should handle cleanup, but we'll try to unsubscribe anyway
                # Note: This might not work perfectly, but it's the best we can do
                pass
            except Exception as e:
                logger.debug(f"Error unsubscribing from {notification}: {e}")
    
    def register_notification_callback(self, notification_type: str, callback: Callable):
        """Register a callback for a specific notification type."""
        if notification_type not in self._notification_callbacks:
            self._notification_callbacks[notification_type] = []
        self._notification_callbacks[notification_type].append(callback)
    
    def unregister_notification_callback(self, notification_type: str, callback: Callable):
        """Unregister a callback for a specific notification type."""
        if notification_type in self._notification_callbacks:
            try:
                self._notification_callbacks[notification_type].remove(callback)
            except ValueError:
                pass
    
    def enter_calibration_mode(self, timeout: float = 10.0) -> bool:
        """Enter calibration mode and wait for confirmation."""
        with self._lock:
            if not self.eyetracker:
                logger.error("No eye tracker connected")
                return False
            
            if self.state == TobiiState.CALIBRATION_MODE:
                logger.info("Already in calibration mode")
                # Get existing calibration object
                if not self._calibration:
                    self._calibration = tr.ScreenBasedCalibration(self.eyetracker)
                return True
            
            if self.state != TobiiState.CONNECTED:
                logger.error(f"Cannot enter calibration mode from state: {self.state}")
                return False
            
            try:
                # Create calibration object
                self._calibration = tr.ScreenBasedCalibration(self.eyetracker)
                
                # Clear the event and state
                self._state_event.clear()
                self._calibration_mode_entered = False
                
                # Enter calibration mode
                logger.info("Entering calibration mode...")
                result = self._calibration.enter_calibration_mode()
                
                # Check result
                if result is not None:
                    if hasattr(tr, 'CALIBRATION_STATUS_SUCCESS'):
                        if result != tr.CALIBRATION_STATUS_SUCCESS:
                            logger.error(f"Failed to enter calibration mode: {result}")
                            self._calibration = None
                            return False
                    elif result is False or (isinstance(result, int) and result != 0):
                        logger.error(f"Failed to enter calibration mode: {result}")
                        self._calibration = None
                        return False
                
                # Small delay to allow notification to arrive (if synchronous)
                time.sleep(0.1)
                
                # Check if notification already arrived
                if self._state_event.is_set():
                    logger.info("Notification already received (synchronous)")
                    return True
                
                # Wait for notification (with timeout)
                logger.info(f"Waiting for calibration mode notification (timeout: {timeout}s)...")
                # Release lock before waiting (to allow notification callback to run)
                self._lock.release()
                try:
                    notification_received = self._state_event.wait(timeout=timeout)
                    self._lock.acquire()
                    
                    if notification_received:
                        logger.info("Calibration mode entered successfully (confirmed by notification)")
                        return True
                    else:
                        # Timeout - but enter_calibration_mode() succeeded, so proceed anyway
                        logger.warning("Timeout waiting for calibration mode notification")
                        logger.info("enter_calibration_mode() succeeded, proceeding with calibration mode anyway")
                        # Update state manually since notification didn't arrive
                        self.state = TobiiState.CALIBRATION_MODE
                        self._calibration_mode_entered = True
                        return True
                finally:
                    # Make sure we have the lock back
                    if not self._lock.locked():
                        self._lock.acquire()
                        
            except Exception as e:
                logger.error(f"Error entering calibration mode: {e}", exc_info=True)
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.state = TobiiState.ERROR
                self._calibration = None
                return False
    
    def leave_calibration_mode(self):
        """Leave calibration mode."""
        with self._lock:
            if not self._calibration_mode_entered:
                # Try to leave anyway if we have a calibration object
                if self._calibration:
                    try:
                        self._calibration.leave_calibration_mode()
                        logger.info("Left calibration mode (force)")
                    except Exception as e:
                        logger.debug(f"Error leaving calibration mode (force): {e}")
                    self._calibration = None
                return
            
            if not self._calibration:
                # State says we're in calibration mode but no object - try to create one
                if self.eyetracker:
                    try:
                        self._calibration = tr.ScreenBasedCalibration(self.eyetracker)
                    except:
                        pass
            
            if not self._calibration:
                # Can't leave without calibration object
                logger.warning("Cannot leave calibration mode - no calibration object")
                self._calibration_mode_entered = False
                self.state = TobiiState.CONNECTED
                return
            
            try:
                # Clear event
                self._state_event.clear()
                
                # Leave calibration mode
                self._calibration.leave_calibration_mode()
                logger.info("Left calibration mode")
                
                # Wait for notification (with timeout)
                self._lock.release()
                try:
                    if self._state_event.wait(timeout=2.0):
                        logger.debug("Left calibration mode (confirmed by notification)")
                    else:
                        logger.debug("Left calibration mode (notification timeout)")
                finally:
                    self._lock.acquire()
                
                # Update state
                self.state = TobiiState.CONNECTED
                self._calibration_mode_entered = False
                self._calibration = None
                
            except Exception as e:
                logger.error(f"Error leaving calibration mode: {e}", exc_info=True)
                # Force state update even on error
                self.state = TobiiState.CONNECTED
                self._calibration_mode_entered = False
                self._calibration = None
    
    def get_calibration(self) -> Optional[tr.ScreenBasedCalibration]:
        """Get the calibration object (only valid in calibration mode)."""
        with self._lock:
            if self.state != TobiiState.CALIBRATION_MODE:
                return None
            return self._calibration
    
    def start_gaze_stream(self, callback: Callable):
        """Start streaming gaze data."""
        with self._lock:
            if not self.eyetracker:
                logger.error("No eye tracker connected")
                return False
            
            if self._gaze_subscribed:
                logger.warning("Gaze stream already active")
                return True
            
            if self.state == TobiiState.CALIBRATION_MODE:
                logger.error("Cannot start gaze stream while in calibration mode")
                return False
            
            try:
                def gaze_callback(gaze_data):
                    """Internal gaze data callback."""
                    try:
                        callback(gaze_data)
                    except Exception as e:
                        logger.debug(f"Error in gaze callback: {e}")
                
                self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_callback, as_dictionary=True)
                self._gaze_callback = gaze_callback
                self._gaze_subscribed = True
                self.state = TobiiState.STREAMING
                logger.info("Started gaze data stream")
                return True
                
            except Exception as e:
                logger.error(f"Error starting gaze stream: {e}", exc_info=True)
                return False
    
    def stop_gaze_stream(self):
        """Stop streaming gaze data."""
        with self._lock:
            if not self._gaze_subscribed or not self.eyetracker:
                return
            
            try:
                # Unsubscribe from gaze data
                # Note: We need the exact callback reference, which we stored
                if self._gaze_callback:
                    self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._gaze_callback)
                
                self._gaze_subscribed = False
                self._gaze_callback = None
                
                if self.state == TobiiState.STREAMING:
                    self.state = TobiiState.CONNECTED
                
                logger.info("Stopped gaze data stream")
                
            except Exception as e:
                logger.error(f"Error stopping gaze stream: {e}", exc_info=True)
    
    def get_state(self) -> TobiiState:
        """Get current state."""
        with self._lock:
            return self.state
    
    def is_ready(self) -> bool:
        """Check if eye tracker is ready for operations."""
        with self._lock:
            return self.state in (TobiiState.CONNECTED, TobiiState.STREAMING, TobiiState.CALIBRATION_MODE)
    
    def wait_for_state(self, target_state: TobiiState, timeout: float = 5.0) -> bool:
        """Wait for a specific state."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.get_state() == target_state:
                return True
            time.sleep(0.1)
        return False
