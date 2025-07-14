import os
from typing import Dict, Any
from dotenv import load_dotenv

class Config:
    """Centralized configuration management for the agentic research system."""
    
    def __init__(self):
        load_dotenv()
        
        # Database configuration
        self.DATABASE_URL = os.getenv('DATABASE_URL', 'data/research.db')
        self.MAX_RESULTS_PER_QUERY = int(os.getenv('MAX_RESULTS_PER_QUERY', '1000'))
        
        # API configuration
        self.GOOGLE_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')
        self.RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '1.0'))
        
        # Memory and performance settings
        self.MAX_TEXT_SIZE = int(os.getenv('MAX_TEXT_SIZE', '10000000'))  # 10MB
        self.MAX_MEMORY_INCREASE = int(os.getenv('MAX_MEMORY_INCREASE', '500000000'))  # 500MB
        self.CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '3000'))
        self.MAX_CHUNKS = int(os.getenv('MAX_CHUNKS', '10'))
        
        # File operation settings
        self.FILE_RETRY_ATTEMPTS = int(os.getenv('FILE_RETRY_ATTEMPTS', '3'))
        self.FILE_RETRY_DELAY = float(os.getenv('FILE_RETRY_DELAY', '1.0'))
        
        # Validation settings
        self.SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.7'))
        self.MIN_VALIDATION_SOURCES = int(os.getenv('MIN_VALIDATION_SOURCES', '2'))
        
        # Target companies
        self.TARGET_COMPANIES = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", 
            "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Validate critical settings
        self._validate_config()
    
    def _validate_config(self):
        """Validate critical configuration settings."""
        if not self.GOOGLE_API_KEY or len(self.GOOGLE_API_KEY) < 10:
            print("⚠️  Warning: Invalid or missing Google Search API key")
        
        if not self.GOOGLE_CSE_ID or len(self.GOOGLE_CSE_ID) < 10:
            print("⚠️  Warning: Invalid or missing Google Custom Search Engine ID")
        
        if self.MAX_RESULTS_PER_QUERY <= 0:
            raise ValueError("MAX_RESULTS_PER_QUERY must be positive")
        
        if self.RATE_LIMIT_DELAY < 0:
            raise ValueError("RATE_LIMIT_DELAY must be non-negative")
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return {
            'url': self.DATABASE_URL,
            'max_results': self.MAX_RESULTS_PER_QUERY
        }
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return {
            'google_api_key': self.GOOGLE_API_KEY,
            'google_cse_id': self.GOOGLE_CSE_ID,
            'rate_limit_delay': self.RATE_LIMIT_DELAY
        }
    
    def get_memory_config(self) -> Dict[str, Any]:
        """Get memory management configuration."""
        return {
            'max_text_size': self.MAX_TEXT_SIZE,
            'max_memory_increase': self.MAX_MEMORY_INCREASE,
            'chunk_size': self.CHUNK_SIZE,
            'max_chunks': self.MAX_CHUNKS
        }
    
    def get_file_config(self) -> Dict[str, Any]:
        """Get file operation configuration."""
        return {
            'retry_attempts': self.FILE_RETRY_ATTEMPTS,
            'retry_delay': self.FILE_RETRY_DELAY
        }
    
    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration."""
        return {
            'similarity_threshold': self.SIMILARITY_THRESHOLD,
            'min_validation_sources': self.MIN_VALIDATION_SOURCES,
            'target_companies': self.TARGET_COMPANIES
        }

# Global configuration instance
config = Config() 