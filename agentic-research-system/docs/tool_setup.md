# Tool-Centric Orchestration Setup

This document explains the new tool-centric architecture added to the Chainlit chat experience. It covers the models, tools, orchestrators, the feature flag that enables them, the ideal workflow, and how everything connects. It also clarifies how Semantic Kernel (SK) via ATLAS remains in use for analysis.

## Why

- Make discovery and analysis capabilities composable “tools” with clear, typed contracts.
- Support multi-intent prompts (briefing + competitor ask) and smarter follow-ups.
- Improve reliability (citation policy), speed (TTL caching), and UX (progress streaming).
- Keep the legacy flow as a safe fallback during migration.

## What Was Added

- Models (typed contracts)
  - `models/schemas.py`
    - `CompanyRef`, `Citation`, `GWBSSection`, `FullGWBS`, `AnalysisItem`, `AnalysisEvent`, `Briefing`.
- Cache
  - `services/cache.py` — minimal TTL cache to avoid repeat GWBS calls.
- Tools
  - `tools/gwbs_tools.py`
    - `gwbs_search(scope, CompanyRef, BingDataExtractionAgent) -> GWBSSection`
    - `gwbs_full(CompanyRef, BingDataExtractionAgent) -> FullGWBS`
    - Supports `sec_filings`, `news`, `procurement`, `earnings`, `industry_context`, and a `competitors` task.
  - `tools/analyst_tools.py`
    - `analyst_synthesis(items, AnalystAgent) -> List[AnalysisEvent]` (async usage)
- Orchestrators
  - `tools/orchestrators.py`
    - `full_company_analysis(CompanyRef, bing_agent, analyst_agent) -> Briefing`
    - `follow_up_research(CompanyRef, question, bing_agent, analyst_agent, ctx_blob) -> (answer, citations)`
    - `competitor_analysis(CompanyRef, bing_agent) -> GWBSSection`
- Chainlit integration (feature-flagged)
  - `chainlit_app/main.py`
    - Uses `ENABLE_TOOL_ORCHESTRATOR=true|1|yes` to switch to the tool-based flow.
    - New analysis: orchestrator path with progress updates and typed presentation.
    - Follow-up: orchestrator path with context-first → targeted GWBS → optional analyst synthesis.
    - Competitor ask detection: If user’s initial ask includes competitor language, auto-run GWBS competitor analysis and present results.

## What Was Not Changed

- SK/ATLAS setup: `config/kernel_setup.py` unchanged. The `AnalystAgent` still uses SK for analysis.
- Bing Grounding agent implementation: `agents/bing_data_extraction_agent.py` unchanged in behavior; tools call its public methods.
- Legacy chat flow preserved when feature flag is off.

## Environment Flags and Dependencies

- Feature flag: `ENABLE_TOOL_ORCHESTRATOR=true` to enable new orchestrator flow.
- Dependencies:
  - `pydantic>=1.10,<3` added to `requirements.txt` for typed models.
  - Existing Azure agents and identity libs unchanged.

## Ideal Workflow (Chat)

1) User asks for briefing on a company.
- Orchestrator runs `gwbs_full` (SEC, News, Procurement, Earnings, Industry) with caching.
- Converts to `AnalysisItem[]`, runs `analyst_synthesis` (Semantic Kernel via ATLAS), returns `Briefing`.
- Chainlit presents events + summaries; stores an `AnalysisBlob` in session.

2) User asks a follow-up.
- Orchestrator uses context to answer trivially if possible.
- Otherwise, runs targeted GWBS scopes based on question label (risk/financial/regulatory/…):
  - If the ask implies synthesis (why/how/impact/angle/priority/timeline), pass through `analyst_synthesis`.
  - Else, answer directly from GWBS summaries with citations.

3) User asks for competitor moves.
- Orchestrator runs `competitor_analysis` (GWBS direct) to identify top competitors and their moves; cites all claims.
- Optionally (only if asked), send through `analyst_synthesis` for implications/angles.

## ASCII Diagram

```
User ──▶ Chainlit (main.py)
          │
          │ route: NEW_ANALYSIS / FOLLOW_UP / COMPARE
          ▼
   Orchestrators (tools/orchestrators.py)
      ├─ full_company_analysis(CompanyRef) ───────┐
      │                                         │
      │               GWBS Tools                 │
      │     gwbs_full / gwbs_search (per scope) │
      │        │                                │
      │        ▼                                │
      │    FullGWBS (typed)                     │
      │        │                                │
      │  map→ AnalysisItem[]                    │
      │        │                                │
      │        ▼                                │
      │   analyst_synthesis (AnalystAgent/SK)   │
      │        │                                │
      │        ▼                                │
      │        Briefing (typed) ◀───────────────┘
      │
      ├─ follow_up_research(CompanyRef, q)
      │     ctx answer → targeted GWBS → optional SK
      │
      └─ competitor_analysis(CompanyRef)
            GWBS-direct; optional SK if asked
```

## Citation Policy

- Summaries strip inline URLs; citations only come from Bing tool annotations.
- Merged and capped for readability; presented as Markdown bullets.

## Caching

- `TTLCache` avoids re-running expensive GWBS calls for repeated queries in a short window.
- Keying by `(company, scope)`, with a default 30-minute TTL.

## Verification Summary

- The Semantic Kernel + ATLAS setup remains intact:
  - No changes to `config/kernel_setup.py`.
  - `AnalystAgent` is still responsible for analysis; tools call it via `analyst_synthesis`.
- Chainlit uses the new orchestrator only when `ENABLE_TOOL_ORCHESTRATOR=true`; otherwise, it follows the legacy pipeline.
- Imports and packaging:
  - `models` and `tools` packages added with `__init__.py`.
  - `main.py` adds imports for `CompanyRef` and `orchestrators` safely; the project root is already appended to `sys.path` in `main.py`.
- Backward compatibility:
  - Follow-up handling falls back to the existing handler when the feature flag is off.
  - Presentation code handles both Pydantic objects and dicts.

## When to Use Analyst vs. GWBS Direct

- Use Analyst (SK) when:
  - The ask implies synthesis: “why it matters”, “impact”, “angle”, “priority”, “timeline”, or requires multi-source reasoning.
- Use GWBS direct when:
  - The ask is list/lookup-oriented: “who/what/when/where/which”, or a quick status check that doesn’t need synthesis.

## Next Steps

- Optionally stream per-scope GWBS completion for even better UX.
- Add focused tests for orchestration contracts and cache behavior.
- Link this document from `docs/QUICKSTART_CHAINLIT.md` and `README.md`.

---

If the new flow needs to be disabled quickly, unset `ENABLE_TOOL_ORCHESTRATOR` and the app will run the legacy pipeline.
