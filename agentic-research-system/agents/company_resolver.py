"""
Company name resolution and canonicalization service.
"""

import re
from typing import Tuple, Optional
from fuzzywuzzy import fuzz
from config.company_config import COMPANY_SLUGS, COMPANY_DISPLAY_NAMES

class CompanyResolver:
    """
    Resolves user input to canonical company slug with fuzzy matching.
    """
    
    def __init__(self):
        self.company_slugs = COMPANY_SLUGS
        self.display_names = COMPANY_DISPLAY_NAMES
    
    def resolve_company(self, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve user input to canonical company slug.
        
        Args:
            user_input: User's company name input
            
        Returns:
            Tuple of (canonical_slug, display_name) or (None, None) if not found
        """
        if not user_input:
            return None, None
            
        # Clean input
        cleaned_input = self._clean_input(user_input)
        
        # Direct match first
        if cleaned_input in self.company_slugs:
            slug = self.company_slugs[cleaned_input]
            return slug, self.display_names.get(slug)
        
        # Fuzzy matching
        best_match = None
        best_score = 0
        
        for input_variant, canonical_slug in self.company_slugs.items():
            score = fuzz.ratio(cleaned_input.lower(), input_variant.lower())
            if score > best_score and score >= 70:  # 70% threshold
                best_score = score
                best_match = canonical_slug
        
        if best_match:
            return best_match, self.display_names.get(best_match)
        
        return None, None
    
    def _clean_input(self, user_input: str) -> str:
        """Clean and normalize user input."""
        # Remove common words and punctuation
        cleaned = re.sub(r'[^\w\s]', '', user_input.lower())
        cleaned = re.sub(r'\b(briefing|on|for|about|company|corp|corporation|inc|llc)\b', '', cleaned)
        return cleaned.strip()
    
    def get_suggestions(self, partial_input: str) -> list:
        """Get company name suggestions for partial input."""
        if not partial_input:
            return []
        
        suggestions = []
        cleaned_input = self._clean_input(partial_input)
        
        for input_variant, canonical_slug in self.company_slugs.items():
            if cleaned_input in input_variant.lower():
                display_name = self.display_names.get(canonical_slug)
                if display_name not in suggestions:
                    suggestions.append(display_name)
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def get_display_name(self, canonical_slug: str) -> Optional[str]:
        """
        Get display name for a canonical slug.
        
        Args:
            canonical_slug: Canonical company slug
            
        Returns:
            Display name or None if not found
        """
        return self.display_names.get(canonical_slug)
    
    def get_profile(self, canonical_slug: str) -> Optional[dict]:
        """
        Get company profile for a canonical slug.
        
        Args:
            canonical_slug: Canonical company slug
            
        Returns:
            Company profile dictionary or None if not found
        """
        from services.profile_loader import ProfileLoader
        profile_loader = ProfileLoader()
        return profile_loader.load_company_profile(canonical_slug)
