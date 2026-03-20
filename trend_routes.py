"""
Trend Blueprint — trendanalyse, configuratie en geheugen.

Routes:
  /trends/            — Overzicht: laatste analyse + geheugen status
  /trends/analyseer   — Loading page (GET) + run analysis (POST)
  /trends/config      — Configuratie met checkbox grids (GET/POST)
  /trends/geheugen    — Gedetailleerd geheugenview met alle actieve trends
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from models import db, MenuSegment, Menu, TrendAnalyse, TrendGeheugen, TrendConfig

trend_bp = Blueprint("trend", __name__)

# --- Vaste opties voor config checkbox-grids ---

CATEGORIE_OPTIES = [
    ("voorgerechten", "Voorgerechten"),
    ("soepen", "Soepen"),
    ("vis", "Vis & zeevruchten"),
    ("vegan_veg", "Vegan & vegetarisch"),
    ("vlees", "Vlees"),
    ("nagerechten", "Nagerechten & desserts"),
    ("dranken", "Dranken & cocktails"),
]

# Inspiratiebronnen in 4 groepen
INSPIRATIE_GROEPEN = [
    ("Chefs & Restaurants", [
        ("michelin", "Michelin-trends"),
        ("ottolenghi", "Ottolenghi"),
        ("ramsay", "Gordon Ramsay"),
        ("jamie_oliver", "Jamie Oliver"),
        ("noma", "Noma / René Redzepi"),
        ("bottura", "Massimo Bottura"),
        ("worlds_50_best", "World's 50 Best"),
        ("momofuku", "David Chang / Momofuku"),
    ]),
    ("Keukenstijlen", [
        ("streetfood", "Streetfood & food trucks"),
        ("asian_fusion", "Asian fusion"),
        ("nordic", "Nordic / Scandinavisch"),
        ("mediterranean", "Mediterraan"),
        ("koreaans", "Koreaans"),
        ("japans", "Japans / Omakase"),
        ("midden_oosten", "Midden-Oosters"),
        ("latijns", "Latijns-Amerikaans"),
    ]),
    ("Media & Platforms", [
        ("tiktok", "TikTok / Virale trends"),
        ("bon_appetit", "Bon Appétit / Food media"),
        ("culy", "Culy.nl / NL food media"),
    ]),
    ("Industrie & Research", [
        ("horeca_nl", "Horeca Nederland"),
        ("innova", "Innova Market Insights"),
        ("gault_millau", "GaultMillau / Culinaire gidsen"),
        ("neo_bistro", "Neo-bistro beweging"),
    ]),
]

# Platte lijst voor form-verwerking
INSPIRATIE_OPTIES = [(k, v) for _, items in INSPIRATIE_GROEPEN for k, v in items]

# Focusthema's in 3 groepen
FOCUS_GROEPEN = [
    ("Ingrediënten & Bereiding", [
        ("plantaardig", "Plantaardig / plant-based"),
        ("fermentatie", "Fermentatie & preservering"),
        ("seizoen", "Seizoensgebonden"),
        ("lokaal", "Lokaal & ambachtelijk"),
        ("premium", "Premium ingrediënten"),
        ("fusion", "Fusion & hybride"),
    ]),
    ("Beleving & Concept", [
        ("nostalgie", "Nostalgie / comfort food"),
        ("experience", "Experience dining"),
        ("social_media", "Social media & presentatie"),
        ("brunch", "Ontbijt & brunch"),
        ("mocktails", "Cocktails & mocktails"),
    ]),
    ("Duurzaamheid & Gezondheid", [
        ("duurzaamheid", "Duurzaamheid"),
        ("food_waste", "Food waste / zero waste"),
        ("allergiebewust", "Allergiebewust"),
        ("gezondheid", "Gezondheid & functioneel"),
        ("gen_z", "Gen Z food culture"),
    ]),
]

# Platte lijst voor form-verwerking
FOCUS_OPTIES = [(k, v) for _, items in FOCUS_GROEPEN for k, v in items]


def _get_default_config_data() -> dict:
    """Return sensible defaults voor TrendConfig."""
    return {
        "categorieen": {
            "voorgerechten": True,
            "soepen": True,
            "vis": True,
            "vegan_veg": True,
            "vlees": True,
            "nagerechten": True,
            "dranken": True
        },
        "inspiratiebronnen": [],
        "focusthemas": [],
        "custom_prompt": ""
    }


def _verwerk_config_form(req) -> dict:
    """Verwerk het config formulier naar een data dict."""
    # Categorie toggles (checkboxes)
    categorieen = {}
    checked = req.form.getlist("categorieen_check")
    for val, _ in CATEGORIE_OPTIES:
        categorieen[val] = val in checked

    # Inspiratiebronnen (checkboxes + anders)
    inspiratie = req.form.getlist("inspiratie_check")
    anders_inspiratie = req.form.get("inspiratie_anders", "").strip()
    if anders_inspiratie:
        for s in anders_inspiratie.split(","):
            s = s.strip()
            if s:
                inspiratie.append(s)

    # Focusthema's (checkboxes + anders)
    focus = req.form.getlist("focus_check")
    anders_focus = req.form.get("focus_anders", "").strip()
    if anders_focus:
        for s in anders_focus.split(","):
            s = s.strip()
            if s:
                focus.append(s)

    # Custom prompt
    custom_prompt = req.form.get("custom_prompt", "").strip()

    return {
        "categorieen": categorieen,
        "inspiratiebronnen": inspiratie,
        "focusthemas": focus,
        "custom_prompt": custom_prompt
    }


def _genereer_config_suggesties(config_data: dict, geheugen_data: dict) -> list:
    """Vergelijk config met trendgeheugen en genereer update-suggesties."""
    from tools.trend_researcher import FOCUS_LABELS

    suggesties = []
    focus = config_data.get("focusthemas", [])
    bekende_focus_keys = {k for k, _ in FOCUS_OPTIES}

    # Verzamel alle tags en beschrijvingen van actieve trends
    actieve_tags = set()
    actieve_beschrijvingen = ""
    for t in geheugen_data.get("trends", []):
        if t.get("status") == "actief":
            actieve_tags.update(tag.lower() for tag in t.get("tags", []))
            actieve_beschrijvingen += " " + t.get("beschrijving", "").lower()
            actieve_beschrijvingen += " " + t.get("naam", "").lower()

    # 1. Focusthema's die niet terugkomen in actieve trends → suggestie verwijderen
    for thema in focus:
        if thema not in bekende_focus_keys:
            continue  # Custom thema's overslaan
        thema_zoekwoorden = FOCUS_LABELS.get(thema, thema).lower().replace(",", "").split()
        # Check of minstens 1 zoekwoord voorkomt in tags of beschrijvingen
        match = any(
            woord in actieve_tags or woord in actieve_beschrijvingen
            for woord in thema_zoekwoorden if len(woord) > 3
        )
        if not match:
            suggesties.append({
                "type": "verwijder_focus",
                "key": thema,
                "label": dict(FOCUS_OPTIES).get(thema, thema),
                "reden": "Geen matching trends gevonden in actief geheugen"
            })

    # 2. Veel voorkomende tags die matchen met niet-geconfigureerde focusthema's → suggestie toevoegen
    tag_counts = {}
    for t in geheugen_data.get("trends", []):
        if t.get("status") == "actief":
            for tag in t.get("tags", []):
                tag_counts[tag.lower()] = tag_counts.get(tag.lower(), 0) + 1

    al_gesuggereerd = set()
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        if count < 2:
            break
        # Check of deze tag overeenkomt met een bekende focus optie die niet is geconfigureerd
        for key, label in FOCUS_OPTIES:
            if key in focus or key in al_gesuggereerd:
                continue
            focus_woorden = FOCUS_LABELS.get(key, "").lower()
            if tag in focus_woorden:
                suggesties.append({
                    "type": "voeg_focus_toe",
                    "key": key,
                    "label": label,
                    "reden": f"Komt {count}x voor in actieve trends"
                })
                al_gesuggereerd.add(key)

    return suggesties


# --- Routes ---

@trend_bp.route("/trends/")
@login_required
def trends_overzicht():
    """Overzichtspagina: laatste analyse + geheugen status."""
    org = current_user.organisatie
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()

    laatste_analyse = TrendAnalyse.query.filter_by(organisatie_id=org.id)\
        .order_by(TrendAnalyse.gegenereerd_op.desc()).first()
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()
    config = TrendConfig.query.filter_by(organisatie_id=org.id).first()

    return render_template("trends.html",
                           org=org,
                           segment=segment,
                           laatste_analyse=laatste_analyse,
                           geheugen=geheugen,
                           config=config)


@trend_bp.route("/trends/analyseer", methods=["GET", "POST"])
@login_required
def trends_analyseer():
    """Loading page (GET) + run analysis pipeline (POST)."""
    org = current_user.organisatie
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()

    if not segment:
        return redirect(url_for("trend.trends_overzicht"))

    if request.method == "GET":
        return render_template("trend_scan.html", org=org)

    # POST: voer de analyse pipeline uit
    try:
        from tools.trend_researcher import research_trends
        from tools.trend_combiner import combine_trends

        # Config ophalen (of defaults)
        config = TrendConfig.query.filter_by(organisatie_id=org.id).first()
        config_data = config.data if config else None

        # Actief menu ophalen (optioneel)
        actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()
        menu_data = actief_menu.data if actief_menu else None

        # Stap 1: Research trends
        analyse_resultaat = research_trends(segment.data, config_data, menu_data)

        # Stap 2: Versienummer bepalen
        vorige_count = TrendAnalyse.query.filter_by(organisatie_id=org.id).count()

        # Stap 3: TrendAnalyse opslaan
        analyse = TrendAnalyse(
            organisatie_id=org.id,
            gegenereerd_door=current_user.id,
            config_snapshot=config_data,
            data=analyse_resultaat,
            bronnen=analyse_resultaat.get("zoek_queries", []),
            versie=vorige_count + 1
        )
        db.session.add(analyse)

        # Stap 4: Combineer met bestaand geheugen
        bestaand_geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()
        bestaand_data = bestaand_geheugen.data if bestaand_geheugen else None

        nieuw_geheugen_data = combine_trends(analyse_resultaat, bestaand_data)

        if bestaand_geheugen:
            bestaand_geheugen.vorige_data = bestaand_geheugen.data
            bestaand_geheugen.data = nieuw_geheugen_data
            bestaand_geheugen.versie += 1
            bestaand_geheugen.laatst_bijgewerkt = datetime.now(timezone.utc)
        else:
            geheugen = TrendGeheugen(
                organisatie_id=org.id,
                data=nieuw_geheugen_data,
                versie=1
            )
            db.session.add(geheugen)

        # Stap 5: Config-suggesties genereren
        if config and config.data:
            suggesties = _genereer_config_suggesties(config.data, nieuw_geheugen_data)
            updated_config = dict(config.data)
            updated_config["suggesties"] = suggesties
            config.data = updated_config
            config.aangepast_op = datetime.now(timezone.utc)

        db.session.commit()
        print(f"[Trend] Analyse v{vorige_count + 1} opgeslagen voor {org.naam}")

        return redirect(url_for("trend.trends_overzicht"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout tijdens trendanalyse: {type(e).__name__}: {str(e)}"
        return render_template("trend_scan.html", org=org, error=error)


@trend_bp.route("/trends/config", methods=["GET", "POST"])
@login_required
def trends_config():
    """Configuratie pagina met checkbox-grids."""
    org = current_user.organisatie
    config = TrendConfig.query.filter_by(organisatie_id=org.id).first()

    if request.method == "POST":
        config_data = _verwerk_config_form(request)

        if config:
            config.data = config_data
            config.aangepast_op = datetime.now(timezone.utc)
        else:
            config = TrendConfig(
                organisatie_id=org.id,
                data=config_data
            )
            db.session.add(config)

        db.session.commit()
        return redirect(url_for("trend.trends_overzicht"))

    # GET: toon config form met huidige waarden of defaults
    config_data = config.data if config else _get_default_config_data()

    # Bereken "anders" waarden die niet in de vaste lijsten zitten
    bekende_inspiratie = {val for val, _ in INSPIRATIE_OPTIES}
    anders_inspiratie = [s for s in config_data.get("inspiratiebronnen", []) if s not in bekende_inspiratie]

    bekende_focus = {val for val, _ in FOCUS_OPTIES}
    anders_focus = [s for s in config_data.get("focusthemas", []) if s not in bekende_focus]

    return render_template("trend_config.html",
                           org=org,
                           config=config_data,
                           categorie_opties=CATEGORIE_OPTIES,
                           inspiratie_groepen=INSPIRATIE_GROEPEN,
                           inspiratie_opties=INSPIRATIE_OPTIES,
                           focus_groepen=FOCUS_GROEPEN,
                           focus_opties=FOCUS_OPTIES,
                           anders_inspiratie=", ".join(anders_inspiratie),
                           anders_focus=", ".join(anders_focus))


@trend_bp.route("/trends/geheugen")
@login_required
def trends_geheugen():
    """Gedetailleerd geheugenview met alle trends."""
    org = current_user.organisatie
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

    if not geheugen:
        return redirect(url_for("trend.trends_overzicht"))

    alle_trends = geheugen.data.get("trends", [])
    actieve_trends = [t for t in alle_trends if t.get("status") == "actief"]
    verouderde_trends = [t for t in alle_trends if t.get("status") == "verouderd"]
    verlopen_trends = [t for t in alle_trends if t.get("status") == "verlopen"]

    return render_template("trend_geheugen.html",
                           org=org,
                           geheugen=geheugen,
                           actieve_trends=actieve_trends,
                           verouderde_trends=verouderde_trends,
                           verlopen_trends=verlopen_trends)
