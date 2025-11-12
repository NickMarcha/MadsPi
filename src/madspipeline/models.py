"""
Data models for the MadsPipeline application.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum
import json


class ProjectType(Enum):
    """Types of projects supported by the pipeline."""
    PICTURE_SLIDESHOW = "picture_slideshow"
    VIDEO = "video"
    SCREEN_RECORDING = "screen_recording"
    EMBEDDED_WEBPAGE = "embedded_webpage"


@dataclass
class PictureSlideshowConfig:
    """Configuration for picture slideshow projects."""
    images: List[Path] = field(default_factory=list)
    auto_play: bool = True
    slide_duration: float = 5.0  # seconds per slide
    manual_navigation: bool = False
    transition_effect: str = "fade"  # fade, slide, none


@dataclass
class VideoConfig:
    """Configuration for video projects."""
    video_path: Optional[Path] = None
    auto_play: bool = True
    loop: bool = False
    start_time: float = 0.0
    end_time: Optional[float] = None


@dataclass
class ScreenRecordingConfig:
    """Configuration for screen recording projects."""
    recording_quality: str = "high"  # low, medium, high
    fps: int = 30
    resolution: Optional[tuple[int, int]] = None  # None for fullscreen
    include_audio: bool = False
    mouse_tracking: bool = True


@dataclass
class EmbeddedWebpageConfig:
    """Configuration for embedded webpage projects."""
    webpage_url: Optional[str] = None
    local_html_path: Optional[Path] = None
    enable_marker_api: bool = True
    fullscreen: bool = True
    allow_external_links: bool = False
    window_size: Optional[tuple[int, int]] = None  # (width, height) - enforced window size for consistent data alignment
    enforce_fullscreen: bool = False  # If True, forces fullscreen mode (overrides window_size)
    normalize_mouse_coordinates: bool = True  # If True, mouse positions are normalized (0-1) relative to window size


@dataclass
class Project:
    """Represents a project with multiple sessions."""
    name: str
    description: str
    project_type: ProjectType
    created_date: datetime
    modified_date: datetime
    project_path: Path
    sessions: List[str] = field(default_factory=list)  # List of session IDs
    
    # Type-specific configuration
    picture_slideshow_config: Optional[PictureSlideshowConfig] = None
    video_config: Optional[VideoConfig] = None
    screen_recording_config: Optional[ScreenRecordingConfig] = None
    embedded_webpage_config: Optional[EmbeddedWebpageConfig] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization."""
        config_data = {}
        if self.picture_slideshow_config:
            config_data['picture_slideshow'] = {
                'images': [str(img) for img in self.picture_slideshow_config.images],
                'auto_play': self.picture_slideshow_config.auto_play,
                'slide_duration': self.picture_slideshow_config.slide_duration,
                'manual_navigation': self.picture_slideshow_config.manual_navigation,
                'transition_effect': self.picture_slideshow_config.transition_effect
            }
        elif self.video_config:
            config_data['video'] = {
                'video_path': str(self.video_config.video_path) if self.video_config.video_path else None,
                'auto_play': self.video_config.auto_play,
                'loop': self.video_config.loop,
                'start_time': self.video_config.start_time,
                'end_time': self.video_config.end_time
            }
        elif self.screen_recording_config:
            config_data['screen_recording'] = {
                'recording_quality': self.screen_recording_config.recording_quality,
                'fps': self.screen_recording_config.fps,
                'resolution': self.screen_recording_config.resolution,
                'include_audio': self.screen_recording_config.include_audio,
                'mouse_tracking': self.screen_recording_config.mouse_tracking
            }
        elif self.embedded_webpage_config:
            config_data['embedded_webpage'] = {
                'webpage_url': self.embedded_webpage_config.webpage_url,
                'local_html_path': str(self.embedded_webpage_config.local_html_path) if self.embedded_webpage_config.local_html_path else None,
                'enable_marker_api': self.embedded_webpage_config.enable_marker_api,
                'fullscreen': self.embedded_webpage_config.fullscreen,
                'allow_external_links': self.embedded_webpage_config.allow_external_links,
                'window_size': self.embedded_webpage_config.window_size,
                'enforce_fullscreen': self.embedded_webpage_config.enforce_fullscreen,
                'normalize_mouse_coordinates': self.embedded_webpage_config.normalize_mouse_coordinates
            }
        
        return {
            'name': self.name,
            'description': self.description,
            'project_type': self.project_type.value,
            'created_date': self.created_date.isoformat(),
            'modified_date': self.modified_date.isoformat(),
            'project_path': str(self.project_path),
            'sessions': self.sessions,
            'config': config_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary."""
        project_type = ProjectType(data['project_type'])
        
        # Initialize type-specific configs
        picture_slideshow_config = None
        video_config = None
        screen_recording_config = None
        embedded_webpage_config = None
        
        config_data = data.get('config', {})
        
        if project_type == ProjectType.PICTURE_SLIDESHOW and 'picture_slideshow' in config_data:
            config = config_data['picture_slideshow']
            picture_slideshow_config = PictureSlideshowConfig(
                images=[Path(img) for img in config.get('images', [])],
                auto_play=config.get('auto_play', True),
                slide_duration=config.get('slide_duration', 5.0),
                manual_navigation=config.get('manual_navigation', False),
                transition_effect=config.get('transition_effect', 'fade')
            )
        elif project_type == ProjectType.VIDEO and 'video' in config_data:
            config = config_data['video']
            video_config = VideoConfig(
                video_path=Path(config['video_path']) if config.get('video_path') else None,
                auto_play=config.get('auto_play', True),
                loop=config.get('loop', False),
                start_time=config.get('start_time', 0.0),
                end_time=config.get('end_time')
            )
        elif project_type == ProjectType.SCREEN_RECORDING and 'screen_recording' in config_data:
            config = config_data['screen_recording']
            screen_recording_config = ScreenRecordingConfig(
                recording_quality=config.get('recording_quality', 'high'),
                fps=config.get('fps', 30),
                resolution=config.get('resolution'),
                include_audio=config.get('include_audio', False),
                mouse_tracking=config.get('mouse_tracking', True)
            )
        elif project_type == ProjectType.EMBEDDED_WEBPAGE and 'embedded_webpage' in config_data:
            config = config_data['embedded_webpage']
            embedded_webpage_config = EmbeddedWebpageConfig(
                webpage_url=config.get('webpage_url'),
                local_html_path=Path(config['local_html_path']) if config.get('local_html_path') else None,
                enable_marker_api=config.get('enable_marker_api', True),
                fullscreen=config.get('fullscreen', True),
                allow_external_links=config.get('allow_external_links', False),
                window_size=tuple(config['window_size']) if config.get('window_size') else None,
                enforce_fullscreen=config.get('enforce_fullscreen', False),
                normalize_mouse_coordinates=config.get('normalize_mouse_coordinates', True)
            )
        
        return cls(
            name=data['name'],
            description=data['description'],
            project_type=project_type,
            created_date=datetime.fromisoformat(data['created_date']),
            modified_date=datetime.fromisoformat(data['modified_date']),
            project_path=Path(data['project_path']),
            sessions=data.get('sessions', []),
            picture_slideshow_config=picture_slideshow_config,
            video_config=video_config,
            screen_recording_config=screen_recording_config,
            embedded_webpage_config=embedded_webpage_config
        )


@dataclass
class Session:
    """Represents a recording session."""
    session_id: str
    name: str
    created_date: datetime
    modified_date: datetime = field(default_factory=datetime.now)
    duration: Optional[float] = None  # Duration in seconds
    recording_path: Optional[Path] = None
    tracking_data_path: Optional[Path] = None
    markers: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'name': self.name,
            'created_date': self.created_date.isoformat(),
            'modified_date': self.modified_date.isoformat(),
            'duration': self.duration,
            'recording_path': str(self.recording_path) if self.recording_path else None,
            'tracking_data_path': str(self.tracking_data_path) if self.tracking_data_path else None,
            'markers': self.markers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create session from dictionary."""
        return cls(
            session_id=data['session_id'],
            name=data['name'],
            created_date=datetime.fromisoformat(data['created_date']),
            modified_date=datetime.fromisoformat(data.get('modified_date', data['created_date'])),
            duration=data.get('duration'),
            recording_path=Path(data['recording_path']) if data.get('recording_path') else None,
            tracking_data_path=Path(data['tracking_data_path']) if data.get('tracking_data_path') else None,
            markers=data.get('markers', [])
        )


@dataclass
class TrackingData:
    """Represents tracking data for a session."""
    session_id: str
    timestamp: datetime
    mouse_position: Optional[tuple[int, int]] = None
    mouse_events: List[Dict[str, Any]] = field(default_factory=list)
    # Future: eye tracking, heart rate, EDA data
    eye_tracking: Optional[Dict[str, Any]] = None
    heart_rate: Optional[float] = None
    eda: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tracking data to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'mouse_position': self.mouse_position,
            'mouse_events': self.mouse_events,
            'eye_tracking': self.eye_tracking,
            'heart_rate': self.heart_rate,
            'eda': self.eda
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrackingData':
        """Create tracking data from dictionary."""
        return cls(
            session_id=data['session_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            mouse_position=data.get('mouse_position'),
            mouse_events=data.get('mouse_events', []),
            eye_tracking=data.get('eye_tracking'),
            heart_rate=data.get('heart_rate'),
            eda=data.get('eda')
        )


@dataclass
class Marker:
    """Represents a custom event marker."""
    marker_id: str
    session_id: str
    timestamp: float  # Time in seconds from session start
    label: str
    description: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert marker to dictionary for serialization."""
        return {
            'marker_id': self.marker_id,
            'session_id': self.session_id,
            'timestamp': self.timestamp,
            'label': self.label,
            'description': self.description,
            'category': self.category,
            'color': self.color
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Marker':
        """Create marker from dictionary."""
        return cls(
            marker_id=data['marker_id'],
            session_id=data['session_id'],
            timestamp=data['timestamp'],
            label=data['label'],
            description=data.get('description'),
            category=data.get('category'),
            color=data.get('color')
        )
