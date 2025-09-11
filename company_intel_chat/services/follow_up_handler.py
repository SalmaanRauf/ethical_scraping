# services/follow_up_handler.py
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from services.conversation_manager import ConversationContext, AnalysisBlob
from agents.bing_data_extraction_agent import BingDataExtractionAgent
from services.classifier import classify_primary, scopes_for_label

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
        label = classify_primary(question)
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
        scopes = scopes_for_label(label)
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
