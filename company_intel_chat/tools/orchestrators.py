"""
Tool-centric orchestrators for the Chainlit chat experience.
"""
from __future__ import annotations
from typing import List, Tuple, Optional, Callable, Awaitable, Dict
import re
import asyncio

from models.schemas import CompanyRef, Citation, GWBSSection, FullGWBS, AnalysisItem, AnalysisEvent, Briefing, ScopeLiteral
from tools.gwbs_tools import gwbs_full, gwbs_search
from tools.analyst_tools import analyst_synthesis
from services.cache import TTLCache, cache_key
from services.classifier import classify_primary, needs_analyst as _needs_analyst, scopes_for_label
from config.config import Config as AppConfig

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
    """
    Run a full company analysis by fetching multiple GWBS scopes concurrently and
    synthesizing analyst events.

    - Concurrency: independent scopes run concurrently with per-scope timeouts.
    - Progress: an optional async callback receives the scope name as each completes.
    - Caching: returns a cached Briefing when available to avoid redundant work.

    Args:
        company: Target company reference (name and optional ticker).
        bing_agent: Research agent to execute GWBS-backed searches.
        analyst_agent: Analyst agent to synthesize structured events.
        progress: Optional async callable receiving completed scope names.

    Returns:
        Briefing: The aggregated company briefing including GWBS sections and events.
    """
    bkey = cache_key("briefing", company.name, company.ticker)
    cached = _briefing_cache.get(bkey)
    if cached:
        return cached

    # Constrain to the allowed ScopeLiteral values to maintain type safety.
    scopes: List[ScopeLiteral] = [
        "sec_filings", "news", "procurement", "earnings", "industry_context"
    ]

    async def _fetch_scope(scope: ScopeLiteral) -> GWBSSection:
        """Fetch a single GWBS scope with a global, configurable timeout."""
        return await asyncio.wait_for(
            asyncio.to_thread(gwbs_search, scope, company, bing_agent),
            timeout=AppConfig.GWBS_SCOPE_TIMEOUT_SECONDS,
        )

    # Kick off all scopes concurrently
    tasks: Dict[asyncio.Task, ScopeLiteral] = {}
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
                except Exception as cb_err:
                    # Non-fatal: log and continue without breaking user flow
                    print(f"Warning: progress callback failed for scope '{scope_name}': {type(cb_err).__name__}: {cb_err}")
        except Exception as fetch_err:
            # Capture failure details in audit for observability
            sections[scope_name] = GWBSSection(
                scope=scope_name,
                summary=f"(Failed to fetch {scope_name})",
                citations=[],
                audit={"error": f"{type(fetch_err).__name__}: {fetch_err}"},
            )

    gwbs = FullGWBS(company=company, sections=sections)
    analysis_items = _analysis_items_from_gwbs(gwbs)
    events = await analyst_synthesis(analysis_items, analyst_agent)
    summary = f"Identified {len(events)} significant events for {company.name}."
    sec_summaries = {k: v.summary for k, v in gwbs.sections.items()}
    briefing = Briefing(company=company, events=events, summary=summary, sections=sec_summaries, gwbs=gwbs.sections)
    _briefing_cache.set(bkey, briefing)
    return briefing

"""Classification helpers are imported from services.classifier."""

async def follow_up_research(company: CompanyRef, question: str, *, bing_agent, analyst_agent, ctx_blob=None) -> Tuple[str, List[Citation]]:
    """
    Answer a follow-up question in the context of a company's existing briefing.

    - Uses contextual hits from the prior analyst blob when possible for speed.
    - Otherwise, classifies the question and runs targeted GWBS scopes with a
      global, configurable timeout per scope.
    - If synthesis is indicated, invokes the analyst to produce a concise answer
      with citations.
    """
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
        return await asyncio.wait_for(
            asyncio.to_thread(gwbs_search, scope, company, bing_agent),
            timeout=AppConfig.GWBS_SCOPE_TIMEOUT_SECONDS,
        )
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


async def general_research(prompt: str, *, bing_agent, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> Tuple[str, List[Citation]]:
    """
    Run a single GWBS session from a general prompt (no company context).
    Streams a single progress marker if provided and returns (summary, citations).
    """
    if progress:
        try:
            await progress("general")
        except Exception as cb_err:
            print(f"Warning: progress callback failed for 'general': {type(cb_err).__name__}: {cb_err}")
    # Run the custom prompt in a background thread with a reasonable timeout
    async def _run():
        return await asyncio.wait_for(
            asyncio.to_thread(bing_agent.run_custom_search, prompt),
            timeout=AppConfig.GENERAL_RESEARCH_TIMEOUT_SECONDS,
        )
    try:
        raw = await _run()
    except Exception as e:
        # Return a friendly message to the user; keep details out of chat
        print(f"Error in general_research: {type(e).__name__}: {e}")
        return "I couldn't complete that search in time. Please try again.", []
    # Extract citations
    md = (raw or {}).get("citations_md", "")
    cites: List[Citation] = []
    if md:
        # simple parse of markdown bullets
        import re
        for line in md.splitlines():
            m = re.match(r"^- \[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)", line.strip())
            if m:
                try:
                    cites.append(Citation(title=m.group("title"), url=m.group("url")))
                except Exception:
                    continue
    return (raw or {}).get("summary", ""), cites[:8]
