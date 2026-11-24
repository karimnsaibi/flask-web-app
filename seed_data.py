"""Fill the database with realistic demo data (all fictional).

- 11 users (3 engineers, 6 technicians, 1 administrator, 1 manager)
- 36 sites across 12 governorates, 3 suppliers
- 180 days of daily KPIs per site ending today, with weekly seasonality,
  traffic growth, VoLTE adoption and a few outage episodes
- tickets opened during outages and degradations, plus routine maintenance,
  with interventions and engineer ratings

Run after `python init_db.py`. Deterministic (fixed random seed).
"""
import math
import os
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from db import get_db_connection

random.seed(42)
DAYS = 180
TODAY = date.today()
START = TODAY - timedelta(days=DAYS - 1)

USERS = [
    ('Amine Ben Salem', 'eng1', 'engineer'),
    ('Sarra Trabelsi', 'eng2', 'engineer'),
    ('Walid Gharbi', 'eng3', 'engineer'),
    ('Hamza Jaziri', 'tech1', 'technician'),
    ('Nour Ayari', 'tech2', 'technician'),
    ('Bilel Saidi', 'tech3', 'technician'),
    ('Rania Hammami', 'tech4', 'technician'),
    ('Oussama Dridi', 'tech5', 'technician'),
    ('Ines Rezgui', 'tech6', 'technician'),
    ('Admin', 'admin', 'administrator'),
    ('Network Manager', 'manager', 'manager'),
]

# governorate: (lat, lon, code base, delegations)
GOVERNORATES = {
    'Tunis':     (36.81, 10.18, 1000, ['Carthage', 'La Marsa', 'Bab Bhar', 'El Menzah']),
    'Ariana':    (36.86, 10.19, 2000, ['Ennasr', 'Raoued', 'Soukra']),
    'Ben Arous': (36.75, 10.22, 3000, ['Rades', 'Megrine', 'Ezzahra']),
    'Nabeul':    (36.45, 10.73, 5000, ['Hammamet', 'Kelibia', 'Nabeul Ville']),
    'Bizerte':   (37.27, 9.87, 7000, ['Bizerte Nord', 'Menzel Bourguiba']),
    'Sousse':    (35.83, 10.64, 12000, ['Kantaoui', 'Sousse Medina', 'Msaken']),
    'Monastir':  (35.77, 10.83, 13000, ['Monastir Ville', 'Ksar Hellal']),
    'Sfax':      (34.74, 10.76, 15000, ['Sfax Centre', 'Sakiet Ezzit', 'Thyna']),
    'Kairouan':  (35.68, 10.10, 16000, ['Kairouan Nord', 'Haffouz']),
    'Gabès':     (33.88, 10.10, 19000, ['Gabès Ville', 'Mareth']),
    'Gafsa':     (34.43, 8.78, 22000, ['Gafsa Nord', 'Metlaoui']),
    'Kef':       (36.18, 8.71, 10000, ['Kef Est', 'Tajerouine']),
}
URBAN = {'Tunis', 'Ariana', 'Ben Arous', 'Sousse', 'Sfax'}
SUPPLIERS = {'Huawei': 0.45, 'Ericsson': 0.35, 'Nokia': 0.20}
# Small per-supplier quality offset, so benchmarking shows a real difference.
SUPPLIER_QUALITY = {'Huawei': 0.0, 'Ericsson': -0.05, 'Nokia': 0.25}

FAULTS = {
    'outage': ['Power Failure', 'Transmission Link Down', 'Sector Outage', 'Battery Failure'],
    'quality': ['VSWR Alarm', 'High Blocking Rate', 'Antenna Misalignment', 'Interference Investigation'],
    'routine': ['Routine Maintenance', 'Feeder Cable Check', 'Air Conditioning Check', 'Battery Replacement'],
}
COMMENTS = ['Quick resolution.', 'Good work.', 'Issue fixed, monitor next days.',
            'Root cause documented.', 'Took longer than expected.']


def weighted_choice(weights):
    return random.choices(list(weights), weights=list(weights.values()), k=1)[0]


def seed_users(conn):
    pw = generate_password_hash(os.getenv('DEMO_PASSWORD', 'demo1234'))
    ids = {}
    for name, uid, profile in USERS:
        row = conn.execute(
            'INSERT INTO users (name, user_id, email, profile, password) VALUES (?, ?, ?, ?, ?) RETURNING id',
            (name, uid, f'{uid}@example.com', profile, pw)).fetchone()
        ids.setdefault(profile, []).append(row['id'])
    return ids


def seed_sites(conn):
    sites = []
    for gov, (lat, lon, base, delegations) in GOVERNORATES.items():
        n_sites = 4 if gov in URBAN else 2
        conn.execute('INSERT INTO site_code_pools (region, start_code, end_code) VALUES (?, ?, ?)',
                     (gov, base, base + 99))
        for i in range(n_sites):
            delegation = delegations[i % len(delegations)]
            supplier = weighted_choice(SUPPLIERS)
            urban = gov in URBAN
            row = conn.execute('''
                INSERT INTO site (region, code, delegation, site_name, x, y, hba, supplier,
                                  access, antenna, surface)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id''', (
                gov, str(base + i + 1), delegation, f'{delegation} {i + 1:02d}',
                f'{lat + random.uniform(-0.06, 0.06):.4f}', f'{lon + random.uniform(-0.06, 0.06):.4f}',
                str(random.choice([18, 24, 30, 36, 42])), supplier,
                random.choice(['Easy', 'Easy', 'Hard']), 'Sector' if urban else random.choice(['Sector', 'Omni']),
                random.choice(['Roof', 'Tower']) if urban else 'Tower',
            )).fetchone()
            sites.append({
                'id': row['id'], 'supplier': supplier, 'urban': urban,
                'size': random.uniform(1.1, 1.8) if urban else random.uniform(0.5, 1.0),
                'quality': SUPPLIER_QUALITY[supplier] + random.uniform(-0.1, 0.2),
            })
    return sites


def plan_incidents(sites):
    """Random outage / degradation episodes: {(site_id, day_index): kind}."""
    incidents = {}
    episodes = []
    for s in sites:
        n = random.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0]
        if s['quality'] > 0.25:   # weaker sites fail more
            n += 1
        for _ in range(n):
            kind = random.choice(['outage', 'quality'])
            start = random.randint(0, DAYS - 3)
            length = random.randint(1, 2) if kind == 'outage' else random.randint(2, 5)
            for d in range(start, min(start + length, DAYS)):
                incidents[(s['id'], d)] = kind
            episodes.append((s['id'], start, kind))
    return incidents, episodes


def kpi_row(site, day_index, d, incident):
    growth = 1 + 0.25 * day_index / DAYS                  # data traffic grows ~25 %
    weekend = d.isoweekday() >= 6
    season = 1 + 0.08 * math.sin(2 * math.pi * day_index / 30)
    voice = site['size'] * random.gauss(85, 8) * (0.85 if weekend else 1.0) * season
    data = site['size'] * random.gauss(620, 50) * growth * (1.15 if weekend else 1.0) * season
    volte_share = 0.10 + 0.15 * day_index / DAYS          # VoLTE adoption 10 % -> 25 %
    volte = data * volte_share * random.uniform(0.9, 1.1)
    blocking = max(0.05, random.gauss(0.6, 0.2) + site['quality'])
    drop = max(0.03, random.gauss(0.35, 0.1) + site['quality'] / 2)
    availability = min(100.0, random.gauss(99.85, 0.1))

    if incident == 'outage':
        availability = random.uniform(70, 95)
        lost = availability / 100
        voice, data, volte = voice * lost, data * lost, volte * lost
        drop += random.uniform(1.0, 2.5)
    elif incident == 'quality':
        blocking += random.uniform(1.5, 4.0)
        drop += random.uniform(0.5, 1.2)
        availability = min(availability, random.uniform(98.2, 99.6))

    return (site['id'], d, round(blocking, 2), round(drop, 2), round(availability, 2),
            round(voice, 1), round(data, 1), round(volte, 1))


def seed_kpis(conn, sites, incidents):
    rows = []
    for s in sites:
        for i in range(DAYS):
            d = START + timedelta(days=i)
            rows.append(kpi_row(s, i, d, incidents.get((s['id'], i))))
    raw = conn._raw.cursor()
    raw.executemany('''
        INSERT INTO kpi_stats (site_id, date, taux_blocage, taux_coupure, taux_disponibilite,
                               trafic_voix_erlang, trafic_data_go, trafic_volte_go, logged_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::date + time '08:00')''',
        [r + (r[1],) for r in rows])
    return len(rows)


def add_ticket(conn, users, site_id, created, kind, priority):
    eng = random.choice(users['engineer'])
    tech = random.choice(users['technician'])
    title = random.choice(FAULTS[kind])
    age_days = (datetime.now() - created).days
    if age_days < 2:
        status = random.choice(['Open', 'In Progress'])
    elif age_days < 10:
        status = random.choices(['In Progress', 'Resolved', 'Closed'], weights=[15, 35, 50])[0]
    else:
        status = random.choices(['Resolved', 'Closed'], weights=[15, 85])[0]

    tid = conn.execute('''
        INSERT INTO tickets (site_id, engineer_id, technician_id, title, description, priority, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id''',
        (site_id, eng, tech, title, f'{title} reported on site. Investigation and fix required.',
         priority, status, created)).fetchone()['id']

    if status in ('Resolved', 'Closed'):
        base_hours = {'High': 6, 'Medium': 18, 'Low': 40}[priority]
        done = created + timedelta(hours=max(1.0, random.gauss(base_hours, base_hours / 3)))
        rating = random.choices([2, 3, 4, 5], weights=[5, 20, 45, 30])[0] if status == 'Closed' else None
        comment = random.choice(COMMENTS) if rating else None
        conn.execute('''
            INSERT INTO interventions (ticket_id, technician_id, date, details, engineer_rating, engineer_comment)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (tid, tech, min(done, datetime.now()), f'{title}: faulty component identified, replaced and tested.',
             rating, comment))


def seed_tickets(conn, users, sites, episodes):
    count = 0
    for site_id, start, kind in episodes:
        created = datetime.combine(START + timedelta(days=start), datetime.min.time()) \
            + timedelta(hours=random.randint(6, 20), minutes=random.randint(0, 59))
        add_ticket(conn, users, site_id, created, kind, 'High' if kind == 'outage' else 'Medium')
        count += 1
    for _ in range(len(sites) * 2):          # routine maintenance
        created = datetime.combine(START + timedelta(days=random.randint(0, DAYS - 1)), datetime.min.time()) \
            + timedelta(hours=random.randint(8, 16))
        add_ticket(conn, users, random.choice(sites)['id'], created, 'routine', 'Low')
        count += 1
    return count


def main():
    conn = get_db_connection()
    users = seed_users(conn)
    sites = seed_sites(conn)
    incidents, episodes = plan_incidents(sites)
    n_kpi = seed_kpis(conn, sites, incidents)
    n_tickets = seed_tickets(conn, users, sites, episodes)
    conn.commit()
    conn.close()
    print(f'Seeded {len(USERS)} users, {len(sites)} sites, {n_kpi} KPI rows '
          f'({START} -> {TODAY}), {n_tickets} tickets.')
    print("Demo logins: eng1 / tech1 / admin / manager, password = DEMO_PASSWORD (default 'demo1234').")


if __name__ == '__main__':
    main()
