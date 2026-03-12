"""
Ingredient Blueprint — ingrediënten-analyse, metrics en slimme voorstellen.

Routes:
    /ingredienten/          — Metrics dashboard met filtertabel
    /ingredienten/voorstel  — Slim voorstel genereren (GET=scan, POST=genereer)
"""

from flask import Blueprint, render_template, redirect, url_for, request, session
from flask_login import login_required, current_user
from models import db, Menu, Gerecht, MenuSegment, KassaboekEntry, TrendGeheugen

ingredient_bp = Blueprint("ingredient", __name__)


@ingredient_bp.route("/ingredienten/")
@login_required
def ingredienten_overzicht():
    """Metrics dashboard met filtertabel."""
    org = current_user.organisatie
    actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()

    if not actief_menu:
        return render_template("ingredienten.html", org=org, heeft_menu=False)

    gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).all()

    # Kassaboek verkoop-data ophalen als beschikbaar
    verkoop_data = None
    kassaboek_actief = org.kassaboek_actief

    if kassaboek_actief:
        from datetime import date, timedelta
        from sqlalchemy import func

        vier_weken_geleden = date.today() - timedelta(weeks=4)
        verkoop = db.session.query(
            KassaboekEntry.gerecht_naam,
            func.avg(KassaboekEntry.aantal_verkocht).label("gem")
        ).filter(
            KassaboekEntry.organisatie_id == org.id,
            KassaboekEntry.datum >= vier_weken_geleden,
            KassaboekEntry.gerecht_naam.isnot(None)
        ).group_by(KassaboekEntry.gerecht_naam).all()

        if verkoop:
            verkoop_data = {v.gerecht_naam: round(v.gem * 7, 1) for v in verkoop}

    from tools.ingredient_analyzer import analyseer_ingredienten
    analyse = analyseer_ingredienten(gerechten, verkoop_data=verkoop_data)

    return render_template("ingredienten.html",
                           org=org,
                           analyse=analyse,
                           menu=actief_menu,
                           heeft_menu=True,
                           kassaboek_actief=kassaboek_actief)


@ingredient_bp.route("/ingredienten/voorstel", methods=["GET", "POST"])
@login_required
def ingredienten_voorstel():
    """Slim voorstel: GET toont scan-pagina, POST genereert voorstel."""
    org = current_user.organisatie
    actief_menu = Menu.query.filter_by(organisatie_id=org.id, actief=True).first()

    if not actief_menu:
        return redirect(url_for("ingredient.ingredienten_overzicht"))

    if request.method == "GET":
        return render_template("ingredient_scan.html", org=org)

    # POST: genereer voorstel
    try:
        gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).all()

        from tools.ingredient_analyzer import analyseer_ingredienten
        from tools.ingredient_suggester import genereer_voorstel

        analyse = analyseer_ingredienten(gerechten)
        segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
        segment_data = segment.data if segment else None
        geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()
        geheugen_data = geheugen.data if geheugen else None

        # Kassaboek verkoop-context ophalen als actief
        verkoop_data = None
        if org.kassaboek_actief:
            from datetime import date, timedelta
            from sqlalchemy import func

            vier_weken_geleden = date.today() - timedelta(weeks=4)
            verkoop_rows = db.session.query(
                KassaboekEntry.gerecht_naam,
                func.sum(KassaboekEntry.aantal_verkocht).label("totaal")
            ).filter(
                KassaboekEntry.organisatie_id == org.id,
                KassaboekEntry.datum >= vier_weken_geleden,
                KassaboekEntry.gerecht_naam.isnot(None),
                KassaboekEntry.aantal_verkocht.isnot(None)
            ).group_by(KassaboekEntry.gerecht_naam).order_by(
                func.sum(KassaboekEntry.aantal_verkocht).desc()
            ).all()

            if verkoop_rows:
                gesorteerd = [{"naam": r.gerecht_naam, "totaal": int(r.totaal or 0)} for r in verkoop_rows]
                verkoop_data = {
                    "top_5": gesorteerd[:5],
                    "flop_5": gesorteerd[-5:] if len(gesorteerd) >= 5 else gesorteerd,
                }

        voorstellen = genereer_voorstel(analyse, segment_data, geheugen_data, verkoop_data)

        # Sla voorstellen op in session voor de resultaatpagina
        # Beperk session grootte: max 3 voorstellen, ingredienten max 20 items per voorstel
        voorstellen_compact = []
        for v in voorstellen[:3]:
            v_copy = dict(v)
            v_copy["ingredienten"] = v.get("ingredienten", [])[:20]
            voorstellen_compact.append(v_copy)
        session["laatste_voorstellen"] = voorstellen_compact
        session["laatste_analyse_stats"] = analyse["statistieken"]

        return redirect(url_for("ingredient.ingredienten_voorstel_resultaat"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij genereren voorstel: {type(e).__name__}: {str(e)}"
        return render_template("ingredient_scan.html", org=org, error=error)


@ingredient_bp.route("/ingredienten/voorstel/resultaat")
@login_required
def ingredienten_voorstel_resultaat():
    """Toon het gegenereerde voorstel met synergie-check."""
    org = current_user.organisatie
    voorstellen = session.get("laatste_voorstellen")

    if not voorstellen:
        return redirect(url_for("ingredient.ingredienten_overzicht"))

    return render_template("ingredient_voorstel.html",
                           org=org,
                           voorstellen=voorstellen)
