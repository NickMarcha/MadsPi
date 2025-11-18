"""
Project management functionality for MadsPipeline.
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
import shutil

# Import local modules using relative imports
from .models import Project, Session, TrackingData, Marker, ProjectType


class ProjectManager:
    """Manages project creation, loading, and file operations."""
    
    def __init__(self, base_projects_dir: Optional[Path] = None):
        """Initialize project manager.
        
        Args:
            base_projects_dir: Base directory for all projects. 
                             Defaults to user's Documents folder.
        """
        if base_projects_dir is None:
            self.base_projects_dir = Path.home() / "Documents" / "MadsPipeline"
        else:
            self.base_projects_dir = Path(base_projects_dir)
        
        self.base_projects_dir.mkdir(parents=True, exist_ok=True)
        self.current_project: Optional[Project] = None
    
    def create_project(self, name: str, description: str, project_type: 'ProjectType', 
                      config: Optional[Dict[str, Any]] = None, location: Optional[Path] = None) -> Project:
        """Create a new project.
        
        Args:
            name: Project name
            description: Project description
            project_type: Type of project (PICTURE_SLIDESHOW, VIDEO, etc.)
            config: Type-specific configuration dictionary
            location: Custom location for project (optional)
            
        Returns:
            Created project instance
        """
        if location is None:
            project_path = self.base_projects_dir / self._sanitize_filename(name)
        else:
            project_path = Path(location) / self._sanitize_filename(name)
        
        # Check if project already exists
        if project_path.exists():
            raise ValueError(f"Project '{name}' already exists at {project_path}")
        
        # Create project directory structure
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "sessions").mkdir(exist_ok=True)
        # Note: All session data (including recordings) is now stored in sessions/{session_id}/
        (project_path / "exports").mkdir(exist_ok=True)
        
        # Create type-specific subdirectories
        if project_type == ProjectType.PICTURE_SLIDESHOW:
            (project_path / "images").mkdir(exist_ok=True)
        elif project_type == ProjectType.VIDEO:
            (project_path / "videos").mkdir(exist_ok=True)
        elif project_type == ProjectType.EMBEDDED_WEBPAGE:
            (project_path / "webpages").mkdir(exist_ok=True)
        
        # Initialize type-specific configurations
        picture_slideshow_config = None
        video_config = None
        screen_recording_config = None
        embedded_webpage_config = None
        
        if project_type == ProjectType.PICTURE_SLIDESHOW:
            from .models import PictureSlideshowConfig
            picture_slideshow_config = PictureSlideshowConfig(
                images=config.get('images', []) if config else [],
                auto_play=config.get('auto_play', True) if config else True,
                slide_duration=config.get('slide_duration', 5.0) if config else 5.0,
                manual_navigation=config.get('manual_navigation', False) if config else False,
                transition_effect=config.get('transition_effect', 'fade') if config else 'fade'
            )
        elif project_type == ProjectType.VIDEO:
            from .models import VideoConfig
            video_config = VideoConfig(
                video_path=Path(config.get('video_path')) if config and config.get('video_path') else None,
                auto_play=config.get('auto_play', True) if config else True,
                loop=config.get('loop', False) if config else False,
                start_time=config.get('start_time', 0.0) if config else 0.0,
                end_time=config.get('end_time') if config else None
            )
        elif project_type == ProjectType.SCREEN_RECORDING:
            from .models import ScreenRecordingConfig
            screen_recording_config = ScreenRecordingConfig(
                recording_quality=config.get('recording_quality', 'high') if config else 'high',
                fps=config.get('fps', 30) if config else 30,
                resolution=config.get('resolution') if config else None,
                include_audio=config.get('include_audio', False) if config else False,
                mouse_tracking=config.get('mouse_tracking', True) if config else True
            )
        elif project_type == ProjectType.EMBEDDED_WEBPAGE:
            from .models import EmbeddedWebpageConfig, LSLConfig
            # Load LSL config if available
            lsl_config = None
            if config and config.get('lsl_config'):
                lsl_cfg = config['lsl_config']
                lsl_config = LSLConfig(
                    enable_mouse_tracking=lsl_cfg.get('enable_mouse_tracking', True),
                    enable_marker_api=lsl_cfg.get('enable_marker_api', True),
                    enable_tobii_eyetracker=lsl_cfg.get('enable_tobii_eyetracker', False),
                    enable_emotibit=lsl_cfg.get('enable_emotibit', False),
                    tobii_stream_name=lsl_cfg.get('tobii_stream_name'),
                    emotibit_stream_name=lsl_cfg.get('emotibit_stream_name'),
                    additional_stream_filters=lsl_cfg.get('additional_stream_filters', [])
                )
            else:
                # Create default LSL config from legacy enable_marker_api flag
                lsl_config = LSLConfig(
                    enable_mouse_tracking=True,
                    enable_marker_api=config.get('enable_marker_api', True) if config else True,
                    enable_tobii_eyetracker=False,
                    enable_emotibit=False
                )
            embedded_webpage_config = EmbeddedWebpageConfig(
                webpage_url=config.get('webpage_url') if config else None,
                local_html_path=Path(config.get('local_html_path')) if config and config.get('local_html_path') else None,
                enable_marker_api=config.get('enable_marker_api', True) if config else True,
                fullscreen=config.get('fullscreen', True) if config else True,
                allow_external_links=config.get('allow_external_links', False) if config else False,
                window_size=tuple(config['window_size']) if config and config.get('window_size') else None,
                enforce_fullscreen=config.get('enforce_fullscreen', False) if config else False,
                normalize_mouse_coordinates=config.get('normalize_mouse_coordinates', True) if config else True,
                lsl_config=lsl_config
            )
        
        # Create project instance
        now = datetime.now()
        project = Project(
            name=name,
            description=description,
            project_type=project_type,
            created_date=now,
            modified_date=now,
            project_path=project_path,
            sessions=[],  # Not used - sessions scanned from filesystem
            version="1.0",  # Current project structure version
            picture_slideshow_config=picture_slideshow_config,
            video_config=video_config,
            screen_recording_config=screen_recording_config,
            embedded_webpage_config=embedded_webpage_config
        )
        
        # Save project metadata
        self._save_project_metadata(project)
        
        self.current_project = project
        return project
    
    def load_project(self, project_path: Path) -> Project:
        """Load an existing project.
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Loaded project instance
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Loading project from: {project_path}")
        
        project_path = Path(project_path)
        metadata_file = project_path / "project.json"
        
        if not metadata_file.exists():
            logger.error(f"Project metadata not found at {metadata_file}")
            raise FileNotFoundError(f"Project metadata not found at {metadata_file}")
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug("Project JSON loaded")
        
            project = Project.from_dict(data)
            logger.info(f"Project loaded: {project.name}")
        except Exception as e:
            logger.error(f"Error loading project: {e}", exc_info=True)
            raise
        
        # Check if migration is needed (but don't run migrations automatically)
        from .migrations import CURRENT_VERSION
        if project.version != CURRENT_VERSION:
            print(f"Note: Project '{project.name}' is version {project.version}, "
                  f"current version is {CURRENT_VERSION}. Migration may be needed.")
        
        # Scan sessions folder to find all sessions (instead of using project.sessions list)
        sessions_dir = project_path / "sessions"
        if sessions_dir.exists():
            found_sessions = []
            for session_dir in sessions_dir.iterdir():
                if session_dir.is_dir():
                    session_file = session_dir / "session.json"
                    if session_file.exists():
                        found_sessions.append(session_dir.name)
            # Update project sessions list from filesystem
            project.sessions = sorted(found_sessions)
        
        self.current_project = project
        return project
    
    def list_projects(self) -> List[Project]:
        """List all available projects.
        
        Returns:
            List of project instances
        """
        projects = []
        
        for project_dir in self.base_projects_dir.iterdir():
            if project_dir.is_dir():
                metadata_file = project_dir / "project.json"
                if metadata_file.exists():
                    try:
                        project = self.load_project(project_dir)
                        projects.append(project)
                    except Exception as e:
                        print(f"Error loading project {project_dir}: {e}")
        
        return projects
    
    def create_session(self, project: Project, name: str) -> Session:
        """Create a new session within a project.
        
        Args:
            project: Project instance
            name: Session name
            
        Returns:
            Created session instance
        """
        now = datetime.now()
        
        # Generate datetime-based session ID: YYYYMMDD_HHMMSS_microseconds
        # Use a more precise timestamp to avoid collisions
        session_id = now.strftime("%Y%m%d_%H%M%S_%f")
        
        # If this ID already exists, add a counter to make it unique
        counter = 1
        original_session_id = session_id
        while session_id in project.sessions:
            session_id = f"{original_session_id}_{counter}"
            counter += 1
        
        session = Session(
            session_id=session_id,
            name=name,
            created_date=now
        )
        
        # Note: We don't add to project.sessions list anymore - it's scanned from filesystem on load
        project.modified_date = now
        
        # Save session metadata
        self._save_session_metadata(project, session)
        # Update project metadata (but don't save sessions list - it's derived from filesystem)
        self._save_project_metadata(project)
        
        return session
    
    def _get_session_dir(self, project: Project, session: Session) -> Path:
        """Get the session directory path.
        
        Args:
            project: Project instance
            session: Session instance
            
        Returns:
            Path to session directory (sessions/{session_id}/)
        """
        return project.project_path / "sessions" / session.session_id
    
    def save_tracking_data(self, project: Project, session: Session, tracking_data: TrackingData) -> None:
        """Save tracking data for a session.
        
        Args:
            project: Project instance
            session: Session instance
            tracking_data: Tracking data to save
        """
        session_dir = self._get_session_dir(project, session)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save individual tracking data point
        timestamp_str = tracking_data.timestamp.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"tracking_{timestamp_str}.json"
        filepath = session_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(tracking_data.to_dict(), f, indent=2)
    
    def save_marker(self, project: Project, session: Session, marker: Marker) -> None:
        """Save a marker for a session.
        
        Args:
            project: Project instance
            session: Session instance
            marker: Marker to save
        """
        # Add marker to session
        session.markers.append(marker.to_dict())
        
        # Save updated session metadata
        self._save_session_metadata(project, session)
    
    def _load_session_lsl_data(self, session: Session, project: Optional[Project] = None) -> Optional[Dict[str, Any]]:
        """Load LSL recording data for a session.
        
        Args:
            session: Session instance
            project: Project instance (required)
            
        Returns:
            LSL data dictionary or None if not found
        """
        if not project:
            return None
        
        session_dir = self._get_session_dir(project, session)
        lsl_file = session_dir / f"lsl_recording_{session.session_id}.json"
        
        if not lsl_file.exists():
            return None
        
        try:
            with open(lsl_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading LSL data for session {session.session_id}: {e}")
            return None
    
    def _load_session_video_info(self, session: Session, project: Optional[Project] = None) -> Optional[Dict[str, Any]]:
        """Load video recording info for a session.
        
        Args:
            session: Session instance
            project: Project instance (required)
            
        Returns:
            Video info dictionary or None if not found
        """
        if not project:
            return None
        
        session_dir = self._get_session_dir(project, session)
        info_file = session_dir / f"screen_recording_info_{session.session_id}.json"
        
        if not info_file.exists():
            return None
        
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading video info for session {session.session_id}: {e}")
            return None
    
    def export_session_data(self, project: Project, session: Session, 
                           export_format: str = "json",
                           include_columns: Optional[List[str]] = None) -> Path:
        """Export a single session's data.
        
        Args:
            project: Project instance
            session: Session instance to export
            export_format: Export format ("json" or "csv")
            include_columns: For CSV, list of columns to include (None = all)
            
        Returns:
            Path to exported file
        """
        export_dir = project.project_path / "exports"
        export_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_format.lower() == "json":
            filename = f"{project.name}_session_{session.session_id}_export_{timestamp}.json"
            filepath = export_dir / filename
            
            # Load LSL data
            lsl_data = self._load_session_lsl_data(session, project)
            
            # Load video info
            video_info = self._load_session_video_info(session, project)
            
            export_data = {
                'export_type': 'session',
                'export_timestamp': datetime.now().isoformat(),
                'session': session.to_dict(),
                'lsl_data': lsl_data,
                'video_info': video_info
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
        
        elif export_format.lower() == "csv":
            filename = f"{project.name}_session_{session.session_id}_export_{timestamp}.csv"
            filepath = export_dir / filename
            
            # Load LSL data
            lsl_data = self._load_session_lsl_data(session, project)
            
            if not lsl_data or 'lsl_samples' not in lsl_data:
                raise ValueError(f"No LSL data found for session {session.session_id}")
            
            # Flatten LSL samples to CSV rows
            rows = self._lsl_samples_to_csv_rows(lsl_data['lsl_samples'], 
                                                 session_id=session.session_id,
                                                 session_name=session.name,
                                                 include_columns=include_columns)
            
            if not rows:
                raise ValueError(f"No data rows to export for session {session.session_id}")
            
            # Collect all possible fieldnames from all rows
            all_fieldnames = set()
            for row in rows:
                all_fieldnames.update(row.keys())
            fieldnames = sorted(all_fieldnames)
            
            # Write CSV
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        return filepath
    
    def export_project_data(self, project: Project, export_format: str = "json",
                           include_columns: Optional[List[str]] = None) -> Path:
        """Export complete project dataset (all sessions).
        
        Args:
            project: Project instance
            export_format: Export format ("json" or "csv")
            include_columns: For CSV, list of columns to include (None = all)
            
        Returns:
            Path to exported file
        """
        export_dir = project.project_path / "exports"
        export_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_format.lower() == "json":
            filename = f"{project.name}_export_{timestamp}.json"
            filepath = export_dir / filename
            
            export_data = {
                'export_type': 'project',
                'export_timestamp': datetime.now().isoformat(),
                'project': project.to_dict(),
                'sessions': []
            }
            
            # Load all sessions and their data
            for session_id in project.sessions:
                session = self._load_session_metadata(project, session_id)
                if session:
                    session_export = {
                        'session': session.to_dict(),
                        'lsl_data': self._load_session_lsl_data(session, project),
                        'video_info': self._load_session_video_info(session, project)
                    }
                    export_data['sessions'].append(session_export)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
        
        elif export_format.lower() == "csv":
            filename = f"{project.name}_export_{timestamp}.csv"
            filepath = export_dir / filename
            
            all_rows = []
            
            # Load all sessions and their data
            for session_id in project.sessions:
                session = self._load_session_metadata(project, session_id)
                if session:
                    lsl_data = self._load_session_lsl_data(session, project)
                    if lsl_data and 'lsl_samples' in lsl_data:
                        rows = self._lsl_samples_to_csv_rows(lsl_data['lsl_samples'],
                                                             session_id=session.session_id,
                                                             session_name=session.name,
                                                             include_columns=include_columns)
                        all_rows.extend(rows)
            
            if not all_rows:
                raise ValueError(f"No data rows to export for project {project.name}")
            
            # Collect all possible fieldnames from all rows
            all_fieldnames = set()
            for row in all_rows:
                all_fieldnames.update(row.keys())
            fieldnames = sorted(all_fieldnames)
            
            # Write CSV
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
        
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        return filepath
    
    def _flatten_dict(self, d: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """Recursively flatten a nested dictionary.
        
        Args:
            d: Dictionary to flatten
            prefix: Prefix for nested keys (e.g., 'data_' for nested data)
            
        Returns:
            Flattened dictionary with keys like 'data_key' or 'data_nested_key'
        """
        flattened = {}
        for key, value in d.items():
            new_key = f"{prefix}{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                nested = self._flatten_dict(value, prefix=f"{new_key}_")
                flattened.update(nested)
            elif isinstance(value, list):
                # For lists, convert to string or handle special cases
                if len(value) == 0:
                    flattened[new_key] = ''
                elif all(isinstance(item, (int, float)) for item in value):
                    # Numeric list - keep as is for now, will be handled separately
                    flattened[new_key] = value
                else:
                    # Mixed or complex list - convert to JSON string
                    flattened[new_key] = json.dumps(value)
            else:
                # Scalar value
                flattened[new_key] = value
        
        return flattened
    
    def _lsl_samples_to_csv_rows(self, lsl_samples: List[Dict[str, Any]],
                                 session_id: str, session_name: str,
                                 include_columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Convert LSL samples to CSV rows.
        
        Args:
            lsl_samples: List of LSL sample dictionaries
            session_id: Session ID to include in rows
            session_name: Session name to include in rows
            include_columns: List of columns to include (None = all)
            
        Returns:
            List of dictionaries suitable for CSV export
        """
        rows = []
        
        for sample in lsl_samples:
            row = {
                'session_id': session_id,
                'session_name': session_name,
                'timestamp': sample.get('timestamp'),
                'relative_time': sample.get('relative_time'),
                'stream_name': sample.get('stream_name', ''),
                'stream_type': sample.get('stream_type', ''),
                'clock_offset': sample.get('clock_offset'),
                'local_time_when_recorded': sample.get('local_time_when_recorded')
            }
            
            # Handle data field - can be various types
            data = sample.get('data', {})
            
            # If data is a dict (parsed JSON from bridge events), flatten it
            if isinstance(data, dict):
                # Add common event fields first
                row['event_type'] = data.get('type', '')
                row['wall_clock'] = data.get('wall_clock', '')
                
                # Get nested 'data' field if it exists and flatten it
                nested_data = data.get('data', {})
                if isinstance(nested_data, dict) and nested_data:
                    # Flatten nested data with 'data_' prefix
                    flattened_nested = self._flatten_dict(nested_data, prefix='data_')
                    row.update(flattened_nested)
                
                # Add any other top-level keys from data (excluding already handled ones)
                for key, value in data.items():
                    if key not in ['type', 'data', 'wall_clock', 'timestamp', 'lsl_timestamp']:
                        # Flatten if it's a dict, otherwise add directly
                        if isinstance(value, dict):
                            flattened_value = self._flatten_dict(value, prefix=f'{key}_')
                            row.update(flattened_value)
                        else:
                            row[f'data_{key}'] = value
            elif isinstance(data, list):
                # Numeric data (mouse tracking, etc.)
                # Convert list to comma-separated string or individual columns
                if len(data) == 1:
                    row['data_value'] = data[0]
                elif len(data) == 2:
                    row['data_x'] = data[0]
                    row['data_y'] = data[1]
                elif len(data) == 3:
                    row['data_x'] = data[0]
                    row['data_y'] = data[1]
                    row['data_z'] = data[2]
                else:
                    # For longer arrays, store as JSON string
                    row['data_array'] = json.dumps(data)
            else:
                # Scalar or other type
                row['data_value'] = str(data)
            
            # Filter columns if requested
            if include_columns:
                row = {k: v for k, v in row.items() if k in include_columns}
            
            rows.append(row)
        
        return rows
    
    def delete_project(self, project: Project) -> None:
        """Delete a project and all its data.
        
        Args:
            project: Project instance to delete
        """
        if self.current_project == project:
            self.current_project = None
        
        # Remove project directory
        shutil.rmtree(project.project_path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        return filename
    
    def _save_project_metadata(self, project: Project) -> None:
        """Save project metadata to file.
        
        Args:
            project: Project instance to save
        """
        metadata_file = project.project_path / "project.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, indent=2)
    
    def _save_session_metadata(self, project: Project, session: Session) -> None:
        """Save session metadata to file.
        
        Args:
            project: Project instance
            session: Session instance to save
        """
        session_dir = project.project_path / "sessions" / session.session_id
        session_dir.mkdir(exist_ok=True)
        
        metadata_file = session_dir / "session.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def _load_session_metadata(self, project: Project, session_id: str) -> Optional[Session]:
        """Load session metadata from file.
        
        Args:
            project: Project instance
            session_id: Session ID to load
            
        Returns:
            Session instance or None if not found
        """
        session_dir = project.project_path / "sessions" / session_id
        metadata_file = session_dir / "session.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None
    
    def _load_session_tracking_data(self, session: Session, project: Project) -> List[TrackingData]:
        """Load all tracking data for a session.
        
        Args:
            session: Session instance
            project: Project instance
            
        Returns:
            List of tracking data instances
        """
        tracking_data = []
        
        session_dir = self._get_session_dir(project, session)
        
        try:
            for data_file in session_dir.glob("tracking_*.json"):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tracking_data.append(TrackingData.from_dict(data))
        except Exception as e:
            print(f"Error loading tracking data for session {session.session_id}: {e}")
        
        # Sort by timestamp
        tracking_data.sort(key=lambda x: x.timestamp)
        return tracking_data
    
    def delete_session(self, project: Project, session_id: str) -> bool:
        """Delete a session from a project.
        
        Args:
            project: Project instance
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted successfully, False otherwise
        """
        try:
            # Remove session from project's session list
            if session_id in project.sessions:
                project.sessions.remove(session_id)
                project.modified_date = datetime.now()
                
                # Delete session directory and all its contents
                # All session data (including recordings) is in sessions/{session_id}/
                session_dir = project.project_path / "sessions" / session_id
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                
                # Save updated project metadata
                self._save_project_metadata(project)
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            return False
