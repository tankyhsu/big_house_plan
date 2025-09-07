#!/usr/bin/env python3
"""
Migration: Add scope_type and scope_data to signal table for extended scope support
"""
from __future__ import annotations


import sqlite3

def migrate_signal_scope(db_path: str):
    """Add scope_type and scope_data columns to signal table"""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Check if columns already exist
        cursor = conn.execute("PRAGMA table_info(signal)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'scope_type' not in columns:
            conn.execute("ALTER TABLE signal ADD COLUMN scope_type TEXT DEFAULT 'INSTRUMENT'")
            
        if 'scope_data' not in columns:
            conn.execute("ALTER TABLE signal ADD COLUMN scope_data TEXT")
            
        # Migrate existing data
        
        # Update scope_type based on existing data
        conn.execute("""
            UPDATE signal 
            SET scope_type = CASE 
                WHEN ts_code IS NOT NULL THEN 'INSTRUMENT'
                WHEN category_id IS NOT NULL THEN 'CATEGORY'
                ELSE 'INSTRUMENT'
            END
            WHERE scope_type = 'INSTRUMENT'
        """)
        
        # Set scope_data for single instrument/category signals
        conn.execute("""
            UPDATE signal 
            SET scope_data = json_array(ts_code)
            WHERE ts_code IS NOT NULL AND scope_data IS NULL
        """)
        
        conn.execute("""
            UPDATE signal 
            SET scope_data = json_array(category_id)
            WHERE category_id IS NOT NULL AND scope_data IS NULL
        """)
        
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    from ..services.config_svc import get_config
    
    config = get_config()
    db_path = config.get("db_path", "portfolio.db")
    
    print(f"Running signal scope migration on {db_path}")
    migrate_signal_scope(db_path)