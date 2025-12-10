#!/usr/bin/env python3
"""
Launch script for the Demo Chainlit application.
This is a simulation for video demo purposes - no real backend required.
"""

import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

def open_browser():
    """Open browser after a short delay to let server start."""
    time.sleep(2)  # Wait for server to start
    webbrowser.open("http://localhost:8000")

def main():
    """Main launch function."""
    print("🚀 Launching Protiviti Account Research Demo...")
    print("=" * 60)
    print("\n🌐 Starting Chainlit application...")
    print("📱 Opening browser at: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop the application")
    print("=" * 60)
    
    try:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent.resolve()
        chainlit_app_dir = script_dir / "chainlit_app"
        
        # Change to chainlit_app directory
        os.chdir(chainlit_app_dir)
        
        # Launch the app using chainlit run
        import subprocess
        
        # Set environment variables for proper imports
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{script_dir}:{env.get('PYTHONPATH', '')}"
        
        # Start browser opener in background thread
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # Run chainlit on localhost
        result = subprocess.run([
            sys.executable, "-m", "chainlit", "run", "main.py", 
            "--host", "localhost", "--port", "8000"
        ], cwd=str(chainlit_app_dir), env=env)
        
        if result.returncode != 0:
            print(f"❌ Chainlit exited with code {result.returncode}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
    except Exception as e:
        print(f"❌ Error launching application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
