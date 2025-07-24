#!/usr/bin/env python3
"""
Fix Chainlit config file issue.
This script removes the outdated Chainlit config file so it can be regenerated.
"""

import os
import shutil
from pathlib import Path

def fix_chainlit_config():
    """Remove outdated Chainlit config file."""
    
    # Path to the Chainlit config file
    config_path = Path("chainlit_app/.chainlit/config.toml")
    
    print("🔧 Fixing Chainlit config file...")
    print(f"📁 Looking for config file: {config_path}")
    
    if config_path.exists():
        print(f"✅ Found config file, removing: {config_path}")
        try:
            config_path.unlink()
            print("✅ Config file removed successfully")
        except Exception as e:
            print(f"❌ Error removing config file: {e}")
            return False
    else:
        print("ℹ️  Config file not found, nothing to remove")
    
    # Also check for the .chainlit directory
    chainlit_dir = Path("chainlit_app/.chainlit")
    if chainlit_dir.exists():
        print(f"📁 Found .chainlit directory: {chainlit_dir}")
        # List contents
        try:
            contents = list(chainlit_dir.iterdir())
            print(f"📄 Directory contents: {[f.name for f in contents]}")
        except Exception as e:
            print(f"❌ Error listing directory: {e}")
    
    print("\n✅ Chainlit config fix complete!")
    print("🚀 You can now run: python launch_chainlit.py")
    
    return True

if __name__ == "__main__":
    fix_chainlit_config() 