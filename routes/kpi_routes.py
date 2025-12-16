from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, session
from db import get_db_connection
import csv
import io

kpi_bp = Blueprint('kpi', __name__)

@kpi_bp.route('/bi')
def bi_dashboard():
    if 'profile' not in session or session['profile'] not in ['engineer', 'administrator']:
        flash('Access denied', 'error')
        return redirect(url_for('auth.login'))
    return render_template('bi_dashboard.html')

@kpi_bp.route('/kpi/add', methods=['GET', 'POST'])
def add_kpi():
    if 'profile' not in session or session['profile'] not in ['engineer', 'administrator']:
        flash('Access denied', 'error')
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        site_id = request.form['site_id']
        date = request.form['date']
        taux_blocage = request.form['taux_blocage']
        taux_coupure = request.form['taux_coupure']
        taux_disponibilite = request.form['taux_disponibilite']
        trafic_voix = request.form['trafic_voix']
        trafic_data = request.form['trafic_data']
        trafic_volte = request.form['trafic_volte']
        
        try:
            conn.execute('''
                INSERT INTO kpi_stats (site_id, date, taux_blocage, taux_coupure, taux_disponibilite, 
                                     trafic_voix_erlang, trafic_data_go, trafic_volte_go)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (site_id, date, taux_blocage, taux_coupure, taux_disponibilite, trafic_voix, trafic_data, trafic_volte))
            conn.commit()
            flash('KPI data logged successfully', 'success')
        except Exception as e:
            flash(f'Error logging data: {str(e)}', 'error')
        finally:
            conn.close()
        return redirect(url_for('kpi.add_kpi'))
    
    # Get list of sites for the dropdown
    sites = conn.execute('SELECT id, site_name, code FROM site').fetchall()
    conn.close()
    return render_template('kpi_entry.html', sites=sites)

@kpi_bp.route('/api/kpi_data')
def get_kpi_data():
    conn = get_db_connection()
    mode = request.args.get('mode', 'overview')
    
    if mode == 'operational':
        # Operational: Worst Offenders (Top 10 High Failure Rates) & Zero Traffic Sites
        # Get dates for context
        dates_row = conn.execute('SELECT DISTINCT date FROM kpi_stats ORDER BY date DESC LIMIT 1').fetchone()
        latest_date = dates_row['date'] if dates_row else None
        
        worst_offenders = []
        zero_traffic = []
        
        if latest_date:
            worst_offenders = conn.execute('''
                SELECT s.site_name, s.code, k.taux_blocage, k.taux_coupure
                FROM kpi_stats k
                JOIN site s ON k.site_id = s.id
                WHERE k.date = ?
                ORDER BY (k.taux_blocage + k.taux_coupure) DESC
                LIMIT 10
            ''', (latest_date,)).fetchall()
            
            zero_traffic = conn.execute('''
                SELECT s.site_name, s.code, k.taux_disponibilite
                FROM kpi_stats k
                JOIN site s ON k.site_id = s.id
                WHERE k.date = ? AND k.trafic_data_go = 0 AND k.trafic_voix_erlang = 0
                AND k.taux_disponibilite < 100
                LIMIT 10
            ''', (latest_date,)).fetchall()

        result = {
            'mode': 'operational',
            'latest_date': latest_date,
            'worst_offenders': [dict(row) for row in worst_offenders],
            'zero_traffic': [dict(row) for row in zero_traffic]
        }
    
    elif mode == 'tactical':
        # Tactical: Supplier Benchmarking & Congestion Analysis
        # 1. Supplier Performance (Avg Availability by Supplier)
        supplier_stats = conn.execute('''
            SELECT s.supplier, AVG(k.taux_disponibilite) as avg_dispo, AVG(k.taux_coupure) as avg_coupure
            FROM kpi_stats k
            JOIN site s ON k.site_id = s.id
            GROUP BY s.supplier
        ''').fetchall()
        
        # 2. Traffic vs Blocking Correlation (Congestion)
        # Get data points for scatter plot
        congestion_data = conn.execute('''
            SELECT k.trafic_data_go, k.taux_blocage
            FROM kpi_stats k
            WHERE k.trafic_data_go > 0
            LIMIT 100
        ''').fetchall()

        result = {
            'mode': 'tactical',
            'suppliers': [dict(row) for row in supplier_stats],
            'congestion': [{'x': row['trafic_data_go'], 'y': row['taux_blocage']} for row in congestion_data]
        }

    elif mode == 'strategic':
        # Strategic: Long-term trends (already covered partially by overview but split by voice/data)
        trend_data = conn.execute('''
            SELECT date, 
                   SUM(trafic_data_go) as total_data,
                   SUM(trafic_voix_erlang) as total_voice
            FROM kpi_stats
            GROUP BY date
            ORDER BY date
        ''').fetchall()
        
        result = {
            'mode': 'strategic',
            'dates': [row['date'] for row in trend_data],
            'data_traffic': [row['total_data'] for row in trend_data],
            'voice_traffic': [row['total_voice'] for row in trend_data]
        }

    else:
        # Default Overview (aggregated stats)
        data = conn.execute('''
            SELECT date, 
                   AVG(taux_blocage) as avg_blocage,
                   AVG(taux_coupure) as avg_coupure,
                   AVG(taux_disponibilite) as avg_dispo,
                   SUM(trafic_data_go) as total_data
            FROM kpi_stats
            GROUP BY date
            ORDER BY date
        ''').fetchall()
        
        result = {
            'mode': 'overview',
            'dates': [row['date'] for row in data],
            'blocage': [row['avg_blocage'] for row in data],
            'coupure': [row['avg_coupure'] for row in data],
            'dispo': [row['avg_dispo'] for row in data],
            'data': [row['total_data'] for row in data]
        }
    
    conn.close()
    return jsonify(result)

@kpi_bp.route('/download/powerbi_data')
def download_powerbi_data():
    conn = get_db_connection()
    # Join with site table to give full context for PowerBI
    rows = conn.execute('''
        SELECT s.region, s.delegation, s.code, s.site_name, k.*
        FROM kpi_stats k
        JOIN site s ON k.site_id = s.id
    ''').fetchall()
    conn.close()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys()) # Header
        for row in rows:
            writer.writerow(list(row))
            
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=powerbi_data.csv"}
    )
