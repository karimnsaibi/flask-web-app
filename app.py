from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import re
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from email_utils import send_activation_email, send_email
from urllib.parse import quote
from datetime import datetime, timedelta


app = Flask(__name__)

# connect database
app.secret_key = 'tunisie_telecom_dashboard'

from routes.authentification import auth_bp
app.register_blueprint(auth_bp)

from routes.manage_sites import manage_site_bp
app.register_blueprint(manage_site_bp)

from routes.manage_site_codes import manage_site_codes_bp
app.register_blueprint(manage_site_codes_bp)

from routes.kpi_routes import kpi_bp
app.register_blueprint(kpi_bp)

from routes.interventions import interventions_bp
app.register_blueprint(interventions_bp)


if __name__ == '__main__':
    app.run(debug=True)
