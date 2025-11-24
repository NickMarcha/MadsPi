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
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QThread
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


class StreamResolutionWorker(QThread):
    """Worker thread to resolve LSL streams without blocking UI."""
    finished = Signal(object)  # Emits the LSLRecorder when done
    
    def __init__(self, recorder, wait_time, name_filters, channel_filters):
        super().__init__()
        self.recorder = recorder
        self.wait_time = wait_time
        self.name_filters = name_filters
        self.channel_filters = channel_filters
    
    def run(self):
        """Run stream resolution in background thread."""
        import logging
        import time
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"StreamResolutionWorker: Starting stream resolution (wait_time={self.wait_time})")
            start_time = time.time()
            
            # Call start_recording with timeout protection
            try:
                self.recorder.start_recording(
                    wait_time=self.wait_time,
                    stream_name_filters=self.name_filters,
                    stream_channel_filters=self.channel_filters
                )
                elapsed = time.time() - start_time
                logger.info(f"StreamResolutionWorker: Resolution complete in {elapsed:.2f}s, found {len(self.recorder.inlets)} streams")
                logger.info(f"StreamResolutionWorker: is_recording={self.recorder.is_recording}, inlets={len(self.recorder.inlets)}")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"StreamResolutionWorker: Error during start_recording after {elapsed:.2f}s: {e}", exc_info=True)
                raise
            
            # Always emit finished signal, even if something went wrong
            logger.info("StreamResolutionWorker: Emitting finished signal")
            self.finished.emit(self.recorder)
            logger.info("StreamResolutionWorker: Finished signal emitted")
        except Exception as e:
            logger.error(f"Error in stream resolution worker: {e}", exc_info=True)
            self.finished.emit(None)


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
        self.stream_resolution_worker: Optional[StreamResolutionWorker] = None
        
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
        
        # Available streams table
        streams_label = QLabel("Available LSL Streams (check 'Record Stream' to include stream in recording):")
        streams_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        test_layout.addWidget(streams_label)
        
        self.streams_table = QTableWidget()
        # Add a 'Record' checkbox column for per-stream selection
        # Also track stream types for filtering
        self.streams_table.setColumnCount(6)
        self.streams_table.setHorizontalHeaderLabels(["Record Stream", "Name", "Type", "Channels", "Sample Rate", "Source ID"])
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

        # Note: Channel selection is now done via the unified channels table below
        # Removed individual stream channel selection button


        refresh_layout.addStretch()
        test_layout.addLayout(refresh_layout)
        
        test_group.setLayout(test_layout)
        scroll_layout.addWidget(test_group)
        
        # Channel Selection Table
        channel_group = QGroupBox("Channel Selection")
        channel_layout = QVBoxLayout()
        
        channel_info_label = QLabel(
            "Select channels to record for each stream. "
            "Channels are only available if their stream is enabled above. "
            "Unchecked channels will be filtered out during recording."
        )
        channel_info_label.setWordWrap(True)
        channel_layout.addWidget(channel_info_label)
        
        self.channels_table = QTableWidget()
        self.channels_table.setColumnCount(4)
        self.channels_table.setHorizontalHeaderLabels(["Stream", "Channel", "Label/Type", "Record Channel"])
        self.channels_table.horizontalHeader().setStretchLastSection(True)
        self.channels_table.setMaximumHeight(250)
        self.channels_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        channel_layout.addWidget(self.channels_table)
        
        channel_buttons_layout = QHBoxLayout()
        refresh_channels_btn = QPushButton("Refresh Channel List")
        refresh_channels_btn.clicked.connect(self._refresh_channels_table)
        channel_buttons_layout.addWidget(refresh_channels_btn)
        channel_buttons_layout.addStretch()
        channel_layout.addLayout(channel_buttons_layout)
        
        channel_group.setLayout(channel_layout)
        scroll_layout.addWidget(channel_group)
        
        # Received data display
        data_group = QGroupBox("Received Data (Test Mode)")
        data_layout = QVBoxLayout()
        
        # Test buttons above the data table
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
        data_layout.addLayout(test_buttons_layout)
        
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(5)
        self.data_table.setHorizontalHeaderLabels(["Time", "Stream", "Channel", "Label", "Value"])
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
            self._refresh_channels_table()
    
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
                logger.info(f"Loaded stream filters: {self.current_config.additional_stream_filters}")
            except Exception:
                self.selected_streams = set()
        
        # Ensure stream_channel_filters is properly initialized
        if not hasattr(self.current_config, 'stream_channel_filters') or self.current_config.stream_channel_filters is None:
            self.current_config.stream_channel_filters = {}
        elif not isinstance(self.current_config.stream_channel_filters, dict):
            # Convert to dict if it's not already
            self.current_config.stream_channel_filters = {}
        
        # Log loaded channel filters for debugging
        if self.current_config.stream_channel_filters:
            logger.info(f"Loaded channel filters: {self.current_config.stream_channel_filters}")
        
        # Refresh channels table after loading config to show saved selections
        # Use QTimer to do this after UI is fully set up
        QTimer.singleShot(100, self._refresh_channels_table)
        
        # Also refresh streams table to restore stream selections
        QTimer.singleShot(150, self._refresh_streams)

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
                    # Update channel table to enable/disable channels for this stream
                    self._update_channel_table_enable_state()

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
            
            # Refresh channels table when streams are refreshed
            self._refresh_channels_table()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh streams: {e}")
    
    def _is_stream_selected(self, stream_name: str) -> bool:
        """Check if a stream is selected by looking at the streams table checkbox."""
        for i in range(self.streams_table.rowCount()):
            stream_item = self.streams_table.item(i, 1)  # Stream name is in column 1
            if stream_item and stream_item.text() == stream_name:
                checkbox = self.streams_table.cellWidget(i, 0)  # Checkbox is in column 0
                if checkbox and isinstance(checkbox, QCheckBox):
                    return checkbox.isChecked()
        # Fallback: check selected_streams set
        return stream_name in self.selected_streams
    
    def _refresh_channels_table(self):
        """Refresh the channel selection table with all channels from all streams."""
        if not LSL_AVAILABLE:
            return
        
        try:
            # Get current channel filters
            channel_filters = getattr(self.current_config, 'stream_channel_filters', {})
            
            # Collect all channels from all streams
            all_channels = []
            for stream in self.available_streams:
                stream_name = stream.name()
                channel_count = stream.channel_count()
                desc = stream.desc()
                
                # Get channel labels from metadata
                channel_labels = {}
                try:
                    chns = desc.child("channels")
                    if chns:
                        # Use next_sibling() method to iterate through channels (as per pylsl example)
                        ch = chns.child("channel")
                        i = 0
                        max_iterations = channel_count + 5  # Safety limit
                        while ch and i < max_iterations:
                            # Try different methods to get label
                            label = None
                            try:
                                label = ch.child_value("label")
                            except:
                                try:
                                    label_elem = ch.child("label")
                                    if label_elem:
                                        label = label_elem.value()
                                except:
                                    pass
                            
                            if not label or label == "":
                                label = f"Channel {i}"
                            
                            # Get type
                            ch_type = ""
                            try:
                                ch_type = ch.child_value("type") or ""
                            except:
                                try:
                                    type_elem = ch.child("type")
                                    if type_elem:
                                        ch_type = type_elem.value()
                                except:
                                    pass
                            
                            # Get unit
                            unit = ""
                            try:
                                unit = ch.child_value("unit") or ""
                            except:
                                try:
                                    unit_elem = ch.child("unit")
                                    if unit_elem:
                                        unit = unit_elem.value()
                                except:
                                    pass
                            
                            channel_labels[i] = {
                                'label': label,
                                'type': ch_type,
                                'unit': unit
                            }
                            
                            # Move to next channel
                            try:
                                ch = ch.next_sibling()
                            except:
                                break
                            i += 1
                            
                            # Stop if we've processed all channels
                            if i >= channel_count:
                                break
                        
                        # Log if we found labels
                        if channel_labels:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.debug(f"Found {len(channel_labels)} channel labels for {stream_name}: {list(channel_labels.values())[:3]}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not read channel labels for {stream_name}: {e}", exc_info=True)
                    pass
                
                # Get selected channels for this stream (empty list means all)
                selected_channels = channel_filters.get(stream_name, [])
                
                # Add each channel as a row
                for ch_idx in range(channel_count):
                    ch_info = channel_labels.get(ch_idx, {})
                    label = ch_info.get('label', f"Channel {ch_idx}")
                    ch_type = ch_info.get('type', '')
                    unit = ch_info.get('unit', '')
                    
                    # Format label/type display
                    label_display = label
                    if ch_type:
                        label_display += f" ({ch_type})"
                    if unit:
                        label_display += f" [{unit}]"
                    
                    all_channels.append({
                        'stream_name': stream_name,
                        'channel_index': ch_idx,
                        'label': label_display,
                        'selected': not selected_channels or ch_idx in selected_channels
                    })
            
            # Populate table
            self.channels_table.setRowCount(len(all_channels))
            for i, ch_data in enumerate(all_channels):
                # Stream name
                self.channels_table.setItem(i, 0, QTableWidgetItem(ch_data['stream_name']))
                
                # Channel index
                self.channels_table.setItem(i, 1, QTableWidgetItem(str(ch_data['channel_index'])))
                
                # Label/Type
                self.channels_table.setItem(i, 2, QTableWidgetItem(ch_data['label']))
                
                # Record checkbox
                record_cb = QCheckBox()
                record_cb.setChecked(ch_data['selected'])
                
                # Enable/disable based on whether stream is selected (check actual checkbox state)
                stream_selected = self._is_stream_selected(ch_data['stream_name'])
                record_cb.setEnabled(stream_selected)
                if not stream_selected:
                    record_cb.setToolTip("Enable the stream above to select channels")
                
                def _cb_state_changed(state, stream=ch_data['stream_name'], ch_idx=ch_data['channel_index']):
                    # Update config when checkbox changes
                    if not hasattr(self.current_config, 'stream_channel_filters'):
                        self.current_config.stream_channel_filters = {}
                    if stream not in self.current_config.stream_channel_filters:
                        self.current_config.stream_channel_filters[stream] = []
                    
                    if state == Qt.CheckState.Checked:
                        # Add channel if not already in list
                        if ch_idx not in self.current_config.stream_channel_filters[stream]:
                            self.current_config.stream_channel_filters[stream].append(ch_idx)
                            self.current_config.stream_channel_filters[stream].sort()
                    else:
                        # Remove channel from list
                        if ch_idx in self.current_config.stream_channel_filters[stream]:
                            self.current_config.stream_channel_filters[stream].remove(ch_idx)
                    
                    # If all channels are selected, clear the filter (empty list = all channels)
                    stream_channels = [ch for ch in all_channels if ch['stream_name'] == stream]
                    selected_count = sum(1 for ch in stream_channels 
                                       if ch['channel_index'] in self.current_config.stream_channel_filters.get(stream, []))
                    if selected_count == len(stream_channels):
                        self.current_config.stream_channel_filters[stream] = []
                
                record_cb.stateChanged.connect(_cb_state_changed)
                self.channels_table.setCellWidget(i, 3, record_cb)
                
                # Also grey out the row if stream is not selected
                if not stream_selected:
                    for col in range(4):
                        item = self.channels_table.item(i, col)
                        if item:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    # Make checkbox visually disabled
                    record_cb.setStyleSheet("color: gray;")
            
            # Resize columns
            self.channels_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh channels: {e}")
    
    def _update_channel_table_enable_state(self):
        """Update enabled/disabled state of channel checkboxes based on stream selection."""
        try:
            for i in range(self.channels_table.rowCount()):
                stream_item = self.channels_table.item(i, 0)
                if stream_item:
                    stream_name = stream_item.text()
                    stream_selected = self._is_stream_selected(stream_name)
                    
                    # Update checkbox
                    checkbox = self.channels_table.cellWidget(i, 3)
                    if checkbox:
                        checkbox.setEnabled(stream_selected)
                        if not stream_selected:
                            checkbox.setStyleSheet("color: gray;")
                            checkbox.setToolTip("Enable the stream above to select channels")
                        else:
                            checkbox.setStyleSheet("")
                            checkbox.setToolTip("")
                    
                    # Update row appearance
                    for col in range(4):
                        item = self.channels_table.item(i, col)
                        if item:
                            if stream_selected:
                                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                            else:
                                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error updating channel table enable state: {e}")
    
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
        """Show channel information and allow selection for the currently selected stream."""
        sel = self.streams_table.currentRow()
        if sel < 0 or sel >= len(self.available_streams):
            QMessageBox.information(self, "No Selection", "Please select a stream in the table first.")
            return

        stream = self.available_streams[sel]
        stream_name = stream.name()
        try:
            desc = stream.desc()
            channel_count = stream.channel_count()
            
            # Get current channel filter for this stream
            current_filter = getattr(self.current_config, 'stream_channel_filters', {}).get(stream_name, [])
            if current_filter is None:
                current_filter = []
            
            # Try to extract channel names from LSL metadata
            channel_info = []
            channel_labels = []
            try:
                chns = desc.child("channels")
                if chns and chns.child_count() > 0:
                    for i in range(chns.child_count()):
                        ch = chns.child(i)
                        label = ch.child_value("label") or f"Channel {i}"
                        ch_type = ch.child_value("type") or "Unknown"
                        unit = ch.child_value("unit") or ""
                        channel_labels.append(label)
                        channel_info.append({
                            'index': i,
                            'label': label,
                            'type': ch_type,
                            'unit': unit
                        })
                else:
                    # No channel metadata, create generic labels
                    for i in range(channel_count):
                        channel_labels.append(f"Channel {i}")
                        channel_info.append({
                            'index': i,
                            'label': f"Channel {i}",
                            'type': 'Unknown',
                            'unit': ''
                        })
            except Exception as e:
                # Fallback: create generic labels
                for i in range(channel_count):
                    channel_labels.append(f"Channel {i}")
                    channel_info.append({
                        'index': i,
                        'label': f"Channel {i}",
                        'type': 'Unknown',
                        'unit': ''
                    })

            # Create dialog with channel selection
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Channel Selection: {stream_name}")
            dlg.setModal(True)
            dlg.setMinimumSize(600, 500)
            layout = QVBoxLayout(dlg)
            
            # Stream info
            info_label = QLabel(f"Stream: {stream_name}\nType: {stream.type()}\nChannels: {channel_count}\nSample Rate: {stream.nominal_srate()} Hz")
            info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            layout.addWidget(info_label)
            
            # Channel selection checkboxes
            channels_label = QLabel("Select channels to record (unchecked channels will be filtered out):")
            channels_label.setFont(QFont("Arial", 9))
            layout.addWidget(channels_label)
            
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            
            channel_checkboxes = {}
            for ch_info in channel_info:
                ch_layout = QHBoxLayout()
                cb = QCheckBox()
                ch_idx = ch_info['index']
                # Check if this channel is in the current filter (or if no filter, all are selected)
                if not current_filter:  # Empty list means all channels
                    cb.setChecked(True)
                else:
                    cb.setChecked(ch_idx in current_filter)
                
                label_text = f"Ch {ch_idx}: {ch_info['label']}"
                if ch_info['type'] != 'Unknown':
                    label_text += f" ({ch_info['type']})"
                if ch_info['unit']:
                    label_text += f" [{ch_info['unit']}]"
                
                cb.setText(label_text)
                channel_checkboxes[ch_idx] = cb
                ch_layout.addWidget(cb)
                ch_layout.addStretch()
                scroll_layout.addLayout(ch_layout)
            
            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)
            
            # Buttons
            button_layout = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            select_none_btn = QPushButton("Select None")
            
            def select_all():
                for cb in channel_checkboxes.values():
                    cb.setChecked(True)
            
            def select_none():
                for cb in channel_checkboxes.values():
                    cb.setChecked(False)
            
            select_all_btn.clicked.connect(select_all)
            select_none_btn.clicked.connect(select_none)
            button_layout.addWidget(select_all_btn)
            button_layout.addWidget(select_none_btn)
            button_layout.addStretch()
            layout.addLayout(button_layout)
            
            # Dialog buttons
            dialog_buttons = QHBoxLayout()
            save_btn = QPushButton("Save Selection")
            cancel_btn = QPushButton("Cancel")
            
            def save_selection():
                # Get selected channel indices
                selected_channels = [idx for idx, cb in channel_checkboxes.items() if cb.isChecked()]
                
                # Update config
                if not hasattr(self.current_config, 'stream_channel_filters'):
                    self.current_config.stream_channel_filters = {}
                
                if selected_channels:
                    # Sort for consistency
                    self.current_config.stream_channel_filters[stream_name] = sorted(selected_channels)
                else:
                    # Empty list means record all channels (no filter)
                    self.current_config.stream_channel_filters[stream_name] = []
                
                dlg.accept()
                QMessageBox.information(self, "Saved", f"Channel selection saved for {stream_name}.\n"
                                                         f"Selected {len(selected_channels)} of {channel_count} channels.")
            
            save_btn.clicked.connect(save_selection)
            cancel_btn.clicked.connect(dlg.reject)
            dialog_buttons.addWidget(save_btn)
            dialog_buttons.addStretch()
            dialog_buttons.addWidget(cancel_btn)
            layout.addLayout(dialog_buttons)
            
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
            
            # Give it more time to connect (auto-discovery can take 5+ seconds), then check status
            # Check multiple times to catch when it actually connects
            QTimer.singleShot(2000, self._check_brainflow_status)  # First check at 2s
            QTimer.singleShot(5000, self._check_brainflow_status)  # Second check at 5s
            QTimer.singleShot(8000, self._check_brainflow_status)  # Final check at 8s
            
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
            # Refresh streams to show the new stream
            if LSL_AVAILABLE:
                QTimer.singleShot(500, self._refresh_streams)
        else:
            # Check if it's still trying to connect or if it failed
            if hasattr(self.brainflow_streamer, '_started') and self.brainflow_streamer._started:
                # Check if board is still trying to connect (board exists but no outlet yet)
                if hasattr(self.brainflow_streamer, '_board') and self.brainflow_streamer._board:
                    if hasattr(self, 'emotibit_status_label'):
                        self.emotibit_status_label.setText("Status: Connecting... (this may take 5-10 seconds)")
                        self.emotibit_status_label.setStyleSheet("color: orange;")
                    logger.debug("BrainFlow streamer still connecting...")
                else:
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
        
        # Disable button to prevent multiple clicks
        self.test_button.setEnabled(False)
        self.test_button.setText("Starting...")
        
        try:
            logger.info("Starting LSL test receiver")
            
            # First, check if EmotiBit is enabled and streamer is not running
            if getattr(self.current_config, 'use_brainflow', False):
                logger.info("EmotiBit (BrainFlow) is enabled - checking if streamer is running")
                if not self.brainflow_streamer:
                    logger.info("Starting BrainFlow streamer automatically for test")
                    self._start_brainflow_streamer()
                    # Wait longer for BrainFlow stream to appear (5 seconds)
                    # Check if streamer actually started successfully
                    QTimer.singleShot(5000, self._check_and_continue_test_start)
                    return
                else:
                    # Check if streamer has an active outlet (stream is actually available)
                    if hasattr(self.brainflow_streamer, '_outlet') and self.brainflow_streamer._outlet:
                        logger.info("BrainFlow streamer already running with active outlet, waiting for stream to be available")
                        QTimer.singleShot(2000, self._continue_test_start)
                    else:
                        logger.warning("BrainFlow streamer exists but has no active outlet - stream may not be available")
                        # Still try, but warn user
                        QTimer.singleShot(2000, self._continue_test_start)
                    return
            
            # Continue with test start immediately if no BrainFlow
            self._continue_test_start()
            
        except Exception as e:
            logger.error(f"Failed to start test: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to start test: {e}")
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
    
    def _check_and_continue_test_start(self):
        """Check if BrainFlow streamer started successfully before continuing test."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Check if streamer has an active outlet
            if self.brainflow_streamer and hasattr(self.brainflow_streamer, '_outlet') and self.brainflow_streamer._outlet:
                logger.info("BrainFlow streamer has active outlet, continuing test start")
                self._continue_test_start()
            else:
                logger.warning("BrainFlow streamer failed to create outlet - device may not be connected")
                QMessageBox.warning(
                    self, 
                    "BrainFlow Stream Not Available",
                    "The EmotiBit streamer failed to connect to the device.\n\n"
                    "Please ensure:\n"
                    "1. EmotiBit device is powered on and connected to the network\n"
                    "2. Device is on the same network as this computer\n"
                    "3. No other program is using the EmotiBit device\n"
                    "4. Try specifying the IP address in the LSL Manager settings\n\n"
                    "You can still test other LSL streams, but EmotiBit data will not be available."
                )
                # Continue anyway - user might want to test other streams
                self._continue_test_start()
        except Exception as e:
            logger.error(f"Failed to check BrainFlow streamer: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to check BrainFlow streamer: {e}")
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
    
    def _continue_test_start(self):
        """Continue starting the test after BrainFlow streamer is ready."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Create test recorder with channel filters
            test_session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.test_recorder = LSLRecorder(test_session_id)
            logger.info(f"Created test recorder with session ID: {test_session_id}")
            
            # Get channel filters from config for test mode
            channel_filters = getattr(self.current_config, 'stream_channel_filters', {})
            
            # For test mode, if no streams are selected, don't filter (show all streams)
            # This allows testing even if user hasn't selected streams yet
            name_filters = None
            if self.selected_streams:
                name_filters = list(self.selected_streams)
                logger.info(f"Test mode: filtering streams by name: {name_filters}")
            else:
                logger.info("Test mode: no stream filters - will show all available streams")
            
            # Run stream resolution in background thread to avoid freezing UI
            self.test_button.setText("Resolving streams...")
            self.stream_resolution_worker = StreamResolutionWorker(
                self.test_recorder,
                wait_time=2.0,  # Increased wait time to ensure streams are discoverable
                name_filters=name_filters,
                channel_filters=channel_filters if channel_filters else None
            )
            self.stream_resolution_worker.finished.connect(self._on_stream_resolution_finished)
            self.stream_resolution_worker.start()
            
        except Exception as e:
            logger.error(f"Failed to start test: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to start test: {e}")
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
    
    def _on_stream_resolution_finished(self, recorder):
        """Handle completion of background stream resolution."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Stream resolution worker finished, processing result...")
        
        if recorder is None:
            logger.error("Stream resolution failed - recorder is None")
            QMessageBox.warning(self, "Error", "Failed to resolve LSL streams.")
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
            return
        
        self.test_recorder = recorder
        logger.info(f"Recording started, found {len(self.test_recorder.inlets)} LSL streams")
        logger.info(f"Test recorder is_recording flag: {self.test_recorder.is_recording}")
        
        if not self.test_recorder.is_recording or len(self.test_recorder.inlets) == 0:
            logger.warning("Test recorder failed to find any LSL streams")
            
            # Check if BrainFlow was supposed to be running
            error_msg = "No LSL streams found for testing."
            
            # If we had filters, suggest they might be too restrictive
            if self.selected_streams:
                error_msg += f"\n\nYou have filters enabled for: {', '.join(self.selected_streams)}"
                error_msg += "\nTry refreshing the stream list to see what streams are actually available."
            
            if getattr(self.current_config, 'use_brainflow', False):
                if self.brainflow_streamer:
                    if not (hasattr(self.brainflow_streamer, '_outlet') and self.brainflow_streamer._outlet):
                        error_msg += (
                            "\n\nNote: EmotiBit (BrainFlow) streamer is running but has no active stream. "
                            "The device may not be connected or may be in use by another program."
                        )
                    else:
                        error_msg += (
                            "\n\nNote: EmotiBit (BrainFlow) streamer appears to be running. "
                            "Try refreshing the stream list or check if the stream name matches your filters."
                        )
                else:
                    error_msg += (
                        "\n\nNote: EmotiBit (BrainFlow) is enabled but the streamer failed to start. "
                        "Please check that the device is powered on and connected to the network."
                    )
            
            QMessageBox.warning(self, "No Streams Found", error_msg)
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
            return
        
        # Continue with test setup (this was after the stream resolution in the original code)
        try:
            # Clear channel label cache for fresh start
            if hasattr(self, '_channel_label_cache'):
                self._channel_label_cache.clear()
            
            # Debug: Log stream metadata to verify channel labels are present
            for i, inlet_info_dict in enumerate(self.test_recorder.stream_info):
                if 'inlet_info' in inlet_info_dict:
                    inlet_info = inlet_info_dict['inlet_info']
                    try:
                        # Log XML to verify metadata
                        xml_str = inlet_info.as_xml()
                        logger.debug(f"Stream {inlet_info_dict['name']} metadata XML (first 500 chars): {xml_str[:500]}")
                        
                        # Try to read channel labels
                        desc = inlet_info.desc()
                        chns = desc.child("channels")
                        if chns:
                            ch = chns.child("channel")
                            labels = []
                            i_ch = 0
                            while ch and i_ch < inlet_info.channel_count():
                                try:
                                    label = ch.child_value("label") or f"Ch{i_ch}"
                                    labels.append(label)
                                except:
                                    labels.append(f"Ch{i_ch}")
                                try:
                                    ch = ch.next_sibling()
                                except:
                                    break
                                i_ch += 1
                            logger.info(f"Stream {inlet_info_dict['name']} has {len(labels)} channel labels: {labels[:5]}...")
                    except Exception as e:
                        logger.warning(f"Could not read metadata for {inlet_info_dict['name']}: {e}")
            
            # Start timer to update data table (slower update rate to prevent freezing)
            self.test_timer = QTimer()
            self.test_timer.timeout.connect(self._update_test_data)
            self.test_timer.start(200)  # Update every 200ms (reduced from 100ms to prevent freezing)
            
            self.is_testing = True
            self.test_button.setText("Receiving...")
            self.test_button.setEnabled(False)
            self.stop_test_button.setEnabled(True)
            logger.info("LSL test receiver started successfully")
            
            # Clear data table
            self.data_table.setRowCount(0)
            
        except Exception as e:
            logger.error(f"Error setting up test display: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Error setting up test: {e}")
            self.test_button.setEnabled(True)
            self.test_button.setText("Start Receiving Test")
            
            # Clear channel label cache for fresh start
            if hasattr(self, '_channel_label_cache'):
                self._channel_label_cache.clear()
            
            # Debug: Log stream metadata to verify channel labels are present
            for i, inlet_info_dict in enumerate(self.test_recorder.stream_info):
                if 'inlet_info' in inlet_info_dict:
                    inlet_info = inlet_info_dict['inlet_info']
                    try:
                        # Log XML to verify metadata
                        xml_str = inlet_info.as_xml()
                        logger.debug(f"Stream {inlet_info_dict['name']} metadata XML (first 500 chars): {xml_str[:500]}")
                        
                        # Try to read channel labels
                        desc = inlet_info.desc()
                        chns = desc.child("channels")
                        if chns:
                            ch = chns.child("channel")
                            labels = []
                            i_ch = 0
                            while ch and i_ch < inlet_info.channel_count():
                                try:
                                    label = ch.child_value("label") or f"Ch{i_ch}"
                                    labels.append(label)
                                except:
                                    labels.append(f"Ch{i_ch}")
                                try:
                                    ch = ch.next_sibling()
                                except:
                                    break
                                i_ch += 1
                            logger.info(f"Stream {inlet_info_dict['name']} has {len(labels)} channel labels: {labels[:5]}...")
                    except Exception as e:
                        logger.warning(f"Could not read metadata for {inlet_info_dict['name']}: {e}")
            
            # Start timer to update data table (slower update rate to prevent freezing)
            self.test_timer = QTimer()
            self.test_timer.timeout.connect(self._update_test_data)
            self.test_timer.start(200)  # Update every 200ms (reduced from 100ms to prevent freezing)
            
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
        """Update the received data table during testing - show each channel as a separate row, applying filters."""
        if not self.test_recorder or not self.test_recorder.is_recording:
            return
        
        # Record a sample (non-blocking)
        try:
            self.test_recorder.record_sample()
        except Exception:
            # If recording fails, don't update display
            return
        
        # Get recent samples and expand each channel as a separate row
        # Limit to last 50 samples to avoid performance issues
        recent_samples = self.test_recorder.recorded_data[-50:]
        
        # Get channel filters from config
        channel_filters = getattr(self.current_config, 'stream_channel_filters', {})
        
        # Cache channel labels per stream to avoid re-reading every update
        if not hasattr(self, '_channel_label_cache'):
            self._channel_label_cache = {}
        
        # Expand samples into channel rows (only showing filtered channels)
        channel_rows = []
        for sample in recent_samples:
            relative_time = sample.get('relative_time', 0.0)
            stream_info = sample.get('stream_info', {})
            stream_name = stream_info.get('name', 'Unknown')
            data = sample.get('data', [])
            filtered_indices = sample.get('filtered_channel_indices')
            
            # Get channel labels from stream if available (use cache)
            if stream_name not in self._channel_label_cache:
                channel_labels = {}
                try:
                    # First try: use pre-extracted channel_labels from stream_info
                    if 'channel_labels' in stream_info and stream_info['channel_labels']:
                        channel_labels = stream_info['channel_labels']
                    else:
                        # Fallback: try to get channel info from inlet_info stored in recorder
                        inlet_info = stream_info.get('inlet_info')
                        if inlet_info:
                            desc = inlet_info.desc()
                            chns = desc.child("channels")
                            if chns:
                                # Use next_sibling() method to iterate through channels (as per pylsl example)
                                ch = chns.child("channel")
                                i = 0
                                while ch:
                                    try:
                                        label = ch.child_value("label") or f"Ch {i}"
                                    except:
                                        try:
                                            label_elem = ch.child("label")
                                            label = label_elem.value() if label_elem else f"Ch {i}"
                                        except:
                                            label = f"Ch {i}"
                                    channel_labels[i] = label
                                    
                                    # Move to next channel
                                    try:
                                        ch = ch.next_sibling()
                                    except:
                                        break
                                    i += 1
                        else:
                            # Fallback: try available streams
                            for stream in self.available_streams:
                                if stream.name() == stream_name:
                                    desc = stream.desc()
                                    chns = desc.child("channels")
                                    if chns:
                                        ch = chns.child("channel")
                                        i = 0
                                        while ch:
                                            try:
                                                label = ch.child_value("label") or f"Ch {i}"
                                            except:
                                                label = f"Ch {i}"
                                            channel_labels[i] = label
                                            try:
                                                ch = ch.next_sibling()
                                            except:
                                                break
                                            i += 1
                                    break
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Could not read channel labels for {stream_name}: {e}")
                
                # Cache the labels
                self._channel_label_cache[stream_name] = channel_labels
            else:
                channel_labels = self._channel_label_cache[stream_name]
            
            # Determine which channels to show based on filters
            if isinstance(data, list):
                # Get filter for this stream
                stream_filter = channel_filters.get(stream_name, [])
                
                # If filter exists and is not empty, only show filtered channels
                # Otherwise show all channels
                channels_to_show = range(len(data))
                if stream_filter:
                    channels_to_show = [ch_idx for ch_idx in stream_filter if 0 <= ch_idx < len(data)]
                
                for ch_idx in channels_to_show:
                    if ch_idx >= len(data):
                        continue
                    
                    value = data[ch_idx]
                    
                    # Get channel label
                    if ch_idx in channel_labels:
                        ch_label = channel_labels[ch_idx]
                    else:
                        ch_label = f"Ch {ch_idx}"
                    
                    channel_rows.append({
                        'time': relative_time,
                        'stream': stream_name,
                        'channel': ch_idx,
                        'label': ch_label,
                        'value': value
                    })
            else:
                # Single value (not a list) - show it
                channel_rows.append({
                    'time': relative_time,
                    'stream': stream_name,
                    'channel': 0,
                    'label': 'Value',
                    'value': data
                })
        
        # Limit to last 200 channel rows for performance
        channel_rows = channel_rows[-200:]
        
        self.data_table.setRowCount(len(channel_rows))
        
        for i, row_data in enumerate(channel_rows):
            self.data_table.setItem(i, 0, QTableWidgetItem(f"{row_data['time']:.3f}s"))
            self.data_table.setItem(i, 1, QTableWidgetItem(row_data['stream']))
            self.data_table.setItem(i, 2, QTableWidgetItem(str(row_data['channel'])))
            self.data_table.setItem(i, 3, QTableWidgetItem(row_data['label']))
            
            # Format value
            value = row_data['value']
            if isinstance(value, float):
                value_str = f"{value:.6f}"
            else:
                value_str = str(value)
            self.data_table.setItem(i, 4, QTableWidgetItem(value_str))
        
        # Scroll to bottom
        if channel_rows:
            self.data_table.scrollToBottom()
    
    def _save_config(self):
        """Save the configuration."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Update config from UI
        self._on_config_changed()
        
        # Read stream selections directly from checkboxes in streams table
        selected_stream_names = []
        try:
            for i in range(self.streams_table.rowCount()):
                checkbox = self.streams_table.cellWidget(i, 0)
                if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                    stream_name_item = self.streams_table.item(i, 1)
                    if stream_name_item:
                        selected_stream_names.append(stream_name_item.text())
        except Exception as e:
            logger.warning(f"Error reading stream selections: {e}")
            # Fallback to selected_streams set
            selected_stream_names = list(self.selected_streams)
        
        # Update selected_streams set
        self.selected_streams = set(selected_stream_names)
        
        # Persist selected streams into additional_stream_filters so recording will include them
        try:
            self.current_config.additional_stream_filters = selected_stream_names
            
            # Also collect stream types from selected streams for type filtering
            selected_types = set()
            for stream in self.available_streams:
                if stream.name() in selected_stream_names:
                    selected_types.add(stream.type())
            self.current_config.additional_stream_type_filters = list(selected_types)
        except Exception as e:
            logger.warning(f"Error saving stream filters: {e}")
            # Fallback: leave as-is
            pass
        
        # Ensure stream_channel_filters is properly initialized
        if not hasattr(self.current_config, 'stream_channel_filters'):
            self.current_config.stream_channel_filters = {}
        
        # Read channel selections directly from checkboxes in channels table
        # This ensures we capture the current state, not just what was loaded
        try:
            channel_filters = {}
            for i in range(self.channels_table.rowCount()):
                stream_name_item = self.channels_table.item(i, 0)
                channel_index_item = self.channels_table.item(i, 1)
                checkbox = self.channels_table.cellWidget(i, 3)
                
                if stream_name_item and channel_index_item and checkbox and isinstance(checkbox, QCheckBox):
                    stream_name = stream_name_item.text()
                    try:
                        channel_index = int(channel_index_item.text())
                    except (ValueError, TypeError):
                        continue
                    
                    # Only process if checkbox is enabled (stream is selected)
                    if checkbox.isEnabled():
                        if stream_name not in channel_filters:
                            channel_filters[stream_name] = []
                        
                        if checkbox.isChecked():
                            if channel_index not in channel_filters[stream_name]:
                                channel_filters[stream_name].append(channel_index)
                        # Note: We don't remove unchecked channels here - we'll check if all are selected later
            # Now, for each stream, check if all channels are selected
            # If all channels are selected, set to empty list (empty = all channels)
            for stream_name in list(channel_filters.keys()):
                # Count total channels for this stream
                total_channels = sum(1 for i in range(self.channels_table.rowCount())
                                   if self.channels_table.item(i, 0) and 
                                   self.channels_table.item(i, 0).text() == stream_name)
                
                selected_count = len(channel_filters[stream_name])
                if selected_count == total_channels:
                    # All channels selected = empty list (record all)
                    channel_filters[stream_name] = []
                else:
                    # Sort for consistency
                    channel_filters[stream_name].sort()
            
            # Update config with current channel selections
            self.current_config.stream_channel_filters = channel_filters
        except Exception as e:
            logger.warning(f"Error reading channel selections: {e}", exc_info=True)
            # Keep existing channel_filters if reading fails
        
        # Log what we're saving for debugging
        logger.info(f"Saving config with stream_channel_filters: {self.current_config.stream_channel_filters}")
        logger.info(f"Saving config with additional_stream_filters: {self.current_config.additional_stream_filters}")
        
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

