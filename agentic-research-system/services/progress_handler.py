"""
Progress handling and real-time updates for Chainlit integration.
"""

import asyncio
from typing import Callable, Optional

# Try to import chainlit, but don't fail if it's not available
try:
    from chainlit import Message
    CHAINLIT_AVAILABLE = True
except ImportError:
    CHAINLIT_AVAILABLE = False

class ProgressHandler:
    """
    Handles real-time progress updates for the single-company workflow.
    """
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.current_step = 0
        self.total_steps = 0
    
    def set_total_steps(self, total: int):
        """Set total number of steps for progress tracking."""
        self.total_steps = total
        self.current_step = 0
    
    async def update_progress(self, message: str):
        """Update progress with message."""
        self.current_step += 1
        
        if self.progress_callback:
            await self.progress_callback(message)
        else:
            print(f"[{self.current_step}/{self.total_steps}] {message}")
    
    async def start_extraction(self, company_name: str):
        """Start extraction process."""
        await self.update_progress(f"Starting intelligence gathering for {company_name}...")
    
    async def sec_extraction(self):
        """SEC extraction progress."""
        await self.update_progress("Fetching SEC filings...")
    
    async def sam_extraction(self):
        """SAM.gov extraction progress."""
        await self.update_progress("Fetching procurement notices...")
    
    async def news_extraction(self):
        """News extraction progress."""
        await self.update_progress("Fetching recent news...")
    
    async def bing_extraction(self):
        """Bing grounding progress."""
        await self.update_progress("Gathering industry context...")
    
    async def analysis_start(self):
        """Analysis start progress."""
        await self.update_progress("Analyzing intelligence data...")
    
    async def analysis_complete(self):
        """Analysis complete progress."""
        await self.update_progress("Generating briefing...")
    
    async def start_step(self, message: str, total_steps: int = 1):
        """Start a new step in the workflow."""
        self.current_step = 0
        self.total_steps = total_steps
        await self.update_progress(message)
    
    async def complete_step(self, message: str):
        """Complete the current step."""
        await self.update_progress(message)


class ChainlitProgressHandler(ProgressHandler):
    """
    Progress handler specifically for Chainlit integration.
    Sends progress updates to the Chainlit UI.
    """
    
    def __init__(self):
        super().__init__()
    
    async def update_progress(self, message: str):
        """Send progress update to Chainlit UI."""
        try:
            import chainlit as cl
            await cl.Message(content=f"🔄 {message}").send()
        except ImportError:
            # Fallback to console if chainlit not available
            print(f"[PROGRESS] {message}")
        except Exception as e:
            # Fallback to console on any error
            print(f"[PROGRESS] {message} (Chainlit error: {e})")
