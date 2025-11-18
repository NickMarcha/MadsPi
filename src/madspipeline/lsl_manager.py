"""
LSL Stream Management interface for MadsPipeline.
Provides a dialog for managing LSL streams, including mouse tracking, marker API, Tobii eyetracker, and Emotibit.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
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


class LSLStreamManagerDialog(QDialog):
    """Dialog for managing LSL streams."""
    
    config_changed = Signal(LSLConfig)  # Emitted when configuration changes
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.current_config: Optional[LSLConfig] = None
        self.test_recorder: Optional[LSLRecorder] = None
        self.test_timer: Optional[QTimer] = None
        self.is_testing = False
        
        # Initialize config from project
        if (project.embedded_webpage_config and 
            project.embedded_webpage_config.lsl_config):
            self.current_config = project.embedded_webpage_config.lsl_config
        else:
            # Create default config
            self.current_config = LSLConfig(
                enable_mouse_tracking=True,
                enable_marker_api=project.embedded_webpage_config.enable_marker_api if project.embedded_webpage_config else True,
                enable_tobii_eyetracker=False,
                enable_emotibit=False
            )
        # Tracks streams selected for recording in the UI
        self.selected_streams = set()
        
        self.setWindowTitle(f"LSL Stream Management - {project.name}")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._update_ui_from_config()
    
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
        
        # Emotibit
        emotibit_layout = QHBoxLayout()
        self.emotibit_check = QCheckBox()
        self.emotibit_check.setChecked(self.current_config.enable_emotibit)
        self.emotibit_check.stateChanged.connect(self._on_config_changed)
        self.emotibit_stream_edit = QLineEdit()
        self.emotibit_stream_edit.setPlaceholderText("Auto-detect (leave empty)")
        if self.current_config.emotibit_stream_name:
            self.emotibit_stream_edit.setText(self.current_config.emotibit_stream_name)
        self.emotibit_stream_edit.textChanged.connect(self._on_config_changed)
        self.emotibit_stream_edit.setEnabled(self.current_config.enable_emotibit)
        self.emotibit_check.stateChanged.connect(
            lambda state: self.emotibit_stream_edit.setEnabled(state == Qt.CheckState.Checked)
        )
        emotibit_layout.addWidget(self.emotibit_check)
        emotibit_layout.addWidget(QLabel("Stream name:"))
        emotibit_layout.addWidget(self.emotibit_stream_edit)
        config_layout.addRow("Enable Emotibit:", emotibit_layout)
        
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
        self.streams_table.setColumnCount(6)
        self.streams_table.setHorizontalHeaderLabels(["Record", "Name", "Type", "Channels", "Sample Rate", "Source ID"])
        self.streams_table.horizontalHeader().setStretchLastSection(True)
        self.streams_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.streams_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.streams_table.setMaximumHeight(200)
        test_layout.addWidget(self.streams_table)
        
        # Refresh streams button
        refresh_button = QPushButton("Refresh Streams")
        refresh_button.clicked.connect(self._refresh_streams)
        refresh_button.setEnabled(LSL_AVAILABLE)
        test_layout.addWidget(refresh_button)
        
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
        if not self.current_config:
            return
        
        self.mouse_tracking_check.setChecked(self.current_config.enable_mouse_tracking)
        self.marker_api_check.setChecked(self.current_config.enable_marker_api)
        self.tobii_check.setChecked(self.current_config.enable_tobii_eyetracker)
        self.emotibit_check.setChecked(self.current_config.enable_emotibit)
        
        if self.current_config.tobii_stream_name:
            self.tobii_stream_edit.setText(self.current_config.tobii_stream_name)
        else:
            self.tobii_stream_edit.clear()
        
        if self.current_config.emotibit_stream_name:
            self.emotibit_stream_edit.setText(self.current_config.emotibit_stream_name)
        else:
            self.emotibit_stream_edit.clear()

        # Pre-load any previously selected stream filters
        if self.current_config.additional_stream_filters:
            try:
                self.selected_streams = set(self.current_config.additional_stream_filters)
            except Exception:
                self.selected_streams = set()
    
    def _on_config_changed(self):
        """Handle configuration changes."""
        # Update current_config from UI
        self.current_config.enable_mouse_tracking = self.mouse_tracking_check.isChecked()
        self.current_config.enable_marker_api = self.marker_api_check.isChecked()
        self.current_config.enable_tobii_eyetracker = self.tobii_check.isChecked()
        self.current_config.enable_emotibit = self.emotibit_check.isChecked()
        
        tobii_name = self.tobii_stream_edit.text().strip()
        self.current_config.tobii_stream_name = tobii_name if tobii_name else None
        
        emotibit_name = self.emotibit_stream_edit.text().strip()
        self.current_config.emotibit_stream_name = emotibit_name if emotibit_name else None
    
    def _refresh_streams(self):
        """Refresh the list of available LSL streams."""
        if not LSL_AVAILABLE:
            return
        
        try:
            # Resolve streams with a short timeout
            streams = resolve_streams(1.0)
            
            self.streams_table.setRowCount(len(streams))
            
            for i, stream in enumerate(streams):
                stream_name = stream.name()
                # Checkbox to indicate recording this stream
                record_cb = QCheckBox()
                record_cb.setChecked(stream_name in (self.current_config.additional_stream_filters or []))

                def _cb_state_changed(state, name=stream_name):
                    if state == Qt.CheckState.Checked:
                        self.selected_streams.add(name)
                    else:
                        self.selected_streams.discard(name)

                record_cb.stateChanged.connect(_cb_state_changed)
                self.streams_table.setCellWidget(i, 0, record_cb)

                self.streams_table.setItem(i, 1, QTableWidgetItem(stream_name))
                self.streams_table.setItem(i, 2, QTableWidgetItem(stream.type()))
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
    
    def _start_test(self):
        """Start receiving LSL streams for testing."""
        if not LSL_AVAILABLE:
            QMessageBox.warning(self, "Error", "LSL is not available.")
            return
        
        try:
            # Create test recorder
            test_session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.test_recorder = LSLRecorder(test_session_id)
            self.test_recorder.start_recording(wait_time=2.0)
            
            if not self.test_recorder.is_recording:
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
            
            # Clear data table
            self.data_table.setRowCount(0)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to start test: {e}")
            if self.test_recorder:
                try:
                    self.test_recorder.stop_recording()
                except:
                    pass
                self.test_recorder = None
    
    def _stop_test(self):
        """Stop stream testing mode."""
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
        except Exception:
            # Fallback: leave as-is
            pass
        
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
        event.accept()

