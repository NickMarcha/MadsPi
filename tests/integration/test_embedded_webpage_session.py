#!/usr/bin/env python3
"""
Test script for embedded webpage session functionality.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from madspipeline.models import Project, ProjectType, EmbeddedWebpageConfig
    from madspipeline.project_manager import ProjectManager
    print("✓ All modules imported successfully")
    
    # Test project manager
    pm = ProjectManager()
    print("✓ Project manager created successfully")
    
    # Test embedded webpage project creation
    config = EmbeddedWebpageConfig(
        webpage_url="https://www.example.com",  # Test with external URL
        local_html_path=Path(__file__).parent.parent / "fixtures" / "test_webpage.html",  # Test with local file
        enable_marker_api=True,
        fullscreen=True,
        allow_external_links=False
    )
    
    test_project = pm.create_project(
        "Test Embedded Webpage", 
        "A test project for embedded webpage sessions", 
        ProjectType.EMBEDDED_WEBPAGE,
        config={
            'webpage_url': config.webpage_url,
            'local_html_path': str(config.local_html_path),
            'enable_marker_api': config.enable_marker_api,
            'fullscreen': config.fullscreen,
            'allow_external_links': config.allow_external_links
        }
    )
    print("✓ Test embedded webpage project created successfully")
    
    # Test session creation
    test_session = pm.create_session(test_project, "Test Webpage Session")
    print("✓ Test session created successfully")
    
    print(f"✓ Project path: {test_project.project_path}")
    print(f"✓ Session ID: {test_session.session_id}")
    print(f"✓ Webpage config: {test_project.embedded_webpage_config}")
    
    print("\n🎉 All tests passed! The embedded webpage session functionality is working correctly.")
    print("\nTo test the full functionality:")
    print("1. Run the main application: python src/madspipeline/main.py")
    print("2. Open the 'Test Embedded Webpage' project")
    print("3. Click 'Start New Session'")
    print("4. Enter a session name and click 'Start Session'")
    print("5. The webpage should load and tracking should begin")
    print("6. Close the session window to end and save the session")
    
except Exception as e:
    print(f"❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

