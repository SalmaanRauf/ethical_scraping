"""
Analyst tool wrappers that expose a typed interface over AnalystAgent.
"""
from __future__ import annotations
from typing import List

from models.schemas import AnalysisItem, AnalysisEvent, Citation
from agents.analyst_agent import AnalystAgent


async def analyst_synthesis(items: List[AnalysisItem], analyst: AnalystAgent) -> List[AnalysisEvent]:
    wire_items = []
    for it in items:
        wire_items.append(
            {
                "company": it.company,
                "title": it.title,
                "description": it.content,
                "content": it.content,
                "raw_data": it.raw,
                "citations": [c.dict() for c in it.citations],
            }
        )
    results = await analyst.analyze_all_data(wire_items)
    events: List[AnalysisEvent] = []
    for ev in results or []:
        title = ev.get("title") or ev.get("headline") or "Untitled"
        insights = ev.get("insights") or {}
        cites_raw = ev.get("citations") or []
        if not cites_raw and isinstance(ev.get("raw_data"), dict):
            md = ev["raw_data"].get("citations_md", "")
            cites_raw = _citations_from_md(md)
        citations: List[Citation] = []
        for c in cites_raw or []:
            try:
                if isinstance(c, Citation):
                    citations.append(c)
                elif isinstance(c, dict) and c.get("url"):
                    citations.append(Citation(title=c.get("title"), url=c.get("url")))
            except Exception:
                continue
        # Extract source_urls from insights and add to citations
        if isinstance(insights, dict) and insights.get("source_urls"):
            for url in insights["source_urls"]:
                if isinstance(url, str) and url.startswith("http"):
                    citations.append(Citation(title="Source", url=url))
        meta = {k: v for k, v in ev.items() if k not in {"title", "insights", "citations"}}
        events.append(AnalysisEvent(title=title, insights=insights, citations=citations, meta=meta))
    return events


def _citations_from_md(md: str) -> list[dict]:
    import re
    out: list[dict] = []
    if not md:
        return out
    for line in (md or "").splitlines():
        m = re.match(r"^- \[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)", line.strip())
        if m:
            out.append({"title": m.group("title"), "url": m.group("url")})
    return out