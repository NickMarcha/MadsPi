"""
MadsPipeline - Data Streaming and Visualization Pipeline

A tool for collecting and analyzing eye tracking, heart rate, and electrodermal activity data
during visual data story interactions.
"""

__version__ = "1.0.0"
__author__ = "MadsPipeline Team"

# Import local modules using relative imports
from .models import Project, Session, TrackingData, Marker
from .project_manager import ProjectManager
from .main_window import MainWindow

__all__ = [
    "Project",
    "Session", 
    "TrackingData",
    "Marker",
    "ProjectManager",
    "MainWindow"
]
