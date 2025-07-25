import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

def get_database_path():
    """Get the absolute path to the database file."""
    project_root = Path(__file__).parent.parent
    return project_root / "data" / "research.db"

class Config:
    """
    Configuration class to hold all settings and API keys.
    """
    # Data Extraction APIs
    SEC_API_KEY = os.getenv("SEC_API_KEY")
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
    SAM_API_KEY = os.getenv("SAM_API_KEY")

    # AI Analysis APIs (Azure AI Foundry)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = os.getenv("BASE_URL")
    PROJECT_ID = os.getenv("PROJECT_ID")
    API_VERSION = os.getenv("API_VERSION", "2024-02-15-preview")
    MODEL = os.getenv("MODEL", "gpt-4o")

    # Azure AI Foundry Agents for Bing Grounding
    PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
    MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
    AZURE_BING_CONNECTION_ID = os.getenv("AZURE_BING_CONNECTION_ID")

    # Validation APIs
    GOOGLE_SEARCH_API_KEY = os.getenv("Google_Search_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
    BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY") # For direct Bing API if not using Azure AI Foundry

    # System Settings
    DATABASE_PATH = str(get_database_path())
    REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Date Requirements (as per specifications)
    SEC_DAYS_BACK = 90  # 3 months for SEC filings
    SAM_DAYS_BACK = 60  # 2 months for SAM.gov notices
    NEWS_HOURS_BACK = 168  # 7 days for news articles
    
    # SAM.gov Scraper Settings
    SAM_NAICS_CODES = [
        "541511", "541512", "541611", "518210"
    ]
    SAM_KEYWORDS = [
        "artificial intelligence", "machine learning", "cloud", 
        "cybersecurity", "data analytics", "digital transformation"
    ]

    @classmethod
    def validate(cls):
        """
        Validates that essential API keys are configured.
        """
        required_keys = [
            "SEC_API_KEY", "GNEWS_API_KEY", 
            "OPENAI_API_KEY", "BASE_URL", "PROJECT_ID", "API_VERSION", "MODEL",
            "GOOGLE_SEARCH_API_KEY", "GOOGLE_CSE_ID",
            # Azure AI Foundry Agents keys - required for Bing grounding
            "PROJECT_ENDPOINT", "MODEL_DEPLOYMENT_NAME", "AZURE_BING_CONNECTION_ID"
        ]
        missing_keys = [key for key in required_keys if not getattr(cls, key)]
        
        if missing_keys:
            # Log a warning, but don't exit, as some paths might not need all keys
            print(f"⚠️  Warning: Missing some API keys in .env file: {', '.join(missing_keys)}")
            print("         Some functionalities might be limited.")
        
        print("✅ Configuration and API keys are loaded.")

# Instantiate the config
try:
    AppConfig = Config()
    AppConfig.validate()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    import sys
    sys.exit(1)