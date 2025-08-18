#!/usr/bin/env python3
"""
Test script to verify embedded webpage project creation works.
"""
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from madspipeline.models import ProjectType
from madspipeline.project_manager import ProjectManager

def test_embedded_webpage_creation():
    """Test creating an embedded webpage project."""
    try:
        # Create project manager
        pm = ProjectManager()
        
        # Create embedded webpage project
        project = pm.create_project(
            "Test Embedded Webpage",
            "A test embedded webpage project",
            ProjectType.EMBEDDED_WEBPAGE,
            {},  # Empty config
            None  # Default location
        )
        
        print(f"✅ Successfully created project: {project.name}")
        print(f"   Type: {project.project_type}")
        print(f"   Path: {project.project_path}")
        print(f"   Config: {project.embedded_webpage_config}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create project: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing embedded webpage project creation...")
    success = test_embedded_webpage_creation()
    
    if success:
        print("\n🎉 Test passed! Embedded webpage projects can be created successfully.")
    else:
        print("\n💥 Test failed! There's still an issue with embedded webpage project creation.")
        sys.exit(1)

