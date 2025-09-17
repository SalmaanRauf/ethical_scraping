"""
Pydantic models for tool inputs/outputs used by the tool-centric orchestrator.

These define exact contracts between discovery tools (GWBS), analysis tools (Semantic Kernel),
and orchestrators that combine results for presentation.
"""
from typing import Dict, List, Optional, Literal

try:
    # Prefer Pydantic v1 for broad compatibility
    from pydantic import BaseModel, Field, AnyHttpUrl, validator
except Exception:  # pragma: no cover - fallback aliasing for environments without pydantic
    class BaseModel:  # type: ignore
        pass
    def Field(*args, **kwargs):  # type: ignore
        return None
    AnyHttpUrl = str  # type: ignore
    def validator(*args, **kwargs):  # type: ignore
        def _decorator(f):
            return f
        return _decorator


class CompanyRef(BaseModel):
    """Canonical company reference used across tools."""
    name: str = Field(..., description="Company name or ticker as provided by user")
    ticker: Optional[str] = Field(None, description="Ticker symbol if known")

    @validator("name")
    def _strip(cls, v: str) -> str:  # type: ignore
        return (v or "").strip()


class Citation(BaseModel):
    """A curated citation, always sourced from Bing tool annotations."""
    title: Optional[str] = Field(None)
    url: AnyHttpUrl


ScopeLiteral = Literal[
    "sec_filings", "news", "procurement", "earnings", "industry_context", "competitors"
]


class GWBSSection(BaseModel):
    """One discovery scope result returned by GWBS with annotations-only citations."""
    scope: ScopeLiteral
    summary: str = Field("", description="Sanitized summary with no inline URLs")
    citations: List[Citation] = Field(default_factory=list)
    audit: Dict = Field(default_factory=dict)


class FullGWBS(BaseModel):
    """Bundle of all GWBS sections for a company."""
    company: CompanyRef
    sections: Dict[str, GWBSSection] = Field(default_factory=dict)


class AnalysisItem(BaseModel):
    """Item passed to Analyst tool for synthesis."""
    company: str
    title: str
    content: str
    citations: List[Citation] = Field(default_factory=list)
    raw: Dict = Field(default_factory=dict)


class AnalysisEvent(BaseModel):
    """Structured event from Analyst synthesis."""
    title: str
    insights: Dict = Field(default_factory=dict)
    citations: List[Citation] = Field(default_factory=list)
    meta: Dict = Field(default_factory=dict)


class Briefing(BaseModel):
    """Final presentation bundle for a company analysis."""
    company: CompanyRef
    events: List[AnalysisEvent] = Field(default_factory=list)
    summary: str = Field("", description="Brief high-level summary of identified high-impact events")
    sections: Dict[str, str] = Field(default_factory=dict, description="Optional per-section summaries")

