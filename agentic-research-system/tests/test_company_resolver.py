"""
Unit tests for company resolver functionality.
"""

import unittest
from agents.company_resolver import CompanyResolver

class TestCompanyResolver(unittest.TestCase):
    
    def setUp(self):
        self.resolver = CompanyResolver()
    
    def test_direct_match(self):
        """Test direct company name matching."""
        slug, display = self.resolver.resolve_company("Capital One")
        self.assertEqual(slug, "Capital_One")
        self.assertEqual(display, "Capital One Financial Corporation")
    
    def test_fuzzy_match(self):
        """Test fuzzy matching for similar names."""
        slug, display = self.resolver.resolve_company("CapitalOne")
        self.assertEqual(slug, "Capital_One")
    
    def test_no_match(self):
        """Test handling of unknown company names."""
        slug, display = self.resolver.resolve_company("Unknown Company")
        self.assertIsNone(slug)
        self.assertIsNone(display)
    
    def test_suggestions(self):
        """Test company name suggestions."""
        suggestions = self.resolver.get_suggestions("Capital")
        self.assertIn("Capital One Financial Corporation", suggestions)

if __name__ == '__main__':
    unittest.main()
