#!/usr/bin/env python3
"""
Launch script for the Chainlit application with proper initialization.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'OPENAI_API_KEY',
        'BASE_URL',
        'PROJECT_ID',
        'API_VERSION',
        'MODEL',
        'PROJECT_ENDPOINT',
        'MODEL_DEPLOYMENT_NAME',
        'AZURE_BING_CONNECTION_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file")
        return False
    
    print("✅ Environment variables configured")
    return True

async def initialize_app_context():
    """Initialize the shared application context."""
    try:
        from services.app_context import app_context
        await app_context.initialize()
        print("✅ Application context initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize application context: {e}")
        return False

def main():
    """Main launch function."""
    print("🚀 Launching Company Intelligence Briefing System...")
    print("=" * 60)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Initialize app context
    try:
        asyncio.run(initialize_app_context())
    except Exception as e:
        print(f"❌ Failed to initialize application: {e}")
        sys.exit(1)
    
    # Launch Chainlit
    print("\n🌐 Starting Chainlit application...")
    print("📱 Access the application at: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop the application")
    print("=" * 60)
    
    try:
        # Change to chainlit_app directory
        os.chdir("chainlit_app")
        
        # Launch the app using chainlit run
        import subprocess
        
        # Set environment variables for proper imports
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{os.path.abspath('..')}:{env.get('PYTHONPATH', '')}"
        
        # Run chainlit directly
        result = subprocess.run([
            sys.executable, "-m", "chainlit", "run", "main.py", 
            "--host", "0.0.0.0", "--port", "8000"
        ], cwd=".", env=env)
        
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