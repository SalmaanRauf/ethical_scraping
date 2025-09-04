# services/follow_up_handler.py
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from services.conversation_manager import ConversationContext, AnalysisBlob
from agents.bing_data_extraction_agent import BingDataExtractionAgent

# --- classification buckets (fast regex; case-insensitive) ---
PATTERNS: Dict[str, List[re.Pattern]] = {
    "risk": [
        re.compile(r"\b(risk|downside|exposure|threat|vulnerab)", re.I),
        re.compile(r"\b(credit risk|regulatory risk|operational risk|cyber|lawsuit|fine)\b", re.I),
    ],
    "financial": [
        re.compile(r"\b(revenue|earnings?|profit|loss|margin|guidance|forecast)\b", re.I),
        re.compile(r"\b(how much|how big|financial impact|cost|investment|capex|opex|cash flow)\b", re.I),
    ],
    "competitive": [
        re.compile(r"\b(competitor|competitive|market share|position|moat|benchmark|vs|versus)\b", re.I),
        re.compile(r"\b(compare|comparison|stack up|edge)\b", re.I),
    ],
    "regulatory": [
        re.compile(r"\b(regulatory|regulation|compliance|legal|SEC|DOJ|FTC|antitrust)\b", re.I),
        re.compile(r"\b(filing|10\-K|10\-Q|8\-K|consent decree|settlement)\b", re.I),
    ],
    "strategic": [
        re.compile(r"\b(strategy|strategic|roadmap|future|plan|initiative|priorit(?:y|ies))\b", re.I),
        re.compile(r"\b(product|launch|expansion|hiring|acquisition|divestiture)\b", re.I),
    ],
    "timeline": [
        re.compile(r"\b(when|timeline|by when|deadline|date)\b", re.I),
    ],
}

# map classification → GWBS scopes to query if needed
FALLBACK_SCOPES: Dict[str, List[str]] = {
    "financial": ["news", "sec_filings"],
    "risk": ["news", "sec_filings"],
    "competitive": ["news", "industry_context"],
    "regulatory": ["sec_filings", "procurement"],
    "strategic": ["news", "industry_context"],
    "timeline": ["news", "sec_filings"],
}

def classify_follow_up(question: str) -> str:
    for label, regs in PATTERNS.items():
        if any(r.search(question) for r in regs):
            return label
    return "general"

def _strip_inline_urls(text: str) -> str:
    # remove naked URLs; we show curated citations separately
    return re.sub(r"https?://\S+", "[link]", text)

def _merge_citations(*citation_lists: List[Dict[str, Any]], cap: int = 8) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for lst in citation_lists:
        for c in (lst or []):
            url = (c.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({"url": url, "title": c.get("title")})
            if len(out) >= cap:
                return out
    return out

class FollowUpHandler:
    """Answer follow-ups using existing analysis; fall back to scoped GWBS queries."""

    def __init__(self, bing_agent: BingDataExtractionAgent):
        self.bing_agent = bing_agent

    def handle_follow_up(self, ctx: ConversationContext, question: str) -> Dict[str, Any]:
        question = question.strip()
        label = classify_follow_up(question)
        active = ctx.get_analysis()
        if not active:
            # No prior analysis; suggest a company analysis
            return {
                "answer": "I don't have an analysis loaded yet. Tell me a company (e.g., Capital One or ticker COF) and I'll run the full analysis.",
                "citations": [],
                "source": "system",
            }

        # 1) Try to answer from existing analyst summary + events.
        answer, cited = self._answer_from_existing(active, question, label)
        if answer:
            return {"answer": answer, "citations": cited, "source": "analysis"}

        # 2) If inadequate, run **scoped** GWBS searches relevant to the label.
        scopes = FALLBACK_SCOPES.get(label, ["news"])
        gwbs = self._targeted_gwbs(active.company_name, scopes)

        # 3) Synthesize response and citations
        body_parts: List[str] = []
        all_cites: List[List[Dict[str, Any]]] = []
        for scope_name, payload in gwbs.items():
            summary = (payload or {}).get("summary") or ""
            if summary:
                body_parts.append(f"**{scope_name.replace('_',' ').title()}**\n{_strip_inline_urls(summary)}")
            cites = (payload or {}).get("citations") or []
            all_cites.append(cites)

        merged = _merge_citations(*all_cites)
        if not body_parts:
            return {
                "answer": "I couldn't find anything new that directly answers that. Try asking more specifically, or I can re-run a broader search.",
                "citations": merged,
                "source": "gwbs",
            }

        final = "\n\n".join(body_parts)
        return {"answer": final, "citations": merged, "source": "gwbs"}

    # ---------- internals ----------

    def _answer_from_existing(self, blob: AnalysisBlob, q: str, label: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Very light-weight lexical search across analyst summary & events."""
        q_lower = q.lower()
        chunks: List[str] = []
        if blob.analyst_summary:
            chunks.append(blob.analyst_summary)

        for ev in blob.analyst_events or []:
            text_bits = [ev.get("what_happened", ""), ev.get("why_it_matters", ""), ev.get("advice", "")]
            chunks.append(" ".join(t for t in text_bits if t))

        # naive contains check; swap with embeddings if you wire them later
        hits = [c for c in chunks if q_lower[:60] in c.lower() or any(k in c.lower() for k in label.split())]
        if not hits:
            return None, []

        # assemble a concise answer
        para = hits[0]
        if len(para) > 1200:
            para = para[:1100].rsplit(" ", 1)[0] + "…"
        return para, []

    def _targeted_gwbs(self, company: str, scopes: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for s in scopes:
            try:
                if s == "news":
                    results["news"] = self.bing_agent.search_news(company)
                elif s == "sec_filings":
                    results["sec_filings"] = self.bing_agent.search_sec_filings(company)
                elif s == "procurement":
                    results["procurement"] = self.bing_agent.search_procurement(company)
                elif s == "industry_context":
                    results["industry_context"] = self.bing_agent.search_industry_context(company)
                else:
                    # ignore unknown scopes silently
                    pass
            except Exception as e:
                # degrade gracefully
                results[s] = {"summary": f"(Failed to fetch {s}: {e})", "citations": []}
        return results

# Global follow-up handler instance (will be initialized with bing_agent)
follow_up_handler = None

def initialize_follow_up_handler(bing_agent: BingDataExtractionAgent):
    """Initialize the global follow-up handler"""
    global follow_up_handler
    follow_up_handler = FollowUpHandler(bing_agent)
    return follow_up_handler
