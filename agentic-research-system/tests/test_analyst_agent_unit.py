#!/usr/bin/env python3
"""
Unit tests for AnalystAgent
Tests all functionality without making API calls using mocks.
"""

import unittest
import os
import sys
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.analyst_agent import AnalystAgent


class TestAnalystAgent(unittest.TestCase):
    """Test cases for AnalystAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test_openai_key_12345',
            'BASE_URL': 'https://api.openai.com/v1',
            'PROJECT_ID': 'test_project',
            'API_VERSION': '2024-01-01',
            'MODEL': 'gpt-4'
        })
        self.env_patcher.start()
        
        # Mock the kernel setup
        self.kernel_patcher = patch('agents.analyst_agent.get_kernel')
        self.mock_kernel = self.kernel_patcher.start()
        
        # Create mock kernel and functions
        self.mock_kernel_instance = Mock()
        self.mock_functions = {}
        self.mock_kernel.return_value = (self.mock_kernel_instance, {})
        
        # Create analyst agent instance
        self.analyst = AnalystAgent(chunk_size=1000, chunk_overlap=200, max_chunks=5)
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.kernel_patcher.stop()
    
    def test_initialization_with_custom_parameters(self):
        """Test that AnalystAgent initializes correctly with custom parameters."""
        analyst = AnalystAgent(chunk_size=2000, chunk_overlap=300, max_chunks=8)
        
        self.assertEqual(analyst.chunk_size, 2000)
        self.assertEqual(analyst.chunk_overlap, 300)
        self.assertEqual(analyst.max_chunks, 8)
        self.assertIsNotNone(analyst.kernel)
        self.assertIsNotNone(analyst.functions)
    
    def test_initialization_with_default_parameters(self):
        """Test that AnalystAgent initializes correctly with default parameters."""
        analyst = AnalystAgent()
        
        self.assertEqual(analyst.chunk_size, 3000)
        self.assertEqual(analyst.chunk_overlap, 500)
        self.assertEqual(analyst.max_chunks, 10)
    
    @patch('agents.analyst_agent.get_kernel')
    def test_function_loading_success(self, mock_get_kernel):
        """Test successful loading of Semantic Kernel functions."""
        # Mock kernel and functions
        mock_kernel = Mock()
        mock_functions = {
            'triage': Mock(),
            'financial': Mock(),
            'procurement': Mock(),
            'earnings': Mock(),
            'insight': Mock()
        }
        
        # Configure mock to return functions
        def mock_add_function(*args, **kwargs):
            function_name = kwargs.get('function_name', args[1])
            return mock_functions.get(function_name, Mock())
        
        mock_kernel.add_function.side_effect = mock_add_function
        mock_get_kernel.return_value = (mock_kernel, {})
        
        # Create analyst agent
        analyst = AnalystAgent()
        
        # Verify functions were loaded
        self.assertIn('triage', analyst.functions)
        self.assertIn('financial', analyst.functions)
        self.assertIn('procurement', analyst.functions)
        self.assertIn('earnings', analyst.functions)
        self.assertIn('insight', analyst.functions)
    
    @patch('agents.analyst_agent.get_kernel')
    def test_function_loading_failure(self, mock_get_kernel):
        """Test handling of function loading failures."""
        # Mock kernel to raise exception
        mock_kernel = Mock()
        mock_kernel.add_function.side_effect = Exception("Function loading failed")
        mock_get_kernel.return_value = (mock_kernel, {})
        
        # Should raise exception
        with self.assertRaises(Exception):
            AnalystAgent()
    
    def test_create_intelligent_chunks_small_text(self):
        """Test chunking of small text that doesn't need chunking."""
        text = "This is a short text that doesn't need chunking."
        chunks = self.analyst._create_intelligent_chunks(text, chunk_size=100)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)
    
    def test_create_intelligent_chunks_large_text(self):
        """Test chunking of large text with intelligent breaks."""
        # Create a long text with sentence boundaries
        text = "First sentence. Second sentence with more content. Third sentence. Fourth sentence. Fifth sentence."
        text = text * 50  # Make it long enough to need chunking
        
        chunks = self.analyst._create_intelligent_chunks(text, chunk_size=200, overlap=50)
        
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks), 5)  # max_chunks limit
        
        # Verify chunks don't exceed size limit
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 250)  # chunk_size + some buffer
    
    def test_create_intelligent_chunks_with_overlap(self):
        """Test that chunks have proper overlap."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        text = text * 20  # Make it long
        
        chunks = self.analyst._create_intelligent_chunks(text, chunk_size=100, overlap=30)
        
        if len(chunks) > 1:
            # Check that consecutive chunks have overlap
            for i in range(len(chunks) - 1):
                chunk1 = chunks[i]
                chunk2 = chunks[i + 1]
                
                # Should have some overlap
                self.assertTrue(
                    chunk1[-20:] in chunk2 or chunk2[:20] in chunk1,
                    f"Chunks {i} and {i+1} don't have proper overlap"
                )
    
    def test_extract_key_terms(self):
        """Test extraction of key terms from text."""
        text = "Capital One announced a $50 million investment in fintech. The deal involves Navy Federal Credit Union."
        
        key_terms = self.analyst._extract_key_terms(text)
        
        # Should find company names
        self.assertIn("Capital One", key_terms)
        self.assertIn("Navy Federal", key_terms)
        
        # Should find dollar amounts
        self.assertIn("$50 million", key_terms)
        
        # Should find action words
        self.assertIn("announced", key_terms)
        self.assertIn("investment", key_terms)
    
    def test_extract_key_terms_no_matches(self):
        """Test key term extraction with no matches."""
        text = "This is a generic text without any specific financial terms or company names."
        
        key_terms = self.analyst._extract_key_terms(text)
        
        # Should return empty list or very few terms
        self.assertIsInstance(key_terms, list)
    
    def test_prioritize_chunks(self):
        """Test chunk prioritization based on key terms."""
        chunks = [
            "This is a generic chunk with no important terms.",
            "Capital One announced a $100 million deal.",
            "Another generic chunk.",
            "Fannie Mae reported earnings of $500 million.",
            "Yet another generic chunk."
        ]
        
        prioritized = self.analyst._prioritize_chunks(chunks)
        
        # Should prioritize chunks with company names and dollar amounts
        self.assertEqual(len(prioritized), len(chunks))
        
        # First chunk should have highest score (Capital One + $100M)
        self.assertIn("Capital One", prioritized[0])
        self.assertIn("$100 million", prioritized[0])
        
        # Second chunk should have second highest score (Fannie Mae + $500M)
        self.assertIn("Fannie Mae", prioritized[1])
        self.assertIn("$500 million", prioritized[1])
    
    def test_prioritize_chunks_empty_list(self):
        """Test prioritization of empty chunk list."""
        prioritized = self.analyst._prioritize_chunks([])
        self.assertEqual(prioritized, [])
    
    @patch('agents.analyst_agent.AnalystAgent._analyze_single_chunk')
    async def test_analyze_chunks_with_map_reduce_success(self, mock_analyze_chunk):
        """Test successful map-reduce analysis of chunks."""
        # Mock chunk analysis results
        mock_analyze_chunk.side_effect = [
            {
                'chunk_index': 0,
                'chunk_text': 'Capital One announced $100M deal',
                'result': {'event_found': True, 'event_type': 'Investment', 'value_usd': 100000000},
                'key_terms': ['Capital One', '$100M', 'deal']
            },
            {
                'chunk_index': 1,
                'chunk_text': 'Fannie Mae reported earnings',
                'result': {'event_found': True, 'event_type': 'Earnings', 'value_usd': 50000000},
                'key_terms': ['Fannie Mae', 'earnings']
            },
            None  # One chunk with no relevant info
        ]
        
        chunks = [
            "Capital One announced a $100 million investment in fintech.",
            "Fannie Mae reported strong earnings for Q4.",
            "This is a generic chunk with no relevant information."
        ]
        
        # Mock the kernel functions
        self.analyst.functions = {'financial': Mock()}
        
        result = await self.analyst._analyze_chunks_with_map_reduce(chunks, 'financial')
        
        # Should return synthesized results
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify chunks were analyzed
        self.assertEqual(mock_analyze_chunk.call_count, 3)
    
    @patch('agents.analyst_agent.AnalystAgent._analyze_single_chunk')
    async def test_analyze_chunks_with_map_reduce_no_results(self, mock_analyze_chunk):
        """Test map-reduce analysis when no chunks have relevant information."""
        # Mock all chunks returning None
        mock_analyze_chunk.return_value = None
        
        chunks = [
            "This is a generic chunk with no relevant information.",
            "Another generic chunk.",
            "Yet another generic chunk."
        ]
        
        # Mock the kernel functions
        self.analyst.functions = {'financial': Mock()}
        
        result = await self.analyst._analyze_chunks_with_map_reduce(chunks, 'financial')
        
        # Should return empty list
        self.assertEqual(result, [])
    
    def test_synthesize_chunk_results_procurement(self):
        """Test synthesis of procurement results."""
        chunk_results = [
            {
                'chunk_index': 0,
                'result': {'event_found': True, 'event_type': 'Procurement', 'value_usd': 15000000}
            },
            {
                'chunk_index': 1,
                'result': {'event_found': True, 'event_type': 'Procurement', 'value_usd': 25000000}
            }
        ]
        
        result = self.analyst._synthesize_chunk_results(chunk_results, 'procurement')
        
        # Should return all relevant results for procurement
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r.get('event_found', False) for r in result))
    
    def test_synthesize_chunk_results_earnings(self):
        """Test synthesis of earnings results."""
        chunk_results = [
            {
                'chunk_index': 0,
                'result': {'event_found': True, 'event_type': 'Earnings', 'value_usd': 50000000}
            }
        ]
        
        result = self.analyst._synthesize_chunk_results(chunk_results, 'earnings')
        
        # Should return all relevant results for earnings
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].get('event_found', False))
    
    def test_synthesize_chunk_results_financial(self):
        """Test synthesis of financial results (should return first result)."""
        chunk_results = [
            {
                'chunk_index': 0,
                'result': {'event_found': True, 'event_type': 'Investment', 'value_usd': 100000000}
            },
            {
                'chunk_index': 1,
                'result': {'event_found': True, 'event_type': 'Investment', 'value_usd': 50000000}
            }
        ]
        
        result = self.analyst._synthesize_chunk_results(chunk_results, 'financial')
        
        # Should return first result for financial analysis
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event_type'], 'Investment')
    
    def test_synthesize_chunk_results_empty(self):
        """Test synthesis with empty chunk results."""
        result = self.analyst._synthesize_chunk_results([], 'financial')
        self.assertEqual(result, [])
    
    @patch('agents.analyst_agent.AnalystAgent._analyze_chunks_with_map_reduce')
    async def test_analyze_financial_events(self, mock_analyze_chunks):
        """Test analysis of financial events."""
        # Mock chunk analysis results
        mock_analyze_chunks.return_value = [
            {
                'synthesized_result': {
                    'event_found': True,
                    'event_type': 'Investment',
                    'value_usd': 100000000,
                    'summary': 'Capital One invests $100M in fintech'
                }
            }
        ]
        
        items = [
            {
                'company': 'Capital One',
                'title': 'Capital One Announces Major Investment',
                'text': 'Capital One announced a $100 million investment in fintech startup.',
                'source': 'news',
                'type': 'news'
            }
        ]
        
        result = await self.analyst.analyze_financial_events(items)
        
        # Should return financial analysis results
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify chunk analysis was called
        mock_analyze_chunks.assert_called_once()
    
    @patch('agents.analyst_agent.AnalystAgent._analyze_chunks_with_map_reduce')
    async def test_analyze_procurement(self, mock_analyze_chunks):
        """Test analysis of procurement notices."""
        # Mock chunk analysis results
        mock_analyze_chunks.return_value = [
            {
                'synthesized_result': {
                    'event_found': True,
                    'event_type': 'Procurement',
                    'value_usd': 15000000,
                    'summary': 'Navy Federal seeks IT consulting services'
                }
            }
        ]
        
        items = [
            {
                'company': 'Navy Federal Credit Union',
                'title': 'IT Consulting Services RFP',
                'text': 'Navy Federal Credit Union is seeking IT consulting services worth $15M.',
                'source': 'procurement',
                'type': 'procurement'
            }
        ]
        
        result = await self.analyst.analyze_procurement(items)
        
        # Should return procurement analysis results
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify chunk analysis was called
        mock_analyze_chunks.assert_called_once()
    
    @patch('agents.analyst_agent.AnalystAgent._analyze_chunks_with_map_reduce')
    async def test_analyze_earnings_calls(self, mock_analyze_chunks):
        """Test analysis of earnings call transcripts."""
        # Mock chunk analysis results
        mock_analyze_chunks.return_value = [
            {
                'synthesized_result': {
                    'event_found': True,
                    'event_type': 'Earnings',
                    'value_usd': 50000000,
                    'summary': 'Capital One reports strong Q4 earnings'
                }
            }
        ]
        
        items = [
            {
                'company': 'Capital One',
                'title': 'Capital One Q4 Earnings Call Transcript',
                'text': 'Capital One reported strong Q4 earnings with $50M in new initiatives.',
                'source': 'SEC',
                'type': 'filing'
            }
        ]
        
        result = await self.analyst.analyze_earnings_calls(items)
        
        # Should return earnings analysis results
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Verify chunk analysis was called
        mock_analyze_chunks.assert_called_once()
    
    @patch('agents.analyst_agent.AnalystAgent.generate_insights')
    async def test_analyze_all_data_integration(self, mock_generate_insights):
        """Test the complete analysis workflow."""
        # Mock insight generation
        mock_generate_insights.return_value = [
            {
                'company': 'Capital One',
                'headline': 'Capital One Announces Major Investment',
                'insights': {
                    'what_happened': 'Capital One invested $100M in fintech',
                    'why_it_matters': 'Shows commitment to digital transformation',
                    'consulting_angle': 'Opportunity for fintech consulting services'
                },
                'financial_analysis': {
                    'event_type': 'Investment',
                    'value_usd': 100000000
                }
            }
        ]
        
        # Mock the individual analysis methods
        with patch.object(self.analyst, 'analyze_financial_events') as mock_financial, \
             patch.object(self.analyst, 'analyze_procurement') as mock_procurement, \
             patch.object(self.analyst, 'analyze_earnings_calls') as mock_earnings:
            
            mock_financial.return_value = [{'event_type': 'Investment', 'value_usd': 100000000}]
            mock_procurement.return_value = []
            mock_earnings.return_value = []
            
            data_items = [
                {
                    'company': 'Capital One',
                    'title': 'Capital One Announces Major Investment',
                    'text': 'Capital One announced a $100 million investment in fintech startup.',
                    'source': 'news',
                    'type': 'news'
                }
            ]
            
            result = await self.analyst.analyze_all_data(data_items)
            
            # Should return complete analysis results
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            
            # Verify all analysis methods were called
            mock_financial.assert_called_once()
            mock_procurement.assert_called_once()
            mock_earnings.assert_called_once()
            mock_generate_insights.assert_called_once()


def run_unit_tests():
    """Run all unit tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAnalystAgent)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_unit_tests()
    if success:
        print("\n✅ All unit tests passed!")
    else:
        print("\n❌ Some unit tests failed!")
        exit(1) 