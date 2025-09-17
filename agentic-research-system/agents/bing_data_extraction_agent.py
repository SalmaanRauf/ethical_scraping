"""
Grounding with Bing Search Tool Research Agent — annotation-driven, no scraping, SDK-safe.

What this does:
- Uses the Grounding with Bing Search tool for discovery and understanding of sources.
- Never trusts inline URLs in model prose; only uses the tool's citation annotations for links.
- If citations are empty, performs ONE corrective follow-up asking the model to re-search and attach citations.
- No web scraping or direct HTTP validation.
- Avoids SDK parameters that caused errors (e.g., 'parallel_tool_calls', 'temperature').

If you later upgrade the azure.ai.agents SDK and want to set model parameters,
add them carefully with a try/except TypeError around create_agent.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool
from azure.identity import DefaultAzureCredential


def _cond_load_dotenv() -> None:
    """Load environment variables from .env if python-dotenv is present."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except ImportError:
        pass


class BingDataExtractionAgent:
    """
    Research agent that relies exclusively on the Grounding with Bing Search tool:
    - Citations (URL + title) are extracted only from the tool's citation annotations.
    - Inline URLs in the model body are stripped and never trusted.
    - One corrective follow-up is attempted if no citations are returned.
    """

    SYSTEM_PROMPT = (
        "You are an intelligent AI agent skilled at using the **Grounding with Bing Search tool** to discover, "
        "understand, and cite reputable web information for the user's question.\n\n"
        "Follow this process:\n"
        "Step 1 — Understand Intent:\n"
        "• Carefully analyze the user's question to capture the key facts required.\n\n"
        "Step 2 — Search & Compile (via the Grounding with Bing Search tool):\n"
        "• Use the tool to perform web search and retrieve information.\n"
        "• Prefer primary/official sources (issuer investor relations sites, SEC EDGAR, U.S. regulators) and tier-1 wires "
        "  (Reuters, Bloomberg, AP, WSJ) when available, but you may use any reputable sources discovered by the tool.\n"
        "• Compile findings into a structured, concise summary with clear bullets and/or short paragraphs.\n"
        "• IMPORTANT: Provide **sources only via the tool’s citation annotations**. Do NOT place raw URLs in your body text.\n"
        "• When citing SEC filings, reference the specific filing page discovered via the tool (e.g., filing index/IXBRL), "
        "  not guessed or constructed links.\n\n"
        "Step 3 — Coverage Check:\n"
        "• If information is insufficient to confidently answer, perform additional searches using the tool and update findings.\n\n"
        "Step 4 — Output Formatting:\n"
        "• Present a clear, organized answer. Use headings where appropriate. Keep the writing concise and factual.\n"
        "• No raw URLs in the body; citations will be attached by the system from your tool annotations.\n"
        "• If nothing qualifies, output: **“No material updates.”**"
    )

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
            raise ValueError(
                "Missing required Azure variables. Set PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME, AZURE_BING_CONNECTION_ID."
            )

    # -----------------------
    # Internal helper methods
    # -----------------------

    def _create_agent(self, agents_client):
        """
        Create an ephemeral agent configured with the Grounding with Bing Search tool.
        NOTE: We do NOT pass unsupported kwargs (e.g., 'parallel_tool_calls', 'temperature').
        """
        bing_tool = BingGroundingTool(connection_id=self.azure_bing_connection_id)
        agent = agents_client.create_agent(
            model=self.model_deployment_name,
            name="bing-data-extraction-session",
            instructions=self.SYSTEM_PROMPT,
            tools=bing_tool.definitions,
        )
        return agent

    @staticmethod
    def _strip_inline_urls(text: str) -> str:
        """Remove any inline raw URLs from the body text (we do not trust them)."""
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
        Pull citation annotations from the Grounding with Bing Search tool.
        This is the ONLY place we source URLs from.
        """
        cites: List[Dict[str, str]] = []
        for ann in getattr(msg, "url_citation_annotations", []) or []:
            try:
                url = ann.url_citation.url
                title = ann.url_citation.title or url
                if url and url.lower().startswith(("http://", "https://")):
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
        Optional audit hook: list run steps and harvest any recorded search query strings
        from the Grounding with Bing Search tool calls (shape can vary; best-effort).
        """
        queries: List[str] = []
        try:
            steps = agents_client.runs.list_steps(thread_id=thread_id, run_id=run_id)
            for s in steps:
                tcalls = getattr(s, "tool_calls", None) or []
                for tc in tcalls:
                    for attr in ("query", "parameters", "args", "arguments"):
                        val = getattr(tc, attr, None)
                        if val:
                            queries.append(str(val))
        except Exception:
            pass
        return queries

    def _run_once(self, agents_client, agent, user_prompt: str) -> Tuple[str, List[Dict[str, str]], List[str]]:
        """
        Single run:
        - Post the user prompt
        - Process
        - Return (body_text, citations_from_annotations, search_queries_audit)
        """
        thread = agents_client.threads.create()
        agents_client.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_prompt,
        )

        print("Processing with the Grounding with Bing Search tool; this may take up to ~30s...")
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        if run.status == "failed":
            raise RuntimeError(f"Run failed: {run.last_error}")

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
        - Create ephemeral agent.
        - Run once and collect citation annotations.
        - If citations are empty, run ONE corrective pass asking the model to re-search and attach citations.
        - Return summary text (without inline URLs) + citations_md + audit of queries.
        """
        with AIProjectClient(endpoint=self.project_endpoint, credential=self.credential) as project_client:
            agents_client = project_client.agents
            agent = self._create_agent(agents_client)

            try:
                # Pass 1
                body, cites, queries = self._run_once(agents_client, agent, user_prompt)

                # If we got zero citations, ask for a corrective pass.
                if not cites:
                    follow_up = (
                        user_prompt
                        + "\n\nFOLLOW-UP:\n"
                          "Citations were missing or incomplete. Re-run the search using the Grounding with Bing Search tool "
                          "and include live, specific citations via annotations for each major claim. "
                          "Do not place raw URLs in the body."
                    )
                    body2, cites2, queries2 = self._run_once(agents_client, agent, follow_up)
                    if cites2:
                        body, cites = body2, cites2
                    queries.extend(queries2 or [])

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
                "search_queries": queries,
                "citation_count": len(cites),
            },
        }

    # -----------------------
    # High-level task helpers
    # -----------------------

    def search_sec_filings(self, company: str) -> Dict[str, Any]:
        """
        Ask for 2025+ SEC filings and findings.
        IMPORTANT: the model must use the Grounding with Bing Search tool to locate the specific filing pages
        and summarize key sections (e.g., Risk Factors, MD&A, 8-K Items). We never guess or construct links.
        """
        query = (
            f"TASK: SEC filings and key findings for {company}. "
            "Focus on 2025+ 10-K, 10-Q, and 8-K; highlight material items (Risk Factors, MD&A, specific 8-K Items). "
            "Use the Grounding with Bing Search tool to discover the specific filing pages (filing index/IXBRL) and "
            "summarize the relevant content. Provide concise bullets per finding. "
            "Do NOT place raw URLs in your body; provide sources only via citation annotations."
        )
        return self._run_agent_task(query)

    def search_news(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: 2025+ impactful news for {company} (regulatory, financial, M&A, risk). "
            "Use the Grounding with Bing Search tool with appropriate freshness. Provide multiple citations for major claims "
            "when available. No raw URLs in body; sources only via citation annotations."
        )
        return self._run_agent_task(query)

    def search_procurement(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: U.S. Government procurement context for {company}. "
            "Use the Grounding with Bing Search tool to find notable government notices or official releases; "
            "if none are visible, say so briefly. No raw URLs in body; sources only via citation annotations."
        )
        return self._run_agent_task(query)

    def search_earnings(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: Earnings for {company} (transcripts, releases, guidance). "
            "Prefer issuer investor relations and SEC filings discovered via the Grounding with Bing Search tool. "
            "Summarize key deltas and guidance clearly. No raw URLs in body; sources only via citation annotations."
        )
        return self._run_agent_task(query)

    def search_industry_context(self, company: str) -> Dict[str, Any]:
        query = (
            f"TASK: Sector/competitive context for {company}. "
            "Use the Grounding with Bing Search tool to discover credible landscape sources; keep to facts and label opinion as such. "
            "No raw URLs in body; sources only via citation annotations."
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
            if audit.get("search_queries"):
                print("- search_queries:")
                for q in audit["search_queries"]:
                    print(f"  • {q}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run research with the Grounding with Bing Search tool for a company.")
    parser.add_argument("--company", "-c", required=True, help="Target company name")
    args = parser.parse_args()
    test_bing_data_extraction(args.company)
