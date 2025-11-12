"""
Project management functionality for MadsPipeline.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
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
        # Note: recordings folder removed - recordings are now stored in tracking_data/{session_id}/
        (project_path / "tracking_data").mkdir(exist_ok=True)
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
            from .models import EmbeddedWebpageConfig
            embedded_webpage_config = EmbeddedWebpageConfig(
                webpage_url=config.get('webpage_url') if config else None,
                local_html_path=Path(config.get('local_html_path')) if config and config.get('local_html_path') else None,
                enable_marker_api=config.get('enable_marker_api', True) if config else True,
                fullscreen=config.get('fullscreen', True) if config else True,
                allow_external_links=config.get('allow_external_links', False) if config else False
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
            sessions=[],
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
        project_path = Path(project_path)
        metadata_file = project_path / "project.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Project metadata not found at {metadata_file}")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        project = Project.from_dict(data)
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
        
        # Add session to project
        project.sessions.append(session_id)
        project.modified_date = now
        
        # Save session metadata
        self._save_session_metadata(project, session)
        self._save_project_metadata(project)
        
        return session
    
    def save_tracking_data(self, project: Project, session: Session, tracking_data: TrackingData) -> None:
        """Save tracking data for a session.
        
        Args:
            project: Project instance
            session: Session instance
            tracking_data: Tracking data to save
        """
        tracking_dir = project.project_path / "tracking_data" / session.session_id
        tracking_dir.mkdir(exist_ok=True)
        
        # Save individual tracking data point
        timestamp_str = tracking_data.timestamp.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"tracking_{timestamp_str}.json"
        filepath = tracking_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(tracking_data.to_dict(), f, indent=2)
        
        # Update session tracking data path if not set
        if session.tracking_data_path is None:
            session.tracking_data_path = tracking_dir
            self._save_session_metadata(project, session)
    
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
    
    def export_project_data(self, project: Project, export_format: str = "json") -> Path:
        """Export complete project dataset.
        
        Args:
            project: Project instance
            export_format: Export format ("json" or "csv")
            
        Returns:
            Path to exported file
        """
        export_dir = project.project_path / "exports"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_format.lower() == "json":
            filename = f"{project.name}_export_{timestamp}.json"
            filepath = export_dir / filename
            
            export_data = {
                'project': project.to_dict(),
                'sessions': [],
                'tracking_data': []
            }
            
            # Load all sessions and their data
            for session_id in project.sessions:
                session = self._load_session_metadata(project, session_id)
                if session:
                    export_data['sessions'].append(session.to_dict())
                    
                    # Load tracking data if available
                    if session.tracking_data_path:
                        tracking_data = self._load_session_tracking_data(session)
                        export_data['tracking_data'].extend([td.to_dict() for td in tracking_data])
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
        
        elif export_format.lower() == "csv":
            # TODO: Implement CSV export
            raise NotImplementedError("CSV export not yet implemented")
        
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        return filepath
    
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
    
    def _load_session_tracking_data(self, session: Session) -> List[TrackingData]:
        """Load all tracking data for a session.
        
        Args:
            session: Session instance
            
        Returns:
            List of tracking data instances
        """
        tracking_data = []
        
        if not session.tracking_data_path:
            return tracking_data
        
        try:
            for data_file in session.tracking_data_path.glob("tracking_*.json"):
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
                session_dir = project.project_path / "sessions" / session_id
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                
                # Delete tracking data directory
                tracking_dir = project.project_path / "tracking_data" / session_id
                if tracking_dir.exists():
                    shutil.rmtree(tracking_dir)
                
                # Save updated project metadata
                self._save_project_metadata(project)
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            return False
