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
    (This app path uses only Azure/OpenAI keys; others remain optional.)
    """
    # AI Analysis APIs (Azure AI Foundry/ATLAS)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = os.getenv("BASE_URL")
    PROJECT_ID = os.getenv("PROJECT_ID")
    API_VERSION = os.getenv("API_VERSION", "2024-02-15-preview")
    MODEL = os.getenv("MODEL", "gpt-4o")

    # Azure AI Foundry Agents for Bing Grounding
    PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
    MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME")
    AZURE_BING_CONNECTION_ID = os.getenv("AZURE_BING_CONNECTION_ID")

    @classmethod
    def validate(cls):
        required_keys = [
            "OPENAI_API_KEY", "BASE_URL", "PROJECT_ID", "API_VERSION", "MODEL",
            "PROJECT_ENDPOINT", "MODEL_DEPLOYMENT_NAME", "AZURE_BING_CONNECTION_ID",
        ]
        missing_keys = [key for key in required_keys if not getattr(cls, key)]
        if missing_keys:
            print(f"⚠️  Warning: Missing some API keys in .env file: {', '.join(missing_keys)}")
        print("✅ Configuration and API keys are loaded.")

# Instantiate the config
try:
    AppConfig = Config()
    AppConfig.validate()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    import sys
    sys.exit(1)

