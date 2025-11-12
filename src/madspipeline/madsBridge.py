"""
Bridge class for HTML-to-Python communication via QWebChannel.
Handles events from JavaScript and emits structured event signals.
"""
import json
from datetime import datetime
from PySide6.QtCore import QObject, Slot, Signal


class Bridge(QObject):
    """Bridge for communication between JavaScript and Python."""
    
    # Signal for sending messages to JavaScript
    messageFromPython = Signal(str)
    
    # Signal for structured events from JavaScript (for LSL streaming)
    event_received = Signal(dict)  # {type, data, timestamp}

    def __init__(self):
        super().__init__()

    # Slots -> callable from JS
    @Slot(str)
    def receiveMessage(self, msg: str):
        """Receive a message from JavaScript.
        
        Args:
            msg: Message string (can be JSON or plain text)
        """
        try:
            # Try to parse as JSON for structured events
            event_data = json.loads(msg)
            
            # Validate event structure
            if isinstance(event_data, dict) and 'type' in event_data:
                # Add Python-side timestamp if not present
                if 'timestamp' not in event_data:
                    event_data['timestamp'] = datetime.now().isoformat()
                
                # Ensure 'data' field exists
                if 'data' not in event_data:
                    event_data['data'] = {}
                
                # Emit structured event signal for LSL streaming
                self.event_received.emit(event_data)
                
                # Also emit plain message for backward compatibility
                self.messageFromPython.emit(f"Event received: {event_data.get('type', 'unknown')}")
            else:
                # Not a structured event, treat as plain message
                self.messageFromPython.emit(f"Echo from Python: {msg}")
                
        except json.JSONDecodeError:
            # Not JSON, treat as plain message
            self.messageFromPython.emit(f"Echo from Python: {msg}")
        except Exception as e:
            # Error handling
            error_msg = f"Error processing message: {e}"
            self.messageFromPython.emit(error_msg)