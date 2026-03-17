"""
Menu Maker Web App

Start de app:
    pip install -r requirements.txt
    python app.py

Open dan: http://localhost:5001
"""

import os
import sys
import logging
import secrets
from pathlib import Path

# Windows fix: forceer UTF-8 output
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# --- Logging ---
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

from flask import Flask, render_template, redirect, url_for, jsonify, abort, send_from_directory, request
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_session import Session
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from models import db, Gebruiker, Organisatie, Menu, MenuSegment, TrendAnalyse, TrendGeheugen, MenuAnnotatie, VoorstelSessie

BASE_DIR = Path(__file__).parent

# --- SECRET_KEY enforcement ---
_secret_key = os.getenv("SECRET_KEY", "")
if not _secret_key:
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("GUNICORN_CMD_ARGS"):
        raise RuntimeError("SECRET_KEY moet gezet zijn in productie! Voeg toe aan .env of platform secrets.")
    _secret_key = os.urandom(24).hex()
    logger.warning("Geen SECRET_KEY in .env — random key gegenereerd (sessies overleven geen restart)")

# --- App initialisatie ---
app = Flask(__name__)
app.secret_key = _secret_key
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["POSTHOG_API_KEY"] = os.getenv("POSTHOG_API_KEY", "")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
Session(app)

# --- Database: dual support (PostgreSQL via DATABASE_URL, fallback SQLite) ---
_db_url = os.getenv("DATABASE_URL", "")
if _db_url:
    # Railway / Heroku: postgres:// → postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
    logger.info("Database: PostgreSQL (DATABASE_URL)")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'menu_maker.db'}"
    logger.info("Database: SQLite (menu_maker.db)")

db.init_app(app)

# --- Flask-Migrate ---
migrate = Migrate(app, db)

# --- CSRF Protection ---
csrf = CSRFProtect(app)

# --- Rate Limiting ---
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Log in om deze pagina te bekijken."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Gebruiker, int(user_id))


# --- Blueprints registreren ---
from auth import auth_bp
from onboarding import onboarding_bp
from segment_routes import segment_bp
from menu_routes import menu_bp
from trend_routes import trend_bp
from ingredient_routes import ingredient_bp
from kassaboek_routes import kassaboek_bp
from voorstel_routes import voorstel_bp

app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(segment_bp)
app.register_blueprint(menu_bp)
app.register_blueprint(trend_bp)
app.register_blueprint(ingredient_bp)
app.register_blueprint(kassaboek_bp)
app.register_blueprint(voorstel_bp)

# --- CSRF exempt: kassaboek webhook routes (API key auth, niet session-based) ---
csrf.exempt(kassaboek_bp)

# --- Rate limits voor specifieke routes ---
limiter.limit("5 per minute")(auth_bp)
limiter.limit("10 per hour")(voorstel_bp)
limiter.limit("60 per minute")(kassaboek_bp)


# --- Statische bestanden: logo's (multi-tenant verified) ---
@app.route("/data/logos/<pad>")
@login_required
def serve_logo(pad):
    org = current_user.organisatie
    # Verify: logo pad moet bij de organisatie horen
    if org.logo_pad and pad not in org.logo_pad:
        abort(403)
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

    # TOEVOEGEN count uit menu.data
    toevoegen_count = len((actief_menu.data or {}).get("toevoegen_suggesties", [])) if actief_menu else 0

    # Segment klant_segment tags
    klant_segmenten = []
    if segment and segment.data:
        ks = segment.data.get("klant_segment", [])
        if isinstance(ks, list):
            klant_segmenten = [k.upper() for k in ks]
        elif isinstance(ks, str):
            klant_segmenten = [k.strip().upper() for k in ks.split(",") if k.strip()]

    # Recente voorstel sessies
    recente_sessies = VoorstelSessie.query.filter_by(
        organisatie_id=org.id
    ).order_by(VoorstelSessie.aangemaakt_op.desc()).limit(3).all()
    laatste_sessie = recente_sessies[0] if recente_sessies else None

    # Twee niveaus: bruikbaar vs optimaal
    basis_bruikbaar = bool(actief_menu and segment)

    # Marktinzichten actueel check
    from datetime import datetime, timezone, timedelta
    marktinzichten_actueel = False
    if geheugen and geheugen.laatst_bijgewerkt:
        try:
            verschil = datetime.now(timezone.utc) - geheugen.laatst_bijgewerkt.replace(tzinfo=timezone.utc)
            marktinzichten_actueel = verschil < timedelta(days=30)
        except Exception:
            marktinzichten_actueel = True

    geheugen_dagen_oud = 0
    if geheugen and geheugen.laatst_bijgewerkt:
        try:
            geheugen_dagen_oud = (datetime.now(timezone.utc) - geheugen.laatst_bijgewerkt.replace(tzinfo=timezone.utc)).days
        except Exception:
            pass

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
                           toevoegen_count=toevoegen_count,
                           klant_segmenten=klant_segmenten,
                           recente_sessies=recente_sessies,
                           laatste_sessie=laatste_sessie,
                           basis_bruikbaar=basis_bruikbaar,
                           marktinzichten_actueel=marktinzichten_actueel,
                           geheugen_dagen_oud=geheugen_dagen_oud,
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


@app.route("/admin/prompts")
@login_required
def admin_prompts():
    if not _is_admin():
        abort(403)
    from tools.prompt_loader import get_all_prompts
    prompts = get_all_prompts()
    selected_tool = request.args.get("tool", list(prompts.keys())[0] if prompts else "")
    return render_template("admin_prompts.html", prompts=prompts, selected_tool=selected_tool)


@app.route("/admin/prompts/save", methods=["POST"])
@login_required
def admin_prompts_save():
    if not _is_admin():
        abort(403)
    from tools.prompt_loader import save_prompt, reset_prompt
    tool = request.form.get("tool", "")
    name = request.form.get("name", "")
    action = request.form.get("action", "save")
    if not tool or not name:
        abort(400)
    if action == "reset":
        reset_prompt(tool, name)
    else:
        updates = {
            "model": request.form.get("model", ""),
            "temperature": float(request.form.get("temperature", 0.1)),
            "template": request.form.get("template", ""),
        }
        save_prompt(tool, name, updates)
    return redirect(url_for("admin_prompts") + f"?tool={tool}")


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


# --- Health check (public, no login required) ---
@app.route("/health")
@limiter.exempt
def health():
    status = {"status": "ok", "checks": {}}

    # DB connectivity
    try:
        db.session.execute(db.text("SELECT 1"))
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"fout: {str(e)[:100]}"
        status["status"] = "degraded"

    # API key aanwezig (geen echte AI call)
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    status["checks"]["openrouter_api_key"] = "aanwezig" if api_key else "ontbreekt"
    if not api_key:
        status["status"] = "degraded"

    http_code = 200 if status["status"] == "ok" else 503
    return jsonify(status), http_code


# --- Legacy status endpoint ---
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
    # Check of Flask-Migrate actief is (migrations/ dir aanwezig)
    migrations_dir = BASE_DIR / "migrations"
    if not migrations_dir.exists():
        # Dev bootstrap: create_all als er geen migrations zijn
        db.create_all()
        logger.info("Database tabellen aangemaakt via create_all (geen migrations/ dir)")
    else:
        logger.info("Flask-Migrate actief — gebruik 'flask db upgrade' voor migraties")


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


# --- Context processor: globale template variabelen ---
@app.context_processor
def inject_globals():
    """Injecteer actief_menu, is_admin en org in alle templates."""
    if not current_user.is_authenticated:
        return {}
    try:
        org = current_user.organisatie
        actief_menu = Menu.query.filter_by(
            organisatie_id=org.id, actief=True
        ).first() if org else None
        return {
            "org": org,
            "actief_menu": actief_menu,
            "is_admin": _is_admin(),
            "posthog_key": app.config.get("POSTHOG_API_KEY", ""),
        }
    except Exception:
        return {}


# --- Jinja2 filter: Nederlandse datum ---
_NL_MAANDEN = ["", "januari", "februari", "maart", "april", "mei", "juni",
               "juli", "augustus", "september", "oktober", "november", "december"]

@app.template_filter("nl_datum")
def nl_datum_filter(dt):
    if not dt:
        return "—"
    return f"{dt.day} {_NL_MAANDEN[dt.month]} {dt.year}"


# --- Security headers ---
@app.after_request
def beveiligings_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not app.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- Rate limits voor specifieke routes ---
@app.before_request
def _apply_rate_limits():
    """Rate limits worden per-route ingesteld via decorators op blueprints."""
    pass


if __name__ == "__main__":
    # DEV ONLY — voor productie: python run.py
    logger.info("=" * 50)
    logger.info("  Menu Maker App (dev mode)")
    logger.info("  http://localhost:5001")
    logger.info("=" * 50)

    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("OPENROUTER_API_KEY niet gevonden in .env!")

    if not os.getenv("SECRET_KEY"):
        logger.info("Tip: zet SECRET_KEY in .env voor stabiele sessies over restarts")

    app.run(debug=True, host="localhost", port=5001)
