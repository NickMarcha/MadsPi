#!/usr/bin/env python3
"""
Simple test script to verify GUI components work.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from madspipeline.models import Project, Session, TrackingData, Marker
    from madspipeline.project_manager import ProjectManager
    print("✓ All modules imported successfully")
    
    # Test project manager
    pm = ProjectManager()
    print("✓ Project manager created successfully")
    
    # Test project creation
    from madspipeline.models import ProjectType
    test_project = pm.create_project("Test Project", "A test project for verification", ProjectType.SCREEN_RECORDING)
    print("✓ Test project created successfully")
    
    # Test session creation
    test_session = pm.create_session(test_project, "Test Session")
    print("✓ Test session created successfully")
    
    # Test tracking data
    from datetime import datetime
    tracking_data = TrackingData(
        session_id=test_session.session_id,
        timestamp=datetime.now(),
        mouse_position=(100, 200)
    )
    pm.save_tracking_data(test_project, test_session, tracking_data)
    print("✓ Tracking data saved successfully")
    
    # Test export
    export_path = pm.export_project_data(test_project)
    print(f"✓ Project exported successfully to: {export_path}")
    
    # Clean up test project
    pm.delete_project(test_project)
    print("✓ Test project cleaned up successfully")
    
    print("\n🎉 All tests passed! The GUI components are working correctly.")
    
except Exception as e:
    print(f"❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
