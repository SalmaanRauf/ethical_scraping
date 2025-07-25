"""
Company profile loading and validation service.
"""

import json
import os
from typing import Dict, Optional
from pathlib import Path

class ProfileLoader:
    """
    Loads and validates company profiles from JSON files.
    """
    
    def __init__(self, profiles_dir: str = None):
        # Always resolve relative to the project root
        project_root = Path(__file__).parent.parent
        if profiles_dir is None:
            profiles_dir = project_root / "data" / "company_profiles"
        else:
            profiles_dir = Path(profiles_dir)
        self.profiles_dir = profiles_dir
        self._validate_profiles_directory()
    
    def _validate_profiles_directory(self):
        """Ensure profiles directory exists and contains expected files."""
        if not self.profiles_dir.exists():
            raise FileNotFoundError(f"Profiles directory not found: {self.profiles_dir}")
        
        # Check for expected profile files
        expected_profiles = [
            "Capital_One_profile.json",
            "Fannie_Mae_profile.json", 
            "Freddie_Mac_profile.json",
            "Navy_Federal_Credit_Union_profile.json",
            "PenFed_Credit_Union_profile.json",
            "Eagle_Bank_profile.json",
            "Capital_Bank_N.A._profile.json"
        ]
        
        missing_profiles = []
        for profile in expected_profiles:
            if not (self.profiles_dir / profile).exists():
                missing_profiles.append(profile)
        
        if missing_profiles:
            print(f"Warning: Missing profile files: {missing_profiles}")
    
    def load_company_profile(self, company_slug: str) -> Optional[Dict]:
        """
        Load company profile by slug.
        
        Args:
            company_slug: Canonical company slug (e.g., "Capital_One")
            
        Returns:
            Company profile dictionary or None if not found
        """
        profile_file = self.profiles_dir / f"{company_slug}_profile.json"
        
        if not profile_file.exists():
            print(f"Warning: Profile file not found: {profile_file}")
            return None
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            # Validate profile structure
            if self._validate_profile_structure(profile):
                return profile
            else:
                print(f"Warning: Invalid profile structure in {profile_file}")
                return None
                
        except json.JSONDecodeError as e:
            print(f"Error loading profile {profile_file}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error loading profile {profile_file}: {e}")
            return None
    
    def load_profiles(self) -> Dict[str, Dict]:
        """
        Load all available company profiles into a dictionary.
        
        Returns:
            Dictionary mapping company slugs to their profile data
        """
        profiles = {}
        for profile_file in self.profiles_dir.glob("*_profile.json"):
            try:
                company_slug = profile_file.stem.replace("_profile", "")
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                
                if self._validate_profile_structure(profile):
                    profiles[company_slug] = profile
                    print(f"✅ Loaded profile for: {company_slug}")
                else:
                    print(f"⚠️  Invalid profile structure in {profile_file}")
                    
            except json.JSONDecodeError as e:
                print(f"❌ Error loading profile {profile_file}: {e}")
            except Exception as e:
                print(f"❌ Unexpected error loading profile {profile_file}: {e}")
        
        print(f"📊 Loaded {len(profiles)} company profiles")
        return profiles
    
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
        
        Returns:
            Dictionary mapping feed names to their URLs
        """
        regulatory_feeds = {
            "SEC": "https://www.sec.gov/news/pressreleases.rss",
            "FDIC": "https://www.fdic.gov/news/news/press/2024/index.xml",
            "OCC": "https://www.occ.gov/news-issuances/news-releases/index.xml",
            "Federal Reserve": "https://www.federalreserve.gov/feeds/press_bcreg.xml",
            "CFPB": "https://www.consumerfinance.gov/about-us/newsroom/feed/",
            "FinCEN": "https://www.fincen.gov/news/news-releases/feed"
        }
        return regulatory_feeds
