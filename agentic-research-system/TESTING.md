# Testing Guide for Agentic Account Research System

This guide explains how to test the SEC extractor and the overall system.

## Quick Start

### 1. Test SEC Extractor Only
```bash
# Quick standalone test
python test_sec_extractor_standalone.py

# Integration test with main workflow
python test_sec_integration.py
```

### 2. Run All Tests
```bash
# Comprehensive test suite
python run_tests.py

# Or run individual test suites
python test_system.py
```

## Test Types

### Unit Tests
- **Location**: `tests/test_sec_extractor.py`
- **Purpose**: Test individual functions and components
- **Coverage**: API connectivity, data processing, error handling
- **Run with**: `python -m pytest tests/test_sec_extractor.py -v`

### Integration Tests
- **Location**: `test_sec_integration.py`
- **Purpose**: Test SEC extractor with main workflow
- **Coverage**: Data flow, archiving, quality analysis
- **Run with**: `python test_sec_integration.py`

### Standalone Tests
- **Location**: `test_sec_extractor_standalone.py`
- **Purpose**: Quick verification of API functionality
- **Coverage**: Basic connectivity and data extraction
- **Run with**: `python test_sec_extractor_standalone.py`

### Comprehensive Tests
- **Location**: `test_system.py`
- **Purpose**: Test entire system including all extractors
- **Coverage**: Full workflow from extraction to reporting
- **Run with**: `python test_system.py`

## Test Coverage

### SEC Extractor Tests
1. **API Connectivity**
   - Validates SEC API key
   - Tests basic query functionality
   - Verifies response structure

2. **Data Extraction**
   - Tests recent filings retrieval
   - Validates data structure consistency
   - Checks required fields presence

3. **Error Handling**
   - Tests missing API key scenarios
   - Validates API error responses
   - Tests individual filing processing errors

4. **Data Quality**
   - Analyzes text length distribution
   - Validates company coverage
   - Checks form type diversity

### Integration Tests
1. **Workflow Integration**
   - Tests SEC data in main workflow
   - Validates archiving functionality
   - Checks analyst compatibility

2. **Data Flow**
   - Verifies data structure consistency
   - Tests database storage
   - Validates reporting integration

## Prerequisites

### Environment Variables
Make sure these are set in your `.env` file:
```bash
SEC_API_KEY=your_sec_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
BASE_URL=your_azure_openai_endpoint
PROJECT_ID=your_project_id
API_VERSION=2024-02-15-preview
MODEL=your_model_name
GOOGLE_SEARCH_API_KEY=your_google_search_api_key
GOOGLE_CSE_ID=your_google_cse_id
MARKETAUX_API_KEY=your_marketaux_api_key
SAM_API_KEY=your_sam_api_key
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Test Results Interpretation

### ✅ Success Indicators
- API connectivity established
- Data extraction working
- Proper data structure
- Integration with main workflow
- No critical errors

### ⚠️ Warning Indicators
- No recent filings found (normal for some periods)
- Missing optional fields
- API rate limits approached

### ❌ Failure Indicators
- Missing API keys
- API connectivity failures
- Data structure mismatches
- Integration errors

## Troubleshooting

### Common Issues

1. **SEC_API_KEY not found**
   - Check `.env` file exists
   - Verify API key is correct
   - Ensure no extra spaces

2. **API connectivity failed**
   - Check internet connection
   - Verify API key validity
   - Check API rate limits

3. **No data found**
   - This might be normal for recent periods
   - Try increasing `days_back` parameter
   - Check if target companies have recent filings

4. **Import errors**
   - Ensure you're in the project root directory
   - Check all dependencies are installed
   - Verify Python path includes project root

### Debug Mode
For detailed debugging, run tests with verbose output:
```bash
python test_sec_extractor_standalone.py 2>&1 | tee test_output.log
```

## Performance Testing

### API Usage Monitoring
The tests are designed to minimize API usage:
- Recent filings test uses 1-7 days only
- Standalone test uses minimal queries
- Integration tests reuse extracted data

### Expected API Calls
- **Standalone test**: ~2-3 API calls
- **Integration test**: ~3-5 API calls
- **Full system test**: ~5-10 API calls

## Continuous Integration

### Automated Testing
The test suite can be integrated into CI/CD pipelines:
```bash
# Run all tests and exit with proper code
python run_tests.py
```

### Test Reports
Tests generate detailed output for analysis:
- Success/failure status
- Performance metrics
- Data quality indicators
- Error details

## Best Practices

1. **Run tests before deployment**
2. **Monitor API usage**
3. **Check data quality regularly**
4. **Update tests when adding features**
5. **Document any API changes**

## Support

If you encounter issues:
1. Check the troubleshooting section
2. Review test output logs
3. Verify environment configuration
4. Test with minimal data first 