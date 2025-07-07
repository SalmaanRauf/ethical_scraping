#!/usr/bin/env python3
"""
Test the new folder structure and imports
"""

def test_import_structure():
    """Test that the new folder structure works."""
    print("🧪 Testing new folder structure...")
    
    # Test extractors folder
    try:
        import extractors
        print("✅ extractors folder exists")
    except ImportError as e:
        print(f"❌ extractors folder issue: {e}")
    
    # Test agents folder
    try:
        import agents
        print("✅ agents folder exists")
    except ImportError as e:
        print(f"❌ agents folder issue: {e}")
    
    # Test that extractors are separate from agents
    try:
        import extractors.sam_extractor
        print("✅ sam_extractor in extractors folder")
    except ImportError as e:
        print(f"❌ sam_extractor import issue: {e}")
    
    try:
        import agents.analyst_agent
        print("✅ analyst_agent in agents folder")
    except ImportError as e:
        print(f"❌ analyst_agent import issue: {e}")

if __name__ == "__main__":
    test_import_structure()
    print("\n✅ Structure test complete!")
    print("💡 Note: Full functionality requires dependencies to be installed.") 