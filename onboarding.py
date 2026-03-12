"""
Onboarding Blueprint — 4-staps registratieflow voor nieuwe organisaties.

Stap 1: /register           — Bedrijfsnaam en adres invoeren
Stap 2: /onboarding/scan    — AI scant bedrijf + logo extractie
Stap 3: /onboarding/approve — Menusegment voorstel bekijken & goedkeuren
Stap 4: /onboarding/gebruiker — Eerste gebruikersaccount aanmaken
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_user, current_user

sys.path.insert(0, str(Path(__file__).parent))

from models import db, Organisatie, Gebruiker, MenuSegment
from tools.segment_analyzer import analyze_segment
from tools.logo_extractor import extract_logo

onboarding_bp = Blueprint("onboarding", __name__)


@onboarding_bp.route("/register", methods=["GET", "POST"])
def register():
    """Stap 1: Bedrijfsnaam en adres invoeren."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None
    naam = ""
    adres = ""

    if request.method == "POST":
        naam = request.form.get("bedrijfsnaam", "").strip()
        adres = request.form.get("adres", "").strip()

        if not naam:
            error = "Vul een bedrijfsnaam in."
        else:
            # Sla tijdelijk op in session voor stap 2
            session["onboarding_naam"] = naam
            session["onboarding_adres"] = adres
            return redirect(url_for("onboarding.scan"))

    return render_template("register.html", error=error, naam=naam, adres=adres)


@onboarding_bp.route("/onboarding/scan", methods=["GET", "POST"])
def scan():
    """Stap 2: AI scant het bedrijf en genereert menusegment voorstel."""
    naam = session.get("onboarding_naam")
    adres = session.get("onboarding_adres")

    if not naam:
        return redirect(url_for("onboarding.register"))

    if request.method == "GET":
        # Toon loading pagina, die meteen een POST doet
        return render_template("onboarding_scan.html", naam=naam, adres=adres)

    # POST: voer AI scan uit
    error = None
    try:
        print(f"\n[Onboarding] Stap 2: AI scan voor '{naam}'")

        # Segment analyzer uitvoeren
        profiel = analyze_segment(naam, adres or naam)

        # Logo extractie (tijdelijk org_id=0 als placeholder)
        logo_pad = None
        try:
            logo_pad = extract_logo(naam, adres or naam, org_id=0)
        except Exception as e:
            print(f"  Logo extractie mislukt: {e}")

        # Sla profiel + logo op in session voor stap 3
        session["onboarding_profiel"] = profiel
        session["onboarding_logo_pad"] = logo_pad
        return redirect(url_for("onboarding.approve"))

    except Exception as e:
        import traceback
        error = f"Fout tijdens AI scan: {type(e).__name__}: {str(e)}"
        print(traceback.format_exc())
        return render_template("onboarding_scan.html", naam=naam, adres=adres, error=error)


@onboarding_bp.route("/onboarding/approve", methods=["GET", "POST"])
def approve():
    """Stap 3: Gebruiker keurt menusegment voorstel goed (of past het aan)."""
    profiel = session.get("onboarding_profiel")
    naam = session.get("onboarding_naam")
    adres = session.get("onboarding_adres")

    if not profiel or not naam:
        return redirect(url_for("onboarding.register"))

    if request.method == "GET":
        return render_template("onboarding_approve.html", profiel=profiel, naam=naam, adres=adres)

    # POST: verwerk aanpassingen
    profiel_data = _verwerk_approve_form(request, profiel)

    # Sla goedgekeurd profiel op in session
    session["onboarding_profiel_goedgekeurd"] = profiel_data
    return redirect(url_for("onboarding.maak_gebruiker"))


@onboarding_bp.route("/onboarding/gebruiker", methods=["GET", "POST"])
def maak_gebruiker():
    """Stap 4: Eerste gebruikersaccount aanmaken voor de organisatie."""
    profiel = session.get("onboarding_profiel_goedgekeurd")
    naam = session.get("onboarding_naam")
    adres = session.get("onboarding_adres")
    logo_pad = session.get("onboarding_logo_pad")

    if not profiel or not naam:
        return redirect(url_for("onboarding.register"))

    error = None

    if request.method == "POST":
        gebruiker_naam = request.form.get("naam", "").strip()
        email = request.form.get("email", "").strip().lower()
        wachtwoord = request.form.get("wachtwoord", "")
        wachtwoord2 = request.form.get("wachtwoord2", "")

        if not gebruiker_naam or not email or not wachtwoord:
            error = "Vul alle velden in."
        elif wachtwoord != wachtwoord2:
            error = "Wachtwoorden komen niet overeen."
        elif len(wachtwoord) < 8:
            error = "Wachtwoord moet minimaal 8 tekens zijn."
        elif Gebruiker.query.filter_by(email=email).first():
            error = "Dit e-mailadres is al in gebruik."
        else:
            # Maak organisatie aan
            org = Organisatie(
                naam=naam,
                adres=adres,
                logo_pad=logo_pad,
                beschrijving=profiel.get("sfeer", ""),
                status="actief"
            )
            db.session.add(org)
            db.session.flush()

            # Hernoem logo naar juiste org_id
            if logo_pad:
                _hernoem_logo(logo_pad, org.id)
                org.logo_pad = f"data/logos/{org.id}.png"

            # Maak eerste gebruiker aan (admin)
            gebruiker = Gebruiker(
                organisatie_id=org.id,
                naam=gebruiker_naam,
                email=email,
                rol="admin"
            )
            gebruiker.set_wachtwoord(wachtwoord)
            db.session.add(gebruiker)
            db.session.flush()

            # Sla menusegment op
            segment = MenuSegment(
                organisatie_id=org.id,
                data=profiel,
                goedgekeurd_door=gebruiker.id,
                goedgekeurd_op=datetime.now(timezone.utc)
            )
            db.session.add(segment)
            db.session.commit()

            # Sessie opruimen
            for key in ["onboarding_naam", "onboarding_adres", "onboarding_profiel",
                        "onboarding_profiel_goedgekeurd", "onboarding_logo_pad"]:
                session.pop(key, None)

            # Meteen inloggen
            login_user(gebruiker, remember=True)
            print(f"[Onboarding] Organisatie '{org.naam}' aangemaakt (id={org.id})")
            return redirect(url_for("dashboard"))

    return render_template("onboarding_gebruiker.html", error=error, naam=naam)


def _verwerk_approve_form(req, profiel: dict) -> dict:
    """Verwerk het goedkeuringsformulier en combineer met AI-voorstel."""
    # Restaurant type checkboxes + anders
    selected_types = req.form.getlist("restaurant_type_check")
    anders_type_raw = req.form.get("restaurant_type_anders", "")
    anders_types = [s.strip() for s in anders_type_raw.split(",") if s.strip()]
    restaurant_type = selected_types + anders_types

    # Culinaire stijl checkboxes + anders
    selected_stijl = req.form.getlist("culinaire_stijl_check")
    anders_stijl_raw = req.form.get("culinaire_stijl_anders", "")
    anders_stijl = [s.strip() for s in anders_stijl_raw.split(",") if s.strip()]
    culinaire_stijl = selected_stijl + anders_stijl

    # Doelgroep checkboxes + anders
    selected_doelgroep = req.form.getlist("doelgroep_check")
    anders_doelgroep_raw = req.form.get("doelgroep_anders", "")
    anders_doelgroep = [s.strip() for s in anders_doelgroep_raw.split(",") if s.strip()]
    doelgroep = selected_doelgroep + anders_doelgroep

    # Prijssegment (radio)
    prijssegment = req.form.get("prijssegment", profiel.get("prijssegment", "middensegment"))

    # Waardepropositie (textarea)
    waardepropositie = req.form.get("waardepropositie", profiel.get("waardepropositie", "")).strip()

    # Menu kenmerken checkboxes + anders
    selected_kenmerken = req.form.getlist("menu_kenmerken_check")
    anders_kenmerken_raw = req.form.get("menu_kenmerken_anders", "")
    anders_kenmerken = [s.strip() for s in anders_kenmerken_raw.split(",") if s.strip()]
    menu_kenmerken = selected_kenmerken + anders_kenmerken

    # Combineer met oorspronkelijk profiel
    result = dict(profiel)
    result["restaurant_type"] = restaurant_type
    result["culinaire_stijl"] = culinaire_stijl
    result["doelgroep"] = doelgroep
    result["prijssegment"] = prijssegment
    result["waardepropositie"] = waardepropositie
    result["menu_kenmerken"] = menu_kenmerken

    return result


def _hernoem_logo(oud_pad: str, org_id: int):
    """Hernoem logo van placeholder (id=0) naar definitieve org_id."""
    oud = Path(__file__).parent / oud_pad
    if oud.exists():
        nieuw = oud.parent / f"{org_id}{oud.suffix}"
        try:
            oud.rename(nieuw)
        except Exception:
            pass
