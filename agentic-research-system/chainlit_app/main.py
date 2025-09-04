# chainlit_app/main.py
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import chainlit as cl
import asyncio
from typing import Dict, Any, Optional
from agents.bing_data_extraction_agent import BingDataExtractionAgent
from agents.analyst_agent import AnalystAgent
from services.conversation_manager import ConversationContext, QueryRouter, AnalysisBlob, QueryType, conversation_manager
from services.follow_up_handler import FollowUpHandler
from services.session_manager import session_manager

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
    """Validate company payload structure."""
    is_valid, error = validate_payload(payload, ["company"])
    if not is_valid:
        return False, error, None
    
    company_data = payload.get("company")
    if not isinstance(company_data, dict):
        return False, "Company data must be a dictionary", None
    
    if "name" not in company_data:
        return False, "Company name is required", None
    
    company_name = company_data.get("name")
    if not isinstance(company_name, str) or not company_name.strip():
        return False, "Company name must be a non-empty string", None
    
    return True, None, company_data

def validate_companies_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[list[str]]]:
    """Validate companies payload for comparison."""
    is_valid, error = validate_payload(payload, ["companies"])
    if not is_valid:
        return False, error, None
    
    companies = payload.get("companies")
    if not isinstance(companies, list) or len(companies) != 2:
        return False, "Companies must be a list of exactly 2 items", None
    
    for i, company in enumerate(companies):
        if not isinstance(company, str) or not company.strip():
            return False, f"Company {i+1} must be a non-empty string", None
    
    return True, None, companies

# --- Safe session helpers ---

def _get_ctx() -> ConversationContext:
    """Get or create conversation context with proper session management."""
    try:
        # Get session ID from chainlit
        session_id = getattr(cl.user_session, "id", None) or cl.user_session.get("session_id")
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            cl.user_session.set("session_id", session_id)
        
        # Use thread-safe session manager
        return conversation_manager.get_or_create_context(session_id)
    except Exception as e:
        print(f"Error getting context: {e}")
        # Fallback to a new context
        import uuid
        session_id = str(uuid.uuid4())
        return conversation_manager.get_or_create_context(session_id)

def _init_singletons() -> None:
    """Initialize singleton services with error handling."""
    try:
        if not cl.user_session.get("bing_agent"):
            cl.user_session.set("bing_agent", BingDataExtractionAgent())
        if not cl.user_session.get("analyst_agent"):
            cl.user_session.set("analyst_agent", AnalystAgent())
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
    """Handle errors with proper logging and user feedback."""
    error_details = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "user_input": user_message[:100] if user_message else "N/A"
    }
    
    # Log error details (without sensitive data)
    print(f"Error in {context}: {error_details}")
    
    # Send user-friendly message
    await cl.Message(content=user_message).send()

# --- lifecycle ---

@cl.on_chat_start
async def start():
    """Initialize chat session."""
    try:
        _init_singletons()
        ctx = _get_ctx()
        
        # Start cleanup tasks
        conversation_manager.start_cleanup()
        session_manager.start_cleanup_task()

        welcome = (
            "👋 **Company Intelligence (Chat)**\n\n"
            "• Type a company (e.g., `Capital One` or ticker `COF`) for a full analysis.\n"
            "• Then ask follow-ups (risk, competitors, regulatory, strategy, timeline, etc.).\n"
            "• I'll remember the context and only search when needed.\n"
        )
        await cl.Message(content=welcome).send()
    except Exception as e:
        await handle_error(e, "chat_start", "Failed to initialize chat session. Please refresh and try again.")

@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages with comprehensive error handling."""
    user_text = ""
    try:
        _init_singletons()
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
        qtype, payload = router.route(user_text, ctx)

        # Handle different query types with validation
        if qtype == QueryType.CLARIFICATION:
            await cl.Message("Which company should I analyze? You can type a name (e.g., `Capital One`) or a ticker (e.g., `COF`).").send()
            return

        elif qtype == QueryType.NEW_ANALYSIS:
            await handle_new_analysis(payload, ctx, bing_agent, analyst_agent)
            return

        elif qtype == QueryType.FOLLOW_UP:
            await handle_follow_up(ctx, fup, user_text)
            return

        elif qtype == QueryType.COMPARE_COMPANIES:
            await handle_company_comparison(payload, ctx, bing_agent, analyst_agent)
            return

        else:
            await cl.Message("I didn't quite catch that. Try a company name or ask a specific follow-up.").send()
            return

    except Exception as e:
        await handle_error(e, "on_message", user_text)

async def handle_new_analysis(payload: Dict[str, Any], ctx: ConversationContext, bing_agent: BingDataExtractionAgent, analyst_agent: AnalystAgent):
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
        # Step 1/2: GWBS (using proper async)
        gwbs = await asyncio.get_event_loop().run_in_executor(
            None, bing_agent.get_full_intelligence, company
        )

        # Stream GWBS summary
        sections_preview = " | ".join(s.replace("_", " ").title() for s in gwbs.keys())
        await cl.Message(f"✅ Collected: {sections_preview}").send()

        # Step 2/2: Analyst step
        analysis_items = []
        for section, section_data in gwbs.items():
            if not isinstance(section_data, dict):
                continue
                
            analysis_items.append({
                "company": company,
                "title": section.replace("_", " ").title(),
                "description": section_data.get("summary", ""),
                "content": section_data.get("summary", ""),
                "citations": section_data.get("citations_md", ""),
                "raw_data": section_data,
                "source": f"Bing Search - {section}",
                "source_type": "web_search"
            })

        # Run analysis
        analysis_results = await analyst_agent.analyze_all_data(analysis_items)

        # Save context
        blob = AnalysisBlob(
            company_name=company,
            ticker=ticker,
            gwbs_sections=gwbs,
            analyst_summary=f"Analysis identified {len(analysis_results)} significant events for {company}.",
            analyst_events=analysis_results,
        )
        ctx.set_analysis(blob)

        # Present results
        await present_analysis_results(company, analysis_results)
        
    except Exception as e:
        await handle_error(e, "new_analysis", f"Failed to analyze {company}")

async def handle_follow_up(ctx: ConversationContext, fup: FollowUpHandler, user_text: str):
    """Handle follow-up questions with validation."""
    try:
        result = fup.handle_follow_up(ctx, user_text)
        
        # Validate result structure
        if not isinstance(result, dict) or "answer" not in result:
            await cl.Message("I couldn't process your question. Please try rephrasing it.").send()
            return
        
        answer = result.get("answer", "")
        cites = result.get("citations", [])
        
        # Format citations safely
        cite_lines = []
        if isinstance(cites, list):
            for c in cites:
                if isinstance(c, dict) and "url" in c:
                    title = c.get("title", c["url"])
                    cite_lines.append(f"- [{title}]({c['url']})")
        
        footer = ("\n\n**Sources**\n" + "\n".join(cite_lines)) if cite_lines else ""
        await cl.Message((answer or "I couldn't find information to answer your question.") + footer).send()
        
    except Exception as e:
        await handle_error(e, "follow_up", "Failed to process your follow-up question")

async def handle_company_comparison(payload: Dict[str, Any], ctx: ConversationContext, bing_agent: BingDataExtractionAgent, analyst_agent: AnalystAgent):
    """Handle company comparison with validation."""
    # Validate payload
    is_valid, error, companies = validate_companies_payload(payload)
    if not is_valid:
        await cl.Message(f"Error: {error}").send()
        return

    a, b = companies
    await cl.Message(f"🔎 Comparing **{a}** vs **{b}** (this runs two analyses)…").send()

    try:
        # Run analyses in parallel
        gwbs_a, gwbs_b = await asyncio.gather(
            asyncio.get_event_loop().run_in_executor(None, bing_agent.get_full_intelligence, a),
            asyncio.get_event_loop().run_in_executor(None, bing_agent.get_full_intelligence, b)
        )
        
        # Format and analyze both companies
        analysis_items_a = format_analysis_items(a, gwbs_a)
        analysis_items_b = format_analysis_items(b, gwbs_b)
        
        # Run analyses in parallel
        ana_a, ana_b = await asyncio.gather(
            analyst_agent.analyze_all_data(analysis_items_a),
            analyst_agent.analyze_all_data(analysis_items_b)
        )

        # Store both analyses (FIXED: Don't overwrite)
        ctx.set_analysis(AnalysisBlob(
            company_name=a, 
            gwbs_sections=gwbs_a, 
            analyst_summary=f"Analysis of {a}", 
            analyst_events=ana_a
        ))
        
        # Store second analysis with different key
        ctx.analyses[f"{b.lower()}_comparison"] = AnalysisBlob(
            company_name=b, 
            gwbs_sections=gwbs_b, 
            analyst_summary=f"Analysis of {b}", 
            analyst_events=ana_b
        )

        # Present comparison
        await present_comparison_results(a, b, ana_a, ana_b)
        
    except Exception as e:
        await handle_error(e, "company_comparison", f"Failed to compare {a} and {b}")

def format_analysis_items(company: str, gwbs_data: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Format GWBS data for analysis."""
    analysis_items = []
    for section, section_data in gwbs_data.items():
        if not isinstance(section_data, dict):
            continue
            
        analysis_items.append({
            "company": company,
            "title": section.replace("_", " ").title(),
            "description": section_data.get("summary", ""),
            "content": section_data.get("summary", ""),
            "raw_data": section_data,
        })
    return analysis_items

async def present_analysis_results(company: str, analysis_results: list[Dict[str, Any]]):
    """Present analysis results with proper formatting."""
    if not analysis_results:
        await cl.Message(f"### 📊 {company} — Analysis Results\n\nNo significant events identified in current data.").send()
        return

    out_lines = [f"### 📊 {company} — Analysis Results", f"Found {len(analysis_results)} significant event(s):"]
    
    for i, ev in enumerate(analysis_results[:6], 1):
        if not isinstance(ev, dict):
            continue
            
        title = ev.get('title', 'Unknown Event')
        insights = ev.get('insights', {})
        what = insights.get('what_happened', '') if isinstance(insights, dict) else ''
        why = insights.get('why_it_matters', '') if isinstance(insights, dict) else ''
        
        out_lines.append(f"{i}. **{title}**")
        if what:
            out_lines.append(f"   • What happened: {what}")
        if why:
            out_lines.append(f"   • Why it matters: {why}")
        
        # Add citations safely
        citations = ev.get('citations') or ev.get('raw_data', {}).get('citations_md', '')
        if citations:
            if isinstance(citations, str) and citations.strip():
                out_lines.append(f"   • Sources: {citations[:200]}{'...' if len(citations) > 200 else ''}")
            elif isinstance(citations, list) and citations:
                cite_list = ", ".join([c.get('title', c.get('url', '')) for c in citations[:3] if isinstance(c, dict)])
                out_lines.append(f"   • Sources: {cite_list}")
        out_lines.append("")
    
    await cl.Message("\n".join(out_lines)).send()

async def present_comparison_results(a: str, b: str, ana_a: list[Dict[str, Any]], ana_b: list[Dict[str, Any]]):
    """Present company comparison results."""
    comparison_text = f"### 🆚 {a} vs {b}\n\n"
    comparison_text += f"**{a}** — Found {len(ana_a)} significant events\n"
    comparison_text += f"**{b}** — Found {len(ana_b)} significant events\n\n"
    
    if ana_a:
        comparison_text += f"**{a} Key Events:**\n"
        for i, ev in enumerate(ana_a[:3], 1):
            if isinstance(ev, dict):
                title = ev.get('title', 'Unknown Event')
                comparison_text += f"{i}. {title}\n"
        comparison_text += "\n"
    
    if ana_b:
        comparison_text += f"**{b} Key Events:**\n"
        for i, ev in enumerate(ana_b[:3], 1):
            if isinstance(ev, dict):
                title = ev.get('title', 'Unknown Event')
                comparison_text += f"{i}. {title}\n"
    
    await cl.Message(comparison_text).send()

# Cleanup on shutdown
@cl.on_chat_end
async def on_chat_end():
    """Clean up resources when chat ends."""
    try:
        conversation_manager.stop_cleanup()
        session_manager.stop_cleanup_task()
    except Exception as e:
        print(f"Error during cleanup: {e}")
