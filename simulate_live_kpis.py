"""Demo helper: log today's KPIs for random sites every few seconds,
as engineers would through the app's KPI form. Leave it running next to
Power BI (DirectQuery + automatic page refresh) to watch the report update.

    python simulate_live_kpis.py            # every 5 s
    python simulate_live_kpis.py 2          # every 2 s
Stop with Ctrl+C.
"""
import random
import sys
import time
from datetime import date

from db import get_db_connection

UPSERT = '''
    INSERT INTO kpi_stats (site_id, date, taux_blocage, taux_coupure, taux_disponibilite,
                           trafic_voix_erlang, trafic_data_go, trafic_volte_go, logged_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
    ON CONFLICT (site_id, date) DO UPDATE SET
        taux_blocage = EXCLUDED.taux_blocage, taux_coupure = EXCLUDED.taux_coupure,
        taux_disponibilite = EXCLUDED.taux_disponibilite,
        trafic_voix_erlang = EXCLUDED.trafic_voix_erlang, trafic_data_go = EXCLUDED.trafic_data_go,
        trafic_volte_go = EXCLUDED.trafic_volte_go, logged_at = now()
'''


def main(interval):
    conn = get_db_connection()
    site_ids = [r['id'] for r in conn.execute('SELECT id FROM site').fetchall()]
    print(f'Logging KPIs for {len(site_ids)} sites every {interval}s. Ctrl+C to stop.')
    try:
        while True:
            site = random.choice(site_ids)
            degraded = random.random() < 0.15
            values = (
                site, date.today(),
                round(random.uniform(2.5, 5.0) if degraded else random.uniform(0.2, 1.2), 2),
                round(random.uniform(1.2, 2.5) if degraded else random.uniform(0.1, 0.6), 2),
                round(random.uniform(85, 97) if degraded else random.uniform(99.5, 100), 2),
                round(random.uniform(40, 160), 1),
                round(random.uniform(300, 1400), 1),
                round(random.uniform(40, 330), 1),
            )
            conn.execute(UPSERT, values)
            conn.commit()
            print(f'{time.strftime("%H:%M:%S")}  site {site:>3}  '
                  f'{"DEGRADED" if degraded else "normal  "}  availability {values[4]}%')
            time.sleep(interval)
    except KeyboardInterrupt:
        print('Stopped.')
    finally:
        conn.close()


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 5)
