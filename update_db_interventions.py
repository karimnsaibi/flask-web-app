import sqlite3
import os

def update_db():
    if not os.path.exists('your_database.db'):
        print("Database not found. Initializing new DB...")
        import init_db
        init_db.init_db()
        return

    conn = sqlite3.connect('your_database.db')
    cur = conn.cursor()
    
    # Create tickets table
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            engineer_id INTEGER NOT NULL,
            technician_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES site(id),
            FOREIGN KEY(engineer_id) REFERENCES users(id),
            FOREIGN KEY(technician_id) REFERENCES users(id)
        )''')
        print("Tickets table created/verified.")
    except Exception as e:
        print(f"Error creating tickets table: {e}")

    # Create interventions table
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            technician_id INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Completed',
            engineer_rating INTEGER,
            engineer_comment TEXT,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id),
            FOREIGN KEY(technician_id) REFERENCES users(id)
        )''')
        print("Interventions table created/verified.")
    except Exception as e:
        print(f"Error creating interventions table: {e}")
        
    conn.commit()
    conn.close()
    print("Database schema update complete.")

if __name__ == '__main__':
    update_db()
