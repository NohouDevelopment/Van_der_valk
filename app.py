"""
Menu Maker Web App

Start de app:
    pip install flask flask-sqlalchemy flask-login flask-dotenv google-genai requests beautifulsoup4 PyMuPDF Pillow
    python app.py

Open dan: http://localhost:5000
"""

import os
import sys
import secrets
from pathlib import Path

# Windows fix: forceer UTF-8 output
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from flask import Flask, render_template, redirect, url_for, jsonify, abort, send_from_directory
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from models import db, Gebruiker, Organisatie, Menu, MenuSegment, TrendAnalyse, TrendGeheugen, MenuAnnotatie

BASE_DIR = Path(__file__).parent

# --- App initialisatie ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'menu_maker.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
db.init_app(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Log in om deze pagina te bekijken."


@login_manager.user_loader
def load_user(user_id):
    return Gebruiker.query.get(int(user_id))


# --- Blueprints registreren ---
from auth import auth_bp
from onboarding import onboarding_bp
from segment_routes import segment_bp
from menu_routes import menu_bp
from trend_routes import trend_bp
from ingredient_routes import ingredient_bp
from kassaboek_routes import kassaboek_bp

app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(segment_bp)
app.register_blueprint(menu_bp)
app.register_blueprint(trend_bp)
app.register_blueprint(ingredient_bp)
app.register_blueprint(kassaboek_bp)


# --- Statische bestanden: logo's ---
@app.route("/data/logos/<pad>")
@login_required
def serve_logo(pad):
    logos_dir = BASE_DIR / "data" / "logos"
    return send_from_directory(logos_dir, pad)


# --- Routes ---
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth.login"))


@app.route("/dashboard")
@login_required
def dashboard():
    org = current_user.organisatie

    # Aantal menu's
    menu_count = Menu.query.filter_by(organisatie_id=org.id).count()
    actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()

    # Menusegment aanwezig?
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()

    # Trendgeheugen
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()
    trend_count = TrendAnalyse.query.filter_by(organisatie_id=org.id).count()

    # Trend actief/afgeschreven counts
    trend_actief = 0
    trend_afgeschreven = 0
    if geheugen and geheugen.data:
        trends = geheugen.data if isinstance(geheugen.data, list) else geheugen.data.get("trends", [])
        for t in trends:
            status = t.get("status", "")
            if status in ("actief", "bevestigd", "nieuw", "verouderd"):
                trend_actief += 1
            elif status in ("verlopen", "afgeschreven"):
                trend_afgeschreven += 1

    # Annotatie badge counts voor actief menu
    annotatie_counts = {"HOUDEN": 0, "AANPASSEN": 0, "VERVANGEN": 0}
    if actief_menu:
        rows = db.session.query(MenuAnnotatie.status, db.func.count()).filter_by(
            menu_id=actief_menu.id
        ).group_by(MenuAnnotatie.status).all()
        for status, count in rows:
            if status and status.upper() in annotatie_counts:
                annotatie_counts[status.upper()] = count

    # Segment klant_segment tags
    klant_segmenten = []
    if segment and segment.data:
        ks = segment.data.get("klant_segment", [])
        if isinstance(ks, list):
            klant_segmenten = [k.upper() for k in ks]
        elif isinstance(ks, str):
            klant_segmenten = [k.strip().upper() for k in ks.split(",") if k.strip()]

    return render_template("dashboard.html",
                           org=org,
                           menu_count=menu_count,
                           actief_menu=actief_menu,
                           segment=segment,
                           geheugen=geheugen,
                           trend_count=trend_count,
                           trend_actief=trend_actief,
                           trend_afgeschreven=trend_afgeschreven,
                           annotatie_counts=annotatie_counts,
                           klant_segmenten=klant_segmenten,
                           is_admin=_is_admin())


# --- Admin panel ---
def _is_admin():
    admin_email = os.getenv("ADMIN_EMAIL", "").lower()
    if not admin_email or not current_user.is_authenticated:
        return False
    return current_user.email.lower() == admin_email


@app.route("/admin")
@login_required
def admin_panel():
    if not _is_admin():
        abort(403)
    orgs = Organisatie.query.order_by(Organisatie.aangemaakt_op.desc()).all()
    return render_template("admin.html", orgs=orgs)


@app.route("/admin/kassaboek/toggle/<int:org_id>", methods=["POST"])
@login_required
def admin_kassaboek_toggle(org_id):
    if not _is_admin():
        abort(403)
    org = Organisatie.query.get_or_404(org_id)
    org.kassaboek_actief = not org.kassaboek_actief
    if org.kassaboek_actief and not org.webhook_api_key:
        org.webhook_api_key = secrets.token_hex(32)
    db.session.commit()
    return redirect(url_for("admin_panel"))


# --- Health check ---
@app.route("/status")
@login_required
def status():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    return jsonify({
        "status": "ok",
        "openrouter_api_key": "aanwezig" if api_key else "ontbreekt",
    })


# --- Database initialiseren bij eerste start ---
with app.app_context():
    db.create_all()


# --- Error handlers ---
@app.errorhandler(404)
def niet_gevonden(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def geen_toegang(e):
    return render_template("403.html"), 403


@app.errorhandler(500)
def server_fout(e):
    return render_template("500.html"), 500


# --- Security headers ---
@app.after_request
def beveiligings_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


if __name__ == "__main__":
    # DEV ONLY — voor productie: python run.py
    print("=" * 50)
    print("  Menu Maker App (dev mode)")
    print("  http://localhost:5001")
    print("=" * 50)

    if not os.getenv("OPENROUTER_API_KEY"):
        print("\n!  OPENROUTER_API_KEY niet gevonden in .env!")
        print("   Zet de key in .env: OPENROUTER_API_KEY=jouw_key\n")

    if not os.getenv("SECRET_KEY"):
        print("!  Tip: zet SECRET_KEY in .env voor stabiele sessies over restarts")

    app.run(debug=True, host="localhost", port=5001)
