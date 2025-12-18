import sqlite3
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def generate_data():
    conn = sqlite3.connect('your_database.db')
    cur = conn.cursor()

    # --- 1. ENSURE USERS EXIST ---
    print("Checking users...")
    users = [
        ('Engineer One', 'ing1', 'engineer', 'admin123'),
        ('Engineer Two', 'ing2', 'engineer', 'admin123'),
        ('Tech Alice', 'tech1', 'technician', 'admin123'),
        ('Tech Bob', 'tech2', 'technician', 'admin123'),
        ('Tech Charlie', 'tech3', 'technician', 'admin123'),
        ('Admin User', 'admin', 'administrator', 'admin123')
    ]
    
    user_ids = {} # map profile -> list of ids
    
    for name, uid, profile, pwd in users:
        try:
            cur.execute('INSERT INTO users (name, user_id, profile, password) VALUES (?, ?, ?, ?)',
                        (name, uid, profile, generate_password_hash(pwd)))
            print(f"Created user {name}")
        except sqlite3.IntegrityError:
            print(f"User {name} exists.")
            
    # Fetch user IDs for linking
    cur.execute("SELECT id, profile FROM users")
    db_users = cur.fetchall()
    tech_ids = [r[0] for r in db_users if r[1] == 'technician']
    eng_ids = [r[0] for r in db_users if r[1] == 'engineer']
    
    if not tech_ids or not eng_ids:
        print("Error: Need at least one technician and one engineer.")
        return

    # --- 2. ENSURE SITES EXIST ---
    print("Checking sites...")
    # (Same site generation logic as before, ensuring we have some sites)
    sites_data = [
        ('Tunis', 'TUN001', 'Carthage', 'Site Carthage', '36.85', '10.33', '30', 'Huawei', 'Easy', 'Omni', 'Roof'),
        ('Ariana', 'ARI001', 'Ennasr', 'Site Ennasr', '36.87', '10.16', '25', 'Ericsson', 'Easy', 'Sector', 'Tower'),
        ('Sousse', 'SOU001', 'Kantaoui', 'Site Kantaoui', '35.89', '10.59', '40', 'Nokia', 'Hard', 'Sector', 'Roof'),
        ('Sfax', 'SFX010', 'Centre', 'Sfax Centre', '34.74', '10.76', '35', 'Huawei', 'Easy', 'Sector', 'Roof'),
        ('Bizerte', 'BIZ005', 'Corniche', 'Bizerte Nord', '37.27', '9.87', '28', 'Ericsson', 'Hard', 'Omni', 'Tower')
    ]
    
    site_ids = []
    
    for s in sites_data:
        try:
            cur.execute('INSERT INTO site (region, code, delegation, site_name, x, y, hba, supplier, access, antenna, surface) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', s)
            site_ids.append(cur.lastrowid)
        except sqlite3.IntegrityError:
            cur.execute('SELECT id FROM site WHERE code = ?', (s[1],))
            site_ids.append(cur.fetchone()[0])

    # --- 2.5 ENSURE SITE CODE POOLS EXIST ---
    print("Checking site code pools...")
    pools = [
        ('Tunis', 1000, 1099),
        ('Ariana', 2000, 2099),
        ('Ben Arous', 3000, 3099),
        ('Manouba', 4000, 4099),
        ('Nabeul', 5000, 5099),
        ('Zaghouan', 6000, 6099),
        ('Bizerte', 7000, 7099),
        ('Béja', 8000, 8099),
        ('Jendouba', 9000, 9099),
        ('Kef', 10000, 10099),
        ('Siliana', 11000, 11099),
        ('Sousse', 12000, 12099),
        ('Monastir', 13000, 13099),
        ('Mahdia', 14000, 14099),
        ('Sfax', 15000, 15099),
        ('Kairouan', 16000, 16099),
        ('Kasserine', 17000, 17099),
        ('Sidi Bouzid', 18000, 18099),
        ('Gabès', 19000, 19099),
        ('Medenine', 20000, 20099),
        ('Tataouine', 21000, 21099),
        ('Gafsa', 22000, 22099),
        ('Tozeur', 23000, 23099),
        ('Kebili', 24000, 24099)
    ]
    
    # clear existing pools to avoid duplicates/overlap issues for this dummy script
    cur.execute('DELETE FROM site_code_pools')
    
    for region, start, end in pools:
        cur.execute('INSERT INTO site_code_pools (region, start_code, end_code) VALUES (?, ?, ?)', (region, start, end))


    # --- 3. GENERATE TICKETS & INTERVENTIONS ---
    print("Generating Tickets and Interventions...")
    
    ticket_titles = [
        "Antenna Misalignment", "Power Failure Warning", "High Temperature Alarm", 
        "Transmission Link Down", "Low Throughput Investigation", "Routine Maintenance", 
        "Battery Replacement", "Feeder Cable Check", "VSWR Alarm", "Sector Outage"
    ]
    
    priorities = ['Low', 'Medium', 'High']
    statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
    
    # Generate ~20 tickets
    for _ in range(20):
        site_id = random.choice(site_ids)
        eng_id = random.choice(eng_ids)
        tech_id = random.choice(tech_ids)
        title = random.choice(ticket_titles)
        priority = random.choice(priorities)
        
        # Determine status distribution (more resolved/closed to show history)
        status = random.choices(statuses, weights=[10, 20, 30, 40], k=1)[0]
        
        created_date = datetime.now() - timedelta(days=random.randint(1, 60))
        created_at_str = created_date.strftime('%Y-%m-%d %H:%M:%S')

        cur.execute('''
            INSERT INTO tickets (site_id, engineer_id, technician_id, title, description, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (site_id, eng_id, tech_id, title, f"Investigation required for {title} at site.", priority, status, created_at_str))
        
        ticket_id = cur.lastrowid
        
        # If ticket is Resolved or Closed, add an Intervention
        if status in ['Resolved', 'Closed']:
            intervention_date = created_date + timedelta(hours=random.randint(2, 48))
            date_str = intervention_date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Engineer rating for Closed tickets
            rating = None
            comment = None
            if status == 'Closed':
                rating = random.randint(3, 5) # Mostly good ratings
                comment = random.choice(["Great job!", "Quick resolution.", "Good work.", "Issue fixed successfully."])
            
            cur.execute('''
                INSERT INTO interventions (ticket_id, technician_id, date, details, engineer_rating, engineer_comment)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticket_id, tech_id, date_str, f"Fixed the issue related to {title}. Replaced faulty component and tested.", rating, comment))

    conn.commit()
    conn.close()
    print("Dummy Tickets and Interventions generated!")

if __name__ == '__main__':
    generate_data()
