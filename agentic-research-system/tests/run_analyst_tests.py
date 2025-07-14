#!/usr/bin/env python3
"""
Test runner for AnalystAgent tests
Runs both unit tests and integration tests.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_unit_tests():
    """Run the unit tests for AnalystAgent."""
    print("🧪 Running AnalystAgent Unit Tests")
    print("=" * 50)
    
    try:
        # Import and run unit tests
        from test_analyst_agent_unit import run_unit_tests
        success = run_unit_tests()
        
        if success:
            print("✅ Unit tests completed successfully!")
        else:
            print("❌ Unit tests failed!")
        
        return success
        
    except Exception as e:
        print(f"❌ Error running unit tests: {e}")
        return False


def run_integration_tests():
    """Run the integration tests for AnalystAgent."""
    print("🧪 Running AnalystAgent Integration Tests")
    print("=" * 50)
    
    try:
        # Import and run integration tests
        from test_analyst_agent_integration import TestAnalystAgentIntegration
        import asyncio
        
        async def run_tests():
            tester = TestAnalystAgentIntegration()
            return await tester.run_all_tests()
        
        success = asyncio.run(run_tests())
        
        if success:
            print("✅ Integration tests completed successfully!")
        else:
            print("❌ Integration tests failed!")
        
        return success
        
    except Exception as e:
        print(f"❌ Error running integration tests: {e}")
        return False


def run_all_tests():
    """Run both unit and integration tests."""
    print("🚀 Running All AnalystAgent Tests")
    print("=" * 50)
    
    # Run unit tests first
    unit_success = run_unit_tests()
    
    print("\n" + "=" * 50)
    
    # Run integration tests
    integration_success = run_integration_tests()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    print(f"Unit Tests: {'✅ PASSED' if unit_success else '❌ FAILED'}")
    print(f"Integration Tests: {'✅ PASSED' if integration_success else '❌ FAILED'}")
    
    overall_success = unit_success and integration_success
    
    if overall_success:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED!")
    
    return overall_success


def check_environment():
    """Check if environment is properly set up for testing."""
    print("🔧 Checking test environment...")
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    if not (current_dir / "tests").exists():
        print("❌ Please run this script from the agentic-research-system directory")
        return False
    
    # Check for required files
    required_files = [
        "tests/test_analyst_agent_unit.py",
        "tests/test_analyst_agent_integration.py",
        "agents/analyst_agent.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    # Check for environment variables (for integration tests)
    required_vars = [
        'OPENAI_API_KEY',
        'GNEWS_API_KEY',
        'SEC_API_KEY',
        'SAM_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing environment variables for integration tests: {missing_vars}")
        print("   Unit tests will still run, but integration tests may fail")
    
    print("✅ Environment check completed")
    return True


def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(description='Run AnalystAgent tests')
    parser.add_argument(
        '--unit-only',
        action='store_true',
        help='Run only unit tests'
    )
    parser.add_argument(
        '--integration-only',
        action='store_true',
        help='Run only integration tests'
    )
    parser.add_argument(
        '--skip-env-check',
        action='store_true',
        help='Skip environment check'
    )
    
    args = parser.parse_args()
    
    # Check environment unless skipped
    if not args.skip_env_check:
        if not check_environment():
            print("❌ Environment check failed. Exiting.")
            return 1
    
    # Run tests based on arguments
    if args.unit_only:
        success = run_unit_tests()
    elif args.integration_only:
        success = run_integration_tests()
    else:
        success = run_all_tests()
    
    return 0 if success else 1


if __name__ == '__main__':
    exit_code = main()
    exit(exit_code) 