import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import re
import logging
from services.profile_loader import ProfileLoader

logger = logging.getLogger(__name__)

class DataConsolidator:
    """
    Consolidates raw data from all extractors into a structured document
    for efficient analysis by the Analyst Agent. It applies detailed relevance
    scoring and key term extraction.
    """

    def __init__(self, profile_loader: ProfileLoader, output_dir: str = "data/consolidated_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.profile_loader = profile_loader
        self.company_profiles = self.profile_loader.load_profiles()
        self.all_company_names = self._get_all_company_names()

        # Keywords that indicate high-impact events (from old implementation)
        self.high_impact_keywords = [
            "earnings", "revenue", "profit", "loss", "quarterly", "annual", "financial results",
            "merger", "acquisition", "buyout", "takeover", "deal", "transaction",
            "layoff", "restructuring", "reorganization", "cost cutting",
            "expansion", "growth", "investment", "funding", "capital raise",
            "regulatory", "compliance", "enforcement", "investigation", "settlement",
            "fine", "penalty", "violation", "cease and desist", "consent order",
            "digital transformation", "technology", "AI", "artificial intelligence",
            "blockchain", "cryptocurrency", "fintech", "innovation",
            "CEO", "executive", "leadership", "appointment", "resignation",
            "board", "director", "management change",
            "market", "trading", "stock", "share", "dividend", "buyback",
            "IPO", "initial public offering", "listing"
        ]

    def _get_all_company_names(self) -> List[str]:
        """Gathers all canonical names and aliases from loaded profiles."""
        names = []
        for profile in self.company_profiles.values():
            # Handle both new and legacy profile formats
            if 'display_name' in profile:
                names.append(profile['display_name'])
            elif 'company_name' in profile:
                names.append(profile['company_name'])
            names.extend(profile.get('aliases', []))
        return sorted(list(set(names)), key=len, reverse=True)

    def process_raw_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process raw data from all extractors, apply relevance scoring and key term extraction.
        """
        logger.info(f"🔄 Processing {len(raw_data)} raw data items...")
        
        processed_items = []
        for item in raw_data:
            # Determine source type (re-integrated from old consolidator)
            source_type = self._determine_source_type(item)
            item['source_type'] = source_type

            # Calculate relevance score (re-integrated from old consolidator)
            relevance_score = self._calculate_relevance_score(item)
            item['relevance_score'] = relevance_score

            # Extract key terms (re-integrated from old consolidator)
            item['key_terms'] = self._extract_key_terms(item)
            
            processed_items.append(item)

        # Filter out items with low relevance (can be adjusted)
        relevant_items = [item for item in processed_items if item['relevance_score'] > 0.0]
        relevant_items.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        analysis_document = self._create_analysis_document(relevant_items)
        output_files = self._save_output(relevant_items, analysis_document)
        
        result = {
            "consolidated_items": relevant_items,
            "analysis_document": analysis_document,
            "files": output_files
        }
        
        logger.info(f"✅ Consolidated {len(relevant_items)} relevant items")
        return result

    def _calculate_relevance_score(self, item: Dict[str, Any]) -> float:
        """
        Calculate a relevance score based on company mentions and high-impact keywords.
        Re-integrated from old implementation.
        """
        score = 0.0

        # Get text to analyze
        title = item.get('title', '').lower()
        description = item.get('description', '').lower()
        content = item.get('content', '').lower()

        all_text = f"{title} {description} {content}"

        # Check for target company mentions
        company_mentioned = False
        for company_lower in [c.lower() for c in self.all_company_names]:
            if company_lower in all_text:
                score += 0.4  # High weight for company mention
                company_mentioned = True
                break

        if not company_mentioned:
            return 0.0  # No relevance if no target company mentioned

        # Check for high-impact keywords
        keyword_matches = 0
        for keyword in [k.lower() for k in self.high_impact_keywords]:
            if keyword in all_text:
                keyword_matches += 1
                score += 0.1  # Moderate weight for each keyword

        # Bonus for multiple keywords
        if keyword_matches >= 3:
            score += 0.2

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
        json_filepath = os.path.join(self.output_dir, json_filename)
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
            
        md_filename = f"analysis_doc_{timestamp}.md"
        md_filepath = os.path.join(self.output_dir, md_filename)
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(document)
            
        return {"json_file": json_filepath, "markdown_file": md_filepath}