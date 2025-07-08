#!/usr/bin/env python3
"""
Unit tests for SEC Extractor
Tests API connectivity, data processing, and error handling.
"""

import unittest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.sec_extractor import SECExtractor


class TestSECExtractor(unittest.TestCase):
    """Test cases for SEC Extractor functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'SEC_API_KEY': 'test_api_key_12345'
        })
        self.env_patcher.start()
        
        # Create extractor instance
        self.extractor = SECExtractor()
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
    
    def test_initialization_with_api_key(self):
        """Test that SECExtractor initializes correctly with API key."""
        self.assertIsNotNone(self.extractor.api_key)
        self.assertEqual(self.extractor.api_key, 'test_api_key_12345')
        self.assertIsNotNone(self.extractor.query_api)
        self.assertIsNotNone(self.extractor.extractor_api)
    
    def test_initialization_without_api_key(self):
        """Test that SECExtractor handles missing API key gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            extractor = SECExtractor()
            self.assertIsNone(extractor.api_key)
    
    def test_target_tickers_configuration(self):
        """Test that target tickers are correctly configured."""
        expected_tickers = {
            "COF": "Capital One Financial Corp",
            "FMCC": "Federal Home Loan Mortgage Corp",
            "FNMA": "Federal National Mortgage Association",
            "EGBN": "Eagle Bancorp Inc",
            "CBNK": "Capital Bancorp Inc"
        }
        
        self.assertEqual(self.extractor.target_tickers, expected_tickers)
        self.assertIn("COF", self.extractor.target_tickers)
        self.assertIn("FMCC", self.extractor.target_tickers)
    
    def test_query_building(self):
        """Test that queries are built correctly."""
        # Test ticker list building
        ticker_list = " OR ".join([f'ticker:"{ticker}"' for ticker in self.extractor.target_tickers.keys()])
        
        expected_tickers = ['ticker:"COF"', 'ticker:"FMCC"', 'ticker:"FNMA"', 'ticker:"EGBN"', 'ticker:"CBNK"']
        for ticker in expected_tickers:
            self.assertIn(ticker, ticker_list)
    
    @patch('extractors.sec_extractor.QueryApi')
    def test_get_filings_and_text_success(self, mock_query_api):
        """Test successful API call and data extraction."""
        # Mock API response
        mock_response = {
            'filings': [
                {
                    'companyName': 'Capital One Financial Corp',
                    'ticker': 'COF',
                    'formType': '8-K',
                    'filedAt': '2024-01-15T10:30:00Z',
                    'linkToFilingDetails': 'https://www.sec.gov/Archives/edgar/data/0000927628/000092762824000001/cof-20240115.htm',
                    'extractedText': 'This is a test filing content for Capital One.'
                },
                {
                    'companyName': 'Federal Home Loan Mortgage Corp',
                    'ticker': 'FMCC',
                    'formType': '10-Q',
                    'filedAt': '2024-01-14T09:15:00Z',
                    'linkToFilingDetails': 'https://www.sec.gov/Archives/edgar/data/0001026214/000102621424000001/fmcc-20240114.htm',
                    'extractedText': 'This is a test filing content for Freddie Mac.'
                }
            ]
        }
        
        # Configure mock
        mock_instance = Mock()
        mock_instance.get_filings.return_value = mock_response
        mock_query_api.return_value = mock_instance
        
        # Test the method
        result = self.extractor.get_filings_and_text()
        
        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['company'], 'Capital One Financial Corp')
        self.assertEqual(result[0]['ticker'], 'COF')
        self.assertEqual(result[0]['type'], '8-K')
        self.assertEqual(result[0]['source'], 'SEC')
        self.assertEqual(result[0]['data_type'], 'filing')
        
        # Verify API was called
        mock_instance.get_filings.assert_called_once()
    
    @patch('extractors.sec_extractor.QueryApi')
    def test_get_filings_and_text_api_error(self, mock_query_api):
        """Test handling of API errors."""
        # Configure mock to raise exception
        mock_instance = Mock()
        mock_instance.get_filings.side_effect = Exception("API Error")
        mock_query_api.return_value = mock_instance
        
        # Test the method
        result = self.extractor.get_filings_and_text()
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    @patch('extractors.sec_extractor.QueryApi')
    def test_get_filings_and_text_no_api_key(self, mock_query_api):
        """Test behavior when no API key is available."""
        # Create extractor without API key
        with patch.dict(os.environ, {}, clear=True):
            extractor = SECExtractor()
            result = extractor.get_filings_and_text()
            self.assertEqual(result, [])
    
    @patch('extractors.sec_extractor.QueryApi')
    def test_get_recent_filings_with_date_range(self, mock_query_api):
        """Test recent filings with date range filtering."""
        # Mock API response
        mock_response = {
            'filings': [
                {
                    'companyName': 'Capital One Financial Corp',
                    'ticker': 'COF',
                    'formType': '8-K',
                    'filedAt': '2024-01-15T10:30:00Z',
                    'linkToFilingDetails': 'https://www.sec.gov/Archives/edgar/data/0000927628/000092762824000001/cof-20240115.htm',
                    'extractedText': 'Recent filing content.'
                }
            ]
        }
        
        # Configure mock
        mock_instance = Mock()
        mock_instance.get_filings.return_value = mock_response
        mock_query_api.return_value = mock_instance
        
        # Test with 7 days back
        result = self.extractor.get_recent_filings(days_back=7)
        
        # Verify results
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['company'], 'Capital One Financial Corp')
        
        # Verify API was called with date range
        mock_instance.get_filings.assert_called_once()
        call_args = mock_instance.get_filings.call_args[0][0]
        self.assertIn('filedAt:[', str(call_args))
    
    def test_data_structure_consistency(self):
        """Test that extracted data has consistent structure."""
        sample_filing = {
            'companyName': 'Test Company',
            'ticker': 'TEST',
            'formType': '8-K',
            'filedAt': '2024-01-15T10:30:00Z',
            'linkToFilingDetails': 'https://example.com',
            'extractedText': 'Test content'
        }
        
        # Simulate processing
        processed_data = {
            'company': sample_filing.get('companyName', ''),
            'ticker': sample_filing.get('ticker', ''),
            'type': sample_filing.get('formType', ''),
            'filedAt': sample_filing.get('filedAt', ''),
            'link': sample_filing.get('linkToFilingDetails', ''),
            'text': sample_filing.get('extractedText', ''),
            'source': 'SEC',
            'data_type': 'filing'
        }
        
        # Verify required fields
        required_fields = ['company', 'ticker', 'type', 'filedAt', 'link', 'text', 'source', 'data_type']
        for field in required_fields:
            self.assertIn(field, processed_data)
        
        # Verify data types
        self.assertIsInstance(processed_data['company'], str)
        self.assertIsInstance(processed_data['ticker'], str)
        self.assertIsInstance(processed_data['type'], str)
        self.assertIsInstance(processed_data['text'], str)
        self.assertEqual(processed_data['source'], 'SEC')
        self.assertEqual(processed_data['data_type'], 'filing')
    
    @patch('extractors.sec_extractor.QueryApi')
    def test_individual_filing_processing_error(self, mock_query_api):
        """Test that individual filing processing errors don't break the entire process."""
        # Mock API response with one problematic filing
        mock_response = {
            'filings': [
                {
                    'companyName': 'Capital One Financial Corp',
                    'ticker': 'COF',
                    'formType': '8-K',
                    'filedAt': '2024-01-15T10:30:00Z',
                    'linkToFilingDetails': 'https://www.sec.gov/Archives/edgar/data/0000927628/000092762824000001/cof-20240115.htm',
                    'extractedText': 'Valid filing content.'
                },
                {
                    # Missing required fields - should cause processing error
                    'companyName': 'Problem Company'
                    # Missing other fields
                }
            ]
        }
        
        # Configure mock
        mock_instance = Mock()
        mock_instance.get_filings.return_value = mock_response
        mock_query_api.return_value = mock_instance
        
        # Test the method
        result = self.extractor.get_filings_and_text()
        
        # Should return the valid filing, skip the problematic one
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['company'], 'Capital One Financial Corp')


class TestSECExtractorIntegration(unittest.TestCase):
    """Integration tests for SEC Extractor with real API calls."""
    
    def setUp(self):
        """Set up test fixtures for integration tests."""
        self.extractor = SECExtractor()
    
    def test_api_key_validation(self):
        """Test that API key is valid and accessible."""
        if not self.extractor.api_key:
            self.skipTest("SEC_API_KEY not available")
        
        self.assertIsNotNone(self.extractor.api_key)
        self.assertGreater(len(self.extractor.api_key), 0)
    
    def test_api_connectivity(self):
        """Test that we can connect to the SEC API."""
        if not self.extractor.api_key:
            self.skipTest("SEC_API_KEY not available")
        
        try:
            # Test a simple query to verify connectivity
            query = {
                "query": {
                    "query_string": {
                        "query": 'ticker:"COF" AND formType:"8-K"'
                    }
                },
                "from": "0",
                "size": "1"
            }
            
            result = self.extractor.query_api.get_filings(query)
            self.assertIsNotNone(result)
            self.assertIn('filings', result)
            
        except Exception as e:
            self.fail(f"API connectivity test failed: {e}")
    
    def test_small_data_extraction(self):
        """Test extracting a small amount of real data."""
        if not self.extractor.api_key:
            self.skipTest("SEC_API_KEY not available")
        
        try:
            # Get a small number of filings
            result = self.extractor.get_recent_filings(days_back=1)
            
            # Verify structure
            if result:
                self.assertIsInstance(result, list)
                for filing in result:
                    self.assertIn('company', filing)
                    self.assertIn('ticker', filing)
                    self.assertIn('type', filing)
                    self.assertIn('source', filing)
                    self.assertEqual(filing['source'], 'SEC')
            
        except Exception as e:
            self.fail(f"Data extraction test failed: {e}")


def run_unit_tests():
    """Run all unit tests."""
    print("🧪 Running SEC Extractor Unit Tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)


def run_integration_tests():
    """Run integration tests."""
    print("🔗 Running SEC Extractor Integration Tests...")
    
    # Create test suite for integration tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSECExtractorIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run unit tests
    run_unit_tests()
    
    # Run integration tests
    print("\n" + "="*50)
    run_integration_tests() 