"""
Tool-centric orchestrators for the Chainlit chat experience.

These orchestrators combine GWBS discovery and SK analysis according to intent.
They are designed to be invoked from Chainlit handlers and respect session context.
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import re

from models.schemas import (
    CompanyRef,
    Citation,
    GWBSSection,
    FullGWBS,
    AnalysisItem,
    AnalysisEvent,
    Briefing,
)
from tools.gwbs_tools import gwbs_full, gwbs_search
from tools.analyst_tools import analyst_synthesis
from services.cache import TTLCache, cache_key


# Lightweight caches for orchestration outputs
_briefing_cache = TTLCache(maxsize=64, ttl_seconds=1800)


def _analysis_items_from_gwbs(bundle: FullGWBS) -> List[AnalysisItem]:
    items: List[AnalysisItem] = []
    for key, section in (bundle.sections or {}).items():
        if not isinstance(section, GWBSSection):
            # If callers pass plain dicts by mistake, skip them safely
            try:
                section = GWBSSection(**section)  # type: ignore[arg-type]
            except Exception:
                continue
        items.append(
            AnalysisItem(
                company=bundle.company.name,
                title=key.replace("_", " ").title(),
                content=section.summary or "",
                citations=section.citations or [],
                raw={"scope": key, "audit": section.audit},
            )
        )
    return items


async def full_company_analysis(company: CompanyRef, *, bing_agent, analyst_agent) -> Briefing:
    """Run the full GWBS → Analysis pipeline and return a Briefing payload."""
    bkey = cache_key("briefing", company.name, company.ticker)
    cached = _briefing_cache.get(bkey)
    if cached:
        return cached

    gwbs = gwbs_full(company, bing_agent)
    analysis_items = _analysis_items_from_gwbs(gwbs)
    events = await analyst_synthesis(analysis_items, analyst_agent)

    # Summarize: keep it simple here; SK already offers robust synthesizing
    summary = f"Identified {len(events)} significant events for {company.name}."
    sections = {k: v.summary for k, v in gwbs.sections.items()}
    briefing = Briefing(company=company, events=events, summary=summary, sections=sections)
    _briefing_cache.set(bkey, briefing)
    return briefing


def _classify_follow_up(question: str) -> str:
    patterns = {
        "risk": [r"\b(risk|downside|exposure|threat|vulnerab)", r"\b(credit risk|regulatory risk|operational risk|cyber|lawsuit|fine)\b"],
        "financial": [r"\b(revenue|earnings?|profit|loss|margin|guidance|forecast)\b", r"\b(financial impact|capex|opex|cash flow)\b"],
        "competitive": [r"\b(competitor|competitive|market share|position|moat|benchmark|vs|versus)\b"],
        "regulatory": [r"\b(regulatory|regulation|compliance|legal|SEC|DOJ|FTC|antitrust)\b", r"\b(filing|10-?K|10-?Q|8-?K|consent decree|settlement)\b"],
        "strategic": [r"\b(strategy|strategic|roadmap|future|plan|initiative|priorit(?:y|ies))\b", r"\b(product|launch|expansion|hiring|acquisition|divestiture)\b"],
        "timeline": [r"\b(when|timeline|by when|deadline|date)\b"],
    }
    q = question or ""
    for label, regs in patterns.items():
        if any(re.search(p, q, re.I) for p in regs):
            return label
    return "general"


def _needs_analyst(label: str, question: str) -> bool:
    # If the ask implies synthesis (why/how/impact/angle/priority/timeline), route through analyst
    if label in {"risk", "financial", "regulatory", "strategic", "timeline"}:
        return True
    if re.search(r"\b(why|impact|angle|priority|prioritize|timeline|how)\b", question, re.I):
        return True
    return False


async def follow_up_research(company: CompanyRef, question: str, *, bing_agent, analyst_agent, ctx_blob=None) -> Tuple[str, List[Citation]]:
    """Answer a follow-up using context, then targeted GWBS, optionally analyst synthesis."""
    # 1) Try from context blob if provided
    if ctx_blob and isinstance(ctx_blob, dict):
        # very lightweight lexical search across stored summary and events
        q_lower = (question or "").lower()
        pools: List[str] = []
        if ctx_blob.get("analyst_summary"):
            pools.append(ctx_blob["analyst_summary"]) 
        for ev in ctx_blob.get("analyst_events") or []:
            if isinstance(ev, dict):
                pools.append(" ".join([ev.get("title", ""), str(ev.get("insights", {}))]))
        hits = [p for p in pools if q_lower[:60] in p.lower()]
        if hits:
            return hits[0][:1200], []

    # 2) Targeted GWBS
    label = _classify_follow_up(question)
    scope_order = {
        "financial": ["news", "sec_filings"],
        "risk": ["news", "sec_filings"],
        "competitive": ["news", "industry_context"],
        "regulatory": ["sec_filings", "news"],
        "strategic": ["news", "industry_context"],
        "timeline": ["news", "sec_filings"],
        "general": ["news"],
    }
    scopes = scope_order.get(label, ["news"])
    sections: List[GWBSSection] = []
    for s in scopes:
        sections.append(gwbs_search(s, company, bing_agent))

    # 3) Synthesize answer
    body_parts: List[str] = []
    citations_all: List[Citation] = []
    for sec in sections:
        if sec.summary:
            body_parts.append(f"**{sec.scope.replace('_', ' ').title()}**\n{sec.summary}")
        citations_all.extend(sec.citations or [])

    if not body_parts:
        return ("I couldn't find information that directly answers that. Try asking more specifically, or I can re-run a broader search.", citations_all[:8])

    if _needs_analyst(label, question):
        # Route summaries back through analyst for deeper reasoning
        items = [
            AnalysisItem(
                company=company.name,
                title=sec.scope.replace("_", " ").title(),
                content=sec.summary,
                citations=sec.citations or [],
                raw={"scope": sec.scope},
            )
            for sec in sections
        ]
        events = await analyst_synthesis(items, analyst_agent)
        # Take top synthesized view
        if events:
            e = events[0]
            what = e.insights.get("what_happened", "") if isinstance(e.insights, dict) else ""
            why = e.insights.get("why_it_matters", "") if isinstance(e.insights, dict) else ""
            combined = "\n".join([p for p in [what, why] if p])
            return combined or "", (e.citations or citations_all)[:8]

    return ("\n\n".join(body_parts), citations_all[:8])


async def competitor_analysis(company: CompanyRef, *, bing_agent) -> GWBSSection:
    """GWBS-only competitor analysis for speed. Can be routed to analyst on-demand later."""
    return gwbs_search("competitors", company, bing_agent)

