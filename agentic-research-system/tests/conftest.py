"""
Pytest configuration and fixtures for testing.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from agents.company_resolver import CompanyResolver
from agents.single_company_workflow import SingleCompanyWorkflow

@pytest.fixture
def company_resolver():
    """Provide CompanyResolver instance for testing."""
    return CompanyResolver()

@pytest.fixture
def single_company_workflow():
    """Provide SingleCompanyWorkflow instance for testing."""
    return SingleCompanyWorkflow()

@pytest.fixture
def mock_extractor():
    """Provide mock extractor for testing."""
    mock = Mock()
    mock.extract_for_company = AsyncMock(return_value=[])
    return mock

@pytest.fixture
def mock_analyst_agent():
    """Provide mock analyst agent for testing."""
    mock = Mock()
    mock.analyze_consolidated_data = AsyncMock(return_value=[])
    return mock

@pytest.fixture
def mock_reporter():
    """Provide mock reporter for testing."""
    mock = Mock()
    mock.format_company_briefing = Mock(return_value={
        'status': 'success',
        'briefing': 'Test briefing content'
    })
    return mock

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 