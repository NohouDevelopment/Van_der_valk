"""
Voorstel Blueprint — Menu Advies (Ontwerpruimte).

Routes:
    /voorstel/                  — Builder pagina (ontwerpruimte.html)
    /voorstel/start             — POST: sla config op in session, redirect naar scan
    /voorstel/genereer          — GET: loading page, POST: orchestratie + redirect
    /voorstel/resultaat/<id>    — Resultaat bekijken
    /voorstel/geschiedenis      — Sessie-historie
    /voorstel/bewaar/<id>       — Bewaar voorstel als concept (POST)
"""

import json
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required, current_user
from models import (
    db, Menu, Gerecht, MenuSegment, TrendGeheugen, KassaboekEntry,
    VoorstelSessie, genereer_sessie_titel
)

logger = logging.getLogger(__name__)

voorstel_bp = Blueprint("voorstel", __name__)


def _get_actief_menu(org):
    return Menu.query.filter_by(organisatie_id=org.id, actief=True).first()


def _filter_menu_data(menu_data: dict, focus_type: str, config: dict, menu_id: int) -> dict:
    """Filter menu_data op basis van focus_type en config."""
    if focus_type == "heel_menu":
        return menu_data

    if focus_type == "categorie":
        cat_naam = config.get("categorie_naam", "")
        gefilterd = {"categorieën": []}
        for cat in menu_data.get("categorieën", []):
            if cat.get("naam", "").lower() == cat_naam.lower():
                gefilterd["categorieën"].append(cat)
        return gefilterd

    if focus_type == "gerechten":
        gerecht_ids = set(config.get("gerecht_ids", []))
        if not gerecht_ids:
            return menu_data

        # Haal gerechtnamen op via IDs
        gerechten_db = Gerecht.query.filter(
            Gerecht.id.in_(gerecht_ids),
            Gerecht.menu_id == menu_id
        ).all()
        gerecht_namen = {g.naam.lower().strip() for g in gerechten_db}

        gefilterd = {"categorieën": []}
        for cat in menu_data.get("categorieën", []):
            cat_gerechten = [
                g for g in cat.get("gerechten", [])
                if g.get("naam", "").lower().strip() in gerecht_namen
            ]
            if cat_gerechten:
                gefilterd["categorieën"].append({
                    "naam": cat.get("naam", "Overig"),
                    "gerechten": cat_gerechten,
                })
        return gefilterd

    return menu_data


@voorstel_bp.route("/voorstel/")
@login_required
def ontwerpruimte():
    """Builder pagina: 'Stel je menuadvies samen'."""
    org = current_user.organisatie
    actief_menu = _get_actief_menu(org)

    if not actief_menu:
        return redirect(url_for("dashboard"))

    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

    # Actieve trends voor selectie
    actieve_trends = []
    if geheugen and geheugen.data:
        trends = geheugen.data.get("trends", [])
        actieve_trends = [t for t in trends if t.get("status") in ("actief", "bevestigd", "nieuw")]
        actieve_trends.sort(key=lambda t: t.get("effectieve_score", 0), reverse=True)

    # Categorieën uit menu
    categorieen = []
    if actief_menu.data:
        for cat in actief_menu.data.get("categorieën", []):
            if cat.get("naam"):
                categorieen.append(cat["naam"])

    # Gerechten voor selectie
    gerechten = Gerecht.query.filter_by(menu_id=actief_menu.id).order_by(Gerecht.categorie, Gerecht.naam).all()

    # Voorgeladen basis config als verfijning
    basis_id = request.args.get("basis")
    basis_config = None
    if basis_id:
        basis = VoorstelSessie.query.filter_by(id=basis_id, organisatie_id=org.id).first()
        if basis:
            basis_config = {
                "doel": basis.doel,
                "focus_type": basis.focus_type,
                "config": basis.config,
                "basis_sessie_id": basis.id,
            }

    return render_template("ontwerpruimte.html",
                           org=org,
                           menu=actief_menu,
                           segment=segment,
                           geheugen=geheugen,
                           actieve_trends=actieve_trends[:15],
                           categorieen=categorieen,
                           gerechten=gerechten,
                           basis_config=basis_config)


@voorstel_bp.route("/voorstel/start", methods=["POST"])
@login_required
def voorstel_start():
    """Sla config op in session en redirect naar loading page."""
    doel = request.form.get("doel", "diagnose")
    focus_type = request.form.get("focus_type", "heel_menu")
    categorie_naam = request.form.get("categorie_naam", "")
    gerecht_ids = [int(x) for x in request.form.getlist("gerecht_ids") if x.isdigit()]
    focus_trends = request.form.getlist("focus_trends")
    extra_instructie = request.form.get("extra_instructie", "").strip()[:500]
    basis_sessie_id = request.form.get("basis_sessie_id", type=int)

    gebruik_trends = request.form.get("gebruik_trends") == "1"
    gebruik_segment = request.form.get("gebruik_segment") == "1"
    gebruik_kassaboek = request.form.get("gebruik_kassaboek") == "1"

    session["voorstel_config"] = {
        "doel": doel,
        "focus_type": focus_type,
        "categorie_naam": categorie_naam,
        "gerecht_ids": gerecht_ids,
        "focus_trends": focus_trends,
        "extra_instructie": extra_instructie,
        "basis_sessie_id": basis_sessie_id,
        "gebruik_trends": gebruik_trends,
        "gebruik_segment": gebruik_segment,
        "gebruik_kassaboek": gebruik_kassaboek,
    }

    return redirect(url_for("voorstel.voorstel_genereer"))


@voorstel_bp.route("/voorstel/genereer", methods=["GET", "POST"])
@login_required
def voorstel_genereer():
    """GET: loading page. POST: orchestratie + redirect naar resultaat."""
    org = current_user.organisatie
    actief_menu = _get_actief_menu(org)

    if not actief_menu:
        return redirect(url_for("dashboard"))

    voorstel_cfg = session.get("voorstel_config")
    if not voorstel_cfg:
        return redirect(url_for("voorstel.ontwerpruimte"))

    if request.method == "GET":
        return render_template("voorstel_scan.html", org=org, menu=actief_menu,
                               doel=voorstel_cfg.get("doel", "diagnose"))

    # POST: orchestratie
    try:
        doel = voorstel_cfg["doel"]
        focus_type = voorstel_cfg["focus_type"]
        categorie_naam = voorstel_cfg.get("categorie_naam", "")
        gerecht_ids = voorstel_cfg.get("gerecht_ids", [])
        focus_trends = voorstel_cfg.get("focus_trends", [])
        extra_instructie = voorstel_cfg.get("extra_instructie", "")
        basis_sessie_id = voorstel_cfg.get("basis_sessie_id")
        gebruik_trends = voorstel_cfg.get("gebruik_trends", True)
        gebruik_segment = voorstel_cfg.get("gebruik_segment", True)
        gebruik_kassaboek = voorstel_cfg.get("gebruik_kassaboek", False)

        config = {
            "categorie_naam": categorie_naam,
            "gerecht_ids": gerecht_ids,
            "focus_trends": focus_trends,
            "extra_instructie": extra_instructie,
            "gebruik_trends": gebruik_trends,
            "gebruik_segment": gebruik_segment,
            "gebruik_kassaboek": gebruik_kassaboek,
        }

        # --- Stap 1: Resolve context ---
        segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
        geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

        segment_data = segment.data if (segment and gebruik_segment) else {}
        geheugen_data = geheugen.data if (geheugen and gebruik_trends) else {"trends": []}

        # --- Stap 2: Filter focus ---
        menu_data = actief_menu.data or {"categorieën": []}
        gefilterde_data = _filter_menu_data(menu_data, focus_type, config, actief_menu.id)

        # --- Stap 3: Run tool(s) ---
        resultaat = {}

        if doel == "diagnose":
            resultaat = _run_diagnose(gefilterde_data, geheugen_data, segment_data, extra_instructie)

        elif doel == "verbeteren":
            resultaat = _run_verbeteren(gefilterde_data, geheugen_data, segment_data, extra_instructie)

        elif doel == "nieuwe_gerechten":
            ingredient_ctx = None
            if gebruik_kassaboek and org.kassaboek_actief:
                ingredient_ctx = _build_kassaboek_context(org.id)

            resultaat = _run_nieuwe_gerechten(
                gefilterde_data, geheugen_data, segment_data,
                focus_trends, extra_instructie, ingredient_ctx
            )

        # --- Stap 4: Auto-titel ---
        titel = genereer_sessie_titel(doel, focus_type, config)

        # --- Stap 5: Opslaan ---
        sessie = VoorstelSessie(
            organisatie_id=org.id,
            menu_id=actief_menu.id,
            gegenereerd_door=current_user.id,
            doel=doel,
            focus_type=focus_type,
            config=config,
            resultaat=resultaat,
            titel=titel,
            status="voltooid",
            basis_sessie_id=basis_sessie_id,
        )
        db.session.add(sessie)
        db.session.commit()

        # Cleanup session
        session.pop("voorstel_config", None)

        logger.info("VoorstelSessie %d aangemaakt: %s", sessie.id, titel)
        return redirect(url_for("voorstel.voorstel_resultaat", sessie_id=sessie.id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("Fout bij voorstel genereren: %s", e)
        session.pop("voorstel_config", None)
        error = f"Fout bij genereren: {type(e).__name__}: {str(e)}"
        return render_template("voorstel_scan.html", org=org, menu=actief_menu,
                               doel=voorstel_cfg.get("doel", "diagnose"), error=error)


def _run_diagnose(menu_data, geheugen_data, segment_data, extra_instructie):
    """Diagnose: annoteer elk gerecht → status + score + motivatie + managementsamenvatting."""
    from tools.menu_annotator import annotate_menu

    annotaties = annotate_menu(menu_data, geheugen_data, segment_data, user_instructions=extra_instructie)

    # Managementsamenvatting
    counts = {"HOUDEN": 0, "AANPASSEN": 0, "VERVANGEN": 0}
    total_score = 0
    for a in annotaties:
        s = a.get("status", "HOUDEN")
        counts[s] = counts.get(s, 0) + 1
        total_score += a.get("score", 5)

    gem_score = round(total_score / len(annotaties), 1) if annotaties else 0

    # Bepaal grootste kans
    aanpas_trends = {}
    for a in annotaties:
        if a.get("status") in ("AANPASSEN", "VERVANGEN"):
            for t in a.get("relevante_trends", []):
                aanpas_trends[t] = aanpas_trends.get(t, 0) + 1
    grootste_kans = max(aanpas_trends, key=aanpas_trends.get) if aanpas_trends else None

    samenvatting_parts = [f"{counts.get('HOUDEN', 0)} gerechten sluiten goed aan"]
    aandacht = counts.get("AANPASSEN", 0) + counts.get("VERVANGEN", 0)
    if aandacht:
        samenvatting_parts.append(f"{aandacht} vragen aandacht")
    samenvatting = ", ".join(samenvatting_parts)
    if grootste_kans:
        samenvatting += f". Grootste kans: {grootste_kans}"

    return {
        "type": "diagnose",
        "annotaties": annotaties,
        "samenvatting": samenvatting,
        "counts": counts,
        "gemiddelde_score": gem_score,
        "grootste_kans": grootste_kans,
    }


def _run_verbeteren(menu_data, geheugen_data, segment_data, extra_instructie):
    """Verbeteren: annoteer → filter alleen AANPASSEN/VERVANGEN (twee-laags)."""
    from tools.menu_annotator import annotate_menu

    verbeter_instructie = "Focus op CONCRETE verbeteracties. Geef per gerecht specifieke wijzigingen, niet alleen een beoordeling."
    if extra_instructie:
        verbeter_instructie = f"{verbeter_instructie}\n{extra_instructie}"

    annotaties = annotate_menu(menu_data, geheugen_data, segment_data, user_instructions=verbeter_instructie)

    # Orchestratie-niveau: filter HOUDEN weg
    actie_items = [a for a in annotaties if a.get("status") in ("AANPASSEN", "VERVANGEN")]

    samenvatting = f"{len(actie_items)} gerecht{'en' if len(actie_items) != 1 else ''} vragen om aanpassing"

    return {
        "type": "verbeteren",
        "annotaties": actie_items,
        "samenvatting": samenvatting,
        "totaal_geanalyseerd": len(annotaties),
    }


def _run_nieuwe_gerechten(menu_data, geheugen_data, segment_data, focus_trends, extra_instructie, ingredient_ctx):
    """Nieuwe gerechten: suggereer_toevoegingen met explainability."""
    from tools.menu_annotator import suggereer_toevoegingen

    voorstellen = suggereer_toevoegingen(
        menu_data, geheugen_data, segment_data,
        focus_trends=focus_trends if focus_trends else None,
        ingredient_context=ingredient_ctx,
        extra_instructie=extra_instructie if extra_instructie else None,
    )

    return {
        "type": "nieuwe_gerechten",
        "voorstellen": voorstellen,
        "aantal": len(voorstellen),
    }


def _build_kassaboek_context(org_id: int) -> str | None:
    """Bouw korte samenvatting van kassaboek data voor ingredient context."""
    from datetime import date, timedelta
    from sqlalchemy import func

    vier_weken = date.today() - timedelta(weeks=4)
    verkoop = db.session.query(
        KassaboekEntry.gerecht_naam,
        func.sum(KassaboekEntry.aantal_verkocht).label("totaal")
    ).filter(
        KassaboekEntry.organisatie_id == org_id,
        KassaboekEntry.datum >= vier_weken,
        KassaboekEntry.gerecht_naam.isnot(None),
        KassaboekEntry.aantal_verkocht.isnot(None)
    ).group_by(KassaboekEntry.gerecht_naam).order_by(
        func.sum(KassaboekEntry.aantal_verkocht).desc()
    ).limit(10).all()

    if not verkoop:
        return None

    lines = ["Populairste gerechten (laatste 4 weken):"]
    for r in verkoop[:5]:
        lines.append(f"- {r.gerecht_naam}: {int(r.totaal or 0)} verkocht")
    return "\n".join(lines)


@voorstel_bp.route("/voorstel/resultaat/<int:sessie_id>")
@login_required
def voorstel_resultaat(sessie_id):
    """Resultaat bekijken."""
    org = current_user.organisatie
    sessie = VoorstelSessie.query.filter_by(id=sessie_id, organisatie_id=org.id).first_or_404()

    return render_template("voorstel_resultaat.html",
                           org=org,
                           sessie=sessie,
                           resultaat=sessie.resultaat or {},
                           config=sessie.config or {},
                           result_goal=sessie.doel or "")


@voorstel_bp.route("/voorstel/geschiedenis")
@login_required
def voorstel_geschiedenis():
    """Sessie-historie."""
    org = current_user.organisatie
    sessies = VoorstelSessie.query.filter_by(
        organisatie_id=org.id
    ).order_by(VoorstelSessie.aangemaakt_op.desc()).limit(50).all()

    return render_template("voorstel_geschiedenis.html", org=org, sessies=sessies)


@voorstel_bp.route("/voorstel/bewaar/<int:sessie_id>", methods=["POST"])
@login_required
def voorstel_bewaar_concept(sessie_id):
    """Bewaar een individueel voorstel als concept (niet direct menu muteren)."""
    org = current_user.organisatie
    sessie = VoorstelSessie.query.filter_by(id=sessie_id, organisatie_id=org.id).first_or_404()

    voorstel_idx = request.form.get("voorstel_index", type=int)
    if voorstel_idx is None:
        return redirect(url_for("voorstel.voorstel_resultaat", sessie_id=sessie.id))

    resultaat = sessie.resultaat or {}
    voorstellen = resultaat.get("voorstellen", [])

    if 0 <= voorstel_idx < len(voorstellen):
        voorstellen[voorstel_idx]["bewaard"] = True
        sessie.resultaat = resultaat
        db.session.commit()
        logger.info("Voorstel %d van sessie %d bewaard als concept", voorstel_idx, sessie.id)

    return redirect(url_for("voorstel.voorstel_resultaat", sessie_id=sessie.id))
