"""
Tobii Eye Tracker Gaze Test Window.
Shows a black screen with gaze point visualization for testing calibration.
"""
import logging
import time
from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeyEvent

logger = logging.getLogger(__name__)

try:
    import tobii_research as tr
    TOBII_AVAILABLE = True
except ImportError:
    TOBII_AVAILABLE = False
    logger.warning("tobii_research not available. Tobii gaze test will be disabled.")
    tr = None


class TobiiGazeTestWindow(QWidget):
    """Fullscreen window for testing Tobii eye tracker gaze data."""
    
    test_complete = Signal()  # Emitted when test is closed
    
    def __init__(self, eyetracker: Optional[tr.EyeTracker] = None, parent=None):
        """Initialize gaze test window.
        
        Args:
            eyetracker: Tobii eye tracker instance (None = auto-detect first)
            parent: Parent widget
        """
        super().__init__(parent)
        
        if not TOBII_AVAILABLE:
            raise RuntimeError("tobii_research is not available")
        
        self.eyetracker = eyetracker
        self.gaze_subscribed = False
        
        # Gaze data
        self.left_gaze = None
        self.right_gaze = None
        self.left_valid = False
        self.right_valid = False
        
        # Screen dimensions
        self.screen_width = 1920
        self.screen_height = 1080
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the gaze test window UI."""
        # Make fullscreen and always on top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        
        # Set background to black
        self.setStyleSheet("background-color: black;")
        
        # Status label at top - will be drawn in paintEvent
        self.status_text = "Connecting to eye tracker..."
        
        # No layout needed - we'll draw everything in paintEvent
        self.setLayout(None)
    
    def showEvent(self, event):
        """Handle window show event - start gaze subscription when window is shown."""
        super().showEvent(event)
        # Show fullscreen
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        
        # Get screen dimensions
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()
        
        # Start gaze subscription after a short delay
        QTimer.singleShot(500, self._start_gaze_subscription)
    
    def _start_gaze_subscription(self):
        """Start subscribing to gaze data."""
        try:
            # Find eye tracker if not provided
            if not self.eyetracker:
                logger.info("Searching for Tobii eye tracker...")
                found_eyetrackers = tr.find_all_eyetrackers()
                if not found_eyetrackers:
                    self.status_text = "No eye tracker found.\n\nPress ESC to exit."
                    self.update()
                    return
                self.eyetracker = found_eyetrackers[0]
                logger.info(f"Using eye tracker: {self.eyetracker.model} at {self.eyetracker.address}")
            
            # Define gaze data callback
            def gaze_data_callback(gaze_data):
                """Callback function for gaze data."""
                try:
                    # Extract gaze data in screen space coordinates (normalized 0-1)
                    left_gaze = gaze_data.get('left_gaze_point_on_display_area', (float('nan'), float('nan')))
                    right_gaze = gaze_data.get('right_gaze_point_on_display_area', (float('nan'), float('nan')))
                    
                    # Extract validity
                    left_valid = gaze_data.get('left_gaze_point_validity', 0) == 1
                    right_valid = gaze_data.get('right_gaze_point_validity', 0) == 1
                    
                    # Convert to screen coordinates
                    if isinstance(left_gaze, (tuple, list)) and len(left_gaze) >= 2:
                        if not (left_gaze[0] != left_gaze[0] or left_gaze[1] != left_gaze[1]):  # Check for NaN
                            self.left_gaze = (
                                int(left_gaze[0] * self.screen_width),
                                int(left_gaze[1] * self.screen_height)
                            )
                            self.left_valid = left_valid
                        else:
                            self.left_gaze = None
                            self.left_valid = False
                    else:
                        self.left_gaze = None
                        self.left_valid = False
                    
                    if isinstance(right_gaze, (tuple, list)) and len(right_gaze) >= 2:
                        if not (right_gaze[0] != right_gaze[0] or right_gaze[1] != right_gaze[1]):  # Check for NaN
                            self.right_gaze = (
                                int(right_gaze[0] * self.screen_width),
                                int(right_gaze[1] * self.screen_height)
                            )
                            self.right_valid = right_valid
                        else:
                            self.right_gaze = None
                            self.right_valid = False
                    else:
                        self.right_gaze = None
                        self.right_valid = False
                    
                    # Trigger repaint
                    self.update()
                except Exception as e:
                    logger.debug(f"Error processing gaze data: {e}")
            
            # Subscribe to gaze data
            self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
            self.gaze_subscribed = True
            logger.info("Subscribed to Tobii gaze data for testing")
            
            self.status_text = (
                "Gaze Test Active\n\n"
                "Look around the screen.\n"
                "Your gaze point will be shown as colored circles:\n"
                "• Red = Left eye\n"
                "• Green = Right eye\n"
                "• Yellow = Both eyes (overlap)\n\n"
                "Press ESC to exit."
            )
            self.update()  # Trigger repaint
        
        except Exception as e:
            logger.error(f"Error starting gaze subscription: {e}", exc_info=True)
            self.status_text = f"Error: {str(e)}\n\nPress ESC to exit."
            self.update()
    
    def paintEvent(self, event):
        """Paint the gaze test window and gaze points."""
        painter = QPainter(self)
        
        # Fill background
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        # Draw status text at top
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        text_rect = self.rect()
        text_rect.setHeight(200)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, self.status_text)
        
        # Now draw gaze points on top
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw gaze points
        if self.left_gaze and self.left_valid:
            x, y = self.left_gaze
            # Draw left eye gaze (red)
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 150)))  # Semi-transparent red
            painter.drawEllipse(x - 10, y - 10, 20, 20)
            # Draw center dot
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.drawEllipse(x - 2, y - 2, 4, 4)
        
        if self.right_gaze and self.right_valid:
            x, y = self.right_gaze
            # Draw right eye gaze (green)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.setBrush(QBrush(QColor(0, 255, 0, 150)))  # Semi-transparent green
            painter.drawEllipse(x - 10, y - 10, 20, 20)
            # Draw center dot
            painter.setBrush(QBrush(QColor(0, 255, 0)))
            painter.drawEllipse(x - 2, y - 2, 4, 4)
        
        # If both eyes are valid and close together, draw yellow overlap
        if (self.left_gaze and self.left_valid and 
            self.right_gaze and self.right_valid):
            lx, ly = self.left_gaze
            rx, ry = self.right_gaze
            # Check if they're close (within 50 pixels)
            distance = ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5
            if distance < 50:
                # Draw yellow circle at average position
                avg_x = (lx + rx) // 2
                avg_y = (ly + ry) // 2
                painter.setPen(QPen(QColor(255, 255, 0), 3))
                painter.setBrush(QBrush(QColor(255, 255, 0, 200)))
                painter.drawEllipse(avg_x - 12, avg_y - 12, 24, 24)
                painter.setBrush(QBrush(QColor(255, 255, 0)))
                painter.drawEllipse(avg_x - 3, avg_y - 3, 6, 6)
    
    def keyPressEvent(self, event):
        """Handle key press events - ESC to exit."""
        if event.key() == Qt.Key.Key_Escape:
            self._close_test()
        else:
            super().keyPressEvent(event)
    
    def _close_test(self):
        """Close the test window and unsubscribe from gaze data."""
        try:
            if self.eyetracker and self.gaze_subscribed:
                try:
                    self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, lambda x: None)
                    logger.info("Unsubscribed from Tobii gaze data")
                except Exception as e:
                    logger.debug(f"Error unsubscribing: {e}")
        except Exception as e:
            logger.warning(f"Error during test cleanup: {e}")
        
        self.test_complete.emit()
        self.close()
    
    def closeEvent(self, event):
        """Handle window close event."""
        self._close_test()
        event.accept()
