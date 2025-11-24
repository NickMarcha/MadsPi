"""
LSL Stream Management interface for MadsPipeline.
Provides a dialog for managing LSL streams, including mouse tracking, marker API, Tobii eyetracker, and Emotibit.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QLineEdit,
    QTextEdit, QMessageBox, QHeaderView, QAbstractItemView, QComboBox,
    QSpinBox, QDoubleSpinBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_streams, local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    print("Warning: pylsl not available. LSL integration will be disabled.")

from .models import Project, LSLConfig
from .lsl_integration import LSLBridgeStreamer, LSLMouseTrackingStreamer, LSLRecorder, LSL_AVAILABLE as LSL_INTEGRATION_AVAILABLE

# Optional BrainFlow-based EmotiBit streamer
try:
    from .emotibit_brainflow import EmotiBitBrainflowStreamer
    BRAINFLOW_UI_AVAILABLE = True
    BRAINFLOW_ERROR = None
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"BrainFlow integration not available: {e}")
    EmotiBitBrainflowStreamer = None
    BRAINFLOW_UI_AVAILABLE = False
    BRAINFLOW_ERROR = str(e)


class LSLStreamManagerDialog(QDialog):
    """Dialog for managing LSL streams."""
    
    config_changed = Signal(LSLConfig)  # Emitted when configuration changes
    
    def __init__(self, project: Project, parent=None):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing LSL Manager for project: {project.name}")
        
        super().__init__(parent)
        self.project = project
        self.current_config: Optional[LSLConfig] = None
        self.selected_streams = set()
        self.available_streams = []
        self.emotibit_process = None
        self.brainflow_streamer = None  # BrainFlow streamer instance
        self.test_recorder: Optional[LSLRecorder] = None
        self.test_timer: Optional[QTimer] = None
        self.is_testing = False
        
        # Initialize config from project
        try:
            if (project.embedded_webpage_config and 
                project.embedded_webpage_config.lsl_config):
                self.current_config = project.embedded_webpage_config.lsl_config
                logger.info("Loaded LSL config from project")
            else:
                # Create default config
                logger.info("Creating default LSL config")
                self.current_config = LSLConfig(
                    enable_mouse_tracking=True,
                    enable_marker_api=project.embedded_webpage_config.enable_marker_api if project.embedded_webpage_config else True,
                    enable_tobii_eyetracker=False,
                    enable_emotibit=False
                )
        except Exception as e:
            logger.error(f"Error initializing LSL config: {e}", exc_info=True)
            self.current_config = LSLConfig()
        
        # Tracks streams selected for recording in the UI
        self.selected_streams = set()
        
        self.setWindowTitle(f"LSL Stream Management - {project.name}")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        try:
            self._setup_ui()
            logger.info("LSL Manager UI setup complete")
        except Exception as e:
            logger.error(f"Error setting up LSL Manager UI: {e}", exc_info=True)
            raise
        
        try:
            self._update_ui_from_config()
            logger.info("LSL Manager UI updated from config")
        except Exception as e:
            logger.error(f"Error updating LSL Manager UI from config: {e}", exc_info=True)
            raise
    
    def _setup_ui(self):
        """Set up the LSL management UI."""
        layout = QVBoxLayout()
        
        # Header
        header_label = QLabel("LSL Stream Management")
        header_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # LSL Status
        status_group = QGroupBox("LSL Status")
        status_layout = QVBoxLayout()
        
        if LSL_AVAILABLE:
            status_label = QLabel("✓ LSL is available")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label = QLabel("✗ LSL is not available (pylsl not installed)")
            status_label.setStyleSheet("color: red; font-weight: bold;")
        
        status_layout.addWidget(status_label)
        status_group.setLayout(status_layout)
        scroll_layout.addWidget(status_group)
        
        # Stream Configuration
        config_group = QGroupBox("Stream Configuration")
        config_layout = QFormLayout()
        
        # Mouse tracking
        self.mouse_tracking_check = QCheckBox()
        self.mouse_tracking_check.setChecked(self.current_config.enable_mouse_tracking)
        self.mouse_tracking_check.stateChanged.connect(self._on_config_changed)
        config_layout.addRow("Enable Mouse Tracking:", self.mouse_tracking_check)
        
        # Marker API
        self.marker_api_check = QCheckBox()
        self.marker_api_check.setChecked(self.current_config.enable_marker_api)
        self.marker_api_check.stateChanged.connect(self._on_config_changed)
        config_layout.addRow("Enable Marker API:", self.marker_api_check)
        
        # Tobii eyetracker
        tobii_layout = QHBoxLayout()
        self.tobii_check = QCheckBox()
        self.tobii_check.setChecked(self.current_config.enable_tobii_eyetracker)
        self.tobii_check.stateChanged.connect(self._on_config_changed)
        self.tobii_stream_edit = QLineEdit()
        self.tobii_stream_edit.setPlaceholderText("Auto-detect (leave empty)")
        if self.current_config.tobii_stream_name:
            self.tobii_stream_edit.setText(self.current_config.tobii_stream_name)
        self.tobii_stream_edit.textChanged.connect(self._on_config_changed)
        self.tobii_stream_edit.setEnabled(self.current_config.enable_tobii_eyetracker)
        self.tobii_check.stateChanged.connect(
            lambda state: self.tobii_stream_edit.setEnabled(state == Qt.CheckState.Checked)
        )
        tobii_layout.addWidget(self.tobii_check)
        tobii_layout.addWidget(QLabel("Stream name:"))
        tobii_layout.addWidget(self.tobii_stream_edit)
        config_layout.addRow("Enable Tobii Eyetracker:", tobii_layout)

        # EmotiBit (BrainFlow backend) - with start/stop controls
        emotibit_group = QGroupBox("EmotiBit (BrainFlow)")
        emotibit_group_layout = QVBoxLayout()
        
        emotibit_enable_layout = QHBoxLayout()
        self.emotibit_check = QCheckBox()
        self.emotibit_check.setChecked(getattr(self.current_config, 'use_brainflow', False))
        self.emotibit_check.stateChanged.connect(self._on_config_changed)
        def _on_emotibit_check_changed(state):
            """Handle EmotiBit checkbox state change."""
            enabled = (state == Qt.CheckState.Checked) and BRAINFLOW_UI_AVAILABLE
            self.start_emotibit_brainflow_button.setEnabled(enabled)
            if not BRAINFLOW_UI_AVAILABLE and state == Qt.CheckState.Checked:
                # Show tooltip explaining why it's disabled
                self.start_emotibit_brainflow_button.setToolTip(
                    f"BrainFlow not available: {BRAINFLOW_ERROR or 'Install brainflow package'}"
                )
            else:
                self.start_emotibit_brainflow_button.setToolTip("")
        
        self.emotibit_check.stateChanged.connect(_on_emotibit_check_changed)
        emotibit_enable_layout.addWidget(self.emotibit_check)
        emotibit_enable_layout.addWidget(QLabel("Enable EmotiBit streaming"))
        emotibit_enable_layout.addStretch()
        emotibit_group_layout.addLayout(emotibit_enable_layout)
        
        # IP address field
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("IP Address (optional):"))
        self.brainflow_ip_edit = QLineEdit()
        self.brainflow_ip_edit.setPlaceholderText("Leave empty for auto-discovery (e.g. 192.168.0.255)")
        if getattr(self.current_config, 'brainflow_ip', None):
            self.brainflow_ip_edit.setText(self.current_config.brainflow_ip)
        self.brainflow_ip_edit.textChanged.connect(self._on_config_changed)
        ip_layout.addWidget(self.brainflow_ip_edit)
        emotibit_group_layout.addLayout(ip_layout)
        
        # Start/Stop buttons
        emotibit_buttons_layout = QHBoxLayout()
        self.start_emotibit_brainflow_button = QPushButton("Start EmotiBit Stream")
        self.start_emotibit_brainflow_button.clicked.connect(self._start_emotibit_via_brainflow)
        # Enable button only if BrainFlow is available AND checkbox is checked
        initial_enabled = BRAINFLOW_UI_AVAILABLE and getattr(self.current_config, 'use_brainflow', False)
        self.start_emotibit_brainflow_button.setEnabled(initial_enabled)
        
        # If BrainFlow is not available, disable the checkbox too
        if not BRAINFLOW_UI_AVAILABLE:
            self.emotibit_check.setEnabled(False)
            self.emotibit_check.setToolTip(f"BrainFlow not available: {BRAINFLOW_ERROR or 'Install brainflow package'}")
        
        self.stop_emotibit_brainflow_button = QPushButton("Stop EmotiBit Stream")
        self.stop_emotibit_brainflow_button.clicked.connect(self._stop_brainflow_streamer)
        self.stop_emotibit_brainflow_button.setEnabled(False)
        
        emotibit_buttons_layout.addWidget(self.start_emotibit_brainflow_button)
        emotibit_buttons_layout.addWidget(self.stop_emotibit_brainflow_button)
        emotibit_buttons_layout.addStretch()
        emotibit_group_layout.addLayout(emotibit_buttons_layout)
        
        # Status label
        if not BRAINFLOW_UI_AVAILABLE:
            error_msg = BRAINFLOW_ERROR or "BrainFlow not installed"
            self.emotibit_status_label = QLabel(f"Status: BrainFlow unavailable ({error_msg})")
            self.emotibit_status_label.setStyleSheet("color: red;")
            self.emotibit_status_label.setWordWrap(True)
        else:
            self.emotibit_status_label = QLabel("Status: Not started")
            self.emotibit_status_label.setStyleSheet("color: gray;")
        emotibit_group_layout.addWidget(self.emotibit_status_label)
        
        emotibit_group.setLayout(emotibit_group_layout)
        config_layout.addRow(emotibit_group)
        
        config_group.setLayout(config_layout)
        scroll_layout.addWidget(config_group)
        
        # Stream Testing
        test_group = QGroupBox("Stream Testing")
        test_layout = QVBoxLayout()
        
        test_buttons_layout = QHBoxLayout()
        self.test_button = QPushButton("Start Receiving Test")
        self.test_button.clicked.connect(self._toggle_test)
        self.test_button.setEnabled(LSL_AVAILABLE)
        self.stop_test_button = QPushButton("Stop Test")
        self.stop_test_button.clicked.connect(self._stop_test)
        self.stop_test_button.setEnabled(False)
        
        test_buttons_layout.addWidget(self.test_button)
        test_buttons_layout.addWidget(self.stop_test_button)
        test_buttons_layout.addStretch()
        
        test_layout.addLayout(test_buttons_layout)
        
        # Available streams table
        streams_label = QLabel("Available LSL Streams:")
        streams_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        test_layout.addWidget(streams_label)
        
        self.streams_table = QTableWidget()
        # Add a 'Record' checkbox column for per-stream selection
        # Also track stream types for filtering
        self.streams_table.setColumnCount(6)
        self.streams_table.setHorizontalHeaderLabels(["Record", "Name", "Type", "Channels", "Sample Rate", "Source ID"])
        self.streams_table.horizontalHeader().setStretchLastSection(True)
        self.streams_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.streams_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.streams_table.setMaximumHeight(200)
        test_layout.addWidget(self.streams_table)
        
        # Refresh streams button and inspect channels
        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh Streams")
        refresh_button.clicked.connect(self._refresh_streams)
        refresh_button.setEnabled(LSL_AVAILABLE)
        refresh_layout.addWidget(refresh_button)

        clear_button = QPushButton("Clear Streams")
        clear_button.clicked.connect(self._clear_streams)
        refresh_layout.addWidget(clear_button)

        self.inspect_button = QPushButton("View Selected Stream Channels")
        self.inspect_button.clicked.connect(self._inspect_selected_stream_channels)
        self.inspect_button.setEnabled(LSL_AVAILABLE)
        refresh_layout.addWidget(self.inspect_button)


        refresh_layout.addStretch()
        test_layout.addLayout(refresh_layout)
        
        test_group.setLayout(test_layout)
        scroll_layout.addWidget(test_group)
        
        # Received data display
        data_group = QGroupBox("Received Data (Test Mode)")
        data_layout = QVBoxLayout()
        
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(4)
        self.data_table.setHorizontalHeaderLabels(["Time", "Stream", "Channels", "Data"])
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.setMaximumHeight(200)
        data_layout.addWidget(self.data_table)
        
        data_group.setLayout(data_layout)
        scroll_layout.addWidget(data_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Configuration")
        self.save_button.clicked.connect(self._save_config)
        self.save_button.setDefault(True)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Refresh streams on startup
        if LSL_AVAILABLE:
            self._refresh_streams()
    
    def _update_ui_from_config(self):
        """Update UI elements from current configuration."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.current_config:
            logger.warning("_update_ui_from_config called with no current_config")
            return
        
        try:
            self.mouse_tracking_check.setChecked(self.current_config.enable_mouse_tracking)
            self.marker_api_check.setChecked(self.current_config.enable_marker_api)
            self.tobii_check.setChecked(self.current_config.enable_tobii_eyetracker)
            
            if self.current_config.tobii_stream_name:
                self.tobii_stream_edit.setText(self.current_config.tobii_stream_name)
            else:
                self.tobii_stream_edit.clear()
            
            # EmotiBit: only load enable checkbox and IP field (BrainFlow backend)
            self.emotibit_check.setChecked(getattr(self.current_config, 'use_brainflow', False))
            if getattr(self.current_config, 'brainflow_ip', None):
                self.brainflow_ip_edit.setText(self.current_config.brainflow_ip)
            else:
                self.brainflow_ip_edit.clear()
            logger.debug("UI updated from config successfully")
        except Exception as e:
            logger.error(f"Error updating UI from config: {e}", exc_info=True)
            raise

        # Pre-load any previously selected stream filters
        if self.current_config.additional_stream_filters:
            try:
                self.selected_streams = set(self.current_config.additional_stream_filters)
            except Exception:
                self.selected_streams = set()

        # Note: BrainFlow streamer is started manually via button, not auto-started
        # This gives user control and allows testing before saving config
    
    def _on_config_changed(self):
        """Handle configuration changes."""
        # Update current_config from UI
        self.current_config.enable_mouse_tracking = self.mouse_tracking_check.isChecked()
        self.current_config.enable_marker_api = self.marker_api_check.isChecked()
        self.current_config.enable_tobii_eyetracker = self.tobii_check.isChecked()
        
        tobii_name = self.tobii_stream_edit.text().strip()
        self.current_config.tobii_stream_name = tobii_name if tobii_name else None
        
        # EmotiBit: persist only enable checkbox and IP field (BrainFlow backend)
        self.current_config.use_brainflow = self.emotibit_check.isChecked()
        iptxt = self.brainflow_ip_edit.text().strip()
        self.current_config.brainflow_ip = iptxt if iptxt else None
    
    def _refresh_streams(self):
        """Refresh the list of available LSL streams."""
        if not LSL_AVAILABLE:
            return
        
        try:
            # Resolve streams with a short timeout
            streams = resolve_streams(1.0)
            # Save available streams for inspection
            self.available_streams = streams
            
            self.streams_table.setRowCount(len(streams))
            
            for i, stream in enumerate(streams):
                stream_name = stream.name()
                stream_type = stream.type()
                
                # Checkbox to indicate recording this stream
                record_cb = QCheckBox()
                # Check if this stream was previously selected (by name)
                was_selected = stream_name in (self.current_config.additional_stream_filters or [])
                record_cb.setChecked(was_selected)
                
                if was_selected:
                    self.selected_streams.add(stream_name)

                def _cb_state_changed(state, name=stream_name):
                    if state == Qt.CheckState.Checked:
                        self.selected_streams.add(name)
                    else:
                        self.selected_streams.discard(name)

                record_cb.stateChanged.connect(_cb_state_changed)
                self.streams_table.setCellWidget(i, 0, record_cb)

                self.streams_table.setItem(i, 1, QTableWidgetItem(stream_name))
                self.streams_table.setItem(i, 2, QTableWidgetItem(stream_type))
                self.streams_table.setItem(i, 3, QTableWidgetItem(str(stream.channel_count())))

                sample_rate = stream.nominal_srate()
                sample_rate_str = f"{sample_rate:.1f} Hz" if sample_rate > 0 else "Irregular"
                self.streams_table.setItem(i, 4, QTableWidgetItem(sample_rate_str))

                self.streams_table.setItem(i, 5, QTableWidgetItem(stream.source_id()))
            
            # Resize columns to content
            self.streams_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh streams: {e}")
    
    def _toggle_test(self):
        """Toggle stream testing mode."""
        if self.is_testing:
            self._stop_test()
        else:
            self._start_test()

    def _start_emotibit_process(self):
        """Start an external process to launch EmotiBit LSL streams (user-provided command)."""
        if self.emotibit_process:
            QMessageBox.information(self, "Info", "EmotiBit process already running.")
            return

        cmd = self.emotibit_cmd_edit.text().strip() if hasattr(self, 'emotibit_cmd_edit') else None
        if not cmd:
            QMessageBox.warning(self, "Missing Command", "No EmotiBit start command provided.")
            return

        try:
            # Start the command as a new process; capture stdout/stderr so logs pick it up
            # Use shell=True to allow complex commands; caller should ensure safety
            self.emotibit_process = subprocess.Popen(cmd, shell=True)
            self.start_emotibit_button.setEnabled(False)
            self.stop_emotibit_button.setEnabled(True)
            QMessageBox.information(self, "EmotiBit", "Started EmotiBit process.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start EmotiBit process: {e}")

    def _stop_emotibit_process(self):
        """Stop the EmotiBit process if it was started from the manager."""
        if not self.emotibit_process:
            QMessageBox.information(self, "Info", "No EmotiBit process to stop.")
            return

        try:
            self.emotibit_process.terminate()
            self.emotibit_process.wait(timeout=5)
        except Exception:
            try:
                self.emotibit_process.kill()
            except Exception:
                pass
        finally:
            self.emotibit_process = None
            self.start_emotibit_button.setEnabled(True)
            self.stop_emotibit_button.setEnabled(False)
            QMessageBox.information(self, "EmotiBit", "Stopped EmotiBit process.")

    def _inspect_selected_stream_channels(self):
        """Show channel information for the currently selected stream in the table."""
        sel = self.streams_table.currentRow()
        if sel < 0 or sel >= len(self.available_streams):
            QMessageBox.information(self, "No Selection", "Please select a stream in the table first.")
            return

        stream = self.available_streams[sel]
        try:
            desc = stream.desc()
            # Try several ways to extract channel info; fall back to stringifying desc
            channels_text = None
            try:
                # Some pylsl StreamInfo desc has to_xml or to_string
                if hasattr(desc, 'to_xml'):
                    channels_text = desc.to_xml()
                elif hasattr(desc, 'to_string'):
                    channels_text = desc.to_string()
                else:
                    channels_text = str(desc)
            except Exception:
                channels_text = str(desc)

            # Show in a scrollable dialog
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Channels: {stream.name()}")
            dlg.setModal(True)
            dlg.setMinimumSize(600, 400)
            layout = QVBoxLayout(dlg)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(channels_text)
            layout.addWidget(text)
            btn = QPushButton("Close")
            btn.clicked.connect(dlg.accept)
            layout.addWidget(btn)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not retrieve channel info: {e}")

    def _start_brainflow_streamer(self):
        """Start the internal BrainFlow-based EmotiBit streamer."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not BRAINFLOW_UI_AVAILABLE or EmotiBitBrainflowStreamer is None:
            error_msg = BRAINFLOW_ERROR or "BrainFlow package not installed"
            detailed_msg = (
                f"BrainFlow integration is not available in this environment.\n\n"
                f"Error: {error_msg}\n\n"
                f"To enable EmotiBit support, please install the brainflow package:\n"
                f"  pip install brainflow"
            )
            QMessageBox.warning(self, "BrainFlow Missing", detailed_msg)
            return

        if self.brainflow_streamer:
            QMessageBox.information(self, "Info", "BrainFlow streamer already running.")
            return

        ip = self.brainflow_ip_edit.text().strip() if hasattr(self, 'brainflow_ip_edit') else None
        try:
            logger.info(f"Starting BrainFlow streamer with IP: {ip}")
            self.brainflow_streamer = EmotiBitBrainflowStreamer(ip_address=ip if ip else None)
            self.brainflow_streamer.start()
            
            # Update UI immediately to show it's starting
            if hasattr(self, 'start_emotibit_brainflow_button'):
                self.start_emotibit_brainflow_button.setEnabled(False)
            if hasattr(self, 'stop_emotibit_brainflow_button'):
                self.stop_emotibit_brainflow_button.setEnabled(True)
            if hasattr(self, 'emotibit_status_label'):
                self.emotibit_status_label.setText("Status: Starting... (checking device connection)")
                self.emotibit_status_label.setStyleSheet("color: orange;")
            
            logger.info("BrainFlow streamer thread started")
            
            # Give it a moment to connect, then check status
            QTimer.singleShot(3000, self._check_brainflow_status)
            
            QMessageBox.information(
                self, 
                "BrainFlow", 
                "Started BrainFlow EmotiBit streamer.\n\n"
                "Note: If the EmotiBit device is already in use by another program "
                "(like EmotiBit Oscilloscope), the connection may fail. "
                "Please close other programs using the device first.\n\n"
                "The stream should appear in available streams once connected."
            )
        except Exception as e:
            logger.error(f"Failed to start BrainFlow streamer: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start BrainFlow streamer: {e}")

    def _check_brainflow_status(self):
        """Check if BrainFlow streamer successfully connected and created LSL stream."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.brainflow_streamer:
            return
        
        # Check if streamer has an outlet (means it successfully connected)
        if hasattr(self.brainflow_streamer, '_outlet') and self.brainflow_streamer._outlet:
            if hasattr(self, 'emotibit_status_label'):
                self.emotibit_status_label.setText("Status: Running (LSL stream active)")
                self.emotibit_status_label.setStyleSheet("color: green;")
            logger.info("BrainFlow streamer confirmed active with LSL outlet")
        else:
            # Check if it's still trying to connect or if it failed
            if hasattr(self.brainflow_streamer, '_started') and self.brainflow_streamer._started:
                if hasattr(self, 'emotibit_status_label'):
                    self.emotibit_status_label.setText("Status: Connection failed - check logs and device")
                    self.emotibit_status_label.setStyleSheet("color: red;")
                logger.warning("BrainFlow streamer started but LSL outlet not created - connection may have failed")
    
    def _stop_brainflow_streamer(self):
        """Stop the BrainFlow-based streamer if running."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.brainflow_streamer:
            QMessageBox.information(self, "Info", "No BrainFlow streamer is running.")
            return

        try:
            logger.info("Stopping BrainFlow streamer")
            self.brainflow_streamer.stop()
        except Exception as e:
            logger.error(f"Error stopping BrainFlow streamer: {e}", exc_info=True)
        finally:
            self.brainflow_streamer = None
            
            # Update UI
            if hasattr(self, 'start_emotibit_brainflow_button'):
                self.start_emotibit_brainflow_button.setEnabled(
                    BRAINFLOW_UI_AVAILABLE and self.emotibit_check.isChecked()
                )
            if hasattr(self, 'stop_emotibit_brainflow_button'):
                self.stop_emotibit_brainflow_button.setEnabled(False)
            if hasattr(self, 'emotibit_status_label'):
                self.emotibit_status_label.setText("Status: Stopped")
                self.emotibit_status_label.setStyleSheet("color: gray;")
            
            logger.info("BrainFlow streamer stopped")
            QMessageBox.information(self, "BrainFlow", "Stopped BrainFlow streamer.")

    def _start_emotibit_via_brainflow(self):
        """Convenience wrapper: start EmotiBit using the BrainFlow backend and update buttons.

        This makes a single-click operation for users: Start EmotiBit (BrainFlow).
        """
        # Ensure config is updated first
        self._on_config_changed()
        
        # Start the brainflow streamer
        self._start_brainflow_streamer()
        
        # Refresh streams after a short delay to allow stream to appear
        if LSL_AVAILABLE:
            QTimer.singleShot(2000, self._refresh_streams)  # Refresh after 2 seconds

    def _clear_streams(self):
        """Clear the list of available streams shown in the table."""
        try:
            self.available_streams = []
            self.streams_table.setRowCount(0)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to clear streams: {e}")
    
    def _start_test(self):
        """Start receiving LSL streams for testing."""
        import logging
        import time
        logger = logging.getLogger(__name__)
        
        if not LSL_AVAILABLE:
            QMessageBox.warning(self, "Error", "LSL is not available.")
            return
        
        try:
            logger.info("Starting LSL test receiver")
            
            # First, check if EmotiBit is enabled and streamer is not running
            if getattr(self.current_config, 'use_brainflow', False):
                logger.info("EmotiBit (BrainFlow) is enabled - checking if streamer is running")
                if not self.brainflow_streamer:
                    logger.info("Starting BrainFlow streamer automatically for test")
                    self._start_brainflow_streamer()
                    time.sleep(1)  # Give streamer time to start
            
            # Create test recorder
            test_session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.test_recorder = LSLRecorder(test_session_id)
            logger.info(f"Created test recorder with session ID: {test_session_id}")
            self.test_recorder.start_recording(wait_time=2.0)
            logger.info(f"Recording started, found {len(self.test_recorder.inlets)} LSL streams")
            
            if not self.test_recorder.is_recording:
                logger.warning("Test recorder failed to find any LSL streams")
                QMessageBox.warning(self, "Error", "No LSL streams found for testing.")
                return
            
            # Start timer to update data table
            self.test_timer = QTimer()
            self.test_timer.timeout.connect(self._update_test_data)
            self.test_timer.start(100)  # Update every 100ms
            
            self.is_testing = True
            self.test_button.setText("Receiving...")
            self.test_button.setEnabled(False)
            self.stop_test_button.setEnabled(True)
            logger.info("LSL test receiver started successfully")
            
            # Clear data table
            self.data_table.setRowCount(0)
            
        except Exception as e:
            logger.error(f"Failed to start test: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to start test: {e}")
            if self.test_recorder:
                try:
                    self.test_recorder.stop_recording()
                except:
                    pass
                self.test_recorder = None
    
    def _stop_test(self):
        """Stop stream testing mode."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Stopping LSL test receiver")
        if self.test_timer:
            self.test_timer.stop()
            self.test_timer = None
        
        if self.test_recorder:
            try:
                self.test_recorder.stop_recording()
            except:
                pass
            self.test_recorder = None
        
        self.is_testing = False
        self.test_button.setText("Start Receiving Test")
        self.test_button.setEnabled(True)
        logger.info("LSL test receiver stopped")
        self.stop_test_button.setEnabled(False)
    
    def _update_test_data(self):
        """Update the received data table during testing."""
        if not self.test_recorder or not self.test_recorder.is_recording:
            return
        
        # Record a sample
        self.test_recorder.record_sample()
        
        # Update table with recent samples (last 50)
        recent_samples = self.test_recorder.recorded_data[-50:]
        
        self.data_table.setRowCount(len(recent_samples))
        
        for i, sample in enumerate(recent_samples):
            relative_time = sample.get('relative_time', 0.0)
            stream_info = sample.get('stream_info', {})
            stream_name = stream_info.get('name', 'Unknown')
            data = sample.get('data', [])
            
            # Format data
            if isinstance(data, list):
                data_str = ', '.join([str(d) for d in data[:5]])  # Show first 5 values
                if len(data) > 5:
                    data_str += f" ... ({len(data)} total)"
            else:
                data_str = str(data)
            
            self.data_table.setItem(i, 0, QTableWidgetItem(f"{relative_time:.3f}s"))
            self.data_table.setItem(i, 1, QTableWidgetItem(stream_name))
            self.data_table.setItem(i, 2, QTableWidgetItem(str(len(data) if isinstance(data, list) else 1)))
            self.data_table.setItem(i, 3, QTableWidgetItem(data_str[:100]))  # Truncate long data
        
        # Scroll to bottom
        if recent_samples:
            self.data_table.scrollToBottom()
    
    def _save_config(self):
        """Save the configuration."""
        # Update config from UI
        self._on_config_changed()
        
        # Persist selected streams into additional_stream_filters so recording will include them
        try:
            self.current_config.additional_stream_filters = list(self.selected_streams)
            
            # Also collect stream types from selected streams for type filtering
            selected_types = set()
            for stream in self.available_streams:
                if stream.name() in self.selected_streams:
                    selected_types.add(stream.type())
            self.current_config.additional_stream_type_filters = list(selected_types)
        except Exception:
            # Fallback: leave as-is
            pass
        
        # Note: BrainFlow streamer state is NOT saved - it's a runtime state
        # The use_brainflow flag and brainflow_ip are saved, but the streamer
        # must be started manually or will be started automatically during session
        
        # Emit signal
        self.config_changed.emit(self.current_config)
        
        # Accept dialog
        self.accept()
    
    def get_config(self) -> LSLConfig:
        """Get the current configuration."""
        self._on_config_changed()
        return self.current_config
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.is_testing:
            self._stop_test()
        
        # Note: We don't stop the BrainFlow streamer on close - it should persist
        # for the recording session. User can stop it manually if needed.
        # The streamer will be managed by the session window during recording.
        
        event.accept()

