from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from db import get_db_connection
import sqlite3
from datetime import datetime

interventions_bp = Blueprint('interventions', __name__)

# --- ROUTES ---

@interventions_bp.route('/tickets', methods=['GET', 'POST'])
def manage_tickets():
    if 'profile' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    conn.row_factory = lambda cursor, row: dict(sqlite3.Row(cursor, row))
    
    if request.method == 'POST':
        # Create Ticket (Engineer only)
        if session['profile'] in ['engineer', 'administrator']:
            site_id = request.form['site_id']
            technician_id = request.form['technician_id']
            title = request.form['title']
            description = request.form['description']
            priority = request.form['priority']
            
            conn.execute('''
                INSERT INTO tickets (site_id, engineer_id, technician_id, title, description, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (site_id, session['user_id'], technician_id, title, description, priority))
            conn.commit()
            flash('Ticket created successfully', 'success')
        
    # Fetch Data for View
    # Technicians see tickets assigned to them
    # Engineers/Admins see all tickets
    
    query = '''
        SELECT t.*, s.site_name, s.code, u_eng.name as engineer_name, u_tech.name as technician_name
        FROM tickets t
        JOIN site s ON t.site_id = s.id
        JOIN users u_eng ON t.engineer_id = u_eng.id
        JOIN users u_tech ON t.technician_id = u_tech.id
    '''
    
    if session['profile'] == 'technician':
        # Get technician ID from session
        tech_id = session['user_id']
        query += f" WHERE t.technician_id = {tech_id}"

    query += " ORDER BY t.created_at DESC"
    
    tickets = conn.execute(query).fetchall()
    
    # Helper data for forms (Sites & Technicians)
    sites = conn.execute('SELECT id, site_name, code FROM site').fetchall()
    technicians = conn.execute("SELECT id, name FROM users WHERE profile = 'technician'").fetchall()
    
    conn.close()
    return render_template('manage_tickets.html', tickets=[dict(row) for row in tickets], sites=[dict(row) for row in sites], technicians=[dict(row) for row in technicians])


@interventions_bp.route('/interventions', methods=['GET', 'POST'])
def manage_interventions():
    if 'profile' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'log_work' and session['profile'] == 'technician':
            # Technician logging work
            ticket_id = request.form['ticket_id']
            details = request.form['details']
            
            # Get tech id
            tech_id = session['user_id']
            
            conn.execute('INSERT INTO interventions (ticket_id, technician_id, details) VALUES (?, ?, ?)',
                         (ticket_id, tech_id, details))
            
            # Close ticket
            conn.execute("UPDATE tickets SET status = 'Resolved' WHERE id = ?", (ticket_id,))
            conn.commit()
            flash('Intervention logged and ticket resolved.', 'success')
            
        elif action == 'rate_work' and session['profile'] in ['engineer', 'administrator']:
            # Engineer rating work
            intervention_id = request.form['intervention_id']
            rating = request.form['rating']
            comment = request.form['comment']
            
            conn.execute('UPDATE interventions SET engineer_rating = ?, engineer_comment = ? WHERE id = ?',
                         (rating, comment, intervention_id))
            
            # Verify if ticket should be Closed completely
            intervention = conn.execute('SELECT ticket_id FROM interventions WHERE id = ?', (intervention_id,)).fetchone()
            if intervention:
                 conn.execute("UPDATE tickets SET status = 'Closed' WHERE id = ?", (intervention[0],))
                 
            conn.commit()
            flash('Intervention rated successfully.', 'success')

    # Data Fetching
    # Technicians: See their assigned 'Open' tickets to work on, and their past interventions
    # Engineers: See completed interventions requiring review
    
    open_tickets = []
    completed_interventions = []
    
    if session['profile'] == 'technician':
        tech_id = session['user_id']
        open_tickets = conn.execute('''
            SELECT t.*, s.site_name, s.code, u_eng.name as engineer_name
            FROM tickets t
            JOIN site s ON t.site_id = s.id
            JOIN users u_eng ON t.engineer_id = u_eng.id
            WHERE t.technician_id = ? AND t.status IN ('Open', 'In Progress')
        ''', (tech_id,)).fetchall()
        
        completed_interventions = conn.execute('''
            SELECT i.*, t.title, s.site_name
            FROM interventions i
            JOIN tickets t ON i.ticket_id = t.id
            JOIN site s ON t.site_id = s.id
            WHERE i.technician_id = ?
            ORDER BY i.date DESC
        ''', (tech_id,)).fetchall()
            
    else: # Engineer/Admin
        completed_interventions = conn.execute('''
            SELECT i.*, t.title, s.site_name, u_tech.name as technician_name
            FROM interventions i
            JOIN tickets t ON i.ticket_id = t.id
            JOIN site s ON t.site_id = s.id
            JOIN users u_tech ON i.technician_id = u_tech.id
            ORDER BY i.date DESC
        ''').fetchall()

    conn.close()
    return render_template('manage_interventions.html', 
                           open_tickets=[dict(row) for row in open_tickets], 
                           interventions=[dict(row) for row in completed_interventions])


@interventions_bp.route('/dashboard_intervention')
def dashboard_intervention():
    if 'profile' not in session or session['profile'] not in ['administrator', 'engineer', 'manager']:
         flash('Access denied', 'error')
         return redirect(url_for('main'))
         
    return render_template('dashboard_interventions.html')

@interventions_bp.route('/api/intervention_stats')
def intervention_stats_api():
    conn = get_db_connection()
    
    # 1. Ticket Status Distribution
    status_counts = conn.execute('SELECT status, COUNT(*) as count FROM tickets GROUP BY status').fetchall()
    
    # 2. Top Performing Technicians (by Tickets Resolved)
    top_techs = conn.execute('''
        SELECT u.name, COUNT(i.id) as resolved_count, AVG(i.engineer_rating) as avg_rating
        FROM users u
        JOIN interventions i ON u.id = i.technician_id
        GROUP BY u.name
        ORDER BY resolved_count DESC
        LIMIT 5
    ''').fetchall()
    
    # 3. Tickets by Priority
    priority_counts = conn.execute('SELECT priority, COUNT(*) as count FROM tickets GROUP BY priority').fetchall()
    
    conn.close()
    
    return jsonify({
        'status_dist': [dict(row) for row in status_counts],
        'top_techs': [dict(row) for row in top_techs],
        'priority_dist': [dict(row) for row in priority_counts]
    })
