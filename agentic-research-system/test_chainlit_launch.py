#!/usr/bin/env python3
"""
Simple test to check if Chainlit launches correctly.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_chainlit_launch():
    """Test if Chainlit can be launched."""
    try:
        # Change to chainlit_app directory
        os.chdir("chainlit_app")
        
        # Set environment variables for proper imports
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{os.path.abspath('..')}:{env.get('PYTHONPATH', '')}"
        
        print("🧪 Testing Chainlit launch...")
        print(f"PYTHONPATH: {env['PYTHONPATH']}")
        print(f"Current directory: {os.getcwd()}")
        
        # Try to run chainlit with a timeout
        result = subprocess.run([
            sys.executable, "-m", "chainlit", "run", "main.py", 
            "--host", "0.0.0.0", "--port", "8000"
        ], cwd=".", env=env, timeout=10)
        
        print(f"Chainlit process exited with code: {result.returncode}")
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("✅ Chainlit launched successfully (timeout reached)")
        return True
    except Exception as e:
        print(f"❌ Error launching Chainlit: {e}")
        return False

if __name__ == "__main__":
    success = test_chainlit_launch()
    sys.exit(0 if success else 1) 