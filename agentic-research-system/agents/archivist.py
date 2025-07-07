import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, Any, List

class Archivist:
    def __init__(self, db_path='data/research.db'):
        self.db_path = db_path

    def _generate_hash(self, headline: str, company: str) -> str:
        """Creates a unique hash for an event."""
        content = f"{headline.strip()}{company.strip()}".encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def save_finding(self, finding: Dict[str, Any]) -> str:
        """Saves a new finding to the database if it doesn't exist."""
        event_hash = self._generate_hash(finding['headline'], finding['company'])

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check for existence
            cursor.execute("SELECT id FROM findings WHERE event_hash = ?", (event_hash,))
            if cursor.fetchone():
                print(f"🔄 Event '{finding['headline']}' is a repeat. Skipping save.")
                conn.close()
                return "Repeat"

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
                datetime.now().isoformat(), 
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
        
        conn.close()
        return stats 