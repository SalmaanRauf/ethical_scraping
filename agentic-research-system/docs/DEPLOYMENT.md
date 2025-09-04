# 🚀 Deployment Guide - Single-Company Briefing System

## 📋 Prerequisites

### System Requirements
- Python 3.11+
- 4GB RAM minimum
- 2GB disk space
- Internet connection for API calls

### API Keys Required
- OpenAI API Key (for analysis)
- Azure OpenAI API Key (for Bing grounding)
- SEC API Key (for filings)

## 🛠️ Local Development Setup

### 1. Clone and Setup
```bash
# Clone repository
git clone <repository-url>
cd agentic-research-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps
```

### 2. Environment Configuration
```bash
# Create .env file
cp .env.example .env

# Edit .env with your API keys
OPENAI_API_KEY=your_openai_key_here
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here
SEC_API_KEY=your_sec_key_here
```

### 3. Launch Application
```bash
# Option 1: Use launch script
python launch_chainlit.py

# Option 2: Direct Chainlit launch
cd chainlit_app
chainlit run main.py --host 0.0.0.0 --port 8000
```

## 🐳 Docker Deployment

### 1. Build and Run
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

### 2. Docker Compose (Recommended)
```bash
# Create .env file with API keys
cp .env.example .env

# Launch with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## ☁️ Production Deployment

### 1. Cloud Platform Setup

#### AWS EC2
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone and deploy
git clone <repository-url>
cd agentic-research-system
docker-compose up -d
```

#### Google Cloud Run
```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/company-intelligence

# Deploy to Cloud Run
gcloud run deploy company-intelligence \
  --image gcr.io/PROJECT_ID/company-intelligence \
  --platform managed \
  --allow-unauthenticated \
  --port 8000
```

#### Azure Container Instances
```bash
# Build and push to Azure Container Registry
az acr build --registry myregistry --image company-intelligence .

# Deploy to Container Instances
az container create \
  --resource-group myResourceGroup \
  --name company-intelligence \
  --image myregistry.azurecr.io/company-intelligence \
  --ports 8000 \
  --environment-variables \
    OPENAI_API_KEY=your_key \
    AZURE_OPENAI_API_KEY=your_key
```

### 2. Environment Variables
```bash
# Required for production
OPENAI_API_KEY=your_openai_key
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
SEC_API_KEY=your_sec_key

# Optional
CHAINLIT_HOST=0.0.0.0
CHAINLIT_PORT=8000
LOG_LEVEL=INFO
```

## 🔧 Configuration

### 1. Company Profiles
Place company profile JSON files in `data/company_profiles/`:
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

### 2. Rate Limiting
Configure rate limits in `config/config.py`:
```python
RATE_LIMITS = {
    'sec_api': {'requests_per_minute': 60},
    'news_api': {'requests_per_minute': 100},
    'bing_api': {'requests_per_minute': 30}
}
```

## 📊 Monitoring

### 1. Health Checks
```bash
# Check application health
curl http://localhost:8000/health

# Check Docker container health
docker ps
docker logs company-intelligence
```

### 2. Logs
```bash
# View application logs
tail -f logs/single_company_workflow.log

# View Docker logs
docker-compose logs -f company-intelligence
```

### 3. Metrics
Monitor these key metrics:
- Response time (target: <60 seconds)
- Success rate (target: >95%)
- API call success rates
- Memory usage
- CPU usage

## 🔒 Security

### 1. API Key Management
- Use environment variables, never hardcode
- Rotate keys regularly
- Use least-privilege access
- Monitor API usage

### 2. Network Security
- Use HTTPS in production
- Configure firewall rules
- Implement rate limiting
- Monitor for suspicious activity

### 3. Data Protection
- Encrypt sensitive data at rest
- Use secure connections for API calls
- Implement proper logging without exposing secrets
- Regular security audits

## 🚨 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Solution: Check Python path
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

For deployment issues:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables
3. Test individual components
4. Contact development team

## 🔄 Updates

### Updating the Application
```bash
# Pull latest changes
git pull origin main

# Rebuild Docker image
docker-compose build

# Restart services
docker-compose up -d
```

### Database Migrations
```bash
# Run migrations (if applicable)
python -m alembic upgrade head
``` 