"""Client wrapper for Azure AI Foundry Deep Research tool."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import AzureError
from azure.ai.projects.aio import AIProjectClient
from azure.ai.agents.models import (
    DeepResearchToolDefinition,
    DeepResearchDetails,
    DeepResearchBingGroundingConnection,
    MessageRole,
)

from config.config import AppConfig


logger = logging.getLogger(__name__)


@dataclass
class DeepResearchCitation:
    title: str
    url: str


@dataclass
class DeepResearchSection:
    heading: str
    content: str
    citations: List[DeepResearchCitation]


@dataclass
class DeepResearchReport:
    summary: str
    sections: List[DeepResearchSection]
    citations: List[DeepResearchCitation]
    metadata: Dict[str, Any]


class DeepResearchClient:
    """Handles interaction with Azure AI Deep Research tool."""

    def __init__(self) -> None:
        if not (AppConfig.PROJECT_ENDPOINT and AppConfig.MODEL_DEPLOYMENT_NAME):
            raise RuntimeError("Project endpoint and model deployment must be configured")
        if not (AppConfig.DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME and AppConfig.BING_CONNECTION_NAME):
            raise RuntimeError("Deep Research configuration missing")

        self._project_endpoint = AppConfig.PROJECT_ENDPOINT
        self._primary_model = AppConfig.MODEL_DEPLOYMENT_NAME
        self._deep_model = AppConfig.DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME
        self._bing_connection = AppConfig.BING_CONNECTION_NAME

        self._credential: Optional[DefaultAzureCredential] = None
        self._client: Optional[AIProjectClient] = None
        self._agent_id: Optional[str] = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> None:
        if self._client:
            return
        async with self._lock:
            if self._client:
                return
            credential = DefaultAzureCredential()
            client = AIProjectClient(endpoint=self._project_endpoint, credential=credential)
            self._credential = credential
            self._client = client
            await self._ensure_agent()

    async def _ensure_agent(self) -> None:
        if self._agent_id or not self._client:
            return
        
        try:
            deep_tool = DeepResearchToolDefinition(
                deep_research=DeepResearchDetails(
                    model=self._deep_model,
                    bing_grounding_connections=[
                        DeepResearchBingGroundingConnection(connection_id=self._bing_connection)
                    ],
                )
            )
            logger.info("Creating Deep Research agent")
            agent = await self._client.agents.create_agent(
                model=self._primary_model,
                name="deep-research-agent",
                instructions=(
                    "You are a research analyst. Always produce a concise summary followed by structured sections. "
                    "Ensure every key fact is supported by citations."
                ),
                tools=[deep_tool],
            )
            self._agent_id = agent.id
            logger.info("Deep Research agent created: %s", agent.id)
            
        except TypeError as e:
            logger.error("Deep Research agent creation failed due to SDK parameter mismatch")
            logger.error("SDK Error: %s", str(e))
            logger.error("Ensure azure-ai-agents SDK version is compatible (current requirement: >=1.0.0b7)")
            logger.error("Configuration used:")
            logger.error("  - Primary model: %s", self._primary_model)
            logger.error("  - Deep Research model: %s", self._deep_model)
            logger.error("  - Bing connection: %s", self._bing_connection[:20] + "..." if len(self._bing_connection) > 20 else self._bing_connection)
            raise RuntimeError(
                "Failed to create Deep Research agent. "
                "This is likely due to an SDK version mismatch or incorrect parameter names. "
                "Check logs for details and verify Azure AI Agents SDK version."
            ) from e
        except Exception as e:
            logger.error("Unexpected error creating Deep Research agent: %s", str(e))
            raise

    async def run(self, query: str) -> DeepResearchReport:
        try:
            await self._ensure_client()
        except Exception as e:
            logger.error("Failed to initialize Deep Research client: %s", str(e))
            raise RuntimeError(
                "Deep Research client initialization failed. "
                "Verify your Azure configuration:\n"
                "  1. PROJECT_ENDPOINT is set and accessible\n"
                "  2. MODEL_DEPLOYMENT_NAME points to a gpt-4o deployment\n"
                "  3. DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME points to o3-deep-research\n"
                "  4. BING_CONNECTION_NAME is the connection ID (not name)\n"
                "  5. All resources are in the same region (West US or Norway East)\n"
                f"Original error: {str(e)}"
            ) from e
        
        assert self._client and self._agent_id

        logger.info("Deep Research run started", extra={"query": query})

        thread = await self._client.agents.threads.create()
        await self._client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=query,
        )

        try:
            run = await self._client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=self._agent_id,
                tool_choice={"type": "deep_research"},
            )
        except AzureError as exc:
            logger.exception("Deep Research run failed to start: %s", exc)
            error_msg = str(exc)
            if "unsupported_tool" in error_msg.lower():
                raise RuntimeError(
                    "Deep Research tool not supported in this configuration. "
                    "Common causes:\n"
                    "  1. Resource region mismatch (must all be in West US or Norway East)\n"
                    "  2. o3-deep-research model not deployed in the same region as AI Project\n"
                    "  3. gpt-4o model not deployed in the same region\n"
                    "  4. Bing connection not properly linked to AI Project\n"
                    f"Azure error: {error_msg}"
                ) from exc
            raise

        if run.status != "completed":
            logger.error("Deep Research run ended with status %s", run.status)
            error_details = getattr(run, 'last_error', None)
            if error_details:
                logger.error("Run error details: %s", error_details)
            raise RuntimeError(
                f"Deep Research run incomplete: {run.status}\n"
                f"Details: {error_details if error_details else 'No additional details available'}"
            )

        messages = await self._client.agents.messages.list(thread_id=thread.id)
        agent_message = next(
            (m for m in messages if getattr(m, "role", "").lower() == "assistant"),
            None,
        )
        if not agent_message:
            raise RuntimeError("Deep Research produced no assistant message")

        report = self._parse_message(agent_message)
        report.metadata.update({
            "thread_id": thread.id,
            "run_id": run.id,
        })
        logger.info("Deep Research run complete", extra=report.metadata)
        return report

    def _parse_message(self, message) -> DeepResearchReport:
        contents = getattr(message, "content", []) or []
        text_blocks = [block for block in contents if getattr(block, "type", "") == "text"]
        if not text_blocks:
            summary = getattr(message, "text", "") or ""
            return DeepResearchReport(summary=summary, sections=[], citations=[], metadata={})

        primary = text_blocks[0]
        summary = primary.text or ""
        annotations = getattr(primary, "annotations", []) or []

        citations = []
        for annotation in annotations:
            uri = getattr(getattr(annotation, "uri_citation", None), "uri", None)
            title = getattr(getattr(annotation, "uri_citation", None), "title", None) or uri or "Source"
            if uri:
                citations.append(DeepResearchCitation(title=title, url=uri))

        sections = []
        for block in contents[1:]:
            if getattr(block, "type", "") != "text":
                continue
            heading = getattr(block, "name", "") or "Additional Findings"
            block_citations = []
            for annotation in getattr(block, "annotations", []) or []:
                uri = getattr(getattr(annotation, "uri_citation", None), "uri", None)
                title = getattr(getattr(annotation, "uri_citation", None), "title", None) or uri or "Source"
                if uri:
                    block_citations.append(DeepResearchCitation(title=title, url=uri))
            sections.append(
                DeepResearchSection(
                    heading=heading,
                    content=block.text or "",
                    citations=block_citations,
                )
            )

        return DeepResearchReport(summary=summary, sections=sections, citations=citations, metadata={})

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        if self._credential:
            await self._credential.close()
            self._credential = None


deep_research_client: Optional[DeepResearchClient] = None


def get_deep_research_client() -> DeepResearchClient:
    global deep_research_client
    if deep_research_client is None:
        deep_research_client = DeepResearchClient()
    return deep_research_client
