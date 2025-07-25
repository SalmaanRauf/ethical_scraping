"""
Company profile loading and validation service.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
import logging

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ProfileLoader:
    """
    Loads and manages company profiles from JSON files.
    Implements caching to prevent multiple loads of the same profiles.
    """
    def __init__(self, profiles_dir: str = None):
        # Always resolve relative to the project root
        project_root = Path(__file__).parent.parent
        if profiles_dir is None:
            self.profiles_dir = project_root / "data" / "company_profiles"
        else:
            self.profiles_dir = Path(profiles_dir)
        
        self._validate_profiles_directory()
        
        # Add caching to prevent multiple loads
        self._profiles_cache = None
        self._regulatory_feeds_cache = None
        logger.info("🔍 ProfileLoader initialized with directory: %s", self.profiles_dir)

    def _validate_profiles_directory(self):
        """Ensure the profiles directory exists and contains profile files."""
        if not self.profiles_dir.exists():
            logger.warning("⚠️  Profiles directory not found: %s", self.profiles_dir)
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            logger.info("✅ Created profiles directory: %s", self.profiles_dir)
        
        profile_files = list(self.profiles_dir.glob("*_profile.json"))
        if not profile_files:
            logger.warning("⚠️  No profile files found in: %s", self.profiles_dir)
        else:
            logger.info("📁 Found %d profile files", len(profile_files))

    def load_company_profile(self, company_slug: str) -> Optional[Dict]:
        """
        Load a single company profile by slug.
        
        Args:
            company_slug: The company identifier (e.g., 'Capital_One')
            
        Returns:
            Profile dictionary or None if not found/invalid
        """
        profile_file = self.profiles_dir / f"{company_slug}_profile.json"
        
        if not profile_file.exists():
            logger.warning("⚠️  Profile file not found: %s", profile_file)
            return None
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            # Validate profile structure
            if self._validate_profile_structure(profile):
                logger.debug("✅ Loaded single profile: %s", company_slug)
                return profile
            else:
                logger.warning("⚠️  Invalid profile structure in %s", profile_file)
                return None
                
        except json.JSONDecodeError as e:
            logger.error("❌ Error loading profile %s: %s", profile_file, e)
            return None
        except Exception as e:
            logger.error("❌ Unexpected error loading profile %s: %s", profile_file, e)
            return None
    
    def load_profiles(self) -> Dict[str, Dict]:
        """
        Load all available company profiles into a dictionary.
        Uses caching to prevent multiple loads of the same data.
        
        Returns:
            Dictionary mapping company slugs to their profile data
        """
        # Return cached profiles if available
        if self._profiles_cache is not None:
            logger.debug("📋 Returning cached profiles (%d profiles)", len(self._profiles_cache))
            return self._profiles_cache
        
        logger.info("📋 Loading company profiles from: %s", self.profiles_dir)
        profiles = {}
        
        for profile_file in self.profiles_dir.glob("*_profile.json"):
            try:
                company_slug = profile_file.stem.replace("_profile", "")
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                
                if self._validate_profile_structure(profile):
                    profiles[company_slug] = profile
                    logger.debug("✅ Loaded profile for: %s", company_slug)
                else:
                    logger.warning("⚠️  Invalid profile structure in %s", profile_file)
                    
            except json.JSONDecodeError as e:
                logger.error("❌ Error loading profile %s: %s", profile_file, e)
            except Exception as e:
                logger.error("❌ Unexpected error loading profile %s: %s", profile_file, e)
        
        # Cache the results
        self._profiles_cache = profiles
        logger.info("📊 Loaded and cached %d company profiles", len(profiles))
        return profiles
    
    def clear_cache(self):
        """Clear the profiles cache to force reloading."""
        self._profiles_cache = None
        self._regulatory_feeds_cache = None
        logger.info("🗑️  Cleared profile cache")

    def _validate_profile_structure(self, profile: Dict) -> bool:
        """Validate profile has expected structure."""
        # For profiles that only have people/projects structure, add default fields
        if 'people' in profile and 'company_name' not in profile:
            # This is a legacy profile format, add default fields
            profile['company_name'] = 'Company Name'
            profile['industry'] = 'Financial Services'
            profile['revenue'] = 'N/A'
            profile['size'] = 'Large'
            profile['description'] = 'Financial services company'
            profile['website'] = 'N/A'
            profile['recent_stock_price'] = 'N/A'
            profile['key_personnel'] = []
            return True
        
        # For new profile format, check required fields
        required_fields = ['company_name', 'industry', 'revenue', 'size']
        for field in required_fields:
            if field not in profile:
                return False
        
        return True
    
    def get_available_profiles(self) -> list:
        """Get list of available company slugs."""
        profiles = []
        for profile_file in self.profiles_dir.glob("*_profile.json"):
            slug = profile_file.stem.replace("_profile", "")
            profiles.append(slug)
        return profiles
    
    def load_regulatory_feeds(self) -> Dict[str, str]:
        """
        Load regulatory RSS feeds for news monitoring.
        Uses caching to prevent multiple loads.
        
        Returns:
            Dictionary mapping feed names to their URLs
        """
        # Return cached feeds if available
        if self._regulatory_feeds_cache is not None:
            logger.debug("📡 Returning cached regulatory feeds")
            return self._regulatory_feeds_cache
        
        logger.info("📡 Loading regulatory feeds")
        regulatory_feeds = {
            "SEC": "https://www.sec.gov/news/pressreleases.rss",
            "FDIC": "https://www.fdic.gov/news/news/press/2024/index.xml",
            "OCC": "https://www.occ.gov/news-issuances/news-releases/index.xml",
            "Federal Reserve": "https://www.federalreserve.gov/feeds/press_bcreg.xml",
            "CFPB": "https://www.consumerfinance.gov/about-us/newsroom/feed/",
            "FinCEN": "https://www.fincen.gov/news/news-releases/feed"
        }
        
        # Cache the results
        self._regulatory_feeds_cache = regulatory_feeds
        logger.info("📡 Loaded and cached %d regulatory feeds", len(regulatory_feeds))
        return regulatory_feeds
