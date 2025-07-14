#!/usr/bin/env python3
"""
Test configuration helper for the agentic research system.

This file helps set up the environment for testing with sample configurations.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path (go up one level from tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_test_environment():
    """Setup the test environment with sample configurations."""
    
    # Load existing .env file if it exists
    load_dotenv()
    
    # Check if we need to create a sample .env file
    if not os.path.exists('.env'):
        print("📝 Creating sample .env file for testing...")
        create_sample_env()
    
    # Validate environment
    validate_test_environment()

def create_sample_env():
    """Create a sample .env file for testing."""
    sample_env_content = """# Agentic Research System - Test Configuration

# Database Configuration
DATABASE_URL=data/research.db
MAX_RESULTS_PER_QUERY=1000

# API Configuration (Replace with your actual keys for full testing)
GOOGLE_SEARCH_API_KEY=your_google_search_api_key_here
GOOGLE_CSE_ID=your_google_cse_id_here

# Rate Limiting
RATE_LIMIT_DELAY=1.0

# Memory Management
MAX_TEXT_SIZE=10000000
MAX_MEMORY_INCREASE=500000000
CHUNK_SIZE=3000
MAX_CHUNKS=10

# File Operations
FILE_RETRY_ATTEMPTS=3
FILE_RETRY_DELAY=1.0

# Validation
SIMILARITY_THRESHOLD=0.7
MIN_VALIDATION_SOURCES=2

# Note: For full testing, you need:
# 1. Google Search API key from: https://developers.google.com/custom-search/v1/overview
# 2. Google Custom Search Engine ID from: https://cse.google.com/
"""
    
    with open('.env', 'w') as f:
        f.write(sample_env_content)
    
    print("✅ Sample .env file created")
    print("⚠️  Please update with your actual API keys for full testing")

def validate_test_environment():
    """Validate the test environment."""
    print("\n🔍 Validating Test Environment...")
    
    # Check required directories
    required_dirs = ['data', 'reports', 'tests']
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✅ Created directory: {dir_name}")
        else:
            print(f"✅ Directory exists: {dir_name}")
    
    # Check .env file
    if os.path.exists('.env'):
        print("✅ .env file exists")
    else:
        print("⚠️  .env file missing")
    
    # Check API keys
    load_dotenv()
    google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
    google_cse_id = os.getenv('GOOGLE_CSE_ID')
    
    if google_api_key and google_api_key != 'your_google_search_api_key_here':
        print("✅ Google Search API key configured")
    else:
        print("⚠️  Google Search API key not configured (will use test data)")
    
    if google_cse_id and google_cse_id != 'your_google_cse_id_here':
        print("✅ Google CSE ID configured")
    else:
        print("⚠️  Google CSE ID not configured (will use test data)")
    
    print("\n📋 Test Environment Summary:")
    print("-" * 30)
    print("✅ Directories: Ready")
    if google_api_key and google_cse_id and google_api_key != 'your_google_search_api_key_here':
        print("✅ API Keys: Configured (will make real API calls)")
    else:
        print("⚠️  API Keys: Not configured (will use test data)")
    print("✅ Ready to run tests")

def get_test_config():
    """Get test-specific configuration."""
    return {
        'use_real_apis': False,  # Set to True when API keys are configured
        'test_data_size': 5,     # Number of test items to create
        'timeout_seconds': 30,   # Timeout for API calls
        'verbose_output': True   # Enable detailed output
    }

if __name__ == "__main__":
    setup_test_environment() 