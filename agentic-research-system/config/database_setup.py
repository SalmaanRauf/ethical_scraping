import sqlite3
import os
from datetime import datetime

def setup_database():
    """Creates the database and the findings table if they don't exist."""
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()
    print("✅ Database setup complete.")
    print("   - findings table created")
    print("   - raw_data table created") 
    print("   - validation_log table created")

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