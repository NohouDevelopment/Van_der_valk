"""
Kassaboek Blueprint — per-gerecht verkoopcijfers, webhook en bulk upload.

Routes:
    POST /kassaboek/webhook    — API key auth, accepteert {datum, omzet, couverts, gerechten:[{naam,aantal,omzet}]}
    POST /kassaboek/bulk       — bulk upload, max 365 entries
    GET  /kassaboek/verkoop    — JSON: populairste + trending gerechten (fuzzy-gekoppeld aan menu)
    GET  /kassaboek/seizoen    — JSON: seizoenspatronen per gerecht (per maand + weekdag)
    GET  /kassaboek/overzicht  — HTML pagina met API key + cURL voorbeeld
"""

import hmac
import difflib
from datetime import date, timedelta
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, Organisatie, KassaboekEntry, Gerecht, Menu

kassaboek_bp = Blueprint("kassaboek", __name__)


def _fuzzy_match_gerecht(naam: str, gerechten: list) -> "Gerecht | None":
    """
    Koppel een kassaboek gerecht_naam aan een Gerecht-object via fuzzy matching.
    Zelfde strategie als menu_annotator: exact lowercase → substring → difflib (threshold 0.75).
    """
    if not naam or not gerechten:
        return None
    naam_lower = naam.lower().strip()
    # 1. Exacte match
    for g in gerechten:
        if g.naam.lower().strip() == naam_lower:
            return g
    # 2. Substring match
    for g in gerechten:
        g_lower = g.naam.lower().strip()
        if naam_lower in g_lower or g_lower in naam_lower:
            return g
    # 3. Difflib fuzzy match (threshold 0.75)
    namen = [g.naam.lower().strip() for g in gerechten]
    matches = difflib.get_close_matches(naam_lower, namen, n=1, cutoff=0.75)
    if matches:
        for g in gerechten:
            if g.naam.lower().strip() == matches[0]:
                return g
    return None


def _get_org_by_api_key(api_key: str) -> Organisatie | None:
    """Zoek organisatie op basis van webhook API key (constant-time vergelijking)."""
    if not api_key:
        return None
    org = Organisatie.query.filter_by(kassaboek_actief=True).filter(
        Organisatie.webhook_api_key.isnot(None)
    ).all()
    for o in org:
        if o.webhook_api_key and hmac.compare_digest(o.webhook_api_key, api_key):
            return o
    return None


@kassaboek_bp.route("/kassaboek/webhook", methods=["POST"])
def kassaboek_webhook():
    """
    Webhook endpoint: accepteert kassadata via JSON POST.

    Headers:
        X-API-Key: <webhook_api_key>

    Body (JSON):
        {
            "datum": "2026-03-12",
            "omzet": 1250.50,
            "couverts": 45,
            "gerechten": [
                {"naam": "Caesar Salade", "aantal": 12, "omzet": 168.00},
                {"naam": "Ribeye", "aantal": 8, "omzet": 232.00}
            ]
        }
    """
    api_key = request.headers.get("X-API-Key", "")
    org = _get_org_by_api_key(api_key)
    if not org:
        return jsonify({"error": "Ongeldige of ontbrekende API key"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Geen geldige JSON body"}), 400

    # Valideer datum
    try:
        datum = date.fromisoformat(data["datum"])
    except (KeyError, ValueError):
        return jsonify({"error": "Ongeldig of ontbrekend 'datum' veld (verwacht: YYYY-MM-DD)"}), 400

    omzet = data.get("omzet")
    couverts = data.get("couverts")
    gerechten_input = data.get("gerechten", [])

    if not isinstance(gerechten_input, list):
        return jsonify({"error": "'gerechten' moet een array zijn"}), 400

    # Laad actief menu-gerechten voor fuzzy matching
    actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()
    menu_gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).all() if actief_menu else []

    opgeslagen = 0
    gekoppeld = 0

    # Sla dag-totaal op (zonder gerecht_naam)
    bestaand = KassaboekEntry.query.filter_by(
        organisatie_id=org.id,
        datum=datum,
        gerecht_naam=None
    ).first()
    if bestaand:
        if omzet is not None:
            bestaand.omzet = omzet
        if couverts is not None:
            bestaand.couverts = couverts
    else:
        db.session.add(KassaboekEntry(
            organisatie_id=org.id,
            datum=datum,
            omzet=omzet,
            couverts=couverts,
            gerecht_naam=None,
            aantal_verkocht=None,
        ))
        opgeslagen += 1

    # Sla per-gerecht entries op
    for g in gerechten_input:
        naam = g.get("naam", "").strip()
        aantal = g.get("aantal")
        gerecht_omzet = g.get("omzet")
        if not naam:
            continue

        # Fuzzy koppeling aan Gerecht model
        match = _fuzzy_match_gerecht(naam, menu_gerechten)
        if match:
            gekoppeld += 1

        bestaand_g = KassaboekEntry.query.filter_by(
            organisatie_id=org.id,
            datum=datum,
            gerecht_naam=naam
        ).first()
        if bestaand_g:
            if aantal is not None:
                bestaand_g.aantal_verkocht = aantal
            if gerecht_omzet is not None:
                bestaand_g.omzet = gerecht_omzet
        else:
            db.session.add(KassaboekEntry(
                organisatie_id=org.id,
                datum=datum,
                omzet=gerecht_omzet,
                couverts=None,
                gerecht_naam=naam,
                aantal_verkocht=aantal,
            ))
            opgeslagen += 1

    db.session.commit()
    return jsonify({"status": "ok", "opgeslagen": opgeslagen, "gekoppeld_aan_menu": gekoppeld}), 200


@kassaboek_bp.route("/kassaboek/bulk", methods=["POST"])
def kassaboek_bulk():
    """
    Bulk upload van kassadata: max 365 entries.

    Headers:
        X-API-Key: <webhook_api_key>

    Body (JSON):
        [
            {
                "datum": "2026-03-12",
                "omzet": 1250.50,
                "couverts": 45,
                "gerechten": [{"naam": "Caesar Salade", "aantal": 12}]
            },
            ...
        ]
    """
    api_key = request.headers.get("X-API-Key", "")
    org = _get_org_by_api_key(api_key)
    if not org:
        return jsonify({"error": "Ongeldige of ontbrekende API key"}), 401

    data = request.get_json(silent=True)
    if not data or not isinstance(data, list):
        return jsonify({"error": "Verwacht een JSON array van entries"}), 400

    if len(data) > 365:
        return jsonify({"error": "Maximaal 365 entries per bulk upload"}), 400

    # Laad actief menu-gerechten voor fuzzy matching (eenmalig)
    actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()
    menu_gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).all() if actief_menu else []

    opgeslagen = 0
    fouten = []

    for i, entry_data in enumerate(data):
        try:
            datum = date.fromisoformat(entry_data["datum"])
        except (KeyError, ValueError):
            fouten.append({"index": i, "fout": "Ongeldig of ontbrekend 'datum' veld"})
            continue

        omzet = entry_data.get("omzet")
        couverts = entry_data.get("couverts")
        gerechten = entry_data.get("gerechten", [])

        # Dag-totaal
        bestaand = KassaboekEntry.query.filter_by(
            organisatie_id=org.id,
            datum=datum,
            gerecht_naam=None
        ).first()
        if bestaand:
            if omzet is not None:
                bestaand.omzet = omzet
            if couverts is not None:
                bestaand.couverts = couverts
        else:
            db.session.add(KassaboekEntry(
                organisatie_id=org.id,
                datum=datum,
                omzet=omzet,
                couverts=couverts,
                gerecht_naam=None,
                aantal_verkocht=None,
            ))
            opgeslagen += 1

        # Per-gerecht
        for g in (gerechten or []):
            naam = g.get("naam", "").strip()
            aantal = g.get("aantal")
            gerecht_omzet = g.get("omzet")
            if not naam:
                continue
            _fuzzy_match_gerecht(naam, menu_gerechten)  # koppeling voor toekomstig gebruik
            bestaand_g = KassaboekEntry.query.filter_by(
                organisatie_id=org.id,
                datum=datum,
                gerecht_naam=naam
            ).first()
            if bestaand_g:
                if aantal is not None:
                    bestaand_g.aantal_verkocht = aantal
                if gerecht_omzet is not None:
                    bestaand_g.omzet = gerecht_omzet
            else:
                db.session.add(KassaboekEntry(
                    organisatie_id=org.id,
                    datum=datum,
                    omzet=gerecht_omzet,
                    couverts=None,
                    gerecht_naam=naam,
                    aantal_verkocht=aantal,
                ))
                opgeslagen += 1

    db.session.commit()
    return jsonify({"status": "ok", "opgeslagen": opgeslagen, "fouten": fouten}), 200


@kassaboek_bp.route("/kassaboek/verkoop")
def kassaboek_verkoop():
    """
    JSON endpoint: populairste en trending gerechten.

    Query params:
        weken: aantal weken terugkijken (default: 4)

    Returns JSON:
        {
            "populairste": [{"naam": ..., "totaal_verkocht": ..., "gemiddeld_per_week": ...}],
            "trending":    [{"naam": ..., "recente_gem": ..., "vorige_gem": ..., "stijging_pct": ...}]
        }
    """
    api_key = request.headers.get("X-API-Key", "")
    org = _get_org_by_api_key(api_key)

    # Authenticated gebruikers mogen ook via sessie
    if not org:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({"error": "Authenticatie vereist"}), 401
        org = current_user.organisatie
        if not org.kassaboek_actief:
            return jsonify({"error": "Kassaboek niet actief voor deze organisatie"}), 403

    try:
        weken = max(1, min(52, int(request.args.get("weken", 4))))
    except ValueError:
        weken = 4

    nu = date.today()
    start = nu - timedelta(weeks=weken)
    halverwege = nu - timedelta(weeks=weken // 2)

    # Populairste gerechten (volledig periode)
    populair = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.sum(KassaboekEntry.aantal_verkocht).label("totaal"),
        func.count(KassaboekEntry.datum.distinct()).label("dagen")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= start,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).order_by(func.sum(KassaboekEntry.aantal_verkocht).desc()).limit(10).all()

    populairste = [
        {
            "naam": r.gerecht_naam,
            "totaal_verkocht": int(r.totaal or 0),
            "gemiddeld_per_week": round((r.totaal or 0) / max(weken, 1), 1),
        }
        for r in populair
    ]

    # Trending: vergelijk eerste vs tweede helft van periode
    recente = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.avg(KassaboekEntry.aantal_verkocht).label("gem")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= halverwege,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).all()

    vorige = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.avg(KassaboekEntry.aantal_verkocht).label("gem")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= start,
        KassaboekEntry.datum < halverwege,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).all()

    vorige_map = {r.gerecht_naam: float(r.gem or 0) for r in vorige}

    trending = []
    for r in recente:
        naam = r.gerecht_naam
        rec_gem = float(r.gem or 0)
        vor_gem = vorige_map.get(naam, 0)
        if vor_gem > 0:
            stijging = round(((rec_gem - vor_gem) / vor_gem) * 100, 1)
        else:
            stijging = 100.0 if rec_gem > 0 else 0.0
        trending.append({
            "naam": naam,
            "recente_gem": round(rec_gem, 1),
            "vorige_gem": round(vor_gem, 1),
            "stijging_pct": stijging,
        })

    trending.sort(key=lambda x: x["stijging_pct"], reverse=True)
    trending = trending[:10]

    return jsonify({"populairste": populairste, "trending": trending}), 200


@kassaboek_bp.route("/kassaboek/seizoen")
def kassaboek_seizoen():
    """
    JSON endpoint: seizoenspatronen per gerecht — gemiddeld aantal verkocht per maand en per weekdag.

    Headers:
        X-API-Key: <webhook_api_key>   (of ingelogde sessie)

    Query params:
        gerecht: naam van het gerecht (verplicht)
        maanden: aantal maanden terugkijken (default: 12, max: 24)

    Returns JSON:
        {
            "gerecht": "Caesar Salade",
            "per_maand":   [{"maand": "2026-01", "gemiddeld": 12.3, "totaal": 148}, ...],
            "per_weekdag": [{"dag": "maandag", "gemiddeld": 8.1}, ...]
        }
    """
    api_key = request.headers.get("X-API-Key", "")
    org = _get_org_by_api_key(api_key)

    if not org:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return jsonify({"error": "Authenticatie vereist"}), 401
        org = current_user.organisatie
        if not org.kassaboek_actief:
            return jsonify({"error": "Kassaboek niet actief voor deze organisatie"}), 403

    gerecht_naam = request.args.get("gerecht", "").strip()
    if not gerecht_naam:
        return jsonify({"error": "Query parameter 'gerecht' is verplicht"}), 400

    try:
        maanden = max(1, min(24, int(request.args.get("maanden", 12))))
    except ValueError:
        maanden = 12

    start = date.today().replace(day=1) - timedelta(days=maanden * 30)

    entries = KassaboekEntry.query.filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.gerecht_naam == gerecht_naam,
        KassaboekEntry.datum >= start,
        KassaboekEntry.aantal_verkocht.isnot(None),
    ).all()

    # Fuzzy match: als exacte naam geen resultaten geeft, probeer via menu
    if not entries:
        actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()
        menu_gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).all() if actief_menu else []
        match = _fuzzy_match_gerecht(gerecht_naam, menu_gerechten)
        if match:
            entries = KassaboekEntry.query.filter(
                KassaboekEntry.organisatie_id == org.id,
                KassaboekEntry.gerecht_naam == match.naam,
                KassaboekEntry.datum >= start,
                KassaboekEntry.aantal_verkocht.isnot(None),
            ).all()
            gerecht_naam = match.naam  # gebruik de gekoppelde naam in response

    if not entries:
        return jsonify({"gerecht": gerecht_naam, "per_maand": [], "per_weekdag": []}), 200

    # Aggregeer per maand (YYYY-MM)
    maand_buckets: dict[str, list[int]] = {}
    weekdag_buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    weekdag_namen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]

    for e in entries:
        maand_key = e.datum.strftime("%Y-%m")
        maand_buckets.setdefault(maand_key, []).append(e.aantal_verkocht)
        weekdag_buckets[e.datum.weekday()].append(e.aantal_verkocht)

    per_maand = sorted([
        {
            "maand": k,
            "gemiddeld": round(sum(v) / len(v), 1),
            "totaal": sum(v),
        }
        for k, v in maand_buckets.items()
    ], key=lambda x: x["maand"])

    per_weekdag = [
        {
            "dag": weekdag_namen[dag],
            "gemiddeld": round(sum(vals) / len(vals), 1) if vals else 0,
        }
        for dag, vals in weekdag_buckets.items()
    ]

    return jsonify({"gerecht": gerecht_naam, "per_maand": per_maand, "per_weekdag": per_weekdag}), 200


@kassaboek_bp.route("/kassaboek/overzicht")
@login_required
def kassaboek_overzicht():
    """HTML pagina met API key + cURL voorbeeld + verkoopcijfers."""
    org = current_user.organisatie

    if not org.kassaboek_actief:
        return render_template("kassaboek_overzicht.html", org=org, kassaboek_actief=False)

    # Recente verkoop voor dashboard
    vier_weken = date.today() - timedelta(weeks=4)
    verkoop = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.sum(KassaboekEntry.aantal_verkocht).label("totaal")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= vier_weken,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).order_by(func.sum(KassaboekEntry.aantal_verkocht).desc()).limit(10).all()

    verkoop_lijst = [{"naam": r.gerecht_naam, "totaal": int(r.totaal or 0)} for r in verkoop]

    # Trending: vergelijk laatste 2 weken vs 2 weken daarvoor
    twee_weken = date.today() - timedelta(weeks=2)
    recente = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.avg(KassaboekEntry.aantal_verkocht).label("gem")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= twee_weken,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).all()

    vorige = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.avg(KassaboekEntry.aantal_verkocht).label("gem")
    ).filter(
        KassaboekEntry.organisatie_id == org.id,
        KassaboekEntry.datum >= vier_weken,
        KassaboekEntry.datum < twee_weken,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).all()

    vorige_map = {r.gerecht_naam: float(r.gem or 0) for r in vorige}
    trending_lijst = []
    for r in recente:
        naam = r.gerecht_naam
        rec_gem = float(r.gem or 0)
        vor_gem = vorige_map.get(naam, 0)
        if vor_gem > 0:
            stijging = round(((rec_gem - vor_gem) / vor_gem) * 100, 1)
        else:
            stijging = 100.0 if rec_gem > 0 else 0.0
        trending_lijst.append({
            "naam": naam,
            "recente_gem": round(rec_gem, 1),
            "vorige_gem": round(vor_gem, 1),
            "stijging_pct": stijging,
        })
    trending_lijst.sort(key=lambda x: x["stijging_pct"], reverse=True)

    return render_template("kassaboek_overzicht.html",
                           org=org,
                           kassaboek_actief=True,
                           verkoop_lijst=verkoop_lijst,
                           trending_lijst=trending_lijst)
