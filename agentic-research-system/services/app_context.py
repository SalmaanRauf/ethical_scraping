import asyncio
from typing import Dict, Any
from services.profile_loader import ProfileLoader
from agents.scraper_agent import ScraperAgent
from agents.company_resolver import CompanyResolver
from agents.data_consolidator import DataConsolidator
from agents.analyst_agent import AnalystAgent
from agents.validator import Validator
from agents.archivist import Archivist
from agents.reporter import Reporter
from agents.bing_grounding_agent import BingGroundingAgent
from extractors.news_extractor import NewsExtractor
from extractors.sec_extractor import SECExtractor
from extractors.sam_extractor import SAMExtractor
from extractors.extractor_wrappers import NewsExtractorWrapper, SECExtractorWrapper, SAMExtractorWrapper, BingExtractorWrapper
from config.kernel_setup import get_kernel
from config.config import AppConfig # Import AppConfig for Azure AI Foundry credentials
from azure.identity import DefaultAzureCredential # For Azure authentication

class AppContext:
    """
    A singleton class to hold the application's shared state and services.
    This ensures that expensive objects (like models and browser instances)
    are initialized only once.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContext, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance._profile_loader = None
            cls._instance._scraper_agent = None
            cls._instance._kernel = None
            cls._instance._agents = {}
            cls._instance._extractors = {}
        return cls._instance

    async def initialize(self):
        """
        Initializes all shared services and agents.
        This method is idempotent.
        """
        if self.initialized:
            return

        print("ð§ Initializing application context...")

        # Core services
        self.profile_loader = ProfileLoader()
        self.scraper_agent = ScraperAgent()
        # ScraperAgent doesn't need explicit initialization
        
        # Initialize kernel - handle async context properly
        try:
            self.kernel = get_kernel()
        except RuntimeError:
            # If we're in an async context, initialize kernel asynchronously
            from config.kernel_setup import get_kernel_async
            self.kernel, _ = await get_kernel_async()

        # Initialize agents
        self.agents: Dict[str, Any] = {
            "company_resolver": CompanyResolver(self.profile_loader),
            "data_consolidator": DataConsolidator(self.profile_loader),
            "analyst_agent": AnalystAgent(self.kernel),
            "validator": Validator(),
            "archivist": Archivist(),
            "reporter": Reporter(),
            "bing_grounding_agent": BingGroundingAgent(
                project_endpoint=AppConfig.PROJECT_ENDPOINT,
                model_deployment_name=AppConfig.MODEL_DEPLOYMENT_NAME,
                azure_bing_connection_id=AppConfig.AZURE_BING_CONNECTION_ID,
                credential=DefaultAzureCredential() # Use DefaultAzureCredential for authentication
            )
        }

        # Initialize extractors, passing profile_loader where needed
        news_extractor = NewsExtractor(self.scraper_agent, self.profile_loader)
        sec_extractor = SECExtractor(self.scraper_agent, self.profile_loader)
        sam_extractor = SAMExtractor(self.scraper_agent, self.profile_loader)
        bing_agent = self.agents['bing_grounding_agent']

        # Initialize extractor wrappers
        self.extractors: Dict[str, Any] = {
            "news": NewsExtractorWrapper(news_extractor),
            "sec": SECExtractorWrapper(sec_extractor),
            "sam": SAMExtractorWrapper(sam_extractor),
            "bing": BingExtractorWrapper(bing_agent)
        }

        self.initialized = True
        print("â Application context initialized successfully.")

    async def cleanup(self):
        """
        Cleans up resources, like the Playwright browser.
        """
        if self.scraper_agent:
            await self.scraper_agent.close()
        print("ð§¹ Application context cleaned up.")

    @property
    def initialized(self):
        return getattr(self, '_initialized', False)
    
    @initialized.setter
    def initialized(self, value):
        self._initialized = value

    @property
    def profile_loader(self):
        return getattr(self, '_profile_loader', None)
    
    @profile_loader.setter
    def profile_loader(self, value):
        self._profile_loader = value

    @property
    def scraper_agent(self):
        return getattr(self, '_scraper_agent', None)
    
    @scraper_agent.setter
    def scraper_agent(self, value):
        self._scraper_agent = value

    @property
    def kernel(self):
        return getattr(self, '_kernel', None)
    
    @kernel.setter
    def kernel(self, value):
        self._kernel = value

    @property
    def agents(self):
        return getattr(self, '_agents', {})
    
    @agents.setter
    def agents(self, value):
        self._agents = value

    @property
    def extractors(self):
        return getattr(self, '_extractors', {})
    
    @extractors.setter
    def extractors(self, value):
        self._extractors = value

# Global instance of the AppContext
app_context = AppContext()