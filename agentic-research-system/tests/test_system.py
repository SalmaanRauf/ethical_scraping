#!/usr/bin/env python3
"""
Simple system test to verify all components are working.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all key components can be imported."""
    print("🧪 Testing imports...")
    
    try:
        from agents.company_resolver import CompanyResolver
        print("✅ CompanyResolver imported successfully")
    except Exception as e:
        print(f"❌ CompanyResolver import failed: {e}")
        return False
    
    try:
        from agents.single_company_workflow import SingleCompanyWorkflow
        print("✅ SingleCompanyWorkflow imported successfully")
    except Exception as e:
        print(f"❌ SingleCompanyWorkflow import failed: {e}")
        return False
    
    try:
        from services.profile_loader import ProfileLoader
        print("✅ ProfileLoader imported successfully")
    except Exception as e:
        print(f"❌ ProfileLoader import failed: {e}")
        return False
    
    try:
        from extractors.extractor_wrappers import SECExtractorWrapper
        print("✅ ExtractorWrappers imported successfully")
    except Exception as e:
        print(f"❌ ExtractorWrappers import failed: {e}")
        return False
    
    return True

def test_company_resolver():
    """Test company resolver functionality."""
    print("\n🔍 Testing company resolver...")
    
    try:
        from agents.company_resolver import CompanyResolver
        resolver = CompanyResolver()
        
        # Test direct match
        slug, display = resolver.resolve_company("Capital One")
        if slug == "Capital_One" and display == "Capital One Financial Corporation":
            print("✅ Company resolver working correctly")
            return True
        else:
            print(f"❌ Company resolver returned unexpected results: {slug}, {display}")
            return False
            
    except Exception as e:
        print(f"❌ Company resolver test failed: {e}")
        return False

def test_profile_loader():
    """Test profile loader functionality."""
    print("\n📁 Testing profile loader...")
    
    try:
        from services.profile_loader import ProfileLoader
        loader = ProfileLoader()
        
        # Test available profiles
        profiles = loader.get_available_profiles()
        if len(profiles) >= 7:  # Should have 7 company profiles
            print(f"✅ Profile loader found {len(profiles)} profiles")
            return True
        else:
            print(f"❌ Profile loader found only {len(profiles)} profiles, expected 7")
            return False
            
    except Exception as e:
        print(f"❌ Profile loader test failed: {e}")
        return False

def test_workflow_creation():
    """Test workflow creation (without execution)."""
    print("\n⚙️ Testing workflow creation...")
    
    try:
        from agents.single_company_workflow import SingleCompanyWorkflow
        workflow = SingleCompanyWorkflow()
        print("✅ Workflow created successfully")
        return True
    except Exception as e:
        print(f"❌ Workflow creation failed: {e}")
        return False

def main():
    """Run all system tests."""
    print("🚀 Running system tests...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_company_resolver,
        test_profile_loader,
        test_workflow_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to use.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)