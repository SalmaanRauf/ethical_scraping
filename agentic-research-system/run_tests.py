#!/usr/bin/env python3
"""
Comprehensive test runner for the Agentic Account Research System
Runs unit tests, integration tests, and component-specific tests.
"""

import os
import sys
import subprocess
from datetime import datetime

def run_command(command, description):
    """Run a command and return success status."""
    print(f"\n🔍 {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Command completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print("❌ Command failed")
            if result.stderr:
                print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False

def run_sec_extractor_tests():
    """Run SEC extractor specific tests."""
    print("\n📄 Running SEC Extractor Tests")
    print("=" * 50)
    
    # Run standalone SEC test
    success1 = run_command(
        "python test_sec_extractor_standalone.py",
        "Standalone SEC Extractor Test"
    )
    
    # Run unit tests
    success2 = run_command(
        "python -m pytest tests/test_sec_extractor.py -v",
        "SEC Extractor Unit Tests"
    )
    
    return success1 and success2

def run_comprehensive_tests():
    """Run the comprehensive test suite."""
    print("\n🧪 Running Comprehensive Test Suite")
    print("=" * 50)
    
    success = run_command(
        "python test_system.py",
        "Comprehensive System Test"
    )
    
    return success

def run_unit_tests():
    """Run all unit tests."""
    print("\n🧪 Running Unit Tests")
    print("=" * 50)
    
    # Check if pytest is available
    try:
        import pytest
        success = run_command(
            "python -m pytest tests/ -v",
            "All Unit Tests"
        )
        return success
    except ImportError:
        print("⚠️  pytest not available, skipping unit tests")
        return True

def main():
    """Main test runner."""
    print("🧪 Agentic Account Research System - Test Runner")
    print("=" * 60)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if we're in the right directory
    if not os.path.exists("extractors/sec_extractor.py"):
        print("❌ Please run this script from the project root directory")
        return
    
    # Run different types of tests
    tests = [
        ("SEC Extractor Tests", run_sec_extractor_tests),
        ("Unit Tests", run_unit_tests),
        ("Comprehensive Tests", run_comprehensive_tests),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🚀 Running {test_name}")
        print(f"{'='*60}")
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 Test Results Summary")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n📈 Overall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for use.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 