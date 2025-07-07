# Agentic Account Research System

An automated, multi-agent system designed to monitor financial companies, identify high-impact events, and generate daily intelligence reports.

## Overview

This system monitors eight predefined financial companies, extracts data from multiple sources (SEC filings, news, procurement notices), analyzes the data using AI, validates findings, and generates structured daily reports.

## Architecture

The system follows a modular, multi-agent architecture with the following components:

- **Orchestrator**: Central scheduler that triggers the workflow daily at 07:00 PT
- **Extractor Agents**: Parallel data collection from SEC, news, and SAM.gov
- **Analyst Agent**: AI-powered analysis using Semantic Kernel
- **Validation Agent**: Cross-source validation of findings
- **Archivist Agent**: Database persistence and deduplication
- **Reporting Agent**: Final report generation

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run database setup: `python config/database_setup.py`
5. Test the system: `python main.py`

## API Keys Required

- SEC_API_KEY (sec-api.io)
- MARKETAUX_API_KEY (Marketaux)
- SAM_API_KEY (SAM.gov)
- OPENAI_API_KEY (OpenAI)
- Google Search_API_KEY (Google Cloud Console)
- GOOGLE_CSE_ID (Google Custom Search Engine)

## Usage

The system runs automatically every weekday at 07:00 PT. For manual testing, run:

```bash
python main.py
```

## Output

Daily reports are generated in the `reports/` directory with the following structure:
- Date
- Company
- Headline
- What Happened?
- Why it Matters
- Consulting Angle
- Source URL
- Key Personnel (N/A - Manual Lookup Required)

## Project Structure

```
agentic-research-system/
├── agents/           # Agent modules
├── config/           # Configuration and setup
├── data/            # SQLite database
├── reports/         # Generated reports
├── sk_functions/    # Semantic Kernel prompts
├── tests/           # Test files
├── main.py          # Main orchestrator
└── requirements.txt # Dependencies
``` 