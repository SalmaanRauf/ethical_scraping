# Research Agent System Architecture

## Overview

The Research Agent is a comprehensive financial intelligence system that automatically extracts, analyzes, validates, and reports on high-impact events for target financial institutions. The system operates as a **sequential workflow** orchestrated by the `ResearchOrchestrator` class in `main.py`.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESEARCH ORCHESTRATOR                       │
│                        (main.py)                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: DATA EXTRACTION                    │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │SAM Extractor│  │News Extractor│  │SEC Extractor│          │
│  │(Procurement)│  │  (RSS/GNews) │  │ (Filings)   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         │                │                │                   │
│         └────────────────┼────────────────┘                   │
│                          ▼                                   │
│              ┌─────────────────────────┐                     │
│              │   Combined Raw Data     │                     │
│              │   (all_raw_data)       │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: DATA CONSOLIDATION                 │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                DATA CONSOLIDATOR                       │   │
│  │  ┌─────────────────┐ ┌─────────────────┐              │   │
│  │  │ Relevance       │ │ Structured      │              │   │
│  │  │ Scoring         │ │ Document        │              │   │
│  │  │ & Filtering     │ │ Generation      │              │   │
│  │  └─────────────────┘ └─────────────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────────┐                     │
│              │   Analysis Document     │                     │
│              │  (Markdown + JSON)     │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: ANALYSIS                          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              ANALYST AGENT                             │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │   Triage    │ │  Financial  │ │  Earnings   │     │   │
│  │  │  Function   │ │ Specialist  │ │   Call      │     │   │
│  │  │             │ │  Function   │ │ Specialist  │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │Procurement  │ │  Insight    │ │  Reporter   │     │   │
│  │  │Specialist   │ │ Generator   │ │  Function   │     │   │
│  │  │  Function   │ │  Function   │ │             │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────────┐                     │
│              │   Analyzed Events       │                     │
│              │  (analyzed_events)      │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: VALIDATION                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    VALIDATOR                           │   │
│  │  ┌─────────────────┐ ┌─────────────────┐              │   │
│  │  │ Internal        │ │ External        │              │   │
│  │  │ Validation      │ │ Validation      │              │   │
│  │  │ (Cross-check    │ │ (Google Search  │              │   │
│  │  │  internal data) │ │  API)          │              │   │
│  │  └─────────────────┘ └─────────────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────────┐                     │
│              │  Validated Events       │                     │
│              │ (validated_events)      │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 4: ARCHIVING                          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   ARCHIVIST                            │   │
│  │  ┌─────────────────┐ ┌─────────────────┐              │   │
│  │  │ Semantic        │ │ Database        │              │   │
│  │  │ Deduplication   │ │ Storage         │              │   │
│  │  │ (Prevents       │ │ (SQLite)        │              │   │
│  │  │  duplicates)    │ │                 │              │   │
│  │  └─────────────────┘ └─────────────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 5: REPORTING                          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   REPORTER                             │   │
│  │  ┌─────────────────┐ ┌─────────────────┐              │   │
│  │  │ Markdown        │ │ CSV Report      │              │   │
│  │  │ Report          │ │ Generation      │              │   │
│  │  │ Generation      │ │                 │              │   │
│  │  └─────────────────┘ └─────────────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Workflow

### 1. **Orchestrator Initialization** (`main.py`)
- Creates instances of all agents and extractors
- Sets up the sequential workflow
- Handles both manual and scheduled execution modes

### 2. **Data Extraction Phase**
The system extracts data from three primary sources:

#### **SAM Extractor** (`extractors/sam_extractor.py`)
- Scrapes SAM.gov for procurement notices
- Targets specific NAICS codes and keywords
- Returns structured procurement data

#### **News Extractor** (`extractors/news_extractor.py`)
- **RSS Feeds**: Company-specific feeds (Capital One, Freddie Mac, Fannie Mae)
- **GNews API**: Comprehensive news search for all target companies
- **Regulatory Feeds**: OCC Bulletins, Federal Reserve Enforcement Actions
- Returns structured news articles with metadata

#### **SEC Extractor** (`extractors/sec_extractor.py`)
- Fetches recent SEC filings (8-K, 10-K, 10-Q)
- Targets specific companies and filing types
- Returns structured SEC filing data

### 2. **Data Consolidation Phase** (`agents/data_consolidator.py`)
The DataConsolidator processes raw data into structured documents:

#### **Key Features**:
- **Relevance Scoring**: Calculates relevance based on company mentions and high-impact keywords
- **Intelligent Filtering**: Removes irrelevant items and focuses on target companies
- **Structured Documents**: Creates organized Markdown documents for analysis
- **Key Term Extraction**: Identifies important terms for analysis
- **Source Classification**: Categorizes items by source type (news, SEC, procurement)

#### **Output**:
- **Consolidated Items**: Filtered, scored, and structured data items
- **Analysis Document**: Markdown document ready for AI processing
- **JSON Metadata**: Structured data for programmatic access

### 3. **Analysis Phase** (`agents/analyst_agent.py`)
The Analyst Agent processes consolidated data through a sophisticated AI pipeline:

#### **Function Chain**:
1. **Triage Function**: Determines event type and relevance
2. **Financial Specialist**: Analyzes financial implications
3. **Earnings Call Specialist**: Processes earnings-related events
4. **Procurement Specialist**: Analyzes procurement events
5. **Insight Generator**: Creates business insights
6. **Reporter Function**: Finalizes analysis

#### **Semantic Kernel Integration**:
- Uses Semantic Kernel 1.34.0 for AI function orchestration
- Loads specialized prompt templates from `sk_functions/`
- Handles async function invocation properly
- Processes structured documents instead of raw command-line data

### 4. **Validation Phase** (`agents/validator.py`)
Two-tier validation system:

#### **Internal Validation**:
- Cross-references events against internal data sources
- Checks for consistency across SEC filings, news, and procurement data

#### **External Validation**:
- Uses Google Custom Search API
- Validates events against external sources
- Requires multiple relevant sources for confirmation

### 5. **Archiving Phase** (`agents/archivist.py`)
Advanced storage with deduplication:

#### **Semantic Deduplication**:
- Prevents duplicate events using semantic similarity
- Stores event summaries for comparison
- Uses Jaccard similarity algorithm

#### **Database Storage**:
- SQLite database (`data/research.db`)
- Structured schema for findings
- Metadata tracking and timestamps

### 6. **Reporting Phase** (`agents/reporter.py`)
Generates comprehensive reports:

#### **Report Types**:
- **Markdown Reports**: Human-readable intelligence reports
- **CSV Reports**: Structured data for analysis
- **Summary Statistics**: Key metrics and insights

## Execution Modes

### **Manual Test Mode**
```bash
python main.py test
```
- Runs the complete workflow once
- Detailed logging and progress tracking
- Immediate results

### **Scheduler Mode**
```bash
python main.py scheduler
```
- Automated daily execution at 7:00 AM PT
- Uses APScheduler for cron-based scheduling
- Runs on weekdays only

### **Default Mode**
```bash
python main.py
```
- Runs manual test by default
- Shows usage instructions

## Data Flow Summary

1. **Extractors** → Raw structured data from multiple sources
2. **DataConsolidator** → Filtered, scored, and structured documents
3. **Analyst Agent** → AI-processed events with insights
4. **Validator** → Cross-verified and validated events
5. **Archivist** → Deduplicated and stored findings
6. **Reporter** → Comprehensive intelligence reports

## Key Features

- **Comprehensive Coverage**: Multiple data sources (RSS, APIs, web scraping)
- **AI-Powered Analysis**: Semantic Kernel integration with specialized functions
- **Quality Assurance**: Multi-tier validation system
- **Deduplication**: Semantic similarity to prevent duplicates
- **Automation**: Scheduled execution with detailed logging
- **Flexible Output**: Multiple report formats (Markdown, CSV)

## Target Companies

The system focuses on these financial institutions:
- Capital One
- Fannie Mae
- Freddie Mac
- Navy Federal Credit Union
- PenFed Credit Union
- EagleBank
- Capital Bank N.A.

This architecture ensures comprehensive, automated financial intelligence gathering with high-quality analysis and reporting. 