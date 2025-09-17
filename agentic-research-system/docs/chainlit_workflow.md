# Chainlit Chat Workflow

This document explains the end‑to‑end Chainlit chat workflow for the single‑company intelligence experience. It focuses on the runtime path triggered when a user chats with the app (not the batch/extractor pipeline).

## Overview

- Entry/UI: Chainlit chat app (`chainlit_app/main.py`)
- Discovery: Bing Grounded Search via Azure AI Foundry Agents (`agents/bing_data_extraction_agent.py`)
- Analysis: Semantic Kernel prompt functions (`agents/analyst_agent.py` + `sk_functions/`)
- Follow‑ups: Use saved context first, then targeted Bing searches (`services/follow_up_handler.py`)
- Context/Sessions: Durable per‑session memory and cleanup (`services/conversation_manager.py`, `services/session_manager.py`)
- Config/Env: Azure/OpenAI/Bing credentials (`config/config.py`, `config/kernel_setup.py`)

## Primary Flow Stages

1) Chat Startup
- File: `chainlit_app/main.py`
- On `@cl.on_chat_start`:
  - Initializes singletons in user session: `BingDataExtractionAgent`, `AnalystAgent`, `FollowUpHandler`, `QueryRouter`.
  - Starts cleanup tasks via `conversation_manager` and `session_manager`.
  - Sends welcome/instructions to the user.

2) User Message Routing
- File: `chainlit_app/main.py` (handler `on_message`)
- Router: `services/conversation_manager.QueryRouter`
  - Classifies input as: NEW_ANALYSIS, FOLLOW_UP, COMPARE_COMPANIES, or CLARIFICATION.
  - Heuristics: tickers, “A vs B”, imperatives (analyze/research …), follow‑up question hints.

3) New Company Analysis
- Files: `chainlit_app/main.py` → `handle_new_analysis`, `agents/bing_data_extraction_agent.py`, `agents/analyst_agent.py`
- Steps:
  1. Validate payload and set company in `ConversationContext`.
  2. Discovery (GWBS): call `BingDataExtractionAgent.get_full_intelligence(company)` to fetch sections:
     - `search_sec_filings`, `search_news`, `search_procurement`, `search_earnings`, `search_industry_context`.
     - Removes inline URLs; uses ONLY Bing tool citation annotations.
     - Returns `summary`, `citations_md`, and audit info.
  3. Prepare analysis items from GWBS sections (title/summary/citations/raw_data).
  4. Analysis: `AnalystAgent.analyze_all_data(items)` → triage → financial/procurement/earnings analyzers → insight generation.
  5. Save `AnalysisBlob` into session context (`ConversationContext`).
  6. Present results in chat (top events + abbreviated citations).

4) Follow‑Up Questions
- File: `services/follow_up_handler.py`
- Strategy:
  - Classify question (risk, financial, regulatory, competitive, strategic, timeline) via regex rules.
  - Try to answer from the current `AnalysisBlob` (summary + events).
  - If insufficient, run targeted Bing GWBS scopes (e.g., news/sec/industry) for that class.
  - Merge citations; strip inline URLs in body; reply in chat.

5) Company Comparison
- File: `chainlit_app/main.py` → `handle_company_comparison`
- Runs two discovery+analysis pipelines in parallel, stores both analyses in the context, and presents a short comparison (event counts, top event titles).

6) Presentation & Cleanup
- File: `chainlit_app/main.py`
- Presents concise bullet summaries for results and comparisons, adds citations where available.
- On `@cl.on_chat_end`, stops background cleanup tasks.

## Key Components & Responsibilities

- UI/Runtime
  - `chainlit_app/main.py`: Chat lifecycle, routing bridge, orchestrates discovery→analysis→presentation.
  - `chainlit_app/launch_chainlit.py`: Optional launcher; ensures env set, initializes app context (batch infra), then runs Chainlit.

- Discovery (Bing Grounded Search)
  - `agents/bing_data_extraction_agent.py`:
    - Creates ephemeral Azure AI Foundry agent with `BingGroundingTool`.
    - Runs 1 pass; if zero citations, runs a single corrective pass to force citations.
    - Returns sanitized `summary` + `citations_md` per scope.

- Analysis (Semantic Kernel)
  - `agents/analyst_agent.py`:
    - Loads SK prompt functions from `sk_functions/` (triage, financial, procurement, earnings, insights, company takeaway).
    - Pipeline: triage → per‑domain analyzers → insight generation → final list of events with structured fields.
  - `config/kernel_setup.py`:
    - Builds SK `Kernel` backed by Azure OpenAI/ATLAS; requires OpenAI/Azure env vars.

- Follow‑up Routing
  - `services/follow_up_handler.py`: Classify, answer from context, or run targeted GWBS queries; merges citations.

- Context & Sessions
  - `services/conversation_manager.py`:
    - `ConversationContext`: current company, chat history, `AnalysisBlob` store; pruning of stale analyses.
    - `QueryRouter`: deterministic routing heuristics.
  - `services/session_manager.py`: Thread‑safe per‑session store with idle cleanup.

- Configuration & Environment
  - `config/config.py`: Loads `.env`, surfaces keys; warns if some are missing.
  - Required for Discovery (Bing Grounding):
    - `PROJECT_ENDPOINT`, `MODEL_DEPLOYMENT_NAME`, `AZURE_BING_CONNECTION_ID`.
  - Required for Analysis (Semantic Kernel/Azure OpenAI/ATLAS):
    - `OPENAI_API_KEY`, `BASE_URL`, `PROJECT_ID`, `API_VERSION`, `MODEL`.

## Not Used by Chat (Batch/Legacy)

These power the batch/ETL workflow and are not in the chat path:

- `services/app_context.py` (centralized wiring for extractors & agents)
- `agents/single_company_workflow.py` (batch orchestration)
- `agents/data_consolidator.py`, `agents/scraper_agent.py`, `agents/validator.py`, `agents/archivist.py`, `agents/reporter.py`
- `extractors/*` (news/sec/sam/http utils + wrappers)
- `config/database_setup.py` (SQLite schema/indexing)

## Sequence at a Glance

1. User sends message in Chainlit.
2. `QueryRouter` decides: new analysis / follow‑up / compare / clarify.
3. New analysis → GWBS (Bing grounded) per scope → Analysis (Semantic Kernel) → Save `AnalysisBlob` → Present.
4. Follow‑up → Answer from `AnalysisBlob` or targeted GWBS → Present with citations.
5. Comparison → Run 2x (GWBS + Analysis) → Present comparison.
6. Context and sessions are cleaned up in the background.

## Developer Notes

- Inline URLs from model output are stripped; citations come only from Bing tool annotations.
- GWBS calls will error without valid Azure AI Foundry Agent configuration.
- SK analysis will error without valid Azure OpenAI/ATLAS configuration.
- If you change the Bing agent implementation details, keep the “single corrective pass if no citations” behavior for reliability.

