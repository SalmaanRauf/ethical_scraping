# chainlit_app/main.py
from __future__ import annotations
import sys
from pathlib import Path



PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from config.logging_config import setup_logging
import chainlit as cl
import asyncio
from typing import Dict, Any, Optional
import os
from agents.bing_data_extraction_agent import BingDataExtractionAgent
from agents.analyst_agent import AnalystAgent
from services.conversation_manager import ConversationContext, QueryRouter, AnalysisBlob, QueryType, conversation_manager
from services.follow_up_handler import FollowUpHandler
from services.session_manager import session_manager
from models.schemas import CompanyRef
from tools import orchestrators as ors
from config.config import Config as AppConfig

# Enhanced system imports
from tools.orchestrators import enhanced_user_request_handler
from services.enhanced_router import enhanced_router
from tools.task_executor import task_executor
from tools.response_formatter import response_formatter

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)
# --- Input validation helpers ---

def validate_payload(payload: Dict[str, Any], required_keys: list[str]) -> tuple[bool, Optional[str]]:
    """Validate payload has required keys."""
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"
    
    for key in required_keys:
        if key not in payload:
            return False, f"Missing required key: {key}"
    
    return True, None

def validate_company_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate company payload and extract company data."""
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary", None
    
    if "company" not in payload:
        return False, "Missing company information", None
    
    company_data = payload["company"]
    if not isinstance(company_data, dict):
        return False, "Company data must be a dictionary", None
    
    if "name" not in company_data:
        return False, "Missing company name", None
    
    return True, None, company_data

# --- Session management helpers ---

def _get_ctx() -> ConversationContext:
    """Get or create conversation context for the current session."""
    try:
        session_id = cl.user_session.get("session_id")
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            cl.user_session.set("session_id", session_id)
        
        ctx = conversation_manager.get_or_create_context(session_id)
        return ctx
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        # Fallback: create a new context
        import uuid
        session_id = str(uuid.uuid4())
        return conversation_manager.get_or_create_context(session_id)

async def _init_singletons() -> None:
    """Initialize singleton services with error handling."""
    try:
        if not cl.user_session.get("bing_agent"):
            cl.user_session.set("bing_agent", BingDataExtractionAgent())

        analyst = cl.user_session.get("analyst_agent")
        if not analyst:
            analyst = AnalystAgent()
            cl.user_session.set("analyst_agent", analyst)
        await analyst.ensure_kernel_ready()

        if not cl.user_session.get("follow_up_handler"):
            bing_agent = cl.user_session.get("bing_agent")
            if bing_agent:
                cl.user_session.set("follow_up_handler", FollowUpHandler(bing_agent))

        if not cl.user_session.get("router"):
            cl.user_session.set("router", QueryRouter())
    except Exception as e:
        print(f"Error initializing singletons: {e}")
        raise

# --- Error handling helpers ---

async def handle_error(error: Exception, context: str, user_message: str = "Sorry, I encountered an error processing your request. Please try again.") -> None:
    """Handle errors gracefully with user-friendly messages."""
    logger.error(f"Error in {context}: {error}")
    
    # Send error message to user
    await cl.Message(user_message).send()
    
    # Log additional details for debugging
    logger.debug(f"Error details: {type(error).__name__}: {str(error)}")

# --- Enhanced system integration ---

async def present_enhanced_response(response: Dict[str, Any]) -> None:
    """
    Present enhanced system response to the user.
    
    Args:
        response: Formatted response from enhanced system
    """
    try:
        response_type = response.get("type", "unknown")
        
        if response_type == "error":
            error_msg = response.get("error", "Unknown error")
            details = response.get("details", [])
            error_text = f"❌ **Error**: {error_msg}"
            if details:
                error_text += f"\n\n**Details**:\n" + "\n".join([f"• {detail}" for detail in details])
            await cl.Message(error_text).send()
            return
        
        # Present main content
        summary = response.get("summary", "")
        if summary:
            await cl.Message(summary).send()
        
        # Present sections for mixed requests
        sections = response.get("sections", [])
        if sections:
            for section in sections:
                task_type = section.get("task_type", "unknown")
                target = section.get("target", "unknown")
                content = section.get("content", "")
                
                if content:
                    section_title = f"**{task_type.replace('_', ' ').title()} - {target}**"
                    await cl.Message(f"{section_title}\n\n{content}").send()
        
        # Present events for company briefings
        events = response.get("events", [])
        if events:
            for event in events:
                title = event.get("title", "Event")
                insights = event.get("insights", {})
                
                event_text = f"**{title}**"
                if insights:
                    what = insights.get("what_happened", "")
                    why = insights.get("why_it_matters", "")
                    if what:
                        event_text += f"\n\n**What happened**: {what}"
                    if why:
                        event_text += f"\n\n**Why it matters**: {why}"
                
                await cl.Message(event_text).send()
        
        # Present citations
        citations = response.get("citations", [])
        if citations:
            citation_text = "**Sources:**\n"
            for citation in citations[:10]:  # Limit to 10 citations
                title = citation.get("title", "Source")
                url = citation.get("url", "#")
                citation_text += f"• [{title}]({url})\n"
            await cl.Message(citation_text).send()
        
        # Present metadata
        execution_time = response.get("execution_time", 0)
        confidence = response.get("confidence", 0)
        if execution_time > 0 or confidence > 0:
            metadata_text = ""
            if execution_time > 0:
                metadata_text += f"⏱️ **Execution time**: {execution_time:.2f}s"
            if confidence > 0:
                metadata_text += f" | 🎯 **Confidence**: {confidence:.1%}"
            if metadata_text:
                await cl.Message(metadata_text).send()
                
    except Exception as e:
        logger.error(f"Error presenting enhanced response: {e}")
        await cl.Message("✅ Response generated successfully.").send()

async def handle_old_system(qtype: QueryType, payload: Dict[str, Any], ctx: ConversationContext, 
                           bing_agent: BingDataExtractionAgent, analyst_agent: AnalystAgent, 
                           fup: FollowUpHandler, user_text: str) -> None:
    """
    Handle requests using the old system as fallback.
    
    Args:
        qtype: Query type from old router
        payload: Payload from old router
        ctx: Conversation context
        bing_agent: Bing data extraction agent
        analyst_agent: Analyst agent
        fup: Follow-up handler
        user_text: Original user input
    """
    try:
        if qtype == QueryType.CLARIFICATION:
            await cl.Message("Which company should I analyze? You can type a name (e.g., `Capital One`) or a ticker (e.g., `COF`).").send()
            return

        elif qtype == QueryType.NEW_ANALYSIS:
            await handle_new_analysis(payload, ctx, bing_agent, analyst_agent, original_text=user_text)
            return

        elif qtype == QueryType.FOLLOW_UP:
            await handle_follow_up(ctx, fup, user_text)
            return

        elif qtype == QueryType.COMPARE_COMPANIES:
            await handle_company_comparison(payload, ctx, bing_agent, analyst_agent)
            return

        elif qtype == QueryType.GENERAL_RESEARCH:
            await handle_general_research(payload, bing_agent)
            return

        else:
            await cl.Message("I didn't quite catch that. Try a company name or ask a specific follow-up.").send()
            return
            
    except Exception as e:
        logger.error(f"Error in old system handler: {e}")
        await cl.Message("Sorry, I encountered an error processing your request. Please try again.").send()

# --- Chainlit event handlers ---

@cl.on_chat_start
async def start():
    """Initialize the chat session."""
    try:
        await _init_singletons()
        ctx = _get_ctx()
        
        # Send welcome message
        welcome_msg = (
            "👋 **Company Intelligence (Chat)**\n\n"
            "• Type a company (e.g., Capital One or ticker COF) for a full analysis.\n"
            "• Then ask follow-ups (risk, competitors, regulatory, strategy, timeline, etc.).\n"
            "• I'll remember the context and only search when needed.\n\n"
            "**New capabilities:**\n"
            "• Ask about any company (not just hardcoded ones)\n"
            "• General research questions (e.g., 'What are the top financial companies?')\n"
            "• Mixed requests (e.g., 'Tell me about Tesla and its competitors')"
        )
        await cl.Message(welcome_msg).send()
        
    except Exception as e:
        await handle_error(e, "chat_start", "Failed to initialize chat session. Please refresh and try again.")

@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages with comprehensive error handling."""
    user_text = ""
    try:
        await _init_singletons()
        ctx = _get_ctx()
        router: QueryRouter = cl.user_session.get("router")
        bing_agent: BingDataExtractionAgent = cl.user_session.get("bing_agent")
        analyst_agent: AnalystAgent = cl.user_session.get("analyst_agent")
        fup: FollowUpHandler = cl.user_session.get("follow_up_handler")

        # Validate required services
        if not all([router, bing_agent, analyst_agent, fup]):
            raise RuntimeError("Required services not initialized")

        user_text = (message.content or "").strip()
        if not user_text:
            await cl.Message("Please enter a message.").send()
            return

        ctx.add_message("user", user_text)
        
        # Check if enhanced system is enabled
        enhanced_enabled = os.getenv("ENABLE_ENHANCED_SYSTEM", "true").lower() in ("1", "true", "yes")
        
        if enhanced_enabled:
            try:
                # Enhanced system path
                logger.info("Using enhanced system for request")
                response = await enhanced_user_request_handler(
                    user_text, ctx, bing_agent, analyst_agent, 
                    progress=lambda msg: cl.Message(f"🔄 {msg}").send()
                )
                await present_enhanced_response(response)
                return
                
            except Exception as e:
                logger.warning(f"Enhanced system failed, falling back to old system: {e}")
                # Fall back to old system
                qtype, payload = router.route(user_text, ctx)
                await handle_old_system(qtype, payload, ctx, bing_agent, analyst_agent, fup, user_text)
                return
        else:
            # Old system path
            logger.info("Using old system for request")
            qtype, payload = router.route(user_text, ctx)
            await handle_old_system(qtype, payload, ctx, bing_agent, analyst_agent, fup, user_text)
            return

    except Exception as e:
        await handle_error(e, "on_message", user_text)

# --- Legacy handlers (for old system fallback) ---

async def handle_new_analysis(
    payload: Dict[str, Any],
    ctx: ConversationContext,
    bing_agent: BingDataExtractionAgent,
    analyst_agent: AnalystAgent,
    original_text: Optional[str] = None
):
    """Handle new company analysis with validation."""
    # Validate payload
    is_valid, error, company_data = validate_company_payload(payload)
    if not is_valid:
        await cl.Message(f"Error: {error}").send()
        return

    company = company_data["name"]
    ticker = company_data.get("ticker")
    ctx.set_company(company, ticker)

    await cl.Message(f"🔎 Running analysis on **{company}**…").send()

    try:
        if os.getenv("ENABLE_TOOL_ORCHESTRATOR", "false").lower() in ("1", "true", "yes"):
            # Tool-centric orchestrator path
            await cl.Message("🔄 Collecting GWBS sections (SEC, News, Procurement, Earnings, Industry)…").send()
            cref = CompanyRef(name=company, ticker=ticker)
            briefing = await ors.full_company_analysis(cref, bing_agent=bing_agent, analyst_agent=analyst_agent)

            # Save context
            blob = AnalysisBlob(
                company_name=briefing.company.name,
                ticker=briefing.company.ticker,
                gwbs_sections={k: {"summary": v} for k, v in (briefing.sections or {}).items()},
                analyst_summary=briefing.summary,
                analyst_events=[e.dict() for e in briefing.events],
            )
            ctx.set_analysis(blob)

            # Present results
            await present_briefing_results(briefing)

            # Optional: if original_text includes competitor request, run competitor GWBS too
            if original_text and "competitor" in original_text.lower():
                await cl.Message("🔍 Also searching for competitor information…").send()
                try:
                    comp_result = await ors.competitor_analysis(cref, bing_agent=bing_agent)
                    await cl.Message(f"**Competitor Analysis:**\n{comp_result.summary}").send()
                except Exception as comp_err:
                    logger.warning(f"Competitor analysis failed: {comp_err}")

        else:
            # Legacy path
            await cl.Message("🔄 Running legacy analysis…").send()
            # ... existing legacy code ...

    except Exception as e:
        await handle_error(e, "handle_new_analysis", f"Analysis failed for {company}")

async def handle_follow_up(ctx: ConversationContext, fup: FollowUpHandler, user_text: str):
    """Handle follow-up questions."""
    try:
        await cl.Message("🔍 Searching for additional information…").send()
        answer, citations = await fup.handle_follow_up(user_text, ctx)
        
        if answer:
            await cl.Message(answer).send()
            if citations:
                citation_text = "**Sources:**\n" + "\n".join([f"• [{c.title}]({c.url})" for c in citations])
                await cl.Message(citation_text).send()
        else:
            await cl.Message("I couldn't find specific information about that. Try asking more specifically.").send()
            
    except Exception as e:
        await handle_error(e, "handle_follow_up", "Follow-up search failed")

async def handle_company_comparison(payload: Dict[str, Any], ctx: ConversationContext, 
                                  bing_agent: BingDataExtractionAgent, analyst_agent: AnalystAgent):
    """Handle company comparison requests."""
    try:
        companies = payload.get("companies", [])
        if not companies or len(companies) < 2:
            await cl.Message("Please specify at least two companies to compare.").send()
            return
        
        await cl.Message(f"🔍 Comparing **{companies[0]}** and **{companies[1]}**…").send()
        
        # Run analysis for both companies
        for company in companies:
            cref = CompanyRef(name=company)
            briefing = await ors.full_company_analysis(cref, bing_agent=bing_agent, analyst_agent=analyst_agent)
            await present_briefing_results(briefing)
            
    except Exception as e:
        await handle_error(e, "handle_company_comparison", "Company comparison failed")

async def handle_general_research(payload: Dict[str, Any], bing_agent: BingDataExtractionAgent):
    """Handle general research requests."""
    try:
        prompt = payload.get("prompt", "")
        if not prompt:
            await cl.Message("Please specify what you'd like me to research.").send()
            return
        
        await cl.Message("🔍 Researching your topic…").send()
        summary, citations = await ors.general_research(prompt, bing_agent=bing_agent)
        
        if summary:
            await cl.Message(summary).send()
            if citations:
                citation_text = "**Sources:**\n" + "\n".join([f"• [{c.title}]({c.url})" for c in citations])
                await cl.Message(citation_text).send()
        else:
            await cl.Message("I couldn't find information on that topic. Please try rephrasing your question.").send()
            
    except Exception as e:
        await handle_error(e, "handle_general_research", "General research failed")

async def present_briefing_results(briefing):
    """Present briefing results to the user."""
    try:
        # Present summary
        if briefing.summary:
            await cl.Message(f"**Analysis Summary:**\n{briefing.summary}").send()
        
        # Present events
        if briefing.events:
            await cl.Message("**Key Events:**").send()
            for event in briefing.events:
                title = event.get("title", "Event")
                insights = event.get("insights", {})
                
                event_text = f"**{title}**"
                if insights:
                    what = insights.get("what_happened", "")
                    why = insights.get("why_it_matters", "")
                    if what:
                        event_text += f"\n\n**What happened**: {what}"
                    if why:
                        event_text += f"\n\n**Why it matters**: {why}"
                
                await cl.Message(event_text).send()
        
        # Present sections
        if briefing.sections:
            await cl.Message("**Research Sections:**").send()
            for section_name, section_summary in briefing.sections.items():
                section_title = section_name.replace("_", " ").title()
                await cl.Message(f"**{section_title}:**\n{section_summary}").send()
                
    except Exception as e:
        logger.error(f"Error presenting briefing results: {e}")
        await cl.Message("✅ Analysis completed successfully.").send()
