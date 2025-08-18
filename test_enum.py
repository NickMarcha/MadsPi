#!/usr/bin/env python3
"""
Test script to verify that ProjectType enum is working correctly.
"""
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_enum():
    """Test that ProjectType enum is accessible and working."""
    try:
        from madspipeline.models import ProjectType
        
        print("✅ ProjectType enum imported successfully")
        print(f"   Available values: {[e.value for e in ProjectType]}")
        print(f"   EMBEDDED_WEBPAGE: {ProjectType.EMBEDDED_WEBPAGE}")
        print(f"   EMBEDDED_WEBPAGE.value: {ProjectType.EMBEDDED_WEBPAGE.value}")
        
        # Test enum comparison
        test_type = ProjectType.EMBEDDED_WEBPAGE
        if test_type == ProjectType.EMBEDDED_WEBPAGE:
            print("✅ Enum comparison works correctly")
        else:
            print("❌ Enum comparison failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to import or use ProjectType: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing ProjectType enum...")
    success = test_enum()
    
    if success:
        print("\n🎉 Test passed! ProjectType enum is working correctly.")
    else:
        print("\n💥 Test failed! There's an issue with the ProjectType enum.")
        sys.exit(1)

