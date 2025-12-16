import sqlite3
import random
from datetime import datetime, timedelta

def generate_data():
    conn = sqlite3.connect('your_database.db')
    cur = conn.cursor()

    # 1. Create Sites
    sites = [
        ('Tunis', 'TUN001', 'Carthage', 'Site Carthage', '36.85', '10.33', '30', 'Huawei', 'Easy', 'Omni', 'Roof'),
        ('Ariana', 'ARI001', 'Ennasr', 'Site Ennasr', '36.87', '10.16', '25', 'Ericsson', 'Easy', 'Sector', 'Tower'),
        ('Sousse', 'SOU001', 'Kantaoui', 'Site Kantaoui', '35.89', '10.59', '40', 'Nokia', 'Hard', 'Sector', 'Roof'),
    ]

    print("Adding dummy sites...")
    slugs = []
    for s in sites:
        try:
            cur.execute('''
                INSERT INTO site (region, code, delegation, site_name, x, y, hba, supplier, access, antenna, surface)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', s)
            slugs.append(cur.lastrowid)
        except sqlite3.IntegrityError:
            print(f"Site {s[1]} already exists, skipping.")
            # Get id if exists
            cur.execute('SELECT id FROM site WHERE code = ?', (s[1],))
            slugs.append(cur.fetchone()[0])
            
    conn.commit()

    # 2. Generate KPIs for last 30 days
    print("Generating KPI data...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    for site_id in slugs:
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Random realistic values
            taux_blocage = round(random.uniform(0.1, 2.0), 2)
            taux_coupure = round(random.uniform(0.1, 1.5), 2)
            taux_disponibilite = round(random.uniform(99.0, 100.0), 2)
            trafic_voix = round(random.uniform(10, 100), 2)
            trafic_data = round(random.uniform(50, 500), 2)
            trafic_volte = round(random.uniform(20, 200), 2)
            
            # Introduce some "incidents"
            if random.random() < 0.1:
                taux_blocage = round(random.uniform(5.0, 15.0), 2)
                taux_disponibilite = round(random.uniform(90.0, 98.0), 2)

            cur.execute('''
                INSERT INTO kpi_stats (site_id, date, taux_blocage, taux_coupure, taux_disponibilite, 
                                     trafic_voix_erlang, trafic_data_go, trafic_volte_go)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (site_id, date_str, taux_blocage, taux_coupure, taux_disponibilite, trafic_voix, trafic_data, trafic_volte))
            
            current_date += timedelta(days=1)

    conn.commit()
    conn.close()
    print("Dummy data successfully generated!")

if __name__ == '__main__':
    generate_data()
