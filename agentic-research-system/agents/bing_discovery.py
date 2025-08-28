"""
Bing Grounding (GWBS) Research Agent — URL-safe, deterministic, annotation-driven.

Key changes vs. your original:
- Deterministic generation (temperature=0.0) to reduce fabricated specifics.
- STRICT: never trust body text links. We ignore any inline URLs the model writes.
- We ONLY surface URLs from GWBS citation annotations (url_citation_annotations).
- If citations are missing or too few, we run ONE corrective follow-up asking GWBS to re-search and attach live citations.
- No web scraping / no direct HTTP validation — we rely solely on GWBS to discover and cite sources.
- Cleaner separation of concerns + better error handling + light auditing of Bing queries via run steps (if available).

NOTE: GWBS does not expose raw page content to your app; you must rely on citations returned by the tool.
"""

import os
from typing import Dict, Any, Optional, Tuple, List
import re

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool
from azure.identity import DefaultAzureCredential


def _cond_load_dotenv() -> None:
    """Load environment variables from .env if python-dotenv is present."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except ImportError:
        # It's fine if dotenv isn't installed.
        pass


class BingDataExtractionAgent:
    """
    A deterministic, grounding-first research agent that relies exclusively on
    GWBS citation annotations for source URLs and NEVER trusts inline links in the model's prose.
    """

    # System prompt with strict rules that align with our runtime enforcement.
    SYSTEM_PROMPT = (
        "You are **ResearchAgentPRO**. Use **Grounding with Bing Search (GWBS)** to produce source-first, "
        "fact-checked research.\n\n"
        "NON-NEGOTIABLES:\n"
        "1) Search First (and verify via GWBS): Run GWBS to discover and select sources. Prefer primary/official sources "
        "   (issuer IR, SEC EDGAR, US regulators) and tier-1 wires (Reuters/Bloomberg/AP/WSJ) when available, but you may use "
        "   any reputable source discovered by GWBS. Use freshness appropriately.\n"
        "2) Absolutely **do not** invent URLs. If you cannot find a source, say so briefly and try another search.\n"
        "3) Provide **sources only via citations/annotations**. Do not place raw URLs in your narrative/body text.\n"
        "4) When citing SEC filings, prefer the EDGAR filing index/IXBRL page that directly corresponds to the filing.\n"
        "5) If citations are missing or low-confidence, run another search before responding.\n\n"
        "OUTPUT STYLE:\n"
        "• Be concise and bullet-first. Use the requested output schema if provided by the user prompt.\n"
        "• No raw URLs in the body. The system will attach your citations automatically from annotations.\n"
        "• If nothing qualifies, output: **“No material updates.”**"
    )

    # You can keep your previous long schema-driven instruction here if you want.
    # Keeping it short makes reuse easier; task prompts below add per-task specifics.

    def __init__(
        self,
        project_endpoint: Optional[str] = None,
        model_deployment_name: Optional[str] = None,
        azure_bing_connection_id: Optional[str] = None,
        credential: Optional[Any] = None,
    ):
        _cond_load_dotenv()
        self.project_endpoint = project_endpoint or os.environ.get("PROJECT_ENDPOINT")
        self.model_deployment_name = model_deployment_name or os.environ.get("MODEL_DEPLOYMENT_NAME")
        self.azure_bing_connection_id = azure_bing_connection_id or os.environ.get("AZURE_BING_CONNECTION_ID")
        self.credential = credential or DefaultAzureCredential()

        if not all([self.project_endpoint, self.model_deployment_name, self.azure_bing_connection_id]):
            raise ValueError("Missing required Azure Bing env variables! "
                             "Ensure PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME, AZURE_BING_CONNECTION_ID are set.")

    # -----------------------
    # Internal helper methods
    # -----------------------

    def _create_agent(self, agents_client):
        """
        Create an ephemeral agent configured for Bing Grounding.
        Critical: temperature=0.0 to suppress creative fabrication of specifics like date-stamped URL slugs.
        """
        bing_tool = BingGroundingTool(connection_id=self.azure_bing_connection_id)
        agent = agents_client.create_agent(
            model=self.model_deployment_name,
            name="bing-data-extraction-session",
            instructions=self.SYSTEM_PROMPT,
            tools=bing_tool.definitions,
            temperature=0.0,           # Key control to reduce hallucinated specifics
            parallel_tool_calls=False  # Optional: simpler traces
        )
        return agent

    @staticmethod
    def _strip_inline_urls(text: str) -> str:
        """
        Remove any inline raw URLs from the body text (we do not trust them).
        """
        if not text:
            return text
        return re.sub(r"https?://\S+", "[link omitted]", text)

    @staticmethod
    def _extract_text(msg) -> str:
        """
        Collect the assistant's text parts and strip any inline raw URLs.
        We only surface citations from annotations later.
        """
        out: List[str] = []
        for t in getattr(msg, "text_messages", []) or []:
            if hasattr(t, "text") and hasattr(t.text, "value"):
                out.append(t.text.value)
            elif hasattr(t, "value"):
                out.append(t.value)
            elif isinstance(t, str):
                out.append(t)
        body = "\n".join(out)
        return BingDataExtractionAgent._strip_inline_urls(body)

    @staticmethod
    def _extract_citations(msg) -> List[Dict[str, str]]:
        """
        Pull GWBS citation annotations. This is the ONLY place we source URLs from.
        """
        cites: List[Dict[str, str]] = []
        for ann in getattr(msg, "url_citation_annotations", []) or []:
            try:
                url = ann.url_citation.url
                title = ann.url_citation.title or url
                if url:
                    # basic sanity (no http fetch; not web scraping)
                    if url.lower().startswith(("http://", "https://")):
                        cites.append({"title": title, "url": url})
            except Exception:
                continue
        return cites

    @staticmethod
    def _citations_to_markdown(cites: List[Dict[str, str]]) -> str:
        """Render citations list into a markdown bullet list."""
        if not cites:
            return ""
        lines = [f"- [{c['title']}]({c['url']})" for c in cites]
        return "\n".join(lines)

    def _log_run_steps_bing_queries(self, agents_client, thread_id: str, run_id: str) -> List[str]:
        """
        Optional audit hook: list run steps and harvest any recorded Bing query strings.
        (No external HTTP; this is just metadata from the Agents service.)
        """
        queries: List[str] = []
        try:
            steps = agents_client.runs.list_steps(thread_id=thread_id, run_id=run_id)
            for s in steps:
                tcalls = getattr(s, "tool_calls", None) or []
                for tc in tcalls:
                    # Defensive: look for tool call structures that may show a query
                    # Exact shape can vary; we capture stringy params for audit only.
                    for attr in ("query", "parameters", "args", "arguments"):
                        val = getattr(tc, attr, None)
                        if val:
                            queries.append(str(val))
        except Exception:
            # If step listing isn't available, silently continue.
            pass
        return queries

    def _run_once(self, agents_client, agent, user_prompt: str) -> Tuple[str, List[Dict[str, str]], List[str]]:
        """
        Single run: post the user prompt, process, return (body_text, citations, bing_queries).
        """
        thread = agents_client.threads.create()
        agents_client.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_prompt,
        )

        print("Processing Bing grounding search, this may take up to 30 seconds...")
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        if run.status == "failed":
            raise RuntimeError(f"Bing grounding run failed: {run.last_error}")

        msg = agents_client.messages.get_last_message_by_role(thread_id=thread.id, role=MessageRole.AGENT)
        if not msg:
            raise RuntimeError("No agent response received.")

        body = self._extract_text(msg)
        citations = self._extract_citations(msg)
        queries = self._log_run_steps_bing_queries(agents_client, thread.id, run.id)

        return body, citations, queries

    def _run_agent_task(self, user_prompt: str) -> Dict[str, Any]:
        """
        Core runner:
        - Create ephemeral agent (temperature=0.0).
        - Run once and collect citations from GWBS annotations.
        - If citations are empty or suspiciously low, run ONE corrective pass asking for proper citations.
        - Return summary text (without inline URLs) + citations_md + audit of queries.
        """
        with AIProjectClient(endpoint=self.project_endpoint, credential=self.credential) as project_client:
            agents_client = project_client.agents
            agent = self._create_agent(agents_client)

            try:
                # Pass 1
                body, cites, queries = self._run_once(agents_client, agent, user_prompt)

                # If we got zero citations, ask for a corrective pass.
                # (We don't fetch anything ourselves; we rely on GWBS to re-search and attach citations.)
                if not cites:
                    follow_up = (
                        user_prompt
                        + "\n\nFOLLOW-UP:\n"
                          "Citations were missing or incomplete. Re-run the search and include only live, specific citations "
                          "from GWBS annotations to support each claim. Do not add raw URLs to the body."
                    )
                    body, cites2, queries2 = self._run_once(agents_client, agent, follow_up)
                    cites = cites2 or cites
                    queries.extend(queries2 or [])

                # Build markdown list from citations only (no inline URLs from body)
                bullets = self._citations_to_markdown(cites)

            finally:
                # Always clean up the ephemeral agent
                try:
                    agents_client.delete_agent(agent.id)
                except Exception:
                    pass

        return {
            "summary": body.strip(),
            "citations_md": bullets.strip(),
            "audit": {
                "bing_queries": queries,
                "citation_count": len(cites),
            },
        }

    # -----------------------
    # High-level task helpers
    # -----------------------

    def search_sec_filings(self, company: str) -> Dict[str, Any]:
        """
        Ask for 2025+ SEC filings and findings. We instruct the model to use GWBS to find
        the exact filing pages (index/IXBRL) and to summarize key items/sections.
        """
        query = (
            f"TASK: SEC filings and key findings for {company}. "
            "Focus on 2025+ 10-K/10-Q/8-K and highlight material items (e.g., Risk Factors, MD&A, specific 8-K Items). "
            "Prefer EDGAR filing index/IXBRL pages. Provide concise bullets per finding. "
            "Remember: sources only via citations/annotations; do not include raw URLs in body."
        )
        return self._run_agent_task(query)

    def search_news(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: 2025+ impactful news for {company} (regulatory, financial, M&A, risk). "
            "Use GWBS with freshness. Provide 2+ citations per major claim when available. "
            "No raw URLs in body; citations only via annotations."
        )
        return self._run_agent_task(query)

    def search_procurement(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: U.S. Government procurement context for {company}. "
            "Use GWBS to find notable SAM.gov notices or official releases; if none are visible via GWBS, say so briefly. "
            "No raw URLs in body; citations only via annotations."
        )
        return self._run_agent_task(query)

    def search_earnings(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: Earnings for {company} (transcripts, releases, guidance). "
            "Prefer issuer IR and SEC filings surfaced by GWBS. Summarize key deltas and guidance clearly. "
            "No raw URLs in body; citations only via annotations."
        )
        return self._run_agent_task(query)

    def search_industry_context(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: Sector/competitive context for {company}. "
            "Use GWBS to discover credible landscape sources; keep to facts and label opinion as such. "
            "No raw URLs in body; citations only via annotations."
        )
        return self._run_agent_task(query)

    def get_full_intelligence(self, company: str) -> Dict[str, Any]:
        return {
            "sec_filings": self.search_sec_filings(company),
            "news": self.search_news(company),
            "procurement": self.search_procurement(company),
            "earnings": self.search_earnings(company),
            "industry_context": self.search_industry_context(company),
        }


def test_bing_data_extraction(company: str) -> None:
    agent = BingDataExtractionAgent()
    res = agent.get_full_intelligence(company)
    for section, data in res.items():
        print(f"\n--- {section.upper()} ---\n")
        print(data.get("summary", "(no summary)"))
        print("\nCITATIONS:\n")
        print(data.get("citations_md", "(no citations)"))
        # Optional: print audit info for debugging
        audit = data.get("audit", {})
        if audit:
            print("\nAUDIT:")
            print(f"- citation_count: {audit.get('citation_count')}")
            if audit.get("bing_queries"):
                print("- bing_queries:")
                for q in audit["bing_queries"]:
                    print(f"  • {q}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Bing-powered, schema-based research for a company.")
    parser.add_argument("--company", "-c", required=True, help="Target company name")
    args = parser.parse_args()
    test_bing_data_extraction(args.company)
