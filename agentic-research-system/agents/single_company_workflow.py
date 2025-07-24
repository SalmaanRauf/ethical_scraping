import asyncio
from typing import Dict, Any, List
from services.app_context import AppContext
from services.progress_handler import ProgressHandler
from services.error_handler import log_error

class SingleCompanyWorkflow:
    """
    Orchestrates the workflow for generating a briefing on a single company.
    Relies on a shared AppContext for all services and agents.
    """
    def __init__(self, app_context: AppContext, progress_handler: ProgressHandler):
        self.app_context = app_context
        self.progress_handler = progress_handler

    async def run(self, company_name: str) -> Dict[str, Any]:
        """
        Executes the single-company research workflow from start to finish.
        """
        try:
            # 1. Resolve Company and Load Profile
            await self.progress_handler.start_step("Resolving company name...", 1)
            resolver = self.app_context.agents['company_resolver']
            canonical_name, display_name = resolver.resolve_company(company_name)
            
            if not canonical_name:
                await self.progress_handler.update_progress(f"Could not resolve company: '{company_name}'", is_error=True)
                return {"error": f"Company '{company_name}' not found in our database."}
            profile = resolver.get_profile(canonical_name)
            if not profile:
                 return {"error": f"Profile for '{display_name}' could not be loaded."}
            await self.progress_handler.complete_step(f"Resolved to {display_name}")

            # 2. Data Extraction
            extractors = list(self.app_context.extractors.values())
            await self.progress_handler.start_step("Extracting data from sources...", len(extractors))
            
            extraction_tasks = [ext.extract_for_company(canonical_name, self.progress_handler) for ext in extractors]
            results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
            
            all_raw_data = []
            for res in results:
                if isinstance(res, Exception):
                    log_error(res, "Extractor failed during single company workflow")
                elif res:
                    all_raw_data.extend(res)
            await self.progress_handler.complete_step(f"Extracted {len(all_raw_data)} total items.")

            # 3. Data Consolidation
            if not all_raw_data:
                await self.progress_handler.complete_step("No new data found for the company.")
                return {"report": f"## No recent information found for {display_name}.", "profile": profile}

            await self.progress_handler.start_step("Consolidating and filtering data...", 1)
            consolidator = self.app_context.agents['data_consolidator']
            consolidation_result = consolidator.process_raw_data(all_raw_data)
            consolidated_items = consolidation_result['consolidated_items']
            analysis_document = consolidation_result['analysis_document']
            await self.progress_handler.complete_step(f"Found {len(consolidated_items)} relevant items.")

            # 4. AI Analysis
            if not consolidated_items:
                return {"report": f"## No relevant recent information found for {display_name}.", "profile": profile}

            analyst = self.app_context.agents['analyst_agent']
            # Set company profiles for the analyst agent
            analyst.set_profiles({canonical_name: profile})
            analyzed_events = await analyst.analyze_consolidated_data(consolidated_items, analysis_document)

            # 5. Report Generation
            await self.progress_handler.start_step("Generating final briefing...", 1)
            report = self._generate_briefing(display_name, analyzed_events, profile)
            await self.progress_handler.complete_step("Briefing complete.")

            return {"report": report, "profile": profile}

        except Exception as e:
            log_error(e, f"Critical error in workflow for {company_name}")
            await self.progress_handler.update_progress(f"An unexpected error occurred: {e}", is_error=True)
            return {"error": "An unexpected error occurred during the analysis."}

    def _generate_briefing(self, display_name: str, events: List[Dict[str, Any]], profile: Dict[str, Any]) -> str:
        """
        Generates a Markdown-formatted briefing from the analyzed events.
        """
        if not events:
            return f"## Briefing for {display_name}\n\nNo significant events found in the last 7 days."

        # Sort events by relevance score before displaying
        sorted_events = sorted(events, key=lambda x: x.get('relevance_score', 0), reverse=True)

        briefing_parts = [f"# Intelligence Briefing: {display_name}\n"]
        
        # --- Profile Section ---
        briefing_parts.append("## Company Profile")
        briefing_parts.append(f"**Description:** {profile.get('description', 'N/A')}")
        briefing_parts.append(f"**Website:** [{profile.get('website')}]({profile.get('website')})")
        briefing_parts.append(f"**Key Personnel:** {', '.join(profile.get('key_personnel', []))}")
        briefing_parts.append(f"**Recent Stock Price:** ${profile.get('recent_stock_price', 'N/A')}")

        # --- Company Profile Snippets (Proprietary Data) ---
        briefing_parts.append("\n## Proprietary Company Insights")
        if profile.get('people', {}).get('keyBuyers'):
            briefing_parts.append("### Key Buyers")
            for buyer in profile['people']['keyBuyers']:
                briefing_parts.append(f"- **{buyer.get('name', 'N/A')}**: {buyer.get('title', 'N/A')} (Wins: {buyer.get('numberOfWins', 0)}) ")
        if profile.get('people', {}).get('alumni'):
            briefing_parts.append("### Alumni Contacts")
            for alumni in profile['people']['alumni']:
                briefing_parts.append(f"- **{alumni.get('name', 'N/A')}**: {alumni.get('title', 'N/A')}")
        if profile.get('opportunities', {}).get('open'):
            briefing_parts.append("### Open Opportunities")
            for opp in profile['opportunities']['open']:
                briefing_parts.append(f"- **{opp.get('name', 'N/A')}**: Status: {opp.get('status', 'N/A')}")

        # --- Key Events Section ---
        briefing_parts.append("\n## Key Recent Events")
        for event in sorted_events:
            briefing_parts.append(self._format_event(event))

        # --- Industry Overview Section ---
        # For simplicity, we take the overview from the most relevant event.
        # A more advanced implementation could synthesize these.
        first_overview = next((e.get('insights', {}).get('industry_overview') for e in sorted_events if e.get('insights', {}).get('industry_overview')), None)
        if first_overview:
            briefing_parts.append("\n## Industry Overview")
            briefing_parts.append(first_overview)

        return "\n".join(briefing_parts)

    def _format_event(self, event: Dict[str, Any]) -> str:
        """Formats a single event into a Markdown string."""
        parts = [f"\n### {event.get('title', 'Untitled Event')}"]
        insights = event.get('insights', {})
        
        # Core Insights
        parts.append(f"- **What Happened:** {insights.get('what_happened', 'N/A')}")
        parts.append(f"- **Why It Matters:** {insights.get('why_it_matters', 'N/A')}")
        parts.append(f"- **Consulting Angle:** {insights.get('consulting_angle', 'N/A')}")
        
        # Structured Analysis
        analysis_parts = []
        if insights.get('urgency'):
            analysis_parts.append(f"**Urgency:** {insights['urgency']}")
        if insights.get('need_type'):
            analysis_parts.append(f"**Need Type:** {insights['need_type'].title()}")
        if insights.get('service_line'):
            analysis_parts.append(f"**Service Line:** {insights['service_line']}")
        
        if analysis_parts:
            parts.append(f"- **Analysis:** {' | '.join(analysis_parts)}")

        # Source Link
        if event.get('link'):
            parts.append(f"- **Source:** [Link]({event.get('link')})")

        return "\n".join(parts)