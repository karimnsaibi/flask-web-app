import sqlite3
import os

def get_db_connection():
    # Use absolute path to ensure database is found regardless of CWD
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'your_database.db')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
