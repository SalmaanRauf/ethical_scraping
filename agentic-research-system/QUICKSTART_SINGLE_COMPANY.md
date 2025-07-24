# 🚀 Quick Start - Single-Company Briefing System

## ⚡ Get Up and Running in 5 Minutes

### 1. Prerequisites
```bash
# Ensure you have Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps
```

### 2. Environment Setup
```bash
# Copy environment template
cp env.example .env

# Edit .env with your API keys
OPENAI_API_KEY=your_openai_key_here
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here
SEC_API_KEY=your_sec_key_here
```

### 3. Launch the Application
```bash
# Option 1: Use launch script (recommended)
python launch_chainlit.py

# Option 2: Direct launch
cd chainlit_app
chainlit run main.py --host 0.0.0.0 --port 8000
```

### 4. Access the Application
Open your browser and go to: **http://localhost:8000**

### 5. Test the System
Try these example requests:
- "Give me a briefing on Capital One"
- "I need intelligence on Fannie Mae"
- "What's happening with Navy Federal?"

## 🧪 Testing

### Run All Tests
```bash
python run_tests.py
```

### Run Individual Test Suites
```bash
# Unit tests
pytest tests/test_company_resolver.py -v

# Integration tests
pytest tests/test_integration.py -v

# System tests
python -c "from agents.company_resolver import CompanyResolver; print('✅ System ready')"
```

## 🐳 Docker Quick Start

### Build and Run
```bash
# Build image
docker build -t company-intelligence .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e AZURE_OPENAI_API_KEY=your_key \
  -e AZURE_OPENAI_ENDPOINT=your_endpoint \
  company-intelligence
```

### Docker Compose
```bash
# Launch with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## 📊 Monitoring

### Check Application Health
```bash
# Health check
curl http://localhost:8000/health

# View logs
tail -f logs/single_company_workflow.log
```

### Performance Metrics
- Response time: <60 seconds
- Success rate: >95%
- Memory usage: <2GB
- CPU usage: <50%

## 🔧 Configuration

### Company Profiles
Add company profiles to `data/company_profiles/`:
```json
{
  "company_name": "Capital One Financial Corporation",
  "industry": "Financial Services",
  "revenue": "$32.5B",
  "size": "Large",
  "key_buyers": ["Federal Reserve", "Treasury Department"],
  "alumni_contacts": ["John Doe", "Jane Smith"],
  "active_opportunities": ["Digital Transformation", "Compliance"]
}
```

### Rate Limiting
Adjust in `config/config.py`:
```python
RATE_LIMITS = {
    'sec_api': {'requests_per_minute': 60},
    'news_api': {'requests_per_minute': 100},
    'bing_api': {'requests_per_minute': 30}
}
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Solution: Set Python path
export PYTHONPATH=/path/to/agentic-research-system:$PYTHONPATH
```

#### 2. API Key Errors
```bash
# Solution: Verify environment variables
echo $OPENAI_API_KEY
echo $AZURE_OPENAI_API_KEY
```

#### 3. Playwright Issues
```bash
# Solution: Reinstall browsers
playwright install --with-deps
```

#### 4. Memory Issues
```bash
# Solution: Increase Docker memory
docker run --memory=4g company-intelligence
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python launch_chainlit.py
```

## 📞 Support

### Getting Help
1. Check logs: `tail -f logs/single_company_workflow.log`
2. Run tests: `python run_tests.py`
3. Verify environment: `python -c "import os; print('API Keys:', bool(os.getenv('OPENAI_API_KEY')))"`

### Useful Commands
```bash
# Check system status
python -c "from agents.company_resolver import CompanyResolver; print('✅ System ready')"

# Test company resolution
python -c "from agents.company_resolver import CompanyResolver; r = CompanyResolver(); print(r.resolve_company('Capital One'))"

# Check available companies
python -c "from config.company_config import get_available_companies; print(get_available_companies())"
```

## 🎯 Next Steps

1. **Customize Company Profiles**: Add your target companies
2. **Adjust Analysis Prompts**: Modify SK functions for your use case
3. **Scale Deployment**: Use Docker Compose for production
4. **Monitor Performance**: Set up logging and metrics
5. **Extend Functionality**: Add new data sources or analysis types

## 📚 Documentation

- [Full Deployment Guide](DEPLOYMENT.md)
- [System Architecture](SYSTEM_ARCHITECTURE.md)
- [Testing Guide](TESTING.md)
- [API Documentation](API_DOCS.md)

---

**🎉 You're ready to start gathering intelligence!** 