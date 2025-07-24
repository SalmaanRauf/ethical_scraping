import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ConsolidatedItem:
    """Represents a consolidated data item, now capable of including company profile info."""
    source_type: str  # 'news', 'sec_filing', 'procurement', 'company_profile'
    company: str
    title: str
    description: str
    url: str
    published_date: str
    source_name: str
    raw_data: Dict[str, Any]  # Original raw data
    relevance_score: float = 0.0
    key_terms: List[str] = None
    company_profile: Dict[str, Any] = None  # <-- added for profile enrichment
    def __post_init__(self):
        if self.key_terms is None:
            self.key_terms = []
        if self.company_profile is None:
            self.company_profile = {}

class DataConsolidator:
    """
    Consolidates raw data from all extractors into a structured document
    for efficient analysis by the Analyst Agent.
    """

    def __init__(self, output_dir: str = "data/consolidated"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Target companies for filtering
        self.target_companies = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", 
            "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]

        # Keywords that indicate high-impact events
        self.high_impact_keywords = [
            # Financial terms
            "earnings", "revenue", "profit", "loss", "quarterly", "annual", "financial results",
            "merger", "acquisition", "buyout", "takeover", "deal", "transaction",
            "layoff", "restructuring", "reorganization", "cost cutting",
            "expansion", "growth", "investment", "funding", "capital raise",

            # Regulatory terms
            "regulatory", "compliance", "enforcement", "investigation", "settlement",
            "fine", "penalty", "violation", "cease and desist", "consent order",

            # Technology terms
            "digital transformation", "technology", "AI", "artificial intelligence",
            "blockchain", "cryptocurrency", "fintech", "innovation",

            # Leadership terms
            "CEO", "executive", "leadership", "appointment", "resignation",
            "board", "director", "management change",

            # Market terms
            "market", "trading", "stock", "share", "dividend", "buyback",
            "IPO", "initial public offering", "listing"
        ]

    def _calculate_relevance_score(self, item: Dict[str, Any]) -> float:
        """
        Calculate a relevance score based on company mentions and high-impact keywords.
        """
        score = 0.0

        # Get text to analyze
        title = item.get('title', '').lower()
        description = item.get('description', '').lower()
        summary = item.get('summary', '').lower()
        content = item.get('content', '').lower()

        all_text = f"{title} {description} {summary} {content}"

        # Pre-compute lowercase versions for efficiency
        target_companies_lower = [company.lower() for company in self.target_companies]
        high_impact_keywords_lower = [keyword.lower() for keyword in self.high_impact_keywords]

        # Check for target company mentions
        company_mentioned = False
        for company_lower in target_companies_lower:
            if company_lower in all_text:
                score += 0.4  # High weight for company mention
                company_mentioned = True
                break

        if not company_mentioned:
            return 0.0  # No relevance if no target company mentioned

        # Check for high-impact keywords
        keyword_matches = 0
        for keyword_lower in high_impact_keywords_lower:
            if keyword_lower in all_text:
                keyword_matches += 1
                score += 0.1  # Moderate weight for each keyword

        # Bonus for multiple keywords
        if keyword_matches >= 3:
            score += 0.2

        # Cap score at 1.0
        return min(score, 1.0)

    def _extract_key_terms(self, item: Dict[str, Any]) -> List[str]:
        """
        Extract key terms from an item for analysis.
        """
        import re

        # Get all text content
        title = item.get('title', '')
        description = item.get('description', '')
        summary = item.get('summary', '')
        content = item.get('content', '')

        all_text = f"{title} {description} {summary} {content}"

        # Extract words (3+ characters, alphanumeric)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())

        # Filter out common words
        common_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'me', 'him', 'her', 'us', 'them', 'from', 'into', 'during',
            'including', 'until', 'against', 'among', 'throughout', 'despite', 'towards',
            'upon', 'concerning', 'about', 'like', 'through', 'over', 'before', 'after',
            'since', 'without', 'under', 'within', 'along', 'following', 'across',
            'behind', 'beyond', 'plus', 'except', 'but', 'up', 'out', 'off', 'above',
            'below', 'between', 'among', 'around', 'down', 'up', 'in', 'out', 'on',
            'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
            'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can',
            'will', 'just', 'don', 'should', 'now', 'd', 'll', 'm', 'o', 're',
            've', 'y', 'ain', 'aren', 'couldn', 'didn', 'doesn', 'hadn', 'hasn',
            'haven', 'isn', 'ma', 'mightn', 'mustn', 'needn', 'shan', 'shouldn',
            'wasn', 'weren', 'won', 'wouldn'
        }

        key_terms = [word for word in words if word not in common_words]

        # Limit to top 10 most frequent terms
        from collections import Counter
        term_counts = Counter(key_terms)
        return [term for term, count in term_counts.most_common(10)]

    def _normalize_item(self, item: Dict[str, Any], source_type: str) -> Optional[ConsolidatedItem]:
        """
        Normalize a raw data item (including company profile type).
        """
        if not isinstance(item, dict):
            logger.warning(f"Invalid item type: {type(item)}, skipping")
            return None
        if source_type == 'company_profile':
            # Profile entries are not directly events; only for embedding
            return ConsolidatedItem(
                source_type=source_type, company=item.get('company', ''), title='', description='', url='',
                published_date='', source_name='company_api', raw_data=item)
        company = str(item.get('company', '')).strip()
        title = str(item.get('title', item.get('headline', ''))).strip()
        url = str(item.get('url', item.get('link', ''))).strip()
        published_date = str(item.get('published_date', item.get('publishedAt', ''))).strip()
        source_name = str(item.get('source_name', item.get('source', ''))).strip()

        # Prefer full_content if available and flagged as enhanced
        if item.get('full_content') and item.get('content_enhanced'):
            description = str(item.get('full_content')).strip()
            logger.info(f"[DATA CONSOLIDATOR] Using full_content for '{title[:60]}' (source_type={source_type}, url={url})")
        else:
            description = str(item.get('description', item.get('summary', ''))).strip()
            logger.info(f"[DATA CONSOLIDATOR] Using description/summary for '{title[:60]}' (source_type={source_type}, url={url})")

        if not title:
            logger.warning("Item missing title, skipping")
            return None

        relevance_score = self._calculate_relevance_score(item)
        key_terms = self._extract_key_terms(item)

        return ConsolidatedItem(
            source_type=source_type,
            company=company,
            title=title,
            description=description,
            url=url,
            published_date=published_date,
            source_name=source_name,
            raw_data=item,
            relevance_score=relevance_score,
            key_terms=key_terms
        )

    def process_raw_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize all raw data. Output is {'events': [event, ...], 'profiles': {company: profile, ...}}.
        For each event, do NOT attach profile. Save both events list and profiles dict.
        """
        logger.info("🚀 Starting data consolidation process...")

        # --- Collect profiles first ---
        company_profiles = {}
        for item in raw_data:
            if item.get('source_type') == 'company_profile':
                company = item.get('company')
                company_profiles[company] = item
        # --- Normalize all events (skip attaching profile on events) ---
        consolidated_items = []
        for item in raw_data:
            norm = self._normalize_item(item, item.get('source_type', 'unknown'))
            if norm is None:
                continue
            # Skip company_profile flat entry, only use for enrichment
            if norm.source_type == 'company_profile':
                continue
            # DO NOT DO: norm.company_profile = company_profiles[norm.company]
            consolidated_items.append(norm)

        if not consolidated_items:
            logger.warning("⚠️ No relevant items found for analysis")
            return {
                'events': [],
                'profiles': {},
                'analysis_document': "# No relevant items found for analysis",
                'files': {},
                'item_count': 0
            }

        analysis_document = self.create_analysis_document(consolidated_items)
        files = self.save_compact_consolidated_data(consolidated_items, company_profiles, analysis_document)
        logger.info(f"✅ Data consolidation complete: {len(consolidated_items)} items processed")
        return {
            "events": [asdict(item) for item in consolidated_items],
            "profiles": company_profiles,
            "analysis_document": analysis_document,
            "files": files,
            "item_count": len(consolidated_items)
        }

    def consolidate_data(self, raw_data: List[Dict[str, Any]]) -> List[ConsolidatedItem]:
        """
        Consolidate raw data from all extractors into structured items.
        Modified: SEC filings always included for downstream analysis regardless of score.
        """
        logger.info(f"🔄 Consolidating {len(raw_data)} raw data items...")

        consolidated_items = []

        for item in raw_data:
            # --- UPDATED SOURCE TYPE LOGIC: SEC comes FIRST ---
            source_type = 'unknown'
            sec_detected = (
                'filing_type' in item
                or 'sec' in str(item.get('source_name', '')).lower()
                or 'sec' in str(item.get('source', '')).lower()
                or 'formType' in item
            )
            if sec_detected:
                source_type = 'sec_filing'
            elif 'feed_source' in item or 'source' in item:
                source_type = 'news'
            elif 'naics' in item or 'procurement' in str(item).lower():
                source_type = 'procurement'

            consolidated_item = self._normalize_item(item, source_type)

            # --- KEY LOGIC: SEC filings always included ---
            if consolidated_item:
                if source_type == 'sec_filing':
                    consolidated_items.append(consolidated_item)
                    logger.debug(f"✅ [SEC] Forced add: {consolidated_item.title[:50]}... (score: {consolidated_item.relevance_score:.2f})")
                elif consolidated_item.relevance_score > 0.0:
                    consolidated_items.append(consolidated_item)
                    logger.debug(f"✅ Added item: {consolidated_item.title[:50]}... (score: {consolidated_item.relevance_score:.2f})")
            else:
                logger.debug(f"❌ Skipped item: {item.get('title', 'Unknown')[:50]}... (score: 0.0)")

        # Sort by relevance score (SEC filings keep original order, news first)
        consolidated_items.sort(key=lambda x: (x.source_type != 'sec_filing', -x.relevance_score))

        logger.info(f"✅ Consolidated {len(consolidated_items)} relevant items from {len(raw_data)} total")
        return consolidated_items

    def create_analysis_document(self, consolidated_items: List[ConsolidatedItem]) -> str:
        """
        Create a structured document for the Analyst Agent to process.
        """
        logger.info(f"📄 Creating analysis document with {len(consolidated_items)} items...")

        # Create document content
        doc_content = []
        doc_content.append("# Financial Intelligence Analysis Document")
        doc_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc_content.append(f"Total Items: {len(consolidated_items)}")
        doc_content.append("")

        # Group by company
        company_groups = {}
        for item in consolidated_items:
            company = item.company or "Unknown"
            if company not in company_groups:
                company_groups[company] = []
            company_groups[company].append(item)

        # Add items grouped by company
        for company, items in company_groups.items():
            doc_content.append(f"## {company}")
            doc_content.append("")

            for i, item in enumerate(items, 1):
                doc_content.append(f"### Item {i}: {item.title}")
                doc_content.append(f"**Source Type:** {item.source_type}")
                doc_content.append(f"**Relevance Score:** {item.relevance_score:.2f}")
                doc_content.append(f"**Published:** {item.published_date}")
                doc_content.append(f"**Source:** {item.source_name}")
                doc_content.append(f"**URL:** {item.url}")
                doc_content.append("")
                doc_content.append(f"**Description:** {item.description}")
                doc_content.append("")
                doc_content.append(f"**Key Terms:** {', '.join(item.key_terms)}")
                doc_content.append("")
                doc_content.append("---")
                doc_content.append("")

        # Add summary statistics
        doc_content.append("## Summary Statistics")
        doc_content.append("")

        # Source type breakdown
        source_counts = {}
        for item in consolidated_items:
            source_counts[item.source_type] = source_counts.get(item.source_type, 0) + 1

        doc_content.append("**Items by Source Type:**")
        for source_type, count in source_counts.items():
            doc_content.append(f"- {source_type}: {count}")
        doc_content.append("")

        # Relevance score distribution
        high_relevance = len([item for item in consolidated_items if item.relevance_score >= 0.7])
        medium_relevance = len([item for item in consolidated_items if 0.3 <= item.relevance_score < 0.7])
        low_relevance = len([item for item in consolidated_items if item.relevance_score < 0.3])

        doc_content.append("**Items by Relevance Score:**")
        doc_content.append(f"- High relevance (≥0.7): {high_relevance}")
        doc_content.append(f"- Medium relevance (0.3-0.7): {medium_relevance}")
        doc_content.append(f"- Low relevance (<0.3): {low_relevance}")
        doc_content.append("")

        return "\n".join(doc_content)

    def save_compact_consolidated_data(self, consolidated_items: List['ConsolidatedItem'],
                                   company_profiles: dict,
                                   analysis_document: str) -> Dict[str, str]:
        """
        Save events and company profiles in deduplicated schema.
        Removes company_profile key from each event for optimal storage.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_data = {
            "events": [
                {k: v for k, v in asdict(item).items() if k != "company_profile"}
                for item in consolidated_items
            ],
            "profiles": company_profiles
        }
        json_filename = os.path.join(self.output_dir, f"consolidated_data_{timestamp}.json")
        try:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(out_data, f, indent=2, default=str)
            logger.info(f"💾 Saved deduplicated data to: {json_filename}")
        except IOError as e:
            logger.error(f"Error saving consolidated data to {json_filename}: {e}")
            return {}
        doc_filename = os.path.join(self.output_dir, f"analysis_document_{timestamp}.md")
        try:
            with open(doc_filename, 'w', encoding='utf-8') as f:
                f.write(analysis_document)
            logger.info(f"💾 Saved analysis document to: {doc_filename}")
        except IOError as e:
            logger.error(f"Error saving analysis document to {doc_filename}: {e}")
            return {}
        return {
            'json_file': json_filename,
            'markdown_file': doc_filename,
            'item_count': len(consolidated_items)
        }

# --- Testing ---
if __name__ == "__main__":
    import json
    # Add a simple test to verify profile splitting (not attached to events)
    test_event = {
        "company": "Capital One",
        "title": "Test Event",
        "description": "Event happened.",
        "url": "http://example.com",
        "published_date": "2024-01-01T00:00:00Z",
        "source": "news"
    }
    test_profile = {
        "source_type": "company_profile",
        "company": "Capital One",
        "industry": "Financial Services",
        "key_buyers": [{"name": "Jane Doe", "email": "jane@co.com"}],
        "projects": [{"name": "ProjectX", "status": "active"}]
    }
    dc = DataConsolidator()
    out = dc.process_raw_data([test_event, test_profile])
    assert out['events'][0]['company'] == "Capital One"
    assert out['profiles']["Capital One"]["industry"] == "Financial Services"
    print("✅ DataConsolidator dedup schema test passed.")


