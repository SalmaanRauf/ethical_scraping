import sqlite3
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

class Archivist:
    def __init__(self, db_path='data/research.db'):
        self.db_path = db_path
        
        # Similarity threshold for de-duplication (0.7 = quite similar)
        self.similarity_threshold = 0.7
        
        # Ensure similarity table exists
        self._setup_similarity_table()

    def _setup_similarity_table(self):
        """Create table to store event summaries for semantic de-duplication."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id INTEGER NOT NULL,
                event_summary TEXT NOT NULL,
                key_terms TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (finding_id) REFERENCES findings (id)
            )
            ''')
            
            conn.commit()
            print("✅ Event summaries table ready")
        except Exception as e:
            print(f"❌ Error setting up summaries table: {e}")
        finally:
            conn.close()

    def _generate_event_summary(self, finding: Dict[str, Any]) -> str:
        """
        Generate a standardized event summary for semantic comparison.
        Focuses on the core event details rather than headline variations.
        """
        company = finding.get('company', '')
        event_type = finding.get('event_type', '')
        value_usd = finding.get('value_usd', 0)
        what_happened = finding.get('what_happened', '')
        
        # Create a standardized summary focusing on the core event
        summary_parts = []
        
        if company:
            summary_parts.append(f"Company: {company}")
        
        if event_type:
            summary_parts.append(f"Event Type: {event_type}")
        
        if value_usd and value_usd > 0:
            summary_parts.append(f"Value: ${value_usd:,}")
        
        if what_happened:
            # Clean up the what_happened text to focus on core event
            cleaned = what_happened.replace('\n', ' ').strip()
            if len(cleaned) > 200:
                cleaned = cleaned[:200] + "..."
            summary_parts.append(f"Details: {cleaned}")
        
        return " | ".join(summary_parts)

    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Extract key terms for similarity comparison.
        """
        # Remove common words and extract meaningful terms
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        # Extract words and filter
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        key_terms = [word for word in words if word not in common_words and len(word) > 2]
        
        return key_terms

    def _calculate_similarity(self, terms1: List[str], terms2: List[str]) -> float:
        """
        Calculate similarity between two sets of terms using Jaccard similarity.
        """
        if not terms1 or not terms2:
            return 0.0
        
        set1 = set(terms1)
        set2 = set(terms2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        if union == 0:
            return 0.0
        
        return intersection / union

    def _check_semantic_duplicate(self, new_summary: str, company: str, date_found: str) -> Tuple[bool, Optional[int]]:
        """
        Check if a new event is semantically similar to existing events from the same day.
        Returns (is_duplicate, existing_finding_id).
        """
        try:
            # Extract key terms from new summary
            new_terms = self._extract_key_terms(new_summary)
            
            # Get existing events from the same day and company
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Parse date to get just the date part
            try:
                event_date = datetime.fromisoformat(date_found).strftime('%Y-%m-%d')
            except:
                event_date = date_found[:10]  # Fallback to first 10 chars
            
            cursor.execute("""
                SELECT f.id, f.headline, e.key_terms
                FROM findings f
                LEFT JOIN event_summaries e ON f.id = e.finding_id
                WHERE f.company = ? AND f.date_found LIKE ?
            """, (company, f"{event_date}%"))
            
            existing_events = cursor.fetchall()
            conn.close()
            
            if not existing_events:
                print(f"✅ No existing events found for {company} on {event_date}")
                return False, None
            
            # Check similarity with each existing event
            for finding_id, headline, stored_terms in existing_events:
                if not stored_terms:
                    print(f"⚠️  No key terms stored for finding {finding_id}")
                    continue
                
                # Parse stored terms
                try:
                    existing_terms = stored_terms.split(',')
                except:
                    continue
                
                similarity = self._calculate_similarity(new_terms, existing_terms)
                
                print(f"🔍 Comparing with existing event {finding_id}:")
                print(f"   New: {new_summary[:100]}...")
                print(f"   Existing: {headline}")
                print(f"   Similarity: {similarity:.3f}")
                
                if similarity >= self.similarity_threshold:
                    print(f"✅ Semantic duplicate detected (similarity: {similarity:.3f})")
                    return True, finding_id
            
            print(f"✅ No semantic duplicates found (max similarity: {max([self._calculate_similarity(new_terms, e[2].split(',') if e[2] else []) for e in existing_events], default=0):.3f})")
            return False, None
            
        except Exception as e:
            print(f"❌ Error checking semantic duplicates: {e}")
            return False, None

    def _generate_hash(self, headline: str, company: str) -> str:
        """Creates a unique hash for an event (fallback method)."""
        content = f"{headline.strip()}{company.strip()}".encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def save_finding(self, finding: Dict[str, Any]) -> str:
        """
        Saves a new finding to the database with semantic de-duplication.
        """
        # Generate event summary for semantic comparison
        event_summary = self._generate_event_summary(finding)
        company = finding.get('company', '')
        date_found = datetime.now().isoformat()
        
        print(f"🔍 Checking for semantic duplicates: {event_summary[:100]}...")
        
        # Check for semantic duplicates
        is_duplicate, existing_id = self._check_semantic_duplicate(
            event_summary, company, date_found
        )
        
        if is_duplicate:
            print(f"🔄 Event is a semantic duplicate of finding {existing_id}. Skipping save.")
            return "SemanticDuplicate"
        
        # Generate traditional hash as backup
        event_hash = self._generate_hash(finding['headline'], finding['company'])
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check for exact hash match (fallback)
            cursor.execute("SELECT id FROM findings WHERE event_hash = ?", (event_hash,))
            if cursor.fetchone():
                print(f"🔄 Event '{finding['headline']}' is an exact repeat. Skipping save.")
                conn.close()
                return "ExactDuplicate"

            # Insert new record
            cursor.execute("""
                INSERT INTO findings (
                    event_hash, date_found, company, headline, what_happened, 
                    why_it_matters, consulting_angle, source_url, event_type, 
                    value_usd, source_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_hash, 
                date_found, 
                finding['company'], 
                finding['headline'], 
                finding.get('what_happened', ''),
                finding.get('why_it_matters', ''),
                finding.get('consulting_angle', ''),
                finding.get('source_url', ''),
                finding.get('event_type', ''),
                finding.get('value_usd', 0),
                finding.get('source_type', '')
            ))
            
            # Get the ID of the newly inserted finding
            finding_id = cursor.lastrowid
            
            # Save summary and key terms for future semantic de-duplication
            try:
                key_terms = self._extract_key_terms(event_summary)
                cursor.execute("""
                    INSERT INTO event_summaries (
                        finding_id, event_summary, key_terms
                    )
                    VALUES (?, ?, ?)
                """, (finding_id, event_summary, ','.join(key_terms)))
                print(f"💾 Saved summary for finding {finding_id}")
            except Exception as e:
                print(f"⚠️  Could not save summary: {e}")

            conn.commit()
            print(f"✅ Saved new finding: {finding['headline']}")
            return "New"
            
        except Exception as e:
            print(f"❌ Error saving finding: {e}")
            conn.rollback()
            return "Error"
        finally:
            conn.close()

    def save_raw_data(self, data_items: List[Dict[str, Any]]) -> None:
        """Save raw data for validation purposes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for item in data_items:
                cursor.execute("""
                    INSERT INTO raw_data (
                        date_collected, data_type, company, title, content, 
                        source_url, source_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    item.get('type', 'unknown'),
                    item.get('company', ''),
                    item.get('title', ''),
                    item.get('text', item.get('summary', '')),
                    item.get('link', item.get('source_url', '')),
                    item.get('source', '')
                ))
            
            conn.commit()
            print(f"✅ Saved {len(data_items)} raw data items")
            
        except Exception as e:
            print(f"❌ Error saving raw data: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_todays_findings(self) -> List[Dict[str, Any]]:
        """Get all findings from today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT * FROM findings 
            WHERE date_found LIKE ? 
            ORDER BY created_at DESC
        """, (f"{today}%",))
        
        columns = [description[0] for description in cursor.description]
        findings = []
        
        for row in cursor.fetchall():
            findings.append(dict(zip(columns, row)))
        
        conn.close()
        return findings

    def get_findings_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get findings within a date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM findings 
            WHERE date_found BETWEEN ? AND ?
            ORDER BY created_at DESC
        """, (start_date, end_date))
        
        columns = [description[0] for description in cursor.description]
        findings = []
        
        for row in cursor.fetchall():
            findings.append(dict(zip(columns, row)))
        
        conn.close()
        return findings

    def save_validation_result(self, finding_id: int, method: str, result: bool, details: str = "") -> None:
        """Save validation result for a finding."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO validation_log (
                    finding_id, validation_method, validation_result, validation_details
                )
                VALUES (?, ?, ?, ?)
            """, (finding_id, method, result, details))
            
            conn.commit()
            print(f"✅ Saved validation result for finding {finding_id}")
            
        except Exception as e:
            print(f"❌ Error saving validation result: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}
        
        # Count findings
        cursor.execute("SELECT COUNT(*) FROM findings")
        stats['total_findings'] = cursor.fetchone()[0]
        
        # Count today's findings
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM findings WHERE date_found LIKE ?", (f"{today}%",))
        stats['todays_findings'] = cursor.fetchone()[0]
        
        # Count raw data
        cursor.execute("SELECT COUNT(*) FROM raw_data")
        stats['total_raw_data'] = cursor.fetchone()[0]
        
        # Count validation logs
        cursor.execute("SELECT COUNT(*) FROM validation_log")
        stats['total_validations'] = cursor.fetchone()[0]
        
        # Count summaries
        cursor.execute("SELECT COUNT(*) FROM event_summaries")
        stats['total_summaries'] = cursor.fetchone()[0]
        
        conn.close()
        return stats

    def test_semantic_deduplication(self):
        """Test the semantic de-duplication system."""
        print("🧪 Testing semantic de-duplication system...")
        
        # Test case 1: Same event, different headlines
        test_finding_1 = {
            'company': 'Capital One',
            'headline': 'Capital One Announces $50M Acquisition of Tech Startup',
            'what_happened': 'Capital One has acquired a financial technology startup for $50 million to enhance its digital banking capabilities.',
            'event_type': 'Acquisition',
            'value_usd': 50000000
        }
        
        test_finding_2 = {
            'company': 'Capital One',
            'headline': 'Capital One Buys FinTech Company for $50 Million',
            'what_happened': 'Capital One has acquired a financial technology startup for $50 million to enhance its digital banking capabilities.',
            'event_type': 'Acquisition',
            'value_usd': 50000000
        }
        
        # Save first finding
        result1 = self.save_finding(test_finding_1)
        print(f"Test 1 result: {result1}")
        
        # Try to save second finding (should be detected as duplicate)
        result2 = self.save_finding(test_finding_2)
        print(f"Test 2 result: {result2}")
        
        # Test case 3: Different event, same company
        test_finding_3 = {
            'company': 'Capital One',
            'headline': 'Capital One Reports Q4 Earnings of $2.1B',
            'what_happened': 'Capital One reported fourth quarter earnings of $2.1 billion, exceeding analyst expectations.',
            'event_type': 'Earnings',
            'value_usd': 2100000000
        }
        
        result3 = self.save_finding(test_finding_3)
        print(f"Test 3 result: {result3}")
        
        print("✅ Semantic de-duplication test complete") 