"""
GWBS (Grounding with Bing Search) tool wrappers.

These functions provide a clean, Pydantic-typed interface over the BingDataExtractionAgent
that the orchestrator can call. They also leverage a TTL cache to reduce repeat calls.
"""
from __future__ import annotations
from typing import Dict

from models.schemas import CompanyRef, Citation, GWBSSection, FullGWBS
from services.cache import TTLCache, cache_key
from agents.bing_data_extraction_agent import BingDataExtractionAgent


# Process-local cache for GWBS results
_gwbs_cache = TTLCache(maxsize=256, ttl_seconds=1800)  # 30 minutes default


def _to_citations_md_list(md: str) -> list[Citation]:
    """Convert markdown bullets to Citation objects (best-effort)."""
    import re
    out: list[Citation] = []
    if not md:
        return out
    for line in (md or "").splitlines():
        m = re.match(r"^- \[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)", line.strip())
        if m:
            out.append(Citation(title=m.group("title"), url=m.group("url")))
    return out


def gwbs_search(scope: str, company: CompanyRef, agent: BingDataExtractionAgent) -> GWBSSection:
    """Run a single GWBS scope for a company and return a typed section result."""
    ckey = cache_key("gwbs_search", scope, company.name, company.ticker)
    cached = _gwbs_cache.get(ckey)
    if cached:
        return cached

    # Dispatch to appropriate public search method
    if scope == "sec_filings":
        raw = agent.search_sec_filings(company.name)
    elif scope == "news":
        raw = agent.search_news(company.name)
    elif scope == "procurement":
        raw = agent.search_procurement(company.name)
    elif scope == "earnings":
        raw = agent.search_earnings(company.name)
    elif scope == "industry_context":
        raw = agent.search_industry_context(company.name)
    elif scope == "competitors":
        # Specialized competitor prompt: reuse agent core runner via industry context
        # without changing the agent surface area.
        prompt = (
            f"TASK: Identify the top 3 competitors for {company.name} and summarize their recent moves "
            f"to gain market share ('take over the market'). Use the Grounding with Bing Search tool, cite all claims."
        )
        # Use the agent's internal runner for a custom task string.
        raw = agent._run_agent_task(prompt)  # type: ignore[attr-defined]
    else:
        raise ValueError(f"Unknown GWBS scope: {scope}")

    section = GWBSSection(
        scope=scope,  # type: ignore[arg-type]
        summary=(raw or {}).get("summary", ""),
        citations=_to_citations_md_list((raw or {}).get("citations_md", "")),
        audit=(raw or {}).get("audit", {}),
    )
    _gwbs_cache.set(ckey, section)
    return section


def gwbs_full(company: CompanyRef, agent: BingDataExtractionAgent) -> FullGWBS:
    """Run all primary scopes for a company and return a FullGWBS bundle."""
    scopes = ["sec_filings", "news", "procurement", "earnings", "industry_context"]
    sections: Dict[str, GWBSSection] = {}
    for s in scopes:
        sections[s] = gwbs_search(s, company, agent)
    return FullGWBS(company=company, sections=sections)

