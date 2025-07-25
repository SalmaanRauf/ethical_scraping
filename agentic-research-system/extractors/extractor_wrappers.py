from typing import List, Dict, Any
from datetime import datetime
from services.progress_handler import ProgressHandler
from extractors.sam_extractor import SAMExtractor
from extractors.news_extractor import NewsExtractor
from extractors.sec_extractor import SECExtractor
from agents.bing_grounding_agent import BingGroundingAgent

class BaseExtractorWrapper:
    """Base class for extractor wrappers."""
    def __init__(self, extractor_instance):
        self.extractor = extractor_instance
        self.source_name = "Unknown"

    async def extract_for_company(self, company_name: str, progress_handler: ProgressHandler) -> List[Dict[str, Any]]:
        raise NotImplementedError

class NewsExtractorWrapper(BaseExtractorWrapper):
    def __init__(self, extractor_instance: NewsExtractor):
        super().__init__(extractor_instance)
        self.source_name = "News & RSS Feeds"

    async def extract_for_company(self, company_name: str, progress_handler: ProgressHandler) -> List[Dict[str, Any]]:
        await progress_handler.update_progress(f"Searching {self.source_name} for {company_name}...")
        results = await self.extractor.get_news_for_company(company_name)
        await progress_handler.update_progress(f"Found {len(results)} news items for {company_name}.")
        return results

class SECExtractorWrapper(BaseExtractorWrapper):
    def __init__(self, extractor_instance: SECExtractor):
        super().__init__(extractor_instance)
        self.source_name = "SEC Filings"

    async def extract_for_company(self, company_name: str, progress_handler: ProgressHandler) -> List[Dict[str, Any]]:
        await progress_handler.update_progress(f"Searching {self.source_name} for {company_name}...")
        # SEC extractor's get_recent_filings now accepts company_name parameter
        results = await self.extractor.get_recent_filings(days_back=90, company_name=company_name) # 90 days for SEC
        await progress_handler.update_progress(f"Found {len(results)} SEC filings for {company_name}.")
        return results

class SAMExtractorWrapper(BaseExtractorWrapper):
    def __init__(self, extractor_instance: SAMExtractor):
        super().__init__(extractor_instance)
        self.source_name = "SAM.gov Procurement"

    async def extract_for_company(self, company_name: str, progress_handler: ProgressHandler) -> List[Dict[str, Any]]:
        await progress_handler.update_progress(f"Searching {self.source_name} for {company_name}...")
        # SAM extractor's get_all_notices already handles company filtering internally
        results = await self.extractor.get_all_notices(days_back=60) # 60 days for SAM
        await progress_handler.update_progress(f"Found {len(results)} procurement notices for {company_name}.")
        return results

class BingExtractorWrapper(BaseExtractorWrapper):
    def __init__(self, extractor_instance: BingGroundingAgent):
        super().__init__(extractor_instance)
        self.source_name = "Bing Search for Industry Context"

    async def extract_for_company(self, company_name: str, progress_handler: ProgressHandler) -> List[Dict[str, Any]]:
        await progress_handler.update_progress(f"Searching {self.source_name} for {company_name}...")
        # The Bing agent's get_industry_briefing returns a summary and citations
        # We need to format this into a list of dicts to match other extractors' output
        bing_result = self.extractor.get_industry_briefing(company_name)  # This is sync, not async
        
        formatted_results = []
        if bing_result and bing_result.get('summary'):
            formatted_results.append({
                "source": "Bing Search",
                "title": f"Industry Overview for {company_name}",
                "link": "N/A", # Bing grounding doesn't provide a single link for the summary
                "content": bing_result['summary'],
                "published_date": datetime.now().isoformat(),
                "citations": bing_result.get('citations_md', '') # Store citations separately
            })
        
        await progress_handler.update_progress(f"Found {len(formatted_results)} industry context items for {company_name}.")
        return formatted_results