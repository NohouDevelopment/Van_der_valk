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


def _lees_checkbox_anders(req, checkbox_naam: str, anders_naam: str) -> list:
    """Lees checkbox-lijst + anders-tekstveld, combineer tot één lijst."""
    selected = req.form.getlist(checkbox_naam)
    anders_raw = req.form.get(anders_naam, "")
    anders = [s.strip() for s in anders_raw.split(",") if s.strip()]
    return selected + anders


def _verwerk_approve_form(req, profiel: dict) -> dict:
    """Verwerk het goedkeuringsformulier (v2: drielaags profiel) en combineer met AI-voorstel."""
    result = dict(profiel)

    # --- Concept niveau ---
    restaurant_type = _lees_checkbox_anders(req, "restaurant_type_check", "restaurant_type_anders")
    culinaire_stijl = _lees_checkbox_anders(req, "culinaire_stijl_check", "culinaire_stijl_anders")
    prijssegment = req.form.get("prijssegment", profiel.get("prijssegment", "middensegment"))

    result["concept"] = {
        "restaurant_type": restaurant_type,
        "culinaire_stijl": culinaire_stijl,
        "prijssegment": prijssegment,
    }

    # --- Doelgroep met prioriteit ---
    doelgroep_primair = _lees_checkbox_anders(req, "doelgroep_primair_check", "doelgroep_primair_anders")
    doelgroep_secundair = _lees_checkbox_anders(req, "doelgroep_secundair_check", "doelgroep_secundair_anders")

    result["doelgroep_primair"] = doelgroep_primair
    result["doelgroep_secundair"] = doelgroep_secundair

    # --- F&B Propositie ---
    result["fb_propositie"] = _lees_checkbox_anders(req, "fb_propositie_check", "fb_propositie_anders")

    # --- Kaarten ---
    kaart_count = int(req.form.get("kaart_count", "0"))
    kaarten = []
    for i in range(kaart_count):
        kaart_type = req.form.get(f"kaart_type_{i}", "")
        if not kaart_type:
            continue
        kaart_label = req.form.get(f"kaart_label_{i}", kaart_type)
        kaart_rol = req.form.get(f"kaart_rol_{i}", "aanvullend")
        kaart_kenmerken = req.form.getlist(f"kaart_kenmerken_{i}")
        kaart_anders_raw = req.form.get(f"kaart_kenmerken_anders_{i}", "")
        kaart_anders = [s.strip() for s in kaart_anders_raw.split(",") if s.strip()]
        kaart_notitie = req.form.get(f"kaart_notitie_{i}", "").strip()[:200]

        kaarten.append({
            "type": kaart_type,
            "label": kaart_label,
            "rol": kaart_rol,
            "kenmerken": kaart_kenmerken + kaart_anders,
            "notitie": kaart_notitie,
        })

    result["kaarten"] = kaarten

    # --- Waardepropositie ---
    result["waardepropositie"] = req.form.get("waardepropositie", profiel.get("waardepropositie", "")).strip()

    # --- Backward compatibility: compute top-level keys ---
    result["restaurant_type"] = restaurant_type
    result["culinaire_stijl"] = culinaire_stijl
    result["prijssegment"] = prijssegment
    result["doelgroep"] = doelgroep_primair + doelgroep_secundair
    result["menu_kenmerken"] = list(set(
        k for kaart in kaarten for k in kaart.get("kenmerken", [])
    ))

    # Schema versie markeren
    result["_schema_versie"] = 2

    return result


def _migrate_v1_to_v2(profiel: dict) -> dict:
    """Converteer oud plat format naar v2 drielaags format (voor display, niet persistent tot save)."""
    if profiel.get("_schema_versie", 0) >= 2:
        return profiel

    migrated = dict(profiel)

    # Concept niveau
    migrated["concept"] = {
        "restaurant_type": profiel.get("restaurant_type", []),
        "culinaire_stijl": profiel.get("culinaire_stijl", []),
        "prijssegment": profiel.get("prijssegment", "middensegment"),
    }

    # Doelgroep: eerste 2 → primair, rest → secundair
    dg = profiel.get("doelgroep", [])
    migrated["doelgroep_primair"] = dg[:2] if len(dg) >= 2 else dg
    migrated["doelgroep_secundair"] = dg[2:] if len(dg) > 2 else []

    # F&B propositie: infer uit menu_kenmerken
    mk = profiel.get("menu_kenmerken", [])
    fb = []
    if "seizoensgebonden" in mk:
        fb.append("seizoensgebonden")
    if "diner" in mk:
        fb.append("dinner_driven")
    if "ontbijt" in mk:
        fb.append("ontbijt_inclusief")
    if "kindermenu" in mk:
        fb.append("family_friendly")
    if "duurzaam" in mk or "biologisch" in mk:
        fb.append("duurzaam_concept")
    migrated["fb_propositie"] = fb

    # Kaarten: infer uit menu_kenmerken
    kenmerk_to_card = {
        "diner": ("dinerkaart", "Dinerkaart", "leidend"),
        "ontbijt": ("ontbijtbuffet", "Ontbijtbuffet", "ondersteunend"),
        "lunch": ("lunchkaart", "Lunchkaart", "ondersteunend"),
        "kindermenu": ("kindermenu", "Kindermenu", "aanvullend"),
        "high tea": ("high_tea", "High Tea", "aanvullend"),
        "bar snacks": ("borrelkaart", "Borrelkaart / Bites", "aanvullend"),
    }
    kaart_level = {"a la carte", "buffet", "dagmenu", "proeverijmenu", "kindermenu",
                   "ontbijt", "lunch", "diner", "high tea", "bar snacks"}
    concept_kenmerken = [k for k in mk if k not in kaart_level]

    kaarten = []
    for mk_key, (ctype, clabel, crol) in kenmerk_to_card.items():
        if mk_key in mk:
            kaarten.append({
                "type": ctype, "label": clabel, "rol": crol,
                "kenmerken": list(concept_kenmerken), "notitie": "",
            })

    if not kaarten:
        kaarten.append({
            "type": "dinerkaart", "label": "Dinerkaart", "rol": "leidend",
            "kenmerken": list(concept_kenmerken), "notitie": "",
        })

    migrated["kaarten"] = kaarten
    migrated["_schema_versie"] = 2
    return migrated


def _hernoem_logo(oud_pad: str, org_id: int):
    """Hernoem logo van placeholder (id=0) naar definitieve org_id."""
    oud = Path(__file__).parent / oud_pad
    if oud.exists():
        nieuw = oud.parent / f"{org_id}{oud.suffix}"
        try:
            oud.rename(nieuw)
        except Exception:
            pass
