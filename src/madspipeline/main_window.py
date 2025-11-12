"""
Main application window for MadsPipeline.
"""
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QDialog, QLineEdit, QTextEdit, QFormLayout, QMessageBox,
    QStackedWidget, QFrame, QScrollArea, QGridLayout,
    QSplitter, QGroupBox, QFileDialog, QComboBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QSlider, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QUrl, QPointF, QRectF
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QPen, QBrush, QPainter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel


class ConsoleLoggingWebPage(QWebEnginePage):
    """Custom QWebEnginePage that forwards JavaScript console messages to Python print."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def javaScriptConsoleMessage(self, level: int, message: str, line_number: int, source_id: str):
        """Override to capture JavaScript console messages.
        
        Args:
            level: Message level (0=Info, 1=Warning, 2=Error)
            message: Console message text
            line_number: Line number in source
            source_id: Source file/URL
        """
        level_names = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "JS-INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "JS-WARN",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "JS-ERROR"
        }
        level_name = level_names.get(level, "JS-UNKNOWN")
        
        # Format: [JS-LEVEL] source:line - message
        print(f"[{level_name}] {source_id}:{line_number} - {message}")
        
        # Call parent method to maintain default behavior
        super().javaScriptConsoleMessage(level, message, line_number, source_id)
import json

# Import local modules using absolute imports for direct execution
from .project_manager import ProjectManager
from .models import Project, Session, ProjectType
from .madsBridge import Bridge
from .lsl_integration import LSLBridgeStreamer, LSLMouseTrackingStreamer, LSLRecorder, LSL_AVAILABLE


class ProjectCreationDialog(QDialog):
    """Dialog for creating new projects."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.project_name = ""
        self.project_description = ""
        self.project_type = ProjectType.PICTURE_SLIDESHOW
        self.project_location = None
        self.project_config = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Form layout for project details
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter project name")
        form_layout.addRow("Project Name:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Enter project description")
        form_layout.addRow("Description:", self.description_edit)
        
        # Project type selection
        self.type_combo = QComboBox()
        self.type_combo.addItem("Picture Slideshow", ProjectType.PICTURE_SLIDESHOW)
        self.type_combo.addItem("Video", ProjectType.VIDEO)
        self.type_combo.addItem("Screen Recording", ProjectType.SCREEN_RECORDING)
        self.type_combo.addItem("Embedded Webpage", ProjectType.EMBEDDED_WEBPAGE)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addRow("Project Type:", self.type_combo)
        
        # Location selection
        location_layout = QHBoxLayout()
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Default location (Documents/MadsPipeline)")
        self.location_edit.setReadOnly(True)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_location)
        
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(self.browse_button)
        form_layout.addRow("Location:", location_layout)
        
        layout.addLayout(form_layout)
        
        # Note about configuration
        config_note = QLabel("Note: Project-specific settings can be configured after creation in the project view.")
        config_note.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        config_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(config_note)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.create_button = QPushButton("Create Project")
        self.create_button.clicked.connect(self._create_project)
        self.create_button.setDefault(True)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _on_type_changed(self):
        """Handle project type change."""
        self.project_type = self.type_combo.currentData()
    
    def _browse_location(self):
        """Browse for custom project location."""
        location = QFileDialog.getExistingDirectory(
            self, "Select Project Location", str(Path.home())
        )
        if location:
            self.project_location = Path(location)
            self.location_edit.setText(str(self.project_location))
    
    def _create_project(self):
        """Create the project and accept dialog."""
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Project name is required.")
            return
        
        # Set empty configuration (will be configured later in project view)
        self.project_config = {}
        
        self.project_name = name
        self.project_description = description
        
        self.accept()
    
    def _collect_type_config(self) -> Dict[str, Any]:
        """Collect type-specific configuration from UI."""
        # Return empty config for new projects - configuration happens in project view
        return {}


class EditProjectDialog(QDialog):
    """Dialog for editing existing projects."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(f"Edit Project: {project.name}")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.project_name = project.name
        self.project_description = project.description
        self.project_type = project.project_type
        self.project_config = {}
        
        self._setup_ui()
        self._load_current_config()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Form layout for project details
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.project_name)
        self.name_edit.setPlaceholderText("Enter project name")
        form_layout.addRow("Project Name:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setText(self.project_description)
        self.description_edit.setPlaceholderText("Enter project description")
        form_layout.addRow("Description:", self.description_edit)
        
        # Project type (read-only, can't change after creation)
        type_label = QLabel(self.project_type.value.replace('_', ' ').title())
        type_label.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addRow("Project Type:", type_label)
        
        layout.addLayout(form_layout)
        
        # Type-specific configuration
        self.config_widget = QWidget()
        self.config_layout = QFormLayout()
        self.config_widget.setLayout(self.config_layout)
        layout.addWidget(self.config_widget)
        
        # Set up configuration UI based on current project type
        self._setup_type_config_ui()
        
        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(self._save_project)
        self.save_button.setDefault(True)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _setup_type_config_ui(self):
        """Set up type-specific configuration UI."""
        # Clear existing config UI
        while self.config_layout.rowCount() > 0:
            self.config_layout.removeRow(0)
        
        if self.project_type == ProjectType.PICTURE_SLIDESHOW:
            self._setup_picture_slideshow_config()
        elif self.project_type == ProjectType.VIDEO:
            self._setup_video_config()
        elif self.project_type == ProjectType.SCREEN_RECORDING:
            self._setup_screen_recording_config()
        elif self.project_type == ProjectType.EMBEDDED_WEBPAGE:
            self._setup_embedded_webpage_config()
    
    def _setup_picture_slideshow_config(self):
        """Set up picture slideshow configuration UI."""
        self.slide_duration_spin = QDoubleSpinBox()
        self.slide_duration_spin.setRange(0.5, 60.0)
        self.slide_duration_spin.setValue(5.0)
        self.slide_duration_spin.setSuffix(" seconds")
        self.config_layout.addRow("Slide Duration:", self.slide_duration_spin)
        
        self.auto_play_check = QCheckBox()
        self.auto_play_check.setChecked(True)
        self.config_layout.addRow("Auto-play:", self.auto_play_check)
        
        self.manual_nav_check = QCheckBox()
        self.manual_nav_check.setChecked(False)
        self.config_layout.addRow("Manual Navigation:", self.manual_nav_check)
        
        self.transition_combo = QComboBox()
        self.transition_combo.addItems(["fade", "slide", "none"])
        self.config_layout.addRow("Transition Effect:", self.transition_combo)
        
        # Add image management
        self.images_label = QLabel("No images selected")
        self.images_label.setStyleSheet("color: gray; font-style: italic;")
        self.add_images_button = QPushButton("Add Images...")
        self.add_images_button.clicked.connect(self._add_images)
        
        images_layout = QHBoxLayout()
        images_layout.addWidget(self.images_label)
        images_layout.addWidget(self.add_images_button)
        self.config_layout.addRow("Images:", images_layout)
    
    def _setup_video_config(self):
        """Set up video configuration UI."""
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Select video file...")
        self.video_path_edit.setReadOnly(True)
        
        self.video_browse_button = QPushButton("Browse...")
        self.video_browse_button.clicked.connect(self._browse_video)
        
        video_path_layout = QHBoxLayout()
        video_path_layout.addWidget(self.video_path_edit)
        video_path_layout.addWidget(self.video_browse_button)
        self.config_layout.addRow("Video File:", video_path_layout)
        
        self.video_auto_play_check = QCheckBox()
        self.video_auto_play_check.setChecked(True)
        self.config_layout.addRow("Auto-play:", self.video_auto_play_check)
        
        self.video_loop_check = QCheckBox()
        self.video_loop_check.setChecked(False)
        self.config_layout.addRow("Loop:", self.video_loop_check)
    
    def _setup_screen_recording_config(self):
        """Set up screen recording configuration UI."""
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["low", "medium", "high"])
        self.quality_combo.setCurrentText("high")
        self.config_layout.addRow("Recording Quality:", self.quality_combo)
        
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(15, 60)
        self.fps_spin.setValue(30)
        self.fps_spin.setSuffix(" FPS")
        self.config_layout.addRow("Frame Rate:", self.fps_spin)
        
        self.audio_check = QCheckBox()
        self.audio_check.setChecked(False)
        self.config_layout.addRow("Include Audio:", self.audio_check)
        
        self.mouse_tracking_check = QCheckBox()
        self.mouse_tracking_check.setChecked(True)
        self.config_layout.addRow("Mouse Tracking:", self.mouse_tracking_check)
    
    def _setup_embedded_webpage_config(self):
        """Set up embedded webpage configuration UI."""
        self.webpage_url_edit = QLineEdit()
        self.webpage_url_edit.setPlaceholderText("https://example.com")
        self.config_layout.addRow("Webpage URL:", self.webpage_url_edit)
        
        self.local_html_edit = QLineEdit()
        self.local_html_edit.setPlaceholderText("Or select local HTML file...")
        self.local_html_edit.setReadOnly(True)
        
        self.html_browse_button = QPushButton("Browse...")
        self.html_browse_button.clicked.connect(self._browse_html)
        
        html_layout = QHBoxLayout()
        html_layout.addWidget(self.local_html_edit)
        html_layout.addWidget(self.html_browse_button)
        self.config_layout.addRow("Local HTML:", html_layout)
        
        self.marker_api_check = QCheckBox()
        self.marker_api_check.setChecked(True)
        self.config_layout.addRow("Enable Marker API:", self.marker_api_check)
        
        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(True)
        self.config_layout.addRow("Fullscreen:", self.fullscreen_check)
    
    def _add_images(self):
        """Add images to the slideshow."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_paths:
            # Update the images label
            if len(file_paths) == 1:
                self.images_label.setText(f"1 image selected")
            else:
                self.images_label.setText(f"{len(file_paths)} images selected")
            self.images_label.setStyleSheet("color: black; font-style: normal;")
    
    def _browse_video(self):
        """Browse for video file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)
    
    def _browse_html(self):
        """Browse for HTML file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select HTML File", "", "HTML Files (*.html *.htm)"
        )
        if file_path:
            self.local_html_edit.setText(file_path)
    
    def _load_current_config(self):
        """Load current project configuration into UI."""
        if self.project.picture_slideshow_config:
            config = self.project.picture_slideshow_config
            self.slide_duration_spin.setValue(config.slide_duration)
            self.auto_play_check.setChecked(config.auto_play)
            self.manual_nav_check.setChecked(config.manual_navigation)
            self.transition_combo.setCurrentText(config.transition_effect)
            if config.images:
                if len(config.images) == 1:
                    self.images_label.setText(f"1 image selected")
                else:
                    self.images_label.setText(f"{len(config.images)} images selected")
                self.images_label.setStyleSheet("color: black; font-style: normal;")
        elif self.project.video_config:
            config = self.project.video_config
            if config.video_path:
                self.video_path_edit.setText(str(config.video_path))
            self.video_auto_play_check.setChecked(config.auto_play)
            self.video_loop_check.setChecked(config.loop)
        elif self.project.screen_recording_config:
            config = self.project.screen_recording_config
            self.quality_combo.setCurrentText(config.recording_quality)
            self.fps_spin.setValue(config.fps)
            self.audio_check.setChecked(config.include_audio)
            self.mouse_tracking_check.setChecked(config.mouse_tracking)
        elif self.project.embedded_webpage_config:
            config = self.project.embedded_webpage_config
            if config.webpage_url:
                self.webpage_url_edit.setText(config.webpage_url)
            if config.local_html_path:
                self.local_html_edit.setText(str(config.local_html_path))
            self.marker_api_check.setChecked(config.enable_marker_api)
            self.fullscreen_check.setChecked(config.fullscreen)
    
    def _save_project(self):
        """Save the project changes and accept dialog."""
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Project name is required.")
            return
        
        # Collect type-specific configuration
        self.project_config = self._collect_type_config()
        
        self.project_name = name
        self.project_description = description
        
        self.accept()
    
    def _collect_type_config(self) -> Dict[str, Any]:
        """Collect type-specific configuration from UI."""
        config = {}
        
        if self.project_type == ProjectType.PICTURE_SLIDESHOW:
            config.update({
                'slide_duration': self.slide_duration_spin.value(),
                'auto_play': self.auto_play_check.isChecked(),
                'manual_navigation': self.manual_nav_check.isChecked(),
                'transition_effect': self.transition_combo.currentText()
            })
        elif self.project_type == ProjectType.VIDEO:
            config.update({
                'video_path': self.video_path_edit.text() if self.video_path_edit.text() else None,
                'auto_play': self.video_auto_play_check.isChecked(),
                'loop': self.video_loop_check.isChecked()
            })
        elif self.project_type == ProjectType.SCREEN_RECORDING:
            config.update({
                'recording_quality': self.quality_combo.currentText(),
                'fps': self.fps_spin.value(),
                'include_audio': self.audio_check.isChecked(),
                'mouse_tracking': self.mouse_tracking_check.isChecked()
            })
        elif self.project_type == ProjectType.EMBEDDED_WEBPAGE:
            config.update({
                'webpage_url': self.webpage_url_edit.text() if self.webpage_url_edit.text() else None,
                'local_html_path': self.local_html_edit.text() if self.local_html_edit.text() else None,
                'enable_marker_api': self.marker_api_check.isChecked(),
                'fullscreen': self.fullscreen_check.isChecked()
            })
        
        return config


class ProjectSelectionWidget(QWidget):
    """Widget for project selection and management."""
    
    project_selected = Signal(Project)
    project_created = Signal(Project)
    
    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self._setup_ui()
        self._refresh_projects()
    
    def _setup_ui(self):
        """Set up the project selection UI."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("MadsPipeline - Project Selection")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Project list
        list_group = QGroupBox("Available Projects")
        list_layout = QVBoxLayout()
        
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self._on_project_selected)
        
        # Set icon size to make icons larger (default is usually 16x16, so 48x48 is about 3x)
        self.project_list.setIconSize(QSize(48, 48))
        
        list_layout.addWidget(self.project_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.new_project_button = QPushButton("New Project")
        self.new_project_button.clicked.connect(self._create_new_project)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_projects)
        
        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.clicked.connect(self._open_selected_project)
        self.open_project_button.setEnabled(False)
        
        button_layout.addWidget(self.new_project_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.open_project_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.project_list.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.setLayout(layout)
    
    def _get_project_type_icon(self, project_type: ProjectType) -> QIcon:
        """Get the appropriate icon for a project type."""
        # Try multiple path resolution methods
        possible_paths = [
            Path(__file__).parent.parent / "icons",  # From main_window.py
            Path.cwd() / "src" / "icons",           # From current working directory
            Path(__file__).parent / "icons"         # From madspipeline directory
        ]
        
        icon_mapping = {
            ProjectType.PICTURE_SLIDESHOW: "picture_slideshow.svg",
            ProjectType.VIDEO: "video.svg", 
            ProjectType.SCREEN_RECORDING: "screen_recording.svg",
            ProjectType.EMBEDDED_WEBPAGE: "embedded_webpage_fixed.svg"
        }
        
        icon_filename = icon_mapping.get(project_type)
        if icon_filename:
            # Try each possible path
            for icons_dir in possible_paths:
                icon_path = icons_dir / icon_filename
                if icon_path.exists():
                    return QIcon(str(icon_path))
        
        # Return empty icon if file doesn't exist
        return QIcon()

    def _refresh_projects(self):
        """Refresh the project list."""
        self.project_list.clear()
        
        try:
            projects = self.project_manager.list_projects()
            for project in projects:
                item = QListWidgetItem()
                project_type_display = project.project_type.value.replace('_', ' ').title()
                item.setText(f"{project.name}\n{project.description}\nType: {project_type_display}")
                item.setData(Qt.ItemDataRole.UserRole, project)
                
                # Set the appropriate icon
                item.setIcon(self._get_project_type_icon(project.project_type))
                
                self.project_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load projects: {e}")
    
    def _create_new_project(self):
        """Create a new project."""
        dialog = ProjectCreationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                project = self.project_manager.create_project(
                    dialog.project_name,
                    dialog.project_description,
                    dialog.project_type,
                    dialog.project_config,
                    dialog.project_location
                )
                self.project_created.emit(project)
                self._refresh_projects()
                QMessageBox.information(
                    self, "Success", f"Project '{project.name}' created successfully!"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create project: {e}")
    
    def _on_selection_changed(self):
        """Handle project selection change."""
        has_selection = len(self.project_list.selectedItems()) > 0
        self.open_project_button.setEnabled(has_selection)
    
    def _on_project_selected(self, item):
        """Handle project double-click."""
        project = item.data(Qt.ItemDataRole.UserRole)
        self.project_selected.emit(project)
    
    def _open_selected_project(self):
        """Open the selected project."""
        items = self.project_list.selectedItems()
        if items:
            project = items[0].data(Qt.ItemDataRole.UserRole)
            self.project_selected.emit(project)


class ProjectDashboardWidget(QWidget):
    """Dashboard widget for managing project operations."""
    
    new_session_requested = Signal()
    debug_session_requested = Signal()
    edit_project_requested = Signal()
    review_sessions_requested = Signal()
    export_data_requested = Signal()
    back_to_projects_requested = Signal()
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the project dashboard UI."""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        
        back_button = QPushButton("← Back to Projects")
        back_button.clicked.connect(self.back_to_projects_requested.emit)
        
        project_title = QLabel(f"Project: {self.project.name}")
        project_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        
        header_layout.addWidget(back_button)
        header_layout.addWidget(project_title)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout()
        
        info_layout.addRow("Description:", QLabel(self.project.description))
        info_layout.addRow("Type:", QLabel(self.project.project_type.value.replace('_', ' ').title()))
        info_layout.addRow("Created:", QLabel(self.project.created_date.strftime("%Y-%m-%d %H:%M")))
        info_layout.addRow("Modified:", QLabel(self.project.modified_date.strftime("%Y-%m-%d %H:%M")))
        
        # Store reference to sessions count label for easy updating
        self.sessions_count_label = QLabel(str(len(self.project.sessions)))
        info_layout.addRow("Sessions:", self.sessions_count_label)
        
        info_layout.addRow("Location:", QLabel(str(self.project.project_path)))
        
        # Add type-specific configuration info
        if self.project.picture_slideshow_config:
            config = self.project.picture_slideshow_config
            info_layout.addRow("Slide Duration:", QLabel(f"{config.slide_duration}s"))
            info_layout.addRow("Auto-play:", QLabel("Yes" if config.auto_play else "No"))
            info_layout.addRow("Manual Navigation:", QLabel("Yes" if config.manual_navigation else "No"))
        elif self.project.video_config:
            config = self.project.video_config
            if config.video_path:
                info_layout.addRow("Video File:", QLabel(config.video_path.name))
            info_layout.addRow("Auto-play:", QLabel("Yes" if config.auto_play else "No"))
            info_layout.addRow("Loop:", QLabel("Yes" if config.loop else "No"))
        elif self.project.screen_recording_config:
            config = self.project.screen_recording_config
            info_layout.addRow("Quality:", QLabel(config.recording_quality.title()))
            info_layout.addRow("FPS:", QLabel(str(config.fps)))
            info_layout.addRow("Mouse Tracking:", QLabel("Yes" if config.mouse_tracking else "No"))
        elif self.project.embedded_webpage_config:
            config = self.project.embedded_webpage_config
            if config.webpage_url:
                info_layout.addRow("URL:", QLabel(config.webpage_url))
            elif config.local_html_path:
                info_layout.addRow("Local HTML:", QLabel(config.local_html_path.name))
            info_layout.addRow("Marker API:", QLabel("Enabled" if config.enable_marker_api else "Disabled"))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Project management buttons
        project_buttons_layout = QHBoxLayout()
        
        self.edit_project_button = QPushButton("Edit Project")
        self.edit_project_button.clicked.connect(self.edit_project_requested.emit)
        
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setToolTip("Refresh project data and sessions")
        self.refresh_button.clicked.connect(self._manual_refresh)
        
        project_buttons_layout.addWidget(self.edit_project_button)
        project_buttons_layout.addWidget(self.refresh_button)
        project_buttons_layout.addStretch()
        
        layout.addLayout(project_buttons_layout)
        
        # Main actions
        actions_group = QGroupBox("Project Actions")
        actions_layout = QGridLayout()
        
        # Create large action buttons
        self.new_session_button = QPushButton("Start New Session")
        self.new_session_button.setMinimumHeight(80)
        self.new_session_button.clicked.connect(self.new_session_requested.emit)
        
        self.debug_session_button = QPushButton("Debug Session")
        self.debug_session_button.setMinimumHeight(80)
        self.debug_session_button.clicked.connect(self.debug_session_requested.emit)
        
        self.review_sessions_button = QPushButton("Review Sessions")
        self.review_sessions_button.setMinimumHeight(80)
        self.review_sessions_button.clicked.connect(self.review_sessions_requested.emit)
        
        self.export_button = QPushButton("Export Dataset")
        self.export_button.setMinimumHeight(80)
        self.export_button.clicked.connect(self.export_data_requested.emit)
        
        actions_layout.addWidget(self.new_session_button, 0, 0)
        actions_layout.addWidget(self.debug_session_button, 0, 1)
        actions_layout.addWidget(self.review_sessions_button, 1, 0)
        actions_layout.addWidget(self.export_button, 1, 1)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # Recent sessions
        if self.project.sessions:
            sessions_group = QGroupBox("Recent Sessions")
            sessions_layout = QVBoxLayout()
            
            # Create a custom widget for each session with delete button
            for session_id in self.project.sessions[-5:]:  # Show last 5 sessions
                session_widget = self._create_session_widget(session_id)
                sessions_layout.addWidget(session_widget)
            
            sessions_group.setLayout(sessions_layout)
            layout.addWidget(sessions_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def refresh_project_data(self, project: Project):
        """Refresh the dashboard with updated project data.
        
        Args:
            project: Updated project instance
        """
        self.project = project
        self._refresh_project_info()
        self._refresh_sessions()
    
    def _refresh_project_info(self):
        """Refresh the project information display."""
        # Update sessions count using stored reference
        if hasattr(self, 'sessions_count_label'):
            self.sessions_count_label.setText(str(len(self.project.sessions)))
    
    def _create_session_widget(self, session_id: str) -> QWidget:
        """Create a widget for displaying a session with delete button.
        
        Args:
            session_id: Session ID to display
            
        Returns:
            Widget containing session info and delete button
        """
        session_widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Session info
        session_info = QLabel(f"Session: {session_id}")
        session_info.setStyleSheet("QLabel { padding: 5px; }")
        
        # Delete button
        delete_button = QPushButton("🗑️")
        delete_button.setToolTip("Delete this session")
        delete_button.setMaximumSize(30, 30)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        delete_button.clicked.connect(lambda: self._delete_session(session_id))
        
        layout.addWidget(session_info)
        layout.addStretch()
        layout.addWidget(delete_button)
        
        session_widget.setLayout(layout)
        return session_widget
    
    def _delete_session(self, session_id: str):
        """Handle session deletion with confirmation dialog.
        
        Args:
            session_id: Session ID to delete
        """
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Session Deletion",
            f"Are you sure you want to delete session {session_id}?\n\n"
            "This will permanently remove all session data including:\n"
            "• Session metadata\n"
            "• Tracking data\n"
            "• Recordings\n"
            "• Markers\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get the project manager from the parent window
                parent_window = self.parent()
                while parent_window and not hasattr(parent_window, 'project_manager'):
                    parent_window = parent_window.parent()
                
                if parent_window and hasattr(parent_window, 'project_manager'):
                    project_manager = parent_window.project_manager
                    
                    # Delete the session
                    if project_manager.delete_session(self.project, session_id):
                        QMessageBox.information(
                            self,
                            "Session Deleted",
                            f"Session {session_id} has been deleted successfully."
                        )
                        
                        # Refresh the dashboard to show updated session list
                        self._refresh_sessions()
                    else:
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Failed to delete session {session_id}."
                        )
                else:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Could not access project manager to delete session."
                    )
                    
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"An error occurred while deleting the session: {e}"
                )
    
    def _refresh_sessions(self):
        """Refresh the sessions display."""
        # Find the sessions group
        sessions_group = None
        for i in range(self.layout().count()):
            child = self.layout().itemAt(i).widget()
            if isinstance(child, QGroupBox) and child.title() == "Recent Sessions":
                sessions_group = child
                break
        
        if sessions_group:
            if self.project.sessions:
                # Sessions group exists and there are sessions, update its content
                sessions_layout = sessions_group.layout()
                
                # Clear existing session widgets
                for i in reversed(range(sessions_layout.count())):
                    child = sessions_layout.itemAt(i).widget()
                    if child:
                        child.deleteLater()
                
                # Add new session widgets
                for session_id in self.project.sessions[-5:]:  # Show last 5 sessions
                    session_widget = self._create_session_widget(session_id)
                    sessions_layout.addWidget(session_widget)
            else:
                # Sessions group exists but no sessions, remove it
                sessions_group.deleteLater()
        else:
            # Sessions group doesn't exist, create it if there are sessions
            if self.project.sessions:
                self._create_sessions_group()
    
    def _create_sessions_group(self):
        """Create the sessions group and add it to the layout."""
        # Find the position to insert the sessions group (after actions group, before stretch)
        insert_position = -1  # Default to end, before stretch
        for i in range(self.layout().count()):
            child = self.layout().itemAt(i).widget()
            if isinstance(child, QGroupBox) and child.title() == "Project Actions":
                insert_position = i + 1
                break
        
        # Create sessions group
        sessions_group = QGroupBox("Recent Sessions")
        sessions_layout = QVBoxLayout()
        
        # Create session widgets
        for session_id in self.project.sessions[-5:]:  # Show last 5 sessions
            session_widget = self._create_session_widget(session_id)
            sessions_layout.addWidget(session_widget)
        
        sessions_group.setLayout(sessions_layout)
        
        # Insert at the correct position
        if insert_position >= 0:
            self.layout().insertWidget(insert_position, sessions_group)
        else:
            # Fallback: add before stretch
            self.layout().insertWidget(self.layout().count() - 1, sessions_group)
    
    def _manual_refresh(self):
        """Manually refresh the project dashboard."""
        try:
            # Get the project manager from the parent window to reload project data
            parent_window = self.parent()
            while parent_window and not hasattr(parent_window, 'project_manager'):
                parent_window = parent_window.parent()
            
            if parent_window and hasattr(parent_window, 'project_manager'):
                project_manager = parent_window.project_manager
                
                # Reload the project data
                reloaded_project = project_manager.load_project(self.project.project_path)
                
                # Refresh the dashboard with updated data
                self.refresh_project_data(reloaded_project)
                
                # Update the parent window's current project reference
                if hasattr(parent_window, 'current_project'):
                    parent_window.current_project = reloaded_project
                
                QMessageBox.information(
                    self,
                    "Refresh Complete",
                    "Project data has been refreshed successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Could not access project manager to refresh data."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while refreshing: {e}"
            )


class DebugSessionWindow(QWidget):
    """Debug session window for real-time tracking visualization."""
    
    session_ended = Signal()
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.is_recording = False
        self.tracking_timer = QTimer()
        self.tracking_timer.timeout.connect(self._update_tracking_data)
        
        # Tracking data storage
        self.mouse_positions = []
        self.mouse_clicks = []
        self.session_start_time = None
        
        self._setup_ui()
        self._setup_tracking()
    
    def _setup_ui(self):
        """Set up the debug session UI."""
        self.setWindowTitle(f"Debug Session - {self.project.name}")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout()
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        self.back_button = QPushButton("← Back to Project")
        self.back_button.clicked.connect(self.session_ended.emit)
        
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self._toggle_recording)
        self.record_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.clear_button = QPushButton("Clear Data")
        self.clear_button.clicked.connect(self._clear_tracking_data)
        
        header_layout.addWidget(self.back_button)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.record_button)
        
        layout.addLayout(header_layout)
        
        # Main content area
        content_layout = QHBoxLayout()
        
        # Left panel - Tracking visualization
        tracking_group = QGroupBox("Real-time Tracking")
        tracking_layout = QVBoxLayout()
        
        # Mouse position display
        self.mouse_pos_label = QLabel("Mouse: (0, 0)")
        self.mouse_pos_label.setFont(QFont("Arial", 12))
        tracking_layout.addWidget(self.mouse_pos_label)
        
        # Mouse movement visualization
        self.mouse_canvas = QWidget()
        self.mouse_canvas.setMinimumSize(400, 300)
        self.mouse_canvas.setStyleSheet("QWidget { background-color: #f0f0f0; border: 1px solid #ccc; }")
        self.mouse_canvas.mouseMoveEvent = self._on_mouse_move
        self.mouse_canvas.paintEvent = self._on_paint
        tracking_layout.addWidget(self.mouse_canvas)
        
        # Tracking statistics
        stats_layout = QFormLayout()
        self.total_moves_label = QLabel("0")
        self.total_clicks_label = QLabel("0")
        self.session_time_label = QLabel("00:00")
        
        stats_layout.addRow("Total Movements:", self.total_moves_label)
        stats_layout.addRow("Total Clicks:", self.total_clicks_label)
        stats_layout.addRow("Session Time:", self.session_time_label)
        tracking_layout.addLayout(stats_layout)
        
        tracking_group.setLayout(tracking_layout)
        content_layout.addWidget(tracking_group)
        
        # Right panel - Data and controls
        right_panel_layout = QVBoxLayout()
        
        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout()
        
        info_layout.addRow("Type:", QLabel(self.project.project_type.value.replace('_', ' ').title()))
        info_layout.addRow("Description:", QLabel(self.project.description))
        
        # Add type-specific info
        if self.project.picture_slideshow_config:
            config = self.project.picture_slideshow_config
            info_layout.addRow("Slide Duration:", QLabel(f"{config.slide_duration}s"))
            info_layout.addRow("Auto-play:", QLabel("Yes" if config.auto_play else "No"))
        elif self.project.video_config:
            config = self.project.video_config
            info_layout.addRow("Video File:", QLabel(config.video_path.name if config.video_path else "None"))
            info_layout.addRow("Loop:", QLabel("Yes" if config.loop else "No"))
        elif self.project.screen_recording_config:
            config = self.project.screen_recording_config
            info_layout.addRow("Quality:", QLabel(config.recording_quality.title()))
            info_layout.addRow("FPS:", QLabel(str(config.fps)))
        elif self.project.embedded_webpage_config:
            config = self.project.embedded_webpage_config
            if config.webpage_url:
                info_layout.addRow("URL:", QLabel(config.webpage_url))
            elif config.local_html_path:
                info_layout.addRow("Local HTML:", QLabel(config.local_html_path.name))
        
        info_group.setLayout(info_layout)
        right_panel_layout.addWidget(info_group)
        
        # Debug controls
        controls_group = QGroupBox("Debug Controls")
        controls_layout = QVBoxLayout()
        
        self.fullscreen_check = QCheckBox("Fullscreen Mode")
        self.fullscreen_check.setChecked(True)
        controls_layout.addWidget(self.fullscreen_check)
        
        self.overlay_check = QCheckBox("Show Tracking Overlay")
        self.overlay_check.setChecked(True)
        controls_layout.addWidget(self.overlay_check)
        
        self.heatmap_check = QCheckBox("Show Heatmap")
        self.heatmap_check.setChecked(False)
        controls_layout.addWidget(self.heatmap_check)
        
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        right_panel_layout.addWidget(controls_group)
        
        # Live data feed
        data_group = QGroupBox("Live Data Feed")
        data_layout = QVBoxLayout()
        
        self.data_text = QTextEdit()
        self.data_text.setMaximumHeight(150)
        self.data_text.setReadOnly(True)
        self.data_text.setFont(QFont("Consolas", 9))
        data_layout.addWidget(self.data_text)
        
        data_group.setLayout(data_layout)
        right_panel_layout.addWidget(data_group)
        
        content_layout.addLayout(right_panel_layout)
        layout.addLayout(content_layout)
        
        self.setLayout(layout)
    
    def _setup_tracking(self):
        """Set up mouse tracking."""
        # Start tracking timer for updates
        self.tracking_timer.start(50)  # 20 FPS updates
        
        # Set up session start time
        from datetime import datetime
        self.session_start_time = datetime.now()
    
    def _toggle_recording(self):
        """Toggle recording state."""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording tracking data."""
        self.is_recording = True
        self.record_button.setText("Stop Recording")
        self.record_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        
        # Add start marker
        self._add_data_entry("Recording started")
    
    def _stop_recording(self):
        """Stop recording tracking data."""
        self.is_recording = False
        self.record_button.setText("Start Recording")
        self.record_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        # Add stop marker
        self._add_data_entry("Recording stopped")
    
    def _clear_tracking_data(self):
        """Clear all tracking data."""
        self.mouse_positions.clear()
        self.mouse_clicks.clear()
        self.session_start_time = datetime.now()
        self.total_moves_label.setText("0")
        self.total_clicks_label.setText("0")
        self.data_text.clear()
        self.mouse_canvas.update()
        
        self._add_data_entry("Data cleared")
    
    def _on_mouse_move(self, event):
        """Handle mouse movement on the canvas."""
        if self.is_recording:
            pos = (event.pos().x(), event.pos().y())
            self.mouse_positions.append(pos)
            self.mouse_pos_label.setText(f"Mouse: ({pos[0]}, {pos[1]})")
            self.total_moves_label.setText(str(len(self.mouse_positions)))
    
    def _on_paint(self, event):
        """Paint the mouse tracking visualization."""
        from PySide6.QtGui import QPainter, QPen, QColor
        
        painter = QPainter(self.mouse_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background grid
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        for x in range(0, self.mouse_canvas.width(), 50):
            painter.drawLine(x, 0, x, self.mouse_canvas.height())
        for y in range(0, self.mouse_canvas.height(), 50):
            painter.drawLine(0, y, self.mouse_canvas.width(), y)
        
        # Draw mouse movement trail
        if len(self.mouse_positions) > 1:
            painter.setPen(QPen(QColor(0, 150, 255), 2))
            for i in range(1, len(self.mouse_positions)):
                prev_pos = self.mouse_positions[i-1]
                curr_pos = self.mouse_positions[i]
                painter.drawLine(prev_pos[0], prev_pos[1], curr_pos[0], curr_pos[1])
        
        # Draw mouse clicks
        painter.setPen(QPen(QColor(255, 0, 0), 4))
        for click_pos in self.mouse_clicks:
            painter.drawEllipse(click_pos[0] - 3, click_pos[1] - 3, 6, 6)
        
        # Draw current mouse position
        if self.mouse_positions:
            current_pos = self.mouse_positions[-1]
            painter.setPen(QPen(QColor(0, 255, 0), 6))
            painter.drawEllipse(current_pos[0] - 4, current_pos[1] - 4, 8, 8)
    
    def _update_tracking_data(self):
        """Update tracking data display."""
        if self.session_start_time:
            elapsed = datetime.now() - self.session_start_time
            minutes = int(elapsed.total_seconds() // 60)
            seconds = int(elapsed.total_seconds() % 60)
            self.session_time_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def _add_data_entry(self, message: str):
        """Add a data entry to the live feed."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.data_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.data_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def mousePressEvent(self, event):
        """Handle mouse clicks globally."""
        if self.is_recording:
            pos = (event.pos().x(), event.pos().y())
            self.mouse_clicks.append(pos)
            self.total_clicks_label.setText(str(len(self.mouse_clicks)))
            
            button = "Left" if event.button() == Qt.MouseButton.LeftButton else "Right" if event.button() == Qt.MouseButton.RightButton else "Middle"
            self._add_data_entry(f"Mouse {button} click at ({pos[0]}, {pos[1]})")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.tracking_timer.stop()
        event.accept()


class EmbeddedWebpageSessionWindow(QMainWindow):
    """Window for running embedded webpage sessions."""
    
    session_ended = Signal(str)  # Emits session_id when session ends
    
    def __init__(self, project: Project, session: Session, parent=None):
        super().__init__(parent)
        self.project = project
        self.session = session
        self.session_start_time = datetime.now()
        self.tracking_data = []
        
        # LSL integration components
        self.bridge: Optional[Bridge] = None
        self.channel: Optional[QWebChannel] = None
        self.lsl_streamer: Optional[LSLBridgeStreamer] = None
        self.lsl_mouse_streamer: Optional[LSLMouseTrackingStreamer] = None
        self.lsl_recorder: Optional[LSLRecorder] = None
        self.lsl_timer: Optional[QTimer] = None
        
        # Flag to prevent double execution of _end_session
        self._session_ending = False
        
        self.setWindowTitle(f"Session: {session.name} - {project.name}")
        self.setMinimumSize(1200, 800)
        
        # Ensure window appears in taskbar and is visible
        # Set window flags before showing
        self.setWindowFlags(
            Qt.WindowType.Window |  # Standard window
            Qt.WindowType.WindowMinimizeButtonHint |  # Minimize button
            Qt.WindowType.WindowMaximizeButtonHint |  # Maximize button
            Qt.WindowType.WindowCloseButtonHint  # Close button
        )
        
        # Ensure window is not deleted when closed (we handle cleanup ourselves)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        # Set up the UI
        self._setup_ui()
        
        # Set up bridge and QWebChannel
        self._setup_bridge()
        
        # Load the webpage
        self._load_webpage()
        
        # Set up tracking
        self._setup_tracking()
    
    def _setup_ui(self):
        """Set up the session window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Header with session info and controls
        header_layout = QHBoxLayout()
        
        # Session info
        info_label = QLabel(f"Session: {self.session.name}")
        info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(info_label)
        
        header_layout.addStretch()
        
        # Session controls
        self.end_session_button = QPushButton("End Session")
        self.end_session_button.clicked.connect(self._end_session)
        self.end_session_button.setStyleSheet("QPushButton { background-color: #dc3545; color: white; padding: 8px 16px; }")
        
        header_layout.addWidget(self.end_session_button)
        
        layout.addLayout(header_layout)
        
        # Webpage display area
        self.web_view = QWebEngineView()
        
        # Set custom page that forwards console messages to Python
        self.web_view.setPage(ConsoleLoggingWebPage(self.web_view))
        
        layout.addWidget(self.web_view)
        
        # Configure web view settings for media playback
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # Enable autoplay for media (disable user gesture requirement)
        # Try multiple attribute names as they may vary by Qt version
        try:
            # Try the standard attribute name
            settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        except (AttributeError, TypeError):
            # If that doesn't work, try alternative approaches
            try:
                # Some versions use different attribute names
                if hasattr(QWebEngineSettings.WebAttribute, 'PlaybackRequiresUserGesture'):
                    settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            except (AttributeError, TypeError):
                print("Warning: Could not set PlaybackRequiresUserGesture - autoplay may require user interaction")
        
        # Enable media features (only if available in this Qt version)
        try:
            settings.setAttribute(QWebEngineSettings.WebAttribute.MediaSourceEnabled, True)
        except (AttributeError, TypeError):
            # MediaSourceEnabled might not be available in all Qt versions
            pass
        try:
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        except (AttributeError, TypeError):
            # WebGLEnabled might not be available in all Qt versions
            pass
        
        # Try to enable hardware acceleration and video codec support
        # Note: QtWebEngine may need to be built with proprietary codecs (H.264) for MP4 playback
        # If videos don't play, you may need to rebuild QtWebEngine with proprietary codecs enabled
        try:
            # Enable hardware acceleration if available
            if hasattr(QWebEngineSettings.WebAttribute, 'Accelerated2dCanvasEnabled'):
                settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        except (AttributeError, TypeError):
            pass
        
        # Set up persistent storage for better media handling
        try:
            profile = self.web_view.page().profile()
            # Enable persistent cookies and cache for better media loading
            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        except Exception as e:
            print(f"Warning: Could not configure web profile for media: {e}")
        
        # Also try setting via page profile (alternative method)
        try:
            profile = self.web_view.page().profile()
            # Some Qt versions require setting this on the profile
            if hasattr(profile, 'setHttpUserAgent'):
                # This ensures the page is properly configured
                pass
        except Exception:
            pass
        
        # Status bar
        status_msg = "Session started - tracking active"
        if LSL_AVAILABLE:
            status_msg += " - LSL enabled"
        else:
            status_msg += " - LSL unavailable"
        self.statusBar().showMessage(status_msg)
    
    def _load_webpage(self):
        """Load the webpage based on project configuration."""
        config = self.project.embedded_webpage_config
        
        if config.webpage_url:
            # Load external URL
            self.web_view.setUrl(QUrl(config.webpage_url))
            self.statusBar().showMessage(f"Loading external webpage: {config.webpage_url}")
        elif config.local_html_path and config.local_html_path.exists():
            # Load local HTML file
            local_url = QUrl.fromLocalFile(str(config.local_html_path))
            self.web_view.setUrl(local_url)
            self.statusBar().showMessage(f"Loading local webpage: {config.local_html_path}")
        else:
            # Show error page
            error_html = """
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>No Webpage Configured</h2>
                <p>Please configure a webpage URL or local HTML file in the project settings.</p>
            </body>
            </html>
            """
            self.web_view.setHtml(error_html)
            self.statusBar().showMessage("No webpage configured")
    
    def _setup_bridge(self):
        """Set up QWebChannel bridge for HTML-to-Python communication."""
        try:
            # Create bridge instance
            self.bridge = Bridge()
            
            # Create QWebChannel and register bridge
            self.channel = QWebChannel()
            self.channel.registerObject("bridge", self.bridge)
            
            # Set channel on web view
            self.web_view.page().setWebChannel(self.channel)
            
            # Connect bridge event signal to LSL streaming
            self.bridge.event_received.connect(self._handle_bridge_event)
            
            # Set up LSL streaming and recording
            if LSL_AVAILABLE:
                try:
                    # Create LSL streamer for bridge events
                    self.lsl_streamer = LSLBridgeStreamer(self.session.session_id)
                    
                    # Create LSL streamer for mouse tracking
                    self.lsl_mouse_streamer = LSLMouseTrackingStreamer(self.session.session_id)
                    
                    # Create LSL recorder for all streams (will capture bridge events, mouse tracking, and any other devices)
                    self.lsl_recorder = LSLRecorder(self.session.session_id)
                    self.lsl_recorder.start_recording(wait_time=2.0)
                    
                    # Start LSL recording timer (50 Hz = every 20ms to avoid overload)
                    self.lsl_timer = QTimer()
                    self.lsl_timer.timeout.connect(self._safe_record_lsl_sample)
                    self.lsl_timer.start(20)  # 20ms = 50 Hz
                    
                    self.statusBar().showMessage("Bridge and LSL initialized successfully")
                except Exception as e:
                    print(f"Warning: Could not initialize LSL: {e}")
                    self.statusBar().showMessage(f"Bridge initialized, but LSL unavailable: {e}")
            else:
                self.statusBar().showMessage("Bridge initialized (LSL not available)")
                
        except Exception as e:
            print(f"Error setting up bridge: {e}")
            self.statusBar().showMessage(f"Bridge setup error: {e}")
    
    def _safe_record_lsl_sample(self):
        """Safely record LSL sample with error handling."""
        try:
            if self.lsl_recorder and self.lsl_recorder.is_recording:
                self.lsl_recorder.record_sample()
        except Exception as e:
            # Don't print errors for every failed sample - just log occasionally
            pass
    
    def _handle_bridge_event(self, event_data: Dict[str, Any]):
        """Handle events received from the HTML bridge.
        
        Args:
            event_data: Event dictionary with type, data, timestamp
        """
        try:
            event_type = event_data.get('type', 'unknown')
            event_data_dict = event_data.get('data', {})
            
            # Check for session end event
            if event_type == 'session_end':
                # Automatically end the session
                self.statusBar().showMessage("Session ending...", 2000)
                # Use QTimer to end session in next event loop iteration
                QTimer.singleShot(500, self._end_session)
                return
            
            # Add to tracking data
            bridge_event = {
                'timestamp': event_data.get('timestamp', datetime.now().isoformat()),
                'event_type': 'bridge_event',
                'bridge_event_type': event_type,
                'bridge_event_data': event_data_dict,
                'session_id': self.session.session_id
            }
            self.tracking_data.append(bridge_event)
            
            # Stream to LSL if available
            if self.lsl_streamer:
                self.lsl_streamer.push_event(event_data)
            
            # Update status bar
            self.statusBar().showMessage(f"Bridge event: {event_type}", 2000)
            
        except Exception as e:
            print(f"Error handling bridge event: {e}")
    
    def _setup_tracking(self):
        """Set up tracking data collection."""
        # Start tracking timer (every 100ms = 10 FPS)
        self.tracking_timer = QTimer()
        self.tracking_timer.timeout.connect(self._collect_tracking_data)
        self.tracking_timer.start(100)
        
        # Track mouse events
        self.web_view.mousePressEvent = self._on_mouse_press
        self.web_view.mouseReleaseEvent = self._on_mouse_release
        self.web_view.mouseMoveEvent = self._on_mouse_move
    
    def _collect_tracking_data(self):
        """Collect current tracking data."""
        cursor_pos = self.web_view.mapFromGlobal(self.web_view.cursor().pos())
        
        tracking_point = {
            'timestamp': datetime.now().isoformat(),
            'mouse_position': (cursor_pos.x(), cursor_pos.y()),
            'session_id': self.session.session_id
        }
        
        self.tracking_data.append(tracking_point)
        
        # Stream to LSL if available
        if self.lsl_mouse_streamer:
            self.lsl_mouse_streamer.push_tracking_data(tracking_point)
    
    def _on_mouse_press(self, event):
        """Handle mouse press events."""
        cursor_pos = self.web_view.mapFromGlobal(event.globalPos())
        
        tracking_point = {
            'timestamp': datetime.now().isoformat(),
            'mouse_position': (cursor_pos.x(), cursor_pos.y()),
            'event_type': 'mouse_press',
            'button': event.button(),
            'session_id': self.session.session_id
        }
        
        self.tracking_data.append(tracking_point)
        
        # Stream to LSL if available
        if self.lsl_mouse_streamer:
            self.lsl_mouse_streamer.push_tracking_data(tracking_point)
        
        # Call parent's mouse press event
        super(QWebEngineView, self.web_view).mousePressEvent(event)
    
    def _on_mouse_release(self, event):
        """Handle mouse release events."""
        cursor_pos = self.web_view.mapFromGlobal(event.globalPos())
        
        tracking_point = {
            'timestamp': datetime.now().isoformat(),
            'mouse_position': (cursor_pos.x(), cursor_pos.y()),
            'event_type': 'mouse_release',
            'button': event.button(),
            'session_id': self.session.session_id
        }
        
        self.tracking_data.append(tracking_point)
        
        # Stream to LSL if available
        if self.lsl_mouse_streamer:
            self.lsl_mouse_streamer.push_tracking_data(tracking_point)
        
        # Call parent's mouse release event
        super(QWebEngineView, self.web_view).mouseReleaseEvent(event)
    
    def _on_mouse_move(self, event):
        """Handle mouse move events."""
        cursor_pos = self.web_view.mapFromGlobal(event.globalPos())
        
        tracking_point = {
            'timestamp': datetime.now().isoformat(),
            'mouse_position': (cursor_pos.x(), cursor_pos.y()),
            'event_type': 'mouse_move',
            'session_id': self.session.session_id
        }
        
        self.tracking_data.append(tracking_point)
        
        # Stream to LSL if available
        if self.lsl_mouse_streamer:
            self.lsl_mouse_streamer.push_tracking_data(tracking_point)
        
        # Call parent's mouse move event
        super(QWebEngineView, self.web_view).mouseMoveEvent(event)
    
    def _end_session(self):
        """End the session and save data."""
        # Prevent double execution
        if self._session_ending:
            return
        
        self._session_ending = True
        
        # Stop any playing video in the webpage - use multiple strategies
        try:
            # Strategy 1: Stop video via JavaScript (aggressive)
            stop_video_js = """
            (function() {
                const video = document.getElementById('attentionVideo');
                if (video) {
                    video.pause();
                    video.currentTime = 0;
                    video.muted = true;
                    // Remove source to completely stop playback
                    const src = video.src;
                    video.src = '';
                    video.load();
                }
            })();
            """
            self.web_view.page().runJavaScript(stop_video_js)
            
            # Strategy 2: Unload the webpage completely to force QtWebEngine to stop all media
            # This is the most reliable way - unloading the page stops all media playback
            # Use QTimer to give JavaScript a moment to execute, then unload
            QTimer.singleShot(100, lambda: self.web_view.setUrl(QUrl("about:blank")))
            
        except Exception as e:
            print(f"Warning: Could not stop video: {e}")
            # Fallback: just unload the page
            try:
                self.web_view.setUrl(QUrl("about:blank"))
            except:
                pass
        
        # Stop tracking
        if hasattr(self, 'tracking_timer'):
            self.tracking_timer.stop()
        
        # Stop LSL recording
        if self.lsl_timer:
            self.lsl_timer.stop()
            self.lsl_timer = None
        
        if self.lsl_recorder:
            try:
                self.lsl_recorder.stop_recording()
            except Exception as e:
                print(f"Error stopping LSL recorder: {e}")
            self.lsl_recorder = None
        
        # Close LSL streamers
        if self.lsl_streamer:
            self.lsl_streamer.close()
        if self.lsl_mouse_streamer:
            self.lsl_mouse_streamer.close()
        
        # Calculate session duration
        session_end_time = datetime.now()
        duration = (session_end_time - self.session_start_time).total_seconds()
        self.session.duration = duration
        
        # Save session data (including LSL data)
        self._save_session_data()
        
        # Emit session ended signal
        self.session_ended.emit(self.session.session_id)
        
        # Close window after a short delay to allow page to unload and stop media
        # This ensures the video stops before the window closes
        QTimer.singleShot(200, self.close)
    
    def _save_session_data(self):
        """Save session tracking data and LSL recorded data."""
        # Create tracking data directory
        tracking_dir = self.project.project_path / "tracking_data" / self.session.session_id
        tracking_dir.mkdir(parents=True, exist_ok=True)
        
        # Save tracking data (mouse events, bridge events, etc.)
        if self.tracking_data:
            tracking_file = tracking_dir / "tracking_data.json"
            with open(tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.tracking_data, f, indent=2)
        
        # Save LSL recorded data if available (this is the comprehensive record with all streams)
        # Try to save even if there was an error, as long as we have some data
        if self.lsl_recorder:
            try:
                if self.lsl_recorder.recorded_data:
                    lsl_file = tracking_dir / "lsl_recorded_data.json"
                    # Include all tracking data in LSL file for completeness
                    # (even though most should already be in LSL streams)
                    self.lsl_recorder.save_to_file(str(lsl_file), additional_tracking_data=self.tracking_data)
                    print(f"Saved {len(self.lsl_recorder.recorded_data)} LSL samples to {lsl_file}")
                else:
                    print("Warning: LSL recorder has no recorded data to save")
            except Exception as e:
                print(f"Error saving LSL data: {e}")
                import traceback
                traceback.print_exc()
            
            # Also add LSL data summary to tracking data
            lsl_summary = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'lsl_summary',
                'total_samples': len(self.lsl_recorder.recorded_data),
                'streams': self.lsl_recorder.stream_info,
                'session_id': self.session.session_id
            }
            self.tracking_data.append(lsl_summary)
        
        # Update session metadata
        self.session.tracking_data_path = tracking_dir
        self.session.modified_date = datetime.now()
        
        # Save session metadata
        session_file = self.project.project_path / "sessions" / f"{self.session.session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(self.session.to_dict(), f, indent=2)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self._end_session()
        event.accept()


class SessionCreationDialog(QDialog):
    """Dialog for creating new sessions."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.session_name = ""
        
        self.setWindowTitle("Create New Session")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Form layout
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter session name")
        self.name_edit.textChanged.connect(self._on_name_changed)
        form_layout.addRow("Session Name:", self.name_edit)
        
        # Session info
        info_label = QLabel(f"Project: {self.project.name}")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addRow("Project:", info_label)
        
        type_label = QLabel(self.project.project_type.value.replace('_', ' ').title())
        type_label.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addRow("Type:", type_label)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.create_button = QPushButton("Start Session")
        self.create_button.clicked.connect(self._create_session)
        self.create_button.setDefault(True)
        self.create_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _on_name_changed(self, text):
        """Handle session name change."""
        self.session_name = text.strip()
        self.create_button.setEnabled(bool(self.session_name))
    
    def _create_session(self):
        """Create the session and accept dialog."""
        if not self.session_name:
            QMessageBox.warning(self, "Validation Error", "Session name is required.")
            return
        
        self.accept()


class SessionSelectionDialog(QDialog):
    """Dialog for selecting a session to review."""
    
    def __init__(self, project: Project, project_manager, parent=None):
        super().__init__(parent)
        self.project = project
        self.project_manager = project_manager
        self.selected_session: Optional[Session] = None
        
        self.setWindowTitle(f"Select Session - {project.name}")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
        self._load_sessions()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Select a session to review:")
        layout.addWidget(info_label)
        
        # Session list
        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(self._on_session_double_clicked)
        layout.addWidget(self.session_list)
        
        # Session info
        self.info_label = QLabel("No session selected")
        self.info_label.setStyleSheet("color: gray; font-style: italic; padding: 10px;")
        layout.addWidget(self.info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.review_button = QPushButton("Review Session")
        self.review_button.clicked.connect(self._on_review_clicked)
        self.review_button.setDefault(True)
        self.review_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.review_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Connect selection change
        self.session_list.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_sessions(self):
        """Load all sessions for the project."""
        self.session_list.clear()
        self.sessions = []
        
        if not self.project.sessions:
            self.info_label.setText("No sessions available for this project.")
            return
        
        # Load each session
        for session_id in self.project.sessions:
            session = self.project_manager._load_session_metadata(self.project, session_id)
            if session:
                self.sessions.append(session)
                # Create list item
                item = QListWidgetItem()
                item.setText(f"{session.name} ({session.created_date.strftime('%Y-%m-%d %H:%M:%S')})")
                item.setData(Qt.ItemDataRole.UserRole, session)
                self.session_list.addItem(item)
        
        if not self.sessions:
            self.info_label.setText("No valid sessions found.")
    
    def _on_selection_changed(self):
        """Handle session selection change."""
        selected_items = self.session_list.selectedItems()
        if selected_items:
            session = selected_items[0].data(Qt.ItemDataRole.UserRole)
            duration_str = f"{session.duration:.1f}s" if session.duration else "N/A"
            self.info_label.setText(
                f"Session: {session.name}\n"
                f"Created: {session.created_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Duration: {duration_str}"
            )
            self.review_button.setEnabled(True)
        else:
            self.info_label.setText("No session selected")
            self.review_button.setEnabled(False)
    
    def _on_session_double_clicked(self, item):
        """Handle double-click on session."""
        self._on_review_clicked()
    
    def _on_review_clicked(self):
        """Handle review button click."""
        selected_items = self.session_list.selectedItems()
        if selected_items:
            self.selected_session = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()


class SessionReviewWindow(QMainWindow):
    """Window for reviewing session data with video playback and overlays."""
    
    def __init__(self, project: Project, session: Session, project_manager, parent=None):
        super().__init__(parent)
        self.project = project
        self.session = session
        self.project_manager = project_manager
        
        self.tracking_data: List[Dict[str, Any]] = []
        self.lsl_data: List[Dict[str, Any]] = []
        self.session_start_time: Optional[datetime] = None
        self.session_duration: float = 0.0
        
        # Current playback time (in seconds from session start)
        self.current_time: float = 0.0
        self.is_playing: bool = False
        self.playback_timer: Optional[QTimer] = None
        
        self.setWindowTitle(f"Review Session: {session.name} - {project.name}")
        self.setMinimumSize(1400, 900)
        
        self._load_session_data()
        self._setup_ui()
        self._setup_playback()
    
    def _load_session_data(self):
        """Load tracking data and LSL data for the session."""
        # Try to find tracking data directory
        tracking_dir = None
        
        # First, try using session.tracking_data_path if set
        if self.session.tracking_data_path:
            tracking_dir = self.session.tracking_data_path
        else:
            # Fallback: construct path from project and session ID
            tracking_dir = self.project.project_path / "tracking_data" / self.session.session_id
        
        print(f"[SessionReview] Looking for tracking data in: {tracking_dir}")
        
        # Load tracking_data.json
        if tracking_dir and tracking_dir.exists():
            tracking_file = tracking_dir / "tracking_data.json"
            print(f"[SessionReview] Checking for tracking file: {tracking_file}")
            if tracking_file.exists():
                try:
                    with open(tracking_file, 'r', encoding='utf-8') as f:
                        self.tracking_data = json.load(f)
                    print(f"[SessionReview] Loaded {len(self.tracking_data)} tracking events")
                except Exception as e:
                    print(f"[SessionReview] Error loading tracking data: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[SessionReview] Tracking file not found: {tracking_file}")
            
            # Load lsl_recorded_data.json
            lsl_file = tracking_dir / "lsl_recorded_data.json"
            print(f"[SessionReview] Checking for LSL file: {lsl_file}")
            if lsl_file.exists():
                try:
                    with open(lsl_file, 'r', encoding='utf-8') as f:
                        lsl_data = json.load(f)
                        # Extract recorded samples (structure: lsl_samples array)
                        self.lsl_data = lsl_data.get('lsl_samples', [])
                    print(f"[SessionReview] Loaded {len(self.lsl_data)} LSL samples")
                except Exception as e:
                    print(f"[SessionReview] Error loading LSL data: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[SessionReview] LSL file not found: {lsl_file}")
        else:
            print(f"[SessionReview] Tracking directory does not exist: {tracking_dir}")
        
        # Calculate session start time and duration
        if self.tracking_data:
            try:
                # Find first valid timestamp
                first_timestamp = None
                last_timestamp = None
                for event in self.tracking_data:
                    ts = event.get('timestamp')
                    if ts and isinstance(ts, str):
                        try:
                            dt = datetime.fromisoformat(ts)
                            if first_timestamp is None:
                                first_timestamp = dt
                            last_timestamp = dt
                        except (ValueError, TypeError):
                            continue
                
                if first_timestamp and last_timestamp:
                    self.session_start_time = first_timestamp
                    self.session_duration = (last_timestamp - first_timestamp).total_seconds()
                    print(f"[SessionReview] Session duration: {self.session_duration:.2f}s")
                else:
                    print(f"[SessionReview] Could not find valid timestamps, using session.duration")
                    if self.session.duration:
                        self.session_duration = self.session.duration
            except Exception as e:
                print(f"[SessionReview] Error calculating duration: {e}")
                import traceback
                traceback.print_exc()
                if self.session.duration:
                    self.session_duration = self.session.duration
        elif self.session.duration:
            self.session_duration = self.session.duration
        else:
            self.session_duration = 0.0
            print(f"[SessionReview] No tracking data and no session duration - setting to 0")
    
    def _setup_ui(self):
        """Set up the review window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top bar with session info and controls
        top_bar = QHBoxLayout()
        
        info_label = QLabel(f"Session: {self.session.name} | Duration: {self.session_duration:.1f}s")
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        top_bar.addWidget(info_label)
        
        top_bar.addStretch()
        
        # Playback controls
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self._toggle_playback)
        top_bar.addWidget(self.play_button)
        
        self.time_label = QLabel("00:00 / 00:00")
        top_bar.addWidget(self.time_label)
        
        # Speed control
        speed_label = QLabel("Speed:")
        top_bar.addWidget(speed_label)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x", "4x"])
        self.speed_combo.setCurrentText("1x")
        top_bar.addWidget(self.speed_combo)
        
        main_layout.addLayout(top_bar)
        
        # Main splitter: Video/Overlay | Events/LSL Data
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Video player with overlay
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        
        # Video player area (placeholder for now - will show webpage or video when screen recording is implemented)
        self.video_scene = QGraphicsScene()
        self.video_view = QGraphicsView(self.video_scene)
        self.video_view.setMinimumSize(800, 600)
        self.video_view.setStyleSheet("background-color: #000;")
        
        # Add placeholder text
        placeholder_text = self.video_scene.addText(
            "Video/Webpage Playback\n(Screen recording not yet implemented)",
            QFont("Arial", 16)
        )
        placeholder_text.setDefaultTextColor(QColor(255, 255, 255))
        placeholder_text.setPos(200, 250)
        
        video_layout.addWidget(self.video_view)
        
        # Timeline scrubber
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(QLabel("Timeline:"))
        
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setMinimum(0)
        max_value = max(1, int(self.session_duration * 100))  # 100ms precision, at least 1
        self.timeline_slider.setMaximum(max_value)
        self.timeline_slider.valueChanged.connect(self._on_timeline_changed)
        self.timeline_slider.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self.timeline_slider.sliderReleased.connect(lambda: setattr(self, '_seeking', False))
        self._seeking = False
        timeline_layout.addWidget(self.timeline_slider)
        
        video_layout.addLayout(timeline_layout)
        
        main_splitter.addWidget(video_widget)
        
        # Right side: Events and LSL data
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Events table
        events_group = QGroupBox("Events Timeline")
        events_layout = QVBoxLayout()
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(4)
        self.events_table.setHorizontalHeaderLabels(["Time", "Type", "Event", "Details"])
        self.events_table.horizontalHeader().setStretchLastSection(True)
        self.events_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.events_table.itemSelectionChanged.connect(self._on_event_selected)
        events_layout.addWidget(self.events_table)
        
        events_group.setLayout(events_layout)
        right_splitter.addWidget(events_group)
        
        # LSL data visualization
        lsl_group = QGroupBox("LSL Tracking Data")
        lsl_layout = QVBoxLayout()
        
        self.lsl_table = QTableWidget()
        self.lsl_table.setColumnCount(4)
        self.lsl_table.setHorizontalHeaderLabels(["Time", "Stream", "Channel", "Value"])
        self.lsl_table.horizontalHeader().setStretchLastSection(True)
        lsl_layout.addWidget(self.lsl_table)
        
        lsl_group.setLayout(lsl_layout)
        right_splitter.addWidget(lsl_group)
        
        right_splitter.setSizes([400, 300])
        main_splitter.addWidget(right_splitter)
        
        main_splitter.setSizes([800, 400])
        main_layout.addWidget(main_splitter)
        
        # Populate events table
        self._populate_events_table()
        
        # Populate LSL table
        self._populate_lsl_table()
    
    def _populate_events_table(self):
        """Populate the events table with tracking data."""
        print(f"[SessionReview] Populating events table with {len(self.tracking_data)} events")
        self.events_table.setRowCount(len(self.tracking_data))
        
        if not self.tracking_data:
            print("[SessionReview] No tracking data to display")
            return
        
        for i, event in enumerate(self.tracking_data):
            # Calculate relative time - handle different timestamp formats
            timestamp = event.get('timestamp')
            if not timestamp:
                relative_time = 0.0
            elif isinstance(timestamp, str):
                try:
                    event_time = datetime.fromisoformat(timestamp)
                    if self.session_start_time:
                        relative_time = (event_time - self.session_start_time).total_seconds()
                    else:
                        relative_time = 0.0
                except (ValueError, TypeError) as e:
                    print(f"[SessionReview] Error parsing timestamp '{timestamp}': {e}")
                    relative_time = 0.0
            else:
                # Timestamp might be a datetime object or other type
                print(f"[SessionReview] Unexpected timestamp type: {type(timestamp)}, value: {timestamp}")
                relative_time = 0.0
            
            # Time column
            time_str = f"{relative_time:.2f}s"
            self.events_table.setItem(i, 0, QTableWidgetItem(time_str))
            
            # Event type
            event_type = event.get('event_type', 'unknown')
            self.events_table.setItem(i, 1, QTableWidgetItem(event_type))
            
            # Event details
            if event_type == 'bridge_event':
                bridge_type = event.get('bridge_event_type', 'unknown')
                self.events_table.setItem(i, 2, QTableWidgetItem(f"Bridge: {bridge_type}"))
                # Details
                bridge_data = event.get('bridge_event_data', {})
                details_str = str(bridge_data)[:100]  # Truncate long details
                self.events_table.setItem(i, 3, QTableWidgetItem(details_str))
            elif event_type in ['mouse_press', 'mouse_release', 'mouse_move']:
                self.events_table.setItem(i, 2, QTableWidgetItem(event_type.replace('_', ' ').title()))
                mouse_pos = event.get('mouse_position', [0, 0])
                self.events_table.setItem(i, 3, QTableWidgetItem(f"Position: ({mouse_pos[0]}, {mouse_pos[1]})"))
            else:
                self.events_table.setItem(i, 2, QTableWidgetItem(event_type))
                self.events_table.setItem(i, 3, QTableWidgetItem(str(event)[:100]))
    
    def _populate_lsl_table(self):
        """Populate the LSL data table."""
        print(f"[SessionReview] Populating LSL table with {len(self.lsl_data)} samples")
        # Show first 100 samples (can be expanded later)
        samples_to_show = min(100, len(self.lsl_data))
        self.lsl_table.setRowCount(samples_to_show)
        
        if not self.lsl_data:
            print("[SessionReview] No LSL data to display")
            return
        
        for i, sample in enumerate(self.lsl_data[:samples_to_show]):
            # Time
            relative_time = sample.get('relative_time', 0.0)
            self.lsl_table.setItem(i, 0, QTableWidgetItem(f"{relative_time:.3f}s"))
            
            # Stream name (from parsed structure)
            stream_name = sample.get('stream_name', 'Unknown')
            self.lsl_table.setItem(i, 1, QTableWidgetItem(stream_name))
            
            # Channel and value
            data = sample.get('data', [])
            if isinstance(data, list) and len(data) > 0:
                # Show first channel value
                self.lsl_table.setItem(i, 2, QTableWidgetItem("Ch 0"))
                self.lsl_table.setItem(i, 3, QTableWidgetItem(str(data[0])[:50]))
            elif isinstance(data, dict):
                # Bridge events might be stored as dict
                self.lsl_table.setItem(i, 2, QTableWidgetItem("Event"))
                self.lsl_table.setItem(i, 3, QTableWidgetItem(str(data)[:50]))
            else:
                self.lsl_table.setItem(i, 2, QTableWidgetItem("N/A"))
                self.lsl_table.setItem(i, 3, QTableWidgetItem(str(data)[:50] if data else "N/A"))
    
    def _setup_playback(self):
        """Set up playback timer and controls."""
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self._update_playback)
        self.playback_timer.setInterval(100)  # Update every 100ms
    
    def _toggle_playback(self):
        """Toggle playback state."""
        if self.is_playing:
            self.playback_timer.stop()
            self.is_playing = False
            self.play_button.setText("▶ Play")
        else:
            self.playback_timer.start()
            self.is_playing = True
            self.play_button.setText("⏸ Pause")
    
    def _update_playback(self):
        """Update playback position."""
        if not self._seeking:
            # Get speed multiplier
            speed_text = self.speed_combo.currentText()
            speed = float(speed_text.replace('x', ''))
            
            # Update time
            self.current_time += 0.1 * speed  # 100ms * speed
            
            if self.current_time >= self.session_duration:
                self.current_time = self.session_duration
                self._toggle_playback()  # Stop at end
            
            # Update timeline slider
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(int(self.current_time * 100))
            self.timeline_slider.blockSignals(False)
        
        # Update time label
        current_str = f"{int(self.current_time // 60):02d}:{int(self.current_time % 60):02d}"
        duration_str = f"{int(self.session_duration // 60):02d}:{int(self.session_duration % 60):02d}"
        self.time_label.setText(f"{current_str} / {duration_str}")
        
        # Update overlay
        self._update_overlay()
    
    def _on_timeline_changed(self, value):
        """Handle timeline slider change."""
        if not self._seeking:
            self.current_time = value / 100.0
            self._update_overlay()
            # Update time label
            current_str = f"{int(self.current_time // 60):02d}:{int(self.current_time % 60):02d}"
            duration_str = f"{int(self.session_duration // 60):02d}:{int(self.session_duration % 60):02d}"
            self.time_label.setText(f"{current_str} / {duration_str}")
    
    def _update_overlay(self):
        """Update mouse tracking overlay on video."""
        # Clear existing overlay items (except placeholder text)
        items_to_remove = []
        for item in self.video_scene.items():
            if not isinstance(item, QGraphicsTextItem) or item.toPlainText() != "Video/Webpage Playback\n(Screen recording not yet implemented)":
                items_to_remove.append(item)
        for item in items_to_remove:
            self.video_scene.removeItem(item)
        
        # Find mouse position at current time
        mouse_pos = self._get_mouse_position_at_time(self.current_time)
        if mouse_pos:
            x, y = mouse_pos
            # Draw mouse cursor (circle)
            cursor = QGraphicsEllipseItem(x - 5, y - 5, 10, 10)
            cursor.setPen(QPen(QColor(255, 0, 0), 2))
            cursor.setBrush(QBrush(QColor(255, 0, 0, 100)))
            self.video_scene.addItem(cursor)
            
            # Draw mouse trail (recent positions)
            recent_positions = self._get_mouse_trail(self.current_time, duration=2.0)  # Last 2 seconds
            if len(recent_positions) > 1:
                for i in range(len(recent_positions) - 1):
                    x1, y1 = recent_positions[i]
                    x2, y2 = recent_positions[i + 1]
                    line = QGraphicsLineItem(x1, y1, x2, y2)
                    # Fade trail (more recent = brighter)
                    alpha = int(255 * (i / len(recent_positions)))
                    line.setPen(QPen(QColor(255, 0, 0, alpha), 1))
                    self.video_scene.addItem(line)
    
    def _get_mouse_position_at_time(self, time: float) -> Optional[tuple]:
        """Get mouse position at a specific time."""
        if not self.session_start_time:
            return None
        
        target_time = self.session_start_time.timestamp() + time
        
        # Find closest tracking data point
        closest = None
        min_diff = float('inf')
        
        for event in self.tracking_data:
            timestamp = event.get('timestamp')
            if not timestamp or not isinstance(timestamp, str):
                continue
            try:
                event_time = datetime.fromisoformat(timestamp).timestamp()
                diff = abs(event_time - target_time)
                if diff < min_diff:
                    min_diff = diff
                    closest = event
            except (ValueError, TypeError):
                continue
        
        if closest and 'mouse_position' in closest:
            pos = closest['mouse_position']
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return (pos[0], pos[1])
        
        return None
    
    def _get_mouse_trail(self, time: float, duration: float = 2.0) -> List[tuple]:
        """Get mouse trail (positions) for the last N seconds."""
        if not self.session_start_time:
            return []
        
        start_time = self.session_start_time.timestamp() + max(0, time - duration)
        end_time = self.session_start_time.timestamp() + time
        
        trail = []
        for event in self.tracking_data:
            timestamp = event.get('timestamp')
            if not timestamp or not isinstance(timestamp, str):
                continue
            try:
                event_time = datetime.fromisoformat(timestamp).timestamp()
                if start_time <= event_time <= end_time and 'mouse_position' in event:
                    pos = event['mouse_position']
                    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        trail.append((pos[0], pos[1]))
            except (ValueError, TypeError):
                continue
        
        return trail
    
    def _on_event_selected(self):
        """Handle event selection - jump to that time."""
        selected_rows = self.events_table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            time_item = self.events_table.item(row, 0)
            if time_item:
                time_str = time_item.text().replace('s', '')
                try:
                    self.current_time = float(time_str)
                    self.timeline_slider.blockSignals(True)
                    self.timeline_slider.setValue(int(self.current_time * 100))
                    self.timeline_slider.blockSignals(False)
                    self._update_overlay()
                    # Update time label
                    current_str = f"{int(self.current_time // 60):02d}:{int(self.current_time % 60):02d}"
                    duration_str = f"{int(self.session_duration // 60):02d}:{int(self.session_duration % 60):02d}"
                    self.time_label.setText(f"{current_str} / {duration_str}")
                except ValueError:
                    pass


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.project_manager = ProjectManager()
        self.current_project: Optional[Project] = None
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("MadsPipeline - Data Streaming and Visualization Pipeline")
        self.setMinimumSize(800, 600)
        
        # Central widget with stacked layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Stacked widget for different views
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # Create widgets
        self.project_selection = ProjectSelectionWidget(self.project_manager)
        self.project_dashboard = None  # Will be created when project is selected
        
        # Add to stacked widget
        self.stacked_widget.addWidget(self.project_selection)
        
        # Set initial view
        self.stacked_widget.setCurrentWidget(self.project_selection)
    
    def _setup_connections(self):
        """Set up signal connections."""
        self.project_selection.project_selected.connect(self._on_project_selected)
        self.project_selection.project_created.connect(self._on_project_created)
    
    def _on_project_selected(self, project: Project):
        """Handle project selection."""
        self.current_project = project
        self._show_project_dashboard()
    
    def _on_project_created(self, project: Project):
        """Handle project creation."""
        self.current_project = project
        self._show_project_dashboard()
    
    def _show_project_dashboard(self):
        """Show the project dashboard."""
        if self.project_dashboard is None:
            self.project_dashboard = ProjectDashboardWidget(self.current_project)
            self.project_dashboard.new_session_requested.connect(self._on_new_session)
            self.project_dashboard.debug_session_requested.connect(self._on_debug_session)
            self.project_dashboard.edit_project_requested.connect(self._on_edit_project)
            self.project_dashboard.review_sessions_requested.connect(self._on_review_sessions)
            self.project_dashboard.export_data_requested.connect(self._on_export_data)
            self.project_dashboard.back_to_projects_requested.connect(self._on_back_to_projects)
            
            self.stacked_widget.addWidget(self.project_dashboard)
        else:
            # Refresh the existing dashboard with current project data
            self.project_dashboard.refresh_project_data(self.current_project)
        
        self.stacked_widget.setCurrentWidget(self.project_dashboard)
    
    def _on_new_session(self):
        """Handle new session request."""
        if self.current_project.project_type == ProjectType.EMBEDDED_WEBPAGE:
            # Show session creation dialog
            dialog = SessionCreationDialog(self.current_project, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                try:
                    # Create the session
                    session = self.project_manager.create_session(
                        self.current_project, 
                        dialog.session_name
                    )
                    
                    # Create and show the embedded webpage session window
                    self.session_window = EmbeddedWebpageSessionWindow(
                        self.current_project, 
                        session, 
                        self
                    )
                    self.session_window.session_ended.connect(self._on_session_ended)
                    
                    # Show window first
                    self.session_window.show()
                    self.session_window.raise_()  # Bring to front
                    self.session_window.activateWindow()  # Activate and focus
                    
                    # Ensure it stays visible - don't hide main window immediately
                    # Let the session window establish itself first
                    QTimer.singleShot(500, lambda: self.hide())
                    
                    # Refresh the dashboard to show the new session
                    if self.project_dashboard:
                        self.project_dashboard.refresh_project_data(self.current_project)
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create session: {e}")
        else:
            # TODO: Implement other project type sessions
            QMessageBox.information(self, "Info", f"Session functionality for {self.current_project.project_type.value} projects coming soon!")
    
    def _on_session_ended(self, session_id: str):
        """Handle session completion."""
        # Show the main window again
        self.show()
        
        # Clean up session window reference
        if hasattr(self, 'session_window'):
            self.session_window = None
        
        # Refresh the project dashboard to show new session
        if self.project_dashboard:
            self.project_dashboard.refresh_project_data(self.current_project)
        
        # Show success message
        QMessageBox.information(self, "Session Complete", "Session has been completed and data saved successfully!")
    
    def _on_debug_session(self):
        """Handle debug session request."""
        self.debug_window = DebugSessionWindow(self.current_project, self)
        self.debug_window.session_ended.connect(self._on_debug_session_ended)
        self.debug_window.show()
    
    def _on_debug_session_ended(self):
        """Handle debug session window close."""
        if hasattr(self, 'debug_window'):
            self.debug_window.close()
            self.debug_window = None
    
    def _on_edit_project(self):
        """Handle edit project request."""
        dialog = EditProjectDialog(self.current_project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Update project with new values
                self.current_project.name = dialog.project_name
                self.current_project.description = dialog.project_description
                
                # Update type-specific configurations
                if self.current_project.project_type == ProjectType.PICTURE_SLIDESHOW:
                    from .models import PictureSlideshowConfig
                    self.current_project.picture_slideshow_config = PictureSlideshowConfig(
                        images=self.current_project.picture_slideshow_config.images if self.current_project.picture_slideshow_config else [],
                        auto_play=dialog.project_config.get('auto_play', True),
                        slide_duration=dialog.project_config.get('slide_duration', 5.0),
                        manual_navigation=dialog.project_config.get('manual_navigation', False),
                        transition_effect=dialog.project_config.get('transition_effect', 'fade')
                    )
                elif self.current_project.project_type == ProjectType.VIDEO:
                    from .models import VideoConfig
                    self.current_project.video_config = VideoConfig(
                        video_path=Path(dialog.project_config.get('video_path')) if dialog.project_config.get('video_path') else None,
                        auto_play=dialog.project_config.get('auto_play', True),
                        loop=dialog.project_config.get('loop', False),
                        start_time=0.0,
                        end_time=None
                    )
                elif self.current_project.project_type == ProjectType.SCREEN_RECORDING:
                    from .models import ScreenRecordingConfig
                    self.current_project.screen_recording_config = ScreenRecordingConfig(
                        recording_quality=dialog.project_config.get('recording_quality', 'high'),
                        fps=dialog.project_config.get('fps', 30),
                        resolution=None,
                        include_audio=dialog.project_config.get('include_audio', False),
                        mouse_tracking=dialog.project_config.get('mouse_tracking', True)
                    )
                elif self.current_project.project_type == ProjectType.EMBEDDED_WEBPAGE:
                    from .models import EmbeddedWebpageConfig
                    self.current_project.embedded_webpage_config = EmbeddedWebpageConfig(
                        webpage_url=dialog.project_config.get('webpage_url'),
                        local_html_path=Path(dialog.project_config.get('local_html_path')) if dialog.project_config.get('local_html_path') else None,
                        enable_marker_api=dialog.project_config.get('enable_marker_api', True),
                        fullscreen=dialog.project_config.get('fullscreen', True),
                        allow_external_links=False
                    )
                
                # Update modified date
                self.current_project.modified_date = datetime.now()
                
                # Save updated project
                self.project_manager._save_project_metadata(self.current_project)
                
                # Refresh dashboard to show updated info
                self._show_project_dashboard()
                
                QMessageBox.information(self, "Success", "Project updated successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update project: {e}")
    
    def _on_review_sessions(self):
        """Handle review sessions request."""
        if not self.current_project:
            return
        
        # Show session selection dialog
        dialog = SessionSelectionDialog(self.current_project, self.project_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_session:
            # Open session review window
            review_window = SessionReviewWindow(
                self.current_project,
                dialog.selected_session,
                self.project_manager,
                self
            )
            review_window.show()
    
    def _on_export_data(self):
        """Handle export data request."""
        try:
            export_path = self.project_manager.export_project_data(self.current_project)
            QMessageBox.information(
                self, "Success", 
                f"Project data exported successfully to:\n{export_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")
    
    def _on_back_to_projects(self):
        """Return to project selection."""
        self.stacked_widget.setCurrentWidget(self.project_selection)
        self.current_project = None
