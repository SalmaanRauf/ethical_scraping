import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import re
import logging
from pathlib import Path
from services.profile_loader import ProfileLoader
from services.error_handler import log_error

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DataConsolidator:
    """
    Consolidates raw data from multiple extractors into a structured format.
    Applies relevance scoring and intelligent filtering to focus on the most
    important findings for each company.
    """
    def __init__(self, profile_loader: ProfileLoader, output_dir: str = None):
        if output_dir is None:
            project_root = Path(__file__).parent.parent
            output_dir = project_root / "data" / "consolidated_output"
        else:
            output_dir = Path(output_dir)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.profile_loader = profile_loader
        # Use lazy loading instead of loading profiles in constructor
        self._company_profiles = None
        
        # Get all company names for relevance scoring
        self._all_company_names = None
        
        # High-impact keywords for relevance scoring
        self.high_impact_keywords = [
            "earnings", "revenue", "profit", "loss", "quarterly", "annual",
            "acquisition", "merger", "partnership", "investment", "funding",
            "regulation", "compliance", "enforcement", "investigation",
            "technology", "digital", "innovation", "transformation",
            "cybersecurity", "data breach", "privacy", "AI", "machine learning",
            "cloud", "blockchain", "fintech", "mobile", "app",
            "customer", "user", "growth", "expansion", "market",
            "competition", "rival", "industry", "sector", "trend",
            "executive", "CEO", "CFO", "leadership", "management",
            "board", "director", "shareholder", "investor", "analyst",
            "rating", "upgrade", "downgrade", "target", "forecast",
            "guidance", "outlook", "expectation", "projection"
        ]
        
        logger.info("🔍 DataConsolidator initialized")
        logger.info("📁 Output directory: %s", self.output_dir)

    @property
    def company_profiles(self):
        """Lazy load company profiles when first accessed."""
        if self._company_profiles is None:
            self._company_profiles = self.profile_loader.load_profiles()
        return self._company_profiles

    @property
    def all_company_names(self):
        """Lazy load company names when first accessed."""
        if self._all_company_names is None:
            self._all_company_names = list(self.company_profiles.keys())
        return self._all_company_names

    async def consolidate_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Consolidates raw data from all extractors, applies relevance scoring,
        and filters to the most important findings.
        """
        logger.info("📊 Starting data consolidation with %d raw items", len(raw_data))
        
        if not raw_data:
            logger.warning("⚠️  No raw data provided for consolidation")
            return []

        # Process each item with relevance scoring
        processed_items = []
        for item in raw_data:
            relevance_score = self._calculate_relevance_score(item)
            item['relevance_score'] = relevance_score
            processed_items.append(item)

        logger.info("📊 Relevance scoring complete for %d items", len(processed_items))
        
        # Show relevance score distribution
        score_distribution = {}
        for item in processed_items:
            score = round(item['relevance_score'], 2)
            score_distribution[score] = score_distribution.get(score, 0) + 1
        
        logger.info("📈 Relevance score distribution: %s", score_distribution)

        # Filter out items with low relevance (can be adjusted)
        relevant_items = [item for item in processed_items if item['relevance_score'] > 0.0]  # Keep all items with any relevance
        relevant_items.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        logger.info("✅ Consolidated %d relevant items (%.1f%% of original)", 
                   len(relevant_items), (len(relevant_items) / len(raw_data) * 100) if raw_data else 0)

        # Save consolidated data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"consolidated_{timestamp}.json"
        
        try:
            with open(output_file, 'w') as f:
                json.dump(relevant_items, f, indent=2, default=str)
            logger.info("💾 Consolidated data saved to: %s", output_file)
        except Exception as e:
            log_error(e, f"Failed to save consolidated data to {output_file}")

        return relevant_items

    def _calculate_relevance_score(self, item: Dict[str, Any]) -> float:
        """
        Calculate a relevance score based on company mentions and high-impact keywords.
        Re-integrated from old implementation with more relaxed filtering.
        """
        score = 0.0

        # Get text to analyze
        title = item.get('title', '').lower()
        description = item.get('description', '').lower()
        content = item.get('content', '').lower()

        all_text = f"{title} {description} {content}"

        # Check for target company mentions - very flexible matching
        company_mentioned = False
        for company_lower in [c.lower() for c in self.all_company_names]:
            # Very flexible company name matching - check for any word in company name
            company_words = company_lower.split()
            if (company_lower in all_text or 
                any(word in all_text for word in company_words if len(word) > 2)):  # Only check words > 2 chars
                score += 0.2  # Lower weight for company mention
                company_mentioned = True
                break

        # Even if no company mentioned, still consider items with high-impact keywords
        if not company_mentioned:
            # Check for high-impact keywords even without company mention
            keyword_matches = 0
            for keyword in [k.lower() for k in self.high_impact_keywords]:
                if keyword in all_text:
                    keyword_matches += 1
                    score += 0.05  # Even smaller weight for keywords

            # If we have multiple keywords, still consider it relevant
            if keyword_matches >= 1:  # Reduced from 2 to 1
                score += 0.1
                company_mentioned = True  # Treat as relevant

        if not company_mentioned:
            return 0.0  # No relevance if no company mentioned and insufficient keywords

        # Check for high-impact keywords
        keyword_matches = 0
        for keyword in [k.lower() for k in self.high_impact_keywords]:
            if keyword in all_text:
                keyword_matches += 1
                score += 0.05  # Reduced weight for each keyword

        # Bonus for multiple keywords
        if keyword_matches >= 1:  # Reduced from 2 to 1
            score += 0.1

        # Normalize score to 0-1 range
        score = min(score, 1.0)

        return score

    def _extract_key_terms(self, item: Dict[str, Any]) -> List[str]:
        """
        Extract key terms from the item for analysis.
        Re-integrated from old implementation.
        """
        key_terms = []
        
        title = item.get('title', '')
        description = item.get('description', '')
        content = item.get('content', '')
        
        all_text = f"{title} {description} {content}".lower()
        
        # Extract terms that match high-impact keywords
        for keyword in self.high_impact_keywords:
            if keyword.lower() in all_text:
                key_terms.append(keyword)
        
        # Extract company names
        for company in self.all_company_names:
            if company.lower() in all_text:
                key_terms.append(company)
        
        # Remove duplicates and limit to top terms
        unique_terms = list(set(key_terms))
        return unique_terms[:10]  # Limit to top 10 terms

    def _determine_source_type(self, item: Dict[str, Any]) -> str:
        """
        Determine the source type of an item.
        Re-integrated from old implementation.
        """
        source = item.get('source_name', item.get('source', '')).lower()
        
        if 'sec' in source or 'filing' in source:
            return 'sec_filing'
        elif 'sam.gov' in source or 'procurement' in source:
            return 'procurement'
        elif 'news' in source or 'article' in source or 'gnews' in source or 'rss' in source:
            return 'news'
        elif 'bing' in source:
            return 'bing_grounding'
        else:
            return 'unknown'

    def _create_analysis_document(self, items: List[Dict[str, Any]]) -> str:
        """
        Creates a structured Markdown document from the consolidated items.
        """
        doc_parts = [f"# Intelligence Analysis Document - {datetime.now().strftime('%Y-%m-%d')}"]
        
        company_summary = {}
        for item in items:
            for company in self.all_company_names:
                if company.lower() in item.get('content', '').lower() or company.lower() in item.get('title', '').lower():
                    company_summary[company] = company_summary.get(company, 0) + 1
        
        if company_summary:
            doc_parts.append("\n## Monitored Companies Mentioned")
            for company, count in company_summary.items():
                doc_parts.append(f"- **{company}:** {count} relevant item(s)")
        
        all_content = " ".join([item.get('content', '') for item in items])
        key_terms_identified = {kw for kw in self.high_impact_keywords if kw.lower() in all_content.lower()}
        if key_terms_identified:
            doc_parts.append("\n## Key Themes Identified")
            doc_parts.append(", ".join(sorted(list(key_terms_identified))))
            
        doc_parts.append("\n---\n\n## Detailed Analysis Items")
        
        for i, item in enumerate(items, 1):
            doc_parts.append(f"\n### Item {i}: {item.get('title', 'No Title')}")
            doc_parts.append(f"**Source:** {item.get('source', 'N/A')} | **Relevance Score:** {item.get('relevance_score', 0):.2f}")
            doc_parts.append(f"**Companies:** {item.get('company', 'N/A')}") # Assuming primary company is set
            if item.get('published_date'):
                doc_parts.append(f"**Date:** {item.get('published_date')}")
            if item.get('link'):
                doc_parts.append(f"**Link:** {item.get('link')}")
            
            content_summary = (item.get('content', '')[:1000] + '...') if len(item.get('content', '')) > 1000 else item.get('content', '')
            doc_parts.append(f"\n**Content Summary:**\n```\n{content_summary}\n```")
        
        return "\n".join(doc_parts)

    def _save_output(self, items: List[Dict[str, Any]], document: str) -> Dict[str, str]:
        """
        Saves the consolidated items (JSON) and the analysis document (Markdown).
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        json_filename = f"consolidated_{timestamp}.json"
        json_filepath = self.output_dir / json_filename
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
            
        md_filename = f"analysis_doc_{timestamp}.md"
        md_filepath = self.output_dir / md_filename
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(document)
            
        return {"json_file": json_filepath, "markdown_file": md_filepath}