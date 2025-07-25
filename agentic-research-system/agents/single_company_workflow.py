import asyncio
from typing import Dict, Any, List
import logging
from services.app_context import AppContext
from services.progress_handler import ProgressHandler
from services.error_handler import log_error

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SingleCompanyWorkflow:
    """
    Orchestrates the single-company briefing process.
    """
    def __init__(self, app_context: AppContext, progress_handler: ProgressHandler):
        self.app_context = app_context
        self.progress_handler = progress_handler

    async def run(self, company_name: str) -> Dict[str, Any]:
        """
        Runs the complete single-company briefing workflow.
        """
        logger.info("🚀 Starting single company workflow for: %s", company_name)
        
        try:
            # 1. Company Resolution
            await self.progress_handler.start_step("Resolving company...", 1)
            resolver = self.app_context.agents['company_resolver']
            canonical_name, display_name = resolver.resolve_company(company_name)
            logger.info("✅ Company resolved: %s -> %s (%s)", company_name, canonical_name, display_name)
            await self.progress_handler.complete_step("Company resolved.")

            # 2. Profile Loading
            profile = resolver.get_profile(canonical_name)
            if not profile:
                logger.error("❌ No profile found for company: %s", canonical_name)
                return {"error": f"No profile found for {company_name}"}
            logger.info("✅ Profile loaded for: %s", canonical_name)

            # 3. Data Extraction
            await self.progress_handler.start_step("Extracting data...", 1)
            extraction_tasks = []
            for extractor_name, extractor in self.app_context.extractors.items():
                logger.info("🔍 Starting extraction with: %s", extractor_name)
                extraction_tasks.append(extractor.extract_for_company(canonical_name, self.progress_handler))

            results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
            logger.info("📊 Extraction completed with %d results", len(results))

            all_raw_data = []
            bing_industry_context = None
            
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error("❌ Extractor %s failed: %s", list(self.app_context.extractors.keys())[i], str(res))
                    log_error(res, f"Extractor {list(self.app_context.extractors.keys())[i]} failed during single company workflow")
                elif res:
                    # Special handling for Bing grounding results
                    if i == len(results) - 1:  # Bing extractor is last
                        if res and len(res) > 0:
                            bing_industry_context = res[0].get('content', '')
                            logger.info("✅ Bing grounding context captured: %d chars", len(bing_industry_context))
                    all_raw_data.extend(res)
                    logger.info("✅ Extractor %s returned %d items", list(self.app_context.extractors.keys())[i], len(res))

            logger.info("📊 Total raw data items: %d", len(all_raw_data))
            await self.progress_handler.complete_step("Data extraction complete.")

            # 4. Data Consolidation
            await self.progress_handler.start_step("Consolidating data...", 1)
            consolidator = self.app_context.agents['data_consolidator']
            consolidated_items = await consolidator.consolidate_data(all_raw_data)
            logger.info("✅ Consolidated %d items", len(consolidated_items))
            await self.progress_handler.complete_step("Data consolidation complete.")

            # 5. Analysis
            await self.progress_handler.start_step("Analyzing data...", 1)
            analyst = self.app_context.agents['analyst_agent']
            # Set company profiles for the analyst agent
            analyst.set_profiles({canonical_name: profile})
            
            # Create analysis document from consolidated items
            analysis_document = self._create_analysis_document(consolidated_items)
            analyzed_events = await analyst.analyze_consolidated_data(consolidated_items, analysis_document)
            logger.info("✅ Analysis complete: %d events analyzed", len(analyzed_events))

            # 6. Report Generation
            await self.progress_handler.start_step("Generating final briefing...", 1)
            report = self._generate_briefing(display_name, analyzed_events, profile, bing_industry_context)
            logger.info("✅ Briefing generated with Bing context: %s", "Yes" if bing_industry_context else "No")
            await self.progress_handler.complete_step("Briefing complete.")

            return {"report": report, "profile": profile}

        except Exception as e:
            logger.error("❌ Critical error in workflow for %s: %s", company_name, str(e))
            log_error(e, f"Critical error in workflow for {company_name}")
            await self.progress_handler.update_progress(f"An unexpected error occurred: {e}")
            return {"error": "An unexpected error occurred during the analysis."}

    def _generate_briefing(self, display_name: str, events: List[Dict[str, Any]], profile: Dict[str, Any], bing_industry_context: str) -> str:
        """
        Generates a Markdown-formatted briefing from the analyzed events.
        Follows the specified output format with all required fields.
        """
        if not events:
            return f"## No relevant recent information found for {display_name}.\n\nProfile\nDescription: {profile.get('description', 'N/A')}\nWebsite: {profile.get('website', 'N/A')}\nRecent Stock Price: ${profile.get('recent_stock_price', 'N/A')}"

        # Sort events by relevance score before displaying
        sorted_events = sorted(events, key=lambda x: x.get('relevance_score', 0), reverse=True)

        briefing_parts = [f"# Intelligence Briefing: {display_name}\n"]
        
        # --- Company Profile Section ---
        briefing_parts.append("## Company Profile")
        briefing_parts.append(f"**Description:** {profile.get('description', 'N/A')}")
        briefing_parts.append(f"**Website:** {profile.get('website', 'N/A')}")
        briefing_parts.append(f"**Recent Stock Price:** ${profile.get('recent_stock_price', 'N/A')}")
        
        # --- Company Profile Snippets ---
        if profile.get('people', {}).get('keyBuyers'):
            key_buyers = [buyer.get('name', 'N/A') for buyer in profile['people']['keyBuyers']]
            briefing_parts.append(f"**Key Buyers:** {', '.join(key_buyers)}")
        
        if profile.get('people', {}).get('alumni'):
            alumni = [alum.get('name', 'N/A') for alum in profile['people']['alumni']]
            briefing_parts.append(f"**Alumni Contacts:** {', '.join(alumni)}")
        
        if profile.get('opportunities', {}).get('open'):
            active_opps = [opp.get('name', 'N/A') for opp in profile['opportunities']['open']]
            briefing_parts.append(f"**Active Opportunities:** {', '.join(active_opps)}")

        # --- Industry Overview Section ---
        briefing_parts.append("\n## Industry Overview")
        if bing_industry_context:
            briefing_parts.append(bing_industry_context)
        else:
            briefing_parts.append("*Industry context and sector trends would be populated by Bing grounding agent*")

        # --- Key Events Section ---
        briefing_parts.append("\n## Key Events & Findings")
        
        if not events:
            briefing_parts.append("*No relevant recent information found for this company.*")
        else:
            for i, event in enumerate(sorted_events[:5], 1):  # Show top 5 events
                event_section = self._format_event(event, i)
                briefing_parts.append(event_section)

        # --- Consulting Opportunities Section ---
        briefing_parts.append("\n## Consulting Opportunities")
        if events:
            briefing_parts.append("*Analysis of how our firm can help based on identified events*")
        else:
            briefing_parts.append("*No specific consulting opportunities identified at this time.*")

        # --- Sources Section ---
        briefing_parts.append("\n## Sources")
        sources = set()
        for event in sorted_events:
            if event.get('url'):
                sources.add(event['url'])
            elif event.get('source_url'):
                sources.add(event['source_url'])
        
        if sources:
            for source in list(sources)[:10]:  # Limit to top 10 sources
                briefing_parts.append(f"- {source}")
        else:
            briefing_parts.append("*No specific sources available.*")

        return "\n".join(briefing_parts)

    def _create_analysis_document(self, consolidated_items: List[Dict[str, Any]]) -> str:
        """
        Creates a simple analysis document from consolidated items.
        """
        if not consolidated_items:
            return "No relevant data found for analysis."
        
        document_parts = ["# Consolidated Data Analysis\n"]
        
        for i, item in enumerate(consolidated_items[:10], 1):  # Limit to top 10 items
            document_parts.append(f"## Item {i}")
            document_parts.append(f"**Title:** {item.get('title', 'N/A')}")
            document_parts.append(f"**Source:** {item.get('source', 'N/A')}")
            document_parts.append(f"**Relevance Score:** {item.get('relevance_score', 0):.2f}")
            if item.get('content'):
                content_preview = item['content'][:200] + "..." if len(item['content']) > 200 else item['content']
                document_parts.append(f"**Content:** {content_preview}")
            document_parts.append("")
        
        return "\n".join(document_parts)

    def _format_event(self, event: Dict[str, Any], index: int) -> str:
        """
        Format a single event according to the specified output structure.
        """
        parts = [f"\n### Event {index}"]
        
        # Extract insights from the event
        insights = event.get('insights', {})
        
        # Required fields from vision
        parts.append(f"**Company:** {event.get('company', 'N/A')}")
        parts.append(f"**What Happened:** {insights.get('what_happened', event.get('title', 'N/A'))}")
        parts.append(f"**Why It Matters:** {insights.get('why_it_matters', 'N/A')}")
        parts.append(f"**Consulting Angle:** {insights.get('consulting_angle', 'N/A')}")
        parts.append(f"**Need Type:** {insights.get('need_type', 'N/A')}")
        parts.append(f"**Service Line:** {insights.get('service_line', 'N/A')}")
        parts.append(f"**Urgency:** {insights.get('urgency', 'Medium')}")
        
        # Additional context
        if event.get('event_type'):
            parts.append(f"**Event Type:** {event['event_type']}")
        
        if event.get('value_usd'):
            parts.append(f"**Value:** ${event['value_usd']:,}")
        
        if event.get('source_url'):
            parts.append(f"**Source:** {event['source_url']}")
        
        return "\n".join(parts)