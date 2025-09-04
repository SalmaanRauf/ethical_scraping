# Quick Start Guide - Agentic Account Research System

## 🚀 Get Started in 5 Minutes

### 1. Setup Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
python config/database_setup.py
```

### 4. Test the System
```bash
python test_system.py
```

### 5. Run Manual Test
```bash
python main.py test
```

## 📋 Required API Keys

Add these to your `.env` file:

```env
# Data Extraction
SEC_API_KEY="your_sec_api_key_here"
GNEWS_API_KEY="your_gnews_api_key_here"
SAM_API_KEY="your_sam_gov_api_key_here"

# AI Analysis
OPENAI_API_KEY="your_openai_api_key_here"

# Validation
Google_Search_API_KEY="your_google_api_key_here"
GOOGLE_CSE_ID="your_google_custom_search_engine_id_here"
```

## 🎯 What the System Does

1. **Extracts Data** from:
   - SAM.gov (procurement notices)
   - **Comprehensive News Coverage**:
     - Company-specific RSS feeds (Capital One, Freddie Mac, Fannie Mae)
     - Regulatory RSS feeds (OCC Bulletins, Federal Reserve Enforcement Actions)
     - GNews.io API for ALL companies (comprehensive coverage)
   - SEC filings (8-K, 10-Q, 10-K)

2. **Analyzes** using AI to find:
   - Financial events > $10M
   - Procurement opportunities > $10M
   - Forward-looking spending guidance
   - Regulatory enforcement actions

3. **Validates** findings across sources

4. **Generates** daily intelligence reports

## 📊 View Results

Check the `reports/` directory for:
- `report-YYYY-MM-DD.md` (Markdown format)
- `report-YYYY-MM-DD.csv` (CSV format)

## 🔄 Automated Operation

Start the scheduler for daily runs at 7:00 AM PT:
```bash
python main.py scheduler
```

## 🆘 Need Help?

- **Full Documentation**: See `docs/BUILD_LOG.md`
- **Troubleshooting**: Run `python test_system.py`
- **Manual Testing**: Run `python main.py test`

## 🎉 Success!

Your Agentic Account Research System is now ready to monitor financial companies and generate daily intelligence reports! 