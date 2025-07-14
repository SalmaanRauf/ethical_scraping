#!/usr/bin/env python3
"""
Simple runner for the workflow integration test.

Usage:
    python run_workflow_test.py
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to the Python path (go up one level from tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_workflow_integration import WorkflowIntegrationTest

def main():
    """Run the workflow integration test."""
    print("🚀 Agentic Research System - Workflow Integration Test")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Run the test
        test = WorkflowIntegrationTest()
        asyncio.run(test.run_full_workflow_test())
        
        print("\n✅ Test completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return 1
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 