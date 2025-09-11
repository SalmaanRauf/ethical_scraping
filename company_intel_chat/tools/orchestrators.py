"""
Tool-centric orchestrators for the Chainlit chat experience.
"""
from __future__ import annotations
from typing import List, Tuple, Optional, Callable, Awaitable, Dict
import re
import asyncio

from models.schemas import CompanyRef, Citation, GWBSSection, FullGWBS, AnalysisItem, AnalysisEvent, Briefing
from tools.gwbs_tools import gwbs_full, gwbs_search
from tools.analyst_tools import analyst_synthesis
from services.cache import TTLCache, cache_key
from services.classifier import classify_primary, needs_analyst as _needs_analyst, scopes_for_label

_briefing_cache = TTLCache(maxsize=64, ttl_seconds=1800)

def _analysis_items_from_gwbs(bundle: FullGWBS) -> List[AnalysisItem]:
    items: List[AnalysisItem] = []
    for key, section in (bundle.sections or {}).items():
        if not isinstance(section, GWBSSection):
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

async def full_company_analysis(
    company: CompanyRef,
    *,
    bing_agent,
    analyst_agent,
    progress: Optional[Callable[[str], Awaitable[None]]] = None,
) -> Briefing:
    bkey = cache_key("briefing", company.name, company.ticker)
    cached = _briefing_cache.get(bkey)
    if cached:
        return cached

    scopes = ["sec_filings", "news", "procurement", "earnings", "industry_context"]

    async def _fetch_scope(scope: str) -> GWBSSection:
        # 45s per-scope timeout guard; run sync GWBS call in thread
        return await asyncio.wait_for(asyncio.to_thread(gwbs_search, scope, company, bing_agent), timeout=45)

    # Kick off all scopes concurrently
    tasks: Dict[asyncio.Task, str] = {}
    for s in scopes:
        t = asyncio.create_task(_fetch_scope(s))
        tasks[t] = s

    # Collect sections as they complete; stream progress if callback provided
    sections: Dict[str, GWBSSection] = {}
    for fut in asyncio.as_completed(tasks.keys()):
        scope_name = tasks[fut]
        try:
            sec = await fut
            sections[scope_name] = sec
            if progress:
                try:
                    await progress(scope_name)
                except Exception:
                    pass
        except Exception:
            sections[scope_name] = GWBSSection(scope=scope_name, summary=f"(Failed to fetch {scope_name})", citations=[], audit={})  # type: ignore[arg-type]

    gwbs = FullGWBS(company=company, sections=sections)
    analysis_items = _analysis_items_from_gwbs(gwbs)
    events = await analyst_synthesis(analysis_items, analyst_agent)
    summary = f"Identified {len(events)} significant events for {company.name}."
    sec_summaries = {k: v.summary for k, v in gwbs.sections.items()}
    briefing = Briefing(company=company, events=events, summary=summary, sections=sec_summaries)
    _briefing_cache.set(bkey, briefing)
    return briefing

"""Classification helpers are imported from services.classifier."""

async def follow_up_research(company: CompanyRef, question: str, *, bing_agent, analyst_agent, ctx_blob=None) -> Tuple[str, List[Citation]]:
    if ctx_blob and isinstance(ctx_blob, dict):
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

    label = classify_primary(question)
    scopes = scopes_for_label(label)
    # Run targeted GWBS scopes concurrently in background threads with timeouts
    async def _fetch(scope: str) -> GWBSSection:
        return await asyncio.wait_for(asyncio.to_thread(gwbs_search, scope, company, bing_agent), timeout=45)
    results = await asyncio.gather(*[asyncio.create_task(_fetch(s)) for s in scopes], return_exceptions=True)
    sections: List[GWBSSection] = []
    for res in results:
        if isinstance(res, Exception):
            continue
        sections.append(res)

    body_parts: List[str] = []
    citations_all: List[Citation] = []
    for sec in sections:
        if sec.summary:
            body_parts.append(f"**{sec.scope.replace('_', ' ').title()}**\n{sec.summary}")
        citations_all.extend(sec.citations or [])
    if not body_parts:
        return ("I couldn't find information that directly answers that. Try asking more specifically, or I can re-run a broader search.", citations_all[:8])

    if _needs_analyst(label, question):
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
        if events:
            e = events[0]
            what = e.insights.get("what_happened", "") if isinstance(e.insights, dict) else ""
            why = e.insights.get("why_it_matters", "") if isinstance(e.insights, dict) else ""
            combined = "\n".join([p for p in [what, why] if p])
            return combined or "", (e.citations or citations_all)[:8]
    return ("\n\n".join(body_parts), citations_all[:8])

async def competitor_analysis(company: CompanyRef, *, bing_agent) -> GWBSSection:
    # Offload to background thread
    return await asyncio.to_thread(gwbs_search, "competitors", company, bing_agent)
