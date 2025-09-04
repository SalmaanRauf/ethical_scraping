#!/usr/bin/env python3
"""
Debug script to troubleshoot environment variable loading.
Run this on your other computer to see what's happening with .env loading.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def debug_environment():
    print("🔍 Environment Variable Debug")
    print("=" * 50)
    
    # Check current working directory
    print(f"📁 Current working directory: {os.getcwd()}")
    
    # Check if .env file exists
    env_file = Path(".env")
    print(f"📄 .env file exists: {env_file.exists()}")
    if env_file.exists():
        print(f"📄 .env file size: {env_file.stat().st_size} bytes")
        print(f"📄 .env file path: {env_file.absolute()}")
    
    # Check .env.example
    env_example = Path(".env.example")
    print(f"📄 .env.example exists: {env_example.exists()}")
    
    # List all .env* files
    env_files = list(Path(".").glob(".env*"))
    print(f"📄 All .env* files: {[f.name for f in env_files]}")
    
    print("\n🔧 Before load_dotenv():")
    print("-" * 30)
    
    # Check environment variables before loading
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
    
    for var in required_vars:
        value = os.getenv(var)
        status = "✅ SET" if value else "❌ MISSING"
        # Show first few characters if set (for security)
        display_value = f"'{value[:10]}...'" if value and len(value) > 10 else f"'{value}'" if value else "None"
        print(f"{status} {var}: {display_value}")
    
    print("\n🔄 Loading .env file...")
    print("-" * 30)
    
    # Try to load .env file
    try:
        result = load_dotenv()
        print(f"✅ load_dotenv() result: {result}")
    except Exception as e:
        print(f"❌ load_dotenv() error: {e}")
    
    print("\n🔧 After load_dotenv():")
    print("-" * 30)
    
    # Check environment variables after loading
    for var in required_vars:
        value = os.getenv(var)
        status = "✅ SET" if value else "❌ MISSING"
        # Show first few characters if set (for security)
        display_value = f"'{value[:10]}...'" if value and len(value) > 10 else f"'{value}'" if value else "None"
        print(f"{status} {var}: {display_value}")
    
    print("\n📋 Sample .env file content (first 10 lines):")
    print("-" * 30)
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                lines = f.readlines()[:10]
                for i, line in enumerate(lines, 1):
                    # Mask sensitive values
                    if '=' in line and any(key in line for key in ['KEY', 'SECRET', 'PASSWORD']):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            masked_value = f"{parts[0]}=***MASKED***"
                            print(f"{i:2d}: {masked_value.strip()}")
                        else:
                            print(f"{i:2d}: {line.strip()}")
                    else:
                        print(f"{i:2d}: {line.strip()}")
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
    else:
        print("❌ .env file not found")
    
    print("\n" + "=" * 50)
    print("🔍 Debug complete!")

if __name__ == "__main__":
    debug_environment() 