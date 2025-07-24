import os
import sys
from typing import Optional, Dict, Any, Tuple  # <--- Add Tuple typing
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

# Add python-dotenv for .env loading
def _cond_load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("python-dotenv not installed; skipping .env autoload. (You can pip install python-dotenv)")

class BingGroundingAgent:
    """
    BingGroundingAgent uses Azure AI Foundry Agents with Bing grounding to produce
    up-to-date, neutral, and well-cited industry summaries for a given company.
    """

    # Use the exact system prompt you provided:
    GROUNDING_SYSTEM_PROMPT = (
        "You are an AI agent who is tasked with analyzing the broader sector/industry/market trends which the provided company exists with in."
        "You are to ALWAYS use a live bing search to source your data."
        "Your results should also return a generalized analysis of current industry trends and competitor moves."
        "Your resulting paragraph of analysis should be between 100-150 words, primarily focused on the broader industry/sector."
        "You may not use any prior knowledge, all data must current search resources as of 07/23/2025."
        "Cite any sites/URL's which you visited to gather your intel."
    )

    def __init__(self,
                 project_endpoint: Optional[str] = None,
                 model_deployment_name: Optional[str] = None,
                 azure_bing_connection_id: Optional[str] = None,
                 credential: Optional[Any] = None):
        # Auto-load .env file if available
        _cond_load_dotenv()

        self.project_endpoint = project_endpoint or os.environ.get("PROJECT_ENDPOINT")
        self.model_deployment_name = model_deployment_name or os.environ.get("MODEL_DEPLOYMENT_NAME")
        self.azure_bing_connection_id = azure_bing_connection_id or os.environ.get("AZURE_BING_CONNECTION_ID")
        self.credential = credential or DefaultAzureCredential()

        if not all([self.project_endpoint, self.model_deployment_name, self.azure_bing_connection_id]):
            raise ValueError(
                "Required Azure environment variables not set: PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME, AZURE_BING_CONNECTION_ID"
            )

        self.project_client = AIProjectClient(
            endpoint=self.project_endpoint,
            credential=self.credential,
        )

    def get_industry_briefing(self, company_name: str, prompt_override: str = None) -> Dict[str, str]:
        """
        For a given company name, run a single Bing-grounded agent session to return:
          - A summary paragraph (str)
          - Markdown-formatted citation bullets (str)
        Returns a dict: {'summary': ..., 'citations_md': ...}
        Optionally override the user prompt for Bing grounding.
        """
        if prompt_override:
            user_prompt = prompt_override
        else:
            user_prompt = company_name

        with self.project_client:
            agents_client = self.project_client.agents

            # --- 1. Create Bing Grounding Tool ---
            bing_tool = BingGroundingTool(connection_id=self.azure_bing_connection_id)

            # --- 2. Create an agent ---
            agent = agents_client.create_agent(
                model=self.model_deployment_name,
                name=f"bing-grounding-agent-session",
                instructions=self.GROUNDING_SYSTEM_PROMPT,
                tools=bing_tool.definitions,
            )

            # --- 3. Create a thread for the "conversation" ---
            thread = agents_client.threads.create()

            # --- 4. Send user prompt (custom or just company name) ---
            message = agents_client.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=user_prompt,
            )

            # --- 5. Run the agent within the thread ---
            print("Processing Bing grounding search, this may take up to 30 seconds...")
            run = agents_client.runs.create_and_process(
                thread_id=thread.id, agent_id=agent.id
            )
            if run.status == "failed":
                raise RuntimeError(f"Bing grounding run failed: {run.last_error}")

            # --- 6. Fetch the agent's message (with citations) ---
            response_message = agents_client.messages.get_last_message_by_role(
                thread_id=thread.id, role=MessageRole.AGENT
            )
            if not response_message:
                raise RuntimeError("No agent response received.")

            # Compile all message text responses
            output_text = ""
            for text_message in getattr(response_message, "text_messages", []):
                if hasattr(text_message, 'text') and hasattr(text_message.text, 'value'):
                    output_text += text_message.text.value + "\n"
                elif hasattr(text_message, 'value'):
                    output_text += text_message.value + "\n"
                elif isinstance(text_message, str):
                    output_text += text_message + "\n"

            # Add citations, if any
            citations_md = []
            for annotation in getattr(response_message, "url_citation_annotations", []):
                url = annotation.url_citation.url
                title = annotation.url_citation.title
                if url and title:
                    citations_md.append(f"[{title}]({url})")
            
            # Try to split the output (paragraph/markdown sources)
            summary, bullets = self._parse_output(output_text, citations_md)
            
            # --- 7. Clean-up agent session (optional but good practice) ---
            agents_client.delete_agent(agent.id)
            # Note: threads/messages are ephemeral by default, no need to clean

        return {"summary": summary.strip(), "citations_md": bullets.strip()}
    @staticmethod
    def _parse_output(output_text: str, citations_md: list) -> Tuple[str, str]:
        """
        Try to extract the summary and list of markdown bullet citations,
        using agent's output and explicit citations if present.
        """
        summary_lines = []
        bullet_lines = []
        collecting_bullets = False
        for line in output_text.strip().splitlines():
            line = line.strip()
            if line.startswith("- ["):
                collecting_bullets = True
            if collecting_bullets:
                bullet_lines.append(line)
            elif line:
                summary_lines.append(line)
        summary = " ".join(summary_lines)
        # Deduplicate/merge bullets from output + explicit citations
        bullets_md = bullet_lines or []
        for md in citations_md:
            if md not in bullets_md:
                bullets_md.append(md)
        # Bullets as a joined newline string
        bullets = "\n".join(bullets_md)
        return summary, bullets

# CLI for local testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Bing grounding search for a company name using Azure AI Agents."
    )
    parser.add_argument(
        "--company", "-c", required=True, help="Company name to summarize (e.g. 'Capital One Financial Corp')"
    )
    parser.add_argument(
        "--prompt", "-p", required=False, default=None, help="Optional: Custom research prompt; use '{company_name}' as a placeholder for the company."
    )

    args = parser.parse_args()
    agent = BingGroundingAgent()
    if args.prompt:
        prompt = args.prompt.format(company_name=args.company)
    else:
        prompt = (
            f"For the company {args.company}, use live Bing web search to find recent, reputable industry, market, and regulatory trends. "
            "ONLY provide citations to sources you find in this Bing search; never invent URLs. "
            "Summarize trends in 100 words, then list those URLs as Markdown bullets."
        )
    result = agent.get_industry_briefing(args.company, prompt_override=prompt)
    print("\n---- INDUSTRY CONTEXT (SUMMARY) ----\n")
    print(result["summary"])
    print("\n---- CITATIONS ----\n")
    print(result["citations_md"] or "(No citations found)")
