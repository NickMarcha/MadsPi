"""
Tobii Eye Tracker Calibration Window.
Provides a fullscreen calibration interface for Tobii eye trackers.
"""
import logging
import time
from typing import Optional, List, Tuple
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeyEvent

logger = logging.getLogger(__name__)

try:
    import tobii_research as tr
    from .tobii_manager import TobiiManager, TobiiState
    TOBII_AVAILABLE = True
except ImportError:
    TOBII_AVAILABLE = False
    logger.warning("tobii_research not available. Tobii calibration will be disabled.")
    tr = None
    TobiiManager = None
    TobiiState = None


class TobiiCalibrationWindow(QWidget):
    """Fullscreen calibration window for Tobii eye tracker."""
    
    calibration_complete = Signal(bool)  # Emits True if successful, False if cancelled/failed
    
    def __init__(self, eyetracker: Optional[tr.EyeTracker] = None, parent=None):
        """Initialize calibration window.
        
        Args:
            eyetracker: Tobii eye tracker instance (None = auto-detect first)
            parent: Parent widget
        """
        super().__init__(parent)
        
        if not TOBII_AVAILABLE:
            raise RuntimeError("tobii_research is not available")
        
        self.eyetracker = eyetracker
        self.tobii_manager: Optional[TobiiManager] = None
        self.calibration = None
        self.calibration_points: List[Tuple[float, float]] = []
        self.current_point_index = -1
        self.calibration_completed = False
        
        # Calibration state
        self.calibration_mode_entered = False
        self.collecting_data = False
        
        # Animation
        self.target_radius = 30  # Initial radius
        self.target_animation_timer = None
        self.target_position = QPoint(0, 0)
        self.target_current_pos = QPoint(0, 0)
        self.target_start_pos = QPoint(0, 0)
        self.target_end_pos = QPoint(0, 0)
        self.animation_start_time = 0
        self.animation_duration = 2000  # milliseconds (2 seconds - slower)
        self.is_animating = False
        self.is_shrinking = False
        self.is_collecting = False
        
        # UI text (drawn in paintEvent, not using QLabel widgets)
        self.status_text = ""
        self.instructions_text = ""
        
        # Setup calibration points (5-point pattern: center, corners)
        # Coordinates are normalized (0.0-1.0) where (0,0) is top-left, (1,1) is bottom-right
        self.calibration_points = [
            (0.5, 0.5),   # Center
            (0.1, 0.1),   # Top-left
            (0.9, 0.1),   # Top-right
            (0.1, 0.9),   # Bottom-left
            (0.9, 0.9),   # Bottom-right
        ]
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the calibration window UI."""
        # Make fullscreen and always on top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        
        # Set background to black
        self.setStyleSheet("background-color: black;")
        
        # Store text strings for drawing in paintEvent
        # We don't use QLabel widgets to avoid blocking the calibration circle
        self.status_text = "Preparing calibration..."
        self.instructions_text = (
            "Please look at the white circle as it moves.\n"
            "Keep your head still and follow with your eyes only.\n\n"
            "Press ESC to cancel."
        )
        
        # No layout needed - we'll draw everything in paintEvent
        self.setLayout(None)
        # The target will be drawn on top of everything
    
    def showEvent(self, event):
        """Handle window show event - start calibration when window is shown."""
        super().showEvent(event)
        # Ensure window is fullscreen and raised
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        # Start calibration after a short delay to ensure window is fully shown
        QTimer.singleShot(1000, self._start_calibration)
    
    def _start_calibration(self):
        """Start the calibration procedure."""
        try:
            # Initialize Tobii manager
            self.tobii_manager = TobiiManager()
            
            # Connect to eye tracker
            if self.eyetracker:
                # Use provided eye tracker
                if not self.tobii_manager.connect(self.eyetracker):
                    QMessageBox.critical(
                        self,
                        "Connection Error",
                        "Failed to connect to provided eye tracker."
                    )
                    self.calibration_complete.emit(False)
                    self.close()
                    return
            else:
                # Auto-detect and connect
                if not self.tobii_manager.connect():
                    QMessageBox.critical(
                        self,
                        "No Eye Tracker",
                        "No Tobii eye tracker found. Please ensure the device is connected."
                    )
                    self.calibration_complete.emit(False)
                    self.close()
                    return
                self.eyetracker = self.tobii_manager.eyetracker
            
            # Enter calibration mode FIRST (this doesn't wake the device)
            # According to Tobii docs, you can enter calibration mode and take your time
            # The device wakes up when you actually start collecting data
            logger.info("Entering calibration mode (device will wake up when we start collecting data)...")
            self.status_text = "Entering calibration mode...\n\nPlease wait..."
            self.update()
            
            # Enter calibration mode and wait for notification
            try:
                success = self.tobii_manager.enter_calibration_mode(timeout=10.0)
                if not success:
                    # Clean up on failure
                    error_msg = "Failed to enter calibration mode.\n\n"
                    error_msg += "This may happen if:\n"
                    error_msg += "• Another application is using the eye tracker\n"
                    error_msg += "• The eye tracker is not ready\n"
                    error_msg += "• The device connection was lost\n"
                    error_msg += "• A previous calibration session wasn't properly closed\n\n"
                    error_msg += "Check the logs for more details."
                    
                    try:
                        self.tobii_manager.leave_calibration_mode()
                        self.tobii_manager.disconnect()
                    except Exception as cleanup_error:
                        logger.error(f"Error during cleanup: {cleanup_error}", exc_info=True)
                        error_msg += f"\n\nCleanup error: {cleanup_error}"
                    
                    QMessageBox.critical(self, "Calibration Error", error_msg)
                    self.calibration_complete.emit(False)
                    self.close()
                    return
            except Exception as e:
                logger.error(f"Exception in enter_calibration_mode: {e}", exc_info=True)
                error_msg = f"Exception occurred while entering calibration mode:\n\n{str(e)}\n\n"
                error_msg += "Check the logs for full details."
                try:
                    self.tobii_manager.leave_calibration_mode()
                    self.tobii_manager.disconnect()
                except:
                    pass
                QMessageBox.critical(self, "Calibration Error", error_msg)
                self.calibration_complete.emit(False)
                self.close()
                return
            
            # Get calibration object from manager
            self.calibration = self.tobii_manager.get_calibration()
            if not self.calibration:
                logger.error("Failed to get calibration object")
                QMessageBox.critical(
                    self,
                    "Calibration Error",
                    "Failed to initialize calibration object."
                )
                self.calibration_complete.emit(False)
                self.close()
                return
            
            self.calibration_mode_entered = True
            logger.info("Calibration mode entered successfully. Waking up device...")
            
            # Wake up the device by calling collect_data() early on the first point
            # This will turn on the red light before we start the actual calibration
            self.status_text = "Waking up eye tracker...\n\nPlease wait for the red light..."
            self.update()
            
            # Call collect_data() early to wake up the device, then wait for it to be ready
            point = self.calibration_points[0]  # First point
            self._wake_up_device(point[0], point[1])
        
        except Exception as e:
            logger.error(f"Error starting calibration: {e}", exc_info=True)
            error_msg = f"An error occurred while starting calibration:\n\n{str(e)}\n\n"
            error_msg += "Full error details have been logged.\n"
            error_msg += "Please check the log file for more information."
            
            # Try to clean up
            try:
                if self.tobii_manager:
                    self.tobii_manager.leave_calibration_mode()
                    self.tobii_manager.disconnect()
            except:
                pass
            
            QMessageBox.critical(self, "Calibration Error", error_msg)
            self.calibration_complete.emit(False)
            self.close()
    
    def _start_calibration_points(self):
        """Start showing calibration points after eye tracker is ready."""
        # Prevent multiple calls
        if self.current_point_index >= 0:
            logger.debug("Calibration points already started, ignoring duplicate call")
            return
        
        try:
            logger.info("Eye tracker ready, starting calibration points")
            
            # Verify we have a calibration object
            if not self.calibration:
                self.calibration = self.tobii_manager.get_calibration()
                if not self.calibration:
                    raise RuntimeError("No calibration object available")
            
            # Start calibration points
            # The device will wake up when we start collecting data (collect_data calls)
            self.status_text = "Starting calibration...\n\nLook at the white circle as it moves"
            self.update()
            
            # Start immediately - no delay needed
            logger.info("Starting calibration points - device will wake up when we collect data")
            self._begin_calibration_points()
        except Exception as e:
            logger.error(f"Error starting calibration points: {e}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            error_msg = f"An error occurred while starting calibration points:\n\n{str(e)}\n\n"
            error_msg += "Full error details have been logged.\n"
            error_msg += "Please check the log file for more information."
            
            # Try to clean up
            try:
                if self.tobii_manager:
                    self.tobii_manager.leave_calibration_mode()
                    self.tobii_manager.disconnect()
            except:
                pass
            
            QMessageBox.critical(self, "Calibration Error", error_msg)
            self.calibration_complete.emit(False)
            self.close()
    
    def _begin_calibration_points(self):
        """Actually begin showing calibration points."""
        # Start with first point
        self.current_point_index = 0
        self._show_calibration_point()
    
    def _show_calibration_point(self):
        """Show and animate to the current calibration point."""
        if self.current_point_index >= len(self.calibration_points):
            # All points done, compute and apply calibration
            self._finish_calibration()
            return
        
        point = self.calibration_points[self.current_point_index]
        x_norm, y_norm = point
        
        # Get screen dimensions - use the actual window size
        screen_width = self.width()
        screen_height = self.height()
        
        # If window isn't sized yet, use screen size
        if screen_width == 0 or screen_height == 0:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            screen_width = screen.width()
            screen_height = screen.height()
            logger.info(f"Window not sized yet, using screen size: {screen_width}x{screen_height}")
        
        x_screen = int(x_norm * screen_width)
        y_screen = int(y_norm * screen_height)
        
        logger.info(f"Showing calibration point {self.current_point_index + 1}: ({x_norm}, {y_norm}) -> ({x_screen}, {y_screen})")
        
        self.target_position = QPoint(x_screen, y_screen)
        
        # Update status
        point_num = self.current_point_index + 1
        total_points = len(self.calibration_points)
        self.status_text = f"Calibration point {point_num} of {total_points}\n\nLook at the white circle"
        self.update()  # Trigger repaint to update text
        
        # Animate target to position (device should already be awake from initial wake-up call)
        self._animate_target_to_position(x_screen, y_screen)
    
    def _wake_up_device(self, x_norm: float, y_norm: float):
        """Wake up the device by calling collect_data() early, then discard it."""
        if not self.calibration:
            return
        
        try:
            logger.info(f"Waking up device with early collect_data() call at ({x_norm}, {y_norm})")
            # Call collect_data() to wake up the device, but we'll discard this data
            result = self.calibration.collect_data(x_norm, y_norm)
            
            # Check result - log what we got
            logger.info(f"Early collect_data() returned: {result} (type: {type(result)})")
            
            # Verify it's a valid result (not an error)
            is_success = False
            if result is None:
                is_success = True
            elif hasattr(tr, 'CALIBRATION_STATUS_SUCCESS'):
                is_success = (result == tr.CALIBRATION_STATUS_SUCCESS or str(result) == 'calibration_status_success')
            else:
                is_success = (result is True or result == 0 or str(result) == 'calibration_status_success')
            
            if not is_success:
                logger.warning(f"Early collect_data() returned non-success: {result}")
            
            # Discard this data point - we just wanted to wake up the device
            try:
                self.calibration.discard_data(x_norm, y_norm)
                logger.info("Discarded early collect_data() point")
            except Exception as e:
                logger.warning(f"Could not discard early data point: {e}")
            
            # Wait for device to fully wake up (red light should be on now)
            # The device needs time to wake up after collect_data() is called
            logger.info("Device wake-up call complete, waiting 3 seconds for device to be ready (red light should turn on)...")
            self.status_text = "Device waking up...\n\nPlease wait for the red light to turn on..."
            self.update()
            
            # Wait longer for device to be fully ready, then start calibration procedure
            # This ensures the red light is on before we start collecting real calibration data
            QTimer.singleShot(3000, self._start_calibration_points)
            
        except Exception as e:
            logger.error(f"Error in early collect_data() call: {e}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue anyway after a delay
            logger.warning("Continuing with calibration despite wake-up error - device may not be ready")
            QTimer.singleShot(3000, self._start_calibration_points)
    
    def _animate_target_to_position(self, x: int, y: int):
        """Animate the calibration target to the specified position using QTimer."""
        # Stop any existing animation
        if self.target_animation_timer:
            self.target_animation_timer.stop()
        
        # Get screen dimensions for initial positioning
        screen_width = self.width()
        screen_height = self.height()
        if screen_width == 0 or screen_height == 0:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            screen_width = screen.width()
            screen_height = screen.height()
        
        # Start from center of screen for first point, or current position for subsequent points
        if self.current_point_index == 0 or self.target_current_pos.x() == 0:
            # First point - start from center
            start_x = screen_width // 2
            start_y = screen_height // 2
            logger.info(f"First point: starting from center ({start_x}, {start_y})")
        else:
            # Subsequent points - start from current position
            start_x = self.target_current_pos.x()
            start_y = self.target_current_pos.y()
            logger.info(f"Point {self.current_point_index + 1}: starting from ({start_x}, {start_y})")
        
        # Set positions
        self.target_start_pos = QPoint(start_x, start_y)
        self.target_end_pos = QPoint(x, y)
        self.target_current_pos = QPoint(start_x, start_y)
        self.is_animating = True
        self.is_shrinking = False
        
        logger.info(f"Animating target from ({start_x}, {start_y}) to ({x}, {y})")
        
        # Start animation timer (update every 16ms for ~60fps)
        import time
        self.animation_start_time = time.time() * 1000  # milliseconds
        self.target_animation_timer = QTimer()
        self.target_animation_timer.timeout.connect(self._update_animation)
        self.target_animation_timer.start(16)  # ~60fps
        
        # Force initial paint
        self.update()
    
    def _update_animation(self):
        """Update animation frame."""
        import time
        current_time = time.time() * 1000  # milliseconds
        elapsed = current_time - self.animation_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        if progress >= 1.0:
            # Animation complete
            self.target_current_pos = self.target_end_pos
            self.is_animating = False
            self.target_animation_timer.stop()
            self.update()  # Final paint
            logger.info(f"Animation finished for point {self.current_point_index + 1}")
            # Wait 1 second for user to focus, then shrink target
            QTimer.singleShot(1000, self._shrink_and_collect)
        else:
            # Easing function (ease-out cubic)
            eased = 1 - pow(1 - progress, 3)
            
            # Interpolate position
            dx = self.target_end_pos.x() - self.target_start_pos.x()
            dy = self.target_end_pos.y() - self.target_start_pos.y()
            self.target_current_pos = QPoint(
                int(self.target_start_pos.x() + dx * eased),
                int(self.target_start_pos.y() + dy * eased)
            )
            self.update()  # Trigger repaint
    
    def _shrink_and_collect(self):
        """Shrink the target and start collecting calibration data."""
        logger.info(f"Shrinking target for point {self.current_point_index + 1}")
        self.is_shrinking = True
        self.target_radius = 10  # Shrink to smaller radius
        self.update()  # Repaint with smaller target
        
        # Wait for user to focus on the smaller target, then collect data
        QTimer.singleShot(500, self._collect_calibration_data)
    
    def _collect_calibration_data(self):
        """Collect calibration data for the current point."""
        if not self.calibration or self.current_point_index >= len(self.calibration_points):
            return
        
        point = self.calibration_points[self.current_point_index]
        
        try:
            logger.info(f"Collecting calibration data for point {self.current_point_index + 1}: {point}")
            result = self.calibration.collect_data(point[0], point[1])
            
            # Log the result to verify we're getting real values
            logger.info(f"collect_data() returned: {result} (type: {type(result)})")
            
            # collect_data() may return None on success, or a status code
            # Check if it's a success (None or SUCCESS status)
            is_success = False
            if result is None:
                # None typically means success
                is_success = True
                logger.info("collect_data() returned None (success)")
            elif hasattr(tr, 'CALIBRATION_STATUS_SUCCESS'):
                is_success = (result == tr.CALIBRATION_STATUS_SUCCESS)
                if is_success:
                    logger.info("collect_data() returned CALIBRATION_STATUS_SUCCESS")
                else:
                    logger.warning(f"collect_data() returned status code: {result}")
            else:
                # If no constant, assume truthy or 0 means success
                is_success = (result is True or result == 0)
                if is_success:
                    logger.info(f"collect_data() returned success value: {result}")
                else:
                    logger.warning(f"collect_data() returned non-success value: {result}")
            
            if is_success:
                logger.info(f"Successfully collected data for point {self.current_point_index + 1}")
            else:
                logger.warning(f"collect_data() returned non-success for point {self.current_point_index + 1}: {result}")
            
            # Restore target size
            self.target_radius = 30
            self.is_shrinking = False
            self.update()
            
            # Move to next point immediately - no delay needed
            self._move_to_next_point()
        
        except Exception as e:
            logger.error(f"Error collecting calibration data: {e}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Restore target size and continue to next point
            self.target_radius = 30
            self.is_shrinking = False
            self.update()
            self._move_to_next_point()
    
    def _move_to_next_point(self):
        """Move to the next calibration point."""
        self.current_point_index += 1
        self._show_calibration_point()
    
    def _finish_calibration(self):
        """Finish calibration by computing and applying the calibration."""
        if not self.calibration:
            return
        
        try:
            # Stop animation and hide target
            if self.target_animation_timer:
                self.target_animation_timer.stop()
            self.target_current_pos = QPoint(0, 0)
            self.is_animating = False
            self.status_text = "Computing calibration..."
            self.update()
            
            # Compute and apply calibration
            logger.info("Computing and applying calibration...")
            result = self.calibration.compute_and_apply()
            
            # compute_and_apply() may return None, a status code, or a CalibrationResult object
            # Extract warnings from the result
            is_success = False
            warnings = []
            calibration_result_obj = None
            
            if result is None:
                # None typically means success
                is_success = True
            elif hasattr(tr, 'CalibrationResult') and isinstance(result, tr.CalibrationResult):
                # It's a CalibrationResult object - extract information
                calibration_result_obj = result
                is_success = True
                logger.info(f"Calibration returned CalibrationResult object")
                
                # Try to extract warnings or status information from the result
                try:
                    # Check calibration points for issues
                    if hasattr(result, 'calibration_points'):
                        points = result.calibration_points
                        logger.info(f"CalibrationResult has {len(points)} calibration points")
                        
                        for i, point in enumerate(points):
                            point_warnings = []
                            
                            # Check if point has samples
                            if hasattr(point, 'calibration_samples'):
                                samples = point.calibration_samples
                                if not samples or len(samples) == 0:
                                    point_warnings.append(f"Point {i+1}: No calibration samples collected")
                                else:
                                    # Check sample validity
                                    invalid_samples = 0
                                    for sample in samples:
                                        if hasattr(sample, 'left_gaze_point_validity') and hasattr(sample, 'right_gaze_point_validity'):
                                            if sample.left_gaze_point_validity == 0 or sample.right_gaze_point_validity == 0:
                                                invalid_samples += 1
                                    if invalid_samples > 0:
                                        point_warnings.append(f"Point {i+1}: {invalid_samples} invalid gaze samples")
                            
                            if point_warnings:
                                warnings.extend(point_warnings)
                    
                    # Check for status codes in the result
                    if hasattr(result, 'status'):
                        status = result.status
                        logger.info(f"CalibrationResult status: {status} (type: {type(status)})")
                        
                        # Check if status indicates warnings (not full success)
                        # Status can be a string like 'calibration_status_success' or a constant
                        status_str = str(status).lower()
                        is_full_success = False
                        
                        if hasattr(tr, 'CALIBRATION_STATUS_SUCCESS'):
                            # Compare with constant
                            if status == tr.CALIBRATION_STATUS_SUCCESS:
                                is_full_success = True
                            # Also check string representation
                            elif status_str == 'calibration_status_success' or status_str == str(tr.CALIBRATION_STATUS_SUCCESS).lower():
                                is_full_success = True
                        
                        # If not full success, check for partial success or other statuses
                        if not is_full_success:
                            if hasattr(tr, 'CALIBRATION_STATUS_SUCCESS_LEFT_EYE'):
                                if status == tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE or 'left_eye' in status_str:
                                    warnings.append("Calibration succeeded for left eye only")
                            elif hasattr(tr, 'CALIBRATION_STATUS_SUCCESS_RIGHT_EYE'):
                                if status == tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE or 'right_eye' in status_str:
                                    warnings.append("Calibration succeeded for right eye only")
                            elif 'success' not in status_str:
                                # Only add warning if it's not a success status
                                warnings.append(f"Calibration status: {status}")
                        
                        # Check calibration points for quality issues
                        logger.info("Checking calibration points for quality issues...")
                        try:
                            if hasattr(result, 'calibration_points'):
                                points = result.calibration_points
                                logger.info(f"Examining {len(points)} calibration points for quality issues...")
                                for i, point in enumerate(points):
                                    point_issues = []
                                    
                                    # Log point details
                                    logger.debug(f"Point {i+1} attributes: {dir(point)}")
                                    
                                    # Check if point has samples
                                    if hasattr(point, 'calibration_samples'):
                                        samples = point.calibration_samples
                                        logger.debug(f"Point {i+1}: {len(samples) if samples else 0} samples")
                                        if not samples or len(samples) == 0:
                                            point_issues.append(f"Point {i+1}: No calibration samples collected")
                                        else:
                                            # Check sample validity
                                            invalid_samples = 0
                                            total_samples = len(samples)
                                            for sample in samples:
                                                # Check various validity attributes
                                                if hasattr(sample, 'left_gaze_point_validity') and hasattr(sample, 'right_gaze_point_validity'):
                                                    if sample.left_gaze_point_validity == 0 or sample.right_gaze_point_validity == 0:
                                                        invalid_samples += 1
                                            
                                            if invalid_samples > 0:
                                                percentage = (invalid_samples / total_samples) * 100
                                                point_issues.append(f"Point {i+1}: {invalid_samples}/{total_samples} invalid gaze samples ({percentage:.1f}%)")
                                    
                                    if point_issues:
                                        warnings.extend(point_issues)
                                        logger.warning(f"Point {i+1} has quality issues: {point_issues}")
                                    else:
                                        logger.debug(f"Point {i+1}: No quality issues detected")
                        except Exception as e:
                            logger.warning(f"Could not check calibration point quality: {e}", exc_info=True)
                    
                    # Log the result object for debugging
                    logger.info(f"CalibrationResult object: {result}")
                    logger.info(f"CalibrationResult attributes: {dir(result)}")
                    
                except Exception as e:
                    logger.warning(f"Could not extract detailed warnings from CalibrationResult: {e}", exc_info=True)
                    # If we can't extract details, at least note that we got a result object
                    warnings.append("Calibration completed (check result details in logs)")
            elif hasattr(tr, 'CALIBRATION_STATUS_SUCCESS'):
                is_success = (result == tr.CALIBRATION_STATUS_SUCCESS)
                if not is_success:
                    # Check for partial success
                    if hasattr(tr, 'CALIBRATION_STATUS_SUCCESS_LEFT_EYE') and result == tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE:
                        is_success = True
                        warnings.append("Calibration succeeded for left eye only")
                    elif hasattr(tr, 'CALIBRATION_STATUS_SUCCESS_RIGHT_EYE') and result == tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE:
                        is_success = True
                        warnings.append("Calibration succeeded for right eye only")
                    else:
                        warnings.append(f"Calibration status: {result}")
            else:
                # If no constant, assume truthy or 0 means success
                is_success = (result is True or result == 0)
                if not is_success:
                    warnings.append(f"Calibration returned: {result}")
            
            # Display result with warnings if any
            if is_success:
                if warnings:
                    logger.warning(f"Calibration completed with warnings: {warnings}")
                    warning_text = "Calibration completed with warnings:\n\n"
                    warning_text += "\n".join(f"• {w}" for w in warnings)
                    warning_text += "\n\nYou may want to recalibrate for better accuracy."
                    self.status_text = warning_text
                    # Give user more time to read warnings
                    QTimer.singleShot(4000, lambda: self._close_calibration(True))
                else:
                    logger.info("Calibration completed successfully")
                    self.status_text = "Calibration completed successfully!"
                    QTimer.singleShot(1500, lambda: self._close_calibration(True))
                self.calibration_completed = True
                self.update()
            else:
                logger.error(f"Calibration computation failed: {result}")
                error_text = "Calibration failed."
                if warnings:
                    error_text += "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in warnings)
                self.status_text = error_text
                self.calibration_completed = True
                self.update()
                QTimer.singleShot(3000, lambda: self._close_calibration(True))
        
        except Exception as e:
            logger.error(f"Error finishing calibration: {e}", exc_info=True)
            self.status_text = f"Error during calibration: {str(e)}"
            self.update()
            QTimer.singleShot(1500, lambda: self._close_calibration(False))
    
    def _close_calibration(self, success: bool):
        """Close calibration window and emit signal."""
        try:
            # Use Tobii manager to leave calibration mode and cleanup
            if self.tobii_manager:
                try:
                    self.tobii_manager.leave_calibration_mode()
                    self.tobii_manager.disconnect()
                    logger.info("Left calibration mode and disconnected")
                except Exception as e:
                    logger.warning(f"Error during Tobii manager cleanup: {e}")
        except Exception as e:
            logger.warning(f"Error during calibration cleanup: {e}")
        
        self.calibration_complete.emit(success)
        self.close()
    
    def paintEvent(self, event):
        """Paint the calibration window and target."""
        # Paint background
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        # Draw text labels directly (so they don't block the circle)
        # Use white text on transparent background
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        
        # Draw status text at top (centered, with padding)
        if self.status_text:
            text_rect = QRect(0, 50, self.width(), 150)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, self.status_text)
        
        # Draw instructions at bottom (centered, with padding) - only if not during calibration points
        if self.instructions_text and self.current_point_index < 0:
            font.setPointSize(18)
            font.setBold(False)
            painter.setFont(font)
            text_rect = QRect(0, self.height() - 200, self.width(), 150)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, self.instructions_text)
        
        # Now draw the target circle on top of everything
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw target if we have a position
        if self.target_current_pos.x() > 0 and self.target_current_pos.y() > 0:
            x = self.target_current_pos.x()
            y = self.target_current_pos.y()
            radius = self.target_radius
            
            # Draw white circle with outline for visibility
            # Use a larger pen for better visibility
            pen = QPen(QColor(255, 255, 255), 4)
            brush = QBrush(QColor(255, 255, 255))
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
            
            # Draw small center dot (black for contrast)
            painter.setPen(QPen(QColor(0, 0, 0), 3))
            painter.setBrush(QBrush(QColor(0, 0, 0)))
            painter.drawEllipse(x - 3, y - 3, 6, 6)
    
    def keyPressEvent(self, event):
        """Handle key press events - ESC to cancel."""
        if event.key() == Qt.Key.Key_Escape:
            self._close_calibration(False)
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop animation timer
        if self.target_animation_timer:
            self.target_animation_timer.stop()
        
        if self.calibration and self.calibration_mode_entered:
            try:
                self.calibration.leave_calibration_mode()
            except Exception:
                pass
        event.accept()

