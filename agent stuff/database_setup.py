import sqlite3
import os
from datetime import datetime

def setup_database():
    """Creates the database and the findings table if they don't exist."""
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()

    # Create version table for migrations
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schema_version (
        id INTEGER PRIMARY KEY,
        version INTEGER NOT NULL,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create table to store high-impact findings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_hash TEXT UNIQUE NOT NULL,
        date_found TEXT NOT NULL,
        company TEXT NOT NULL,
        headline TEXT NOT NULL,
        what_happened TEXT,
        why_it_matters TEXT,
        consulting_angle TEXT,
        source_url TEXT,
        event_type TEXT,
        value_usd INTEGER,
        source_type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create table to store raw data for validation
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_collected TEXT NOT NULL,
        data_type TEXT NOT NULL,
        company TEXT,
        title TEXT,
        content TEXT,
        source_url TEXT,
        source_type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create table to store validation results
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS validation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        finding_id INTEGER,
        validation_method TEXT,
        validation_result BOOLEAN,
        validation_details TEXT,
        validated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (finding_id) REFERENCES findings (id)
    )
    ''')

    # Create performance indices
    create_database_indices(cursor)

    # Set initial schema version
    cursor.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1)")
    
    conn.commit()
    conn.close()
    print("✅ Database setup complete.")
    print("   - findings table created")
    print("   - raw_data table created") 
    print("   - validation_log table created")
    print("   - performance indices created")

def create_database_indices(cursor):
    """Create performance indices for critical queries."""
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_findings_date_found ON findings(date_found)",
        "CREATE INDEX IF NOT EXISTS idx_findings_company ON findings(company)",
        "CREATE INDEX IF NOT EXISTS idx_findings_event_hash ON findings(event_hash)",
        "CREATE INDEX IF NOT EXISTS idx_findings_event_type ON findings(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_findings_created_at ON findings(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_raw_data_date_collected ON raw_data(date_collected)",
        "CREATE INDEX IF NOT EXISTS idx_raw_data_data_type ON raw_data(data_type)",
        "CREATE INDEX IF NOT EXISTS idx_validation_log_finding_id ON validation_log(finding_id)",
        "CREATE INDEX IF NOT EXISTS idx_validation_log_method ON validation_log(validation_method)"
    ]
    
    for index_sql in indices:
        cursor.execute(index_sql)

def run_migrations():
    """Run database migrations to update schema."""
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()
    
    # Get current version
    cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    result = cursor.fetchone()
    current_version = result[0] if result else 0
    
    # Define migrations
    migrations = [
        # Migration 1: Add indices (already handled in setup)
        # Migration 2: Add new columns if needed in future
    ]
    
    for i, migration in enumerate(migrations, start=current_version + 1):
        if i > current_version:
            try:
                # Execute migration
                cursor.execute(migration)
                # Update version
                cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (i,))
                print(f"✅ Applied migration {i}")
            except Exception as e:
                print(f"❌ Migration {i} failed: {e}")
                conn.rollback()
                break
    
    conn.commit()
    conn.close()

def reset_database():
    """Reset the database by dropping all tables and recreating them."""
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS findings")
    cursor.execute("DROP TABLE IF EXISTS raw_data")
    cursor.execute("DROP TABLE IF EXISTS validation_log")
    
    conn.commit()
    conn.close()
    
    print("🗑️  Database reset complete.")
    setup_database()

def check_database_status():
    """Check the current status of the database."""
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("📊 Database Status:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   - {table[0]}: {count} records")
    
    conn.close()

if __name__ == '__main__':
    setup_database()
    check_database_status() 