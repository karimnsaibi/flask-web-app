import os
import secrets

import db  # noqa: F401  (loads .env before anything reads environment variables)
from flask import Flask

app = Flask(__name__)

# Session signing key from .env; random fallback for local runs
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

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
