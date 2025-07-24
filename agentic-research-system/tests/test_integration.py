"""
Integration tests for complete single-company workflow.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from agents.company_resolver import CompanyResolver
from agents.single_company_workflow import SingleCompanyWorkflow
from services.profile_loader import ProfileLoader

class TestCompleteWorkflow:
    """Test complete workflow from user input to briefing output."""
    
    @pytest.fixture
    def setup_workflow(self):
        """Setup workflow with mocked components."""
        workflow = SingleCompanyWorkflow()
        return workflow
    
    @pytest.mark.asyncio
    async def test_complete_capital_one_workflow(self, setup_workflow):
        """Test complete workflow for Capital One."""
        
        with patch('agents.single_company_workflow.SECExtractor') as mock_sec, \
             patch('agents.single_company_workflow.SAMExtractor') as mock_sam, \
             patch('agents.single_company_workflow.NewsExtractor') as mock_news, \
             patch('agents.single_company_workflow.BingGroundingAgent') as mock_bing:
            
            # Mock extractor responses
            mock_sec.return_value.get_recent_filings.return_value = [
                {'title': '10-K Filing', 'company': 'Capital One Financial Corp'}
            ]
            mock_sam.return_value.get_all_notices.return_value = [
                {'title': 'Procurement Notice', 'description': 'Capital One contract'}
            ]
            mock_news.return_value.get_all_news.return_value = [
                {'title': 'Capital One News', 'company': 'Capital One Financial Corp'}
            ]
            mock_bing.return_value.get_industry_briefing.return_value = {
                'summary': 'Financial services industry overview',
                'citations_md': 'Source: Industry Report'
            }
            
            # Execute workflow
            result = await setup_workflow.execute("Capital_One")
            
            # Verify result structure
            assert 'status' in result
            assert 'company_slug' in result
            assert result['company_slug'] == "Capital_One"
    
    @pytest.mark.asyncio
    async def test_workflow_with_missing_profile(self, setup_workflow):
        """Test workflow when company profile is missing."""
        
        with patch('services.profile_loader.ProfileLoader.load_company_profile') as mock_load:
            mock_load.return_value = None
            
            result = await setup_workflow.execute("Unknown_Company")
            
            # Should still complete with empty profile
            assert result['status'] in ['success', 'partial_success']
    
    @pytest.mark.asyncio
    async def test_workflow_with_extractor_failures(self, setup_workflow):
        """Test workflow when some extractors fail."""
        
        with patch('agents.single_company_workflow.SECExtractor') as mock_sec, \
             patch('agents.single_company_workflow.SAMExtractor') as mock_sam:
            
            # Mock SEC extractor to fail
            mock_sec.return_value.get_recent_filings.side_effect = Exception("SEC API Error")
            
            # Mock SAM extractor to succeed
            mock_sam.return_value.get_all_notices.return_value = [
                {'title': 'Working Notice', 'description': 'Test'}
            ]
            
            result = await setup_workflow.execute("Capital_One")
            
            # Should complete with partial data
            assert result['status'] in ['success', 'partial_success']
    
    def test_company_resolver_integration(self):
        """Test company resolver with various inputs."""
        resolver = CompanyResolver()
        
        # Test direct match
        slug, display = resolver.resolve_company("Capital One")
        assert slug == "Capital_One"
        assert display == "Capital One Financial Corporation"
        
        # Test fuzzy match
        slug, display = resolver.resolve_company("CapitalOne")
        assert slug == "Capital_One"
        
        # Test no match
        slug, display = resolver.resolve_company("Unknown Company")
        assert slug is None
        assert display is None
    
    def test_profile_loader_integration(self):
        """Test profile loader functionality."""
        loader = ProfileLoader()
        
        # Test available profiles
        profiles = loader.get_available_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) > 0
        
        # Test loading specific profile
        profile = loader.load_company_profile("Capital_One")
        if profile:  # Profile might not exist in test environment
            assert isinstance(profile, dict)
            assert 'company_name' in profile

if __name__ == '__main__':
    pytest.main([__file__]) 