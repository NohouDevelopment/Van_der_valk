"""
Menu Blueprint — menu uploaden, parsen, bekijken en annoteren.

Routes:
  /menu/                       — Overzicht van alle menu's
  /menu/upload                 — Upload PDF/afbeelding of plak tekst
  /menu/<id>                   — Detail view van geparsed menu
  /menu/<id>/verwijder         — Menu verwijderen
  /menu/<id>/actief            — Menu als actief instellen
  /menu/<id>/annotaties        — Geannoteerd menu bekijken
  /menu/<id>/annotaties/genereer — Annotaties genereren (GET=loading, POST=run)
"""

import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Menu, Gerecht, MenuAnnotatie, MenuSegment, TrendGeheugen

menu_bp = Blueprint("menu", __name__)

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@menu_bp.route("/menu/")
@login_required
def menu_overzicht():
    """Toon alle menu's van de organisatie."""
    org = current_user.organisatie
    menus = Menu.query.filter_by(organisatie_id=org.id).order_by(Menu.aangemaakt_op.desc()).all()
    return render_template("menu_overzicht.html", org=org, menus=menus)


@menu_bp.route("/menu/upload", methods=["GET", "POST"])
@login_required
def menu_upload():
    """Upload een menu via PDF/afbeelding of plak tekst."""
    org = current_user.organisatie

    if request.method == "GET":
        return render_template("menu_upload.html", org=org)

    error = None
    menu_naam = request.form.get("menu_naam", "").strip() or "Menu"
    upload_type = request.form.get("upload_type", "tekst")

    ruwe_tekst = ""
    bron_type = "tekst"
    bron_bestand = None

    try:
        if upload_type == "tekst":
            # Tekst direct plakken
            ruwe_tekst = request.form.get("menu_tekst", "").strip()
            if not ruwe_tekst:
                error = "Plak je menutekst in het tekstvak."

        elif upload_type == "bestand":
            # Bestand uploaden
            bestand = request.files.get("menu_bestand")
            if not bestand or not bestand.filename:
                error = "Selecteer een bestand om te uploaden."
            elif not _allowed_file(bestand.filename):
                error = f"Ongeldig bestandstype. Toegestaan: {', '.join(ALLOWED_EXTENSIONS)}"
            else:
                # Bestandsgrootte checken
                bestand.seek(0, 2)
                size = bestand.tell()
                bestand.seek(0)
                if size > MAX_FILE_SIZE:
                    error = "Bestand is te groot (max 10 MB)."
                else:
                    # Opslaan
                    filename = secure_filename(bestand.filename)
                    save_name = f"{org.id}_{filename}"
                    save_path = UPLOAD_DIR / save_name
                    bestand.save(str(save_path))
                    bron_bestand = f"data/uploads/{save_name}"

                    ext = filename.rsplit(".", 1)[1].lower()
                    if ext == "pdf":
                        bron_type = "pdf"
                        from tools.menu_parser import extract_text_from_pdf
                        ruwe_tekst = extract_text_from_pdf(str(save_path))
                    else:
                        bron_type = "afbeelding"
                        from tools.menu_parser import extract_text_from_image
                        ruwe_tekst = extract_text_from_image(str(save_path))

                    if not ruwe_tekst.strip():
                        error = "Kon geen tekst uit het bestand extraheren. Probeer de tekst handmatig te plakken."

        if error:
            return render_template("menu_upload.html", org=org, error=error,
                                   menu_naam=menu_naam, upload_type=upload_type)

        # Parse menu tekst naar JSON
        from tools.menu_parser import parse_menu_text
        data = parse_menu_text(ruwe_tekst)

        # Sla menu op in database
        menu = Menu(
            organisatie_id=org.id,
            naam=menu_naam,
            bron_type=bron_type,
            bron_bestand=bron_bestand,
            ruwe_tekst=ruwe_tekst,
            data=data,
            actief=True,
            geupload_door=current_user.id
        )

        # Zet andere menu's op niet-actief
        Menu.query.filter_by(organisatie_id=org.id, actief=True).update({"actief": False})

        db.session.add(menu)
        db.session.flush()

        # Denormaliseer gerechten
        _sla_gerechten_op(menu, data, org.id)

        db.session.commit()
        print(f"[Menu] Menu '{menu_naam}' opgeslagen (id={menu.id}, {bron_type})")

        return redirect(url_for("menu.menu_detail", menu_id=menu.id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij verwerken: {type(e).__name__}: {str(e)}"
        return render_template("menu_upload.html", org=org, error=error,
                               menu_naam=menu_naam, upload_type=upload_type)


@menu_bp.route("/menu/<int:menu_id>")
@login_required
def menu_detail(menu_id):
    """Toon een geparsed menu met alle categorieën en gerechten."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()
    return render_template("menu_detail.html", org=org, menu=menu)


@menu_bp.route("/menu/<int:menu_id>/actief", methods=["POST"])
@login_required
def menu_actief(menu_id):
    """Stel een menu in als het actieve menu."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    Menu.query.filter_by(organisatie_id=org.id, actief=True).update({"actief": False})
    menu.actief = True
    db.session.commit()

    return redirect(url_for("menu.menu_detail", menu_id=menu.id))


@menu_bp.route("/menu/<int:menu_id>/verwijder", methods=["POST"])
@login_required
def menu_verwijder(menu_id):
    """Verwijder een menu en alle bijbehorende gerechten."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    db.session.delete(menu)
    db.session.commit()
    print(f"[Menu] Menu '{menu.naam}' verwijderd (id={menu.id})")

    return redirect(url_for("menu.menu_overzicht"))


def _sla_gerechten_op(menu: Menu, data: dict, org_id: int):
    """Denormaliseer gerechten uit menu.data naar de Gerecht tabel."""
    for categorie in data.get("categorieën", []):
        cat_naam = categorie.get("naam", "Overig")
        for gerecht_data in categorie.get("gerechten", []):
            gerecht = Gerecht(
                menu_id=menu.id,
                organisatie_id=org_id,
                categorie=cat_naam,
                naam=gerecht_data.get("naam", "Onbekend"),
                prijs=gerecht_data.get("prijs"),
                beschrijving=gerecht_data.get("beschrijving"),
                ingredienten=gerecht_data.get("ingredienten", []),
                tags=gerecht_data.get("tags", []),
                dieet=gerecht_data.get("dieet", [])
            )
            db.session.add(gerecht)


# --- Annotatie routes ---

@menu_bp.route("/menu/<int:menu_id>/annotaties")
@login_required
def menu_annotaties(menu_id):
    """Toon het geannoteerde menu met per-gerecht opmerkingen."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    # Haal annotaties op
    annotaties = MenuAnnotatie.query.filter_by(menu_id=menu.id).all()

    # Bouw lookup: gerecht_id → annotatie
    annot_map = {a.gerecht_id: a for a in annotaties}

    # Haal gerechten op
    gerechten = Gerecht.query.filter_by(menu_id=menu.id).all()

    # Check prerequisites
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

    return render_template("menu_annotaties.html",
                           org=org,
                           menu=menu,
                           gerechten=gerechten,
                           annot_map=annot_map,
                           segment=segment,
                           geheugen=geheugen,
                           heeft_annotaties=len(annotaties) > 0)


@menu_bp.route("/menu/<int:menu_id>/annotaties/genereer", methods=["GET", "POST"])
@login_required
def menu_annotaties_genereer(menu_id):
    """Loading page (GET) + genereer annotaties (POST)."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

    if not segment or not geheugen:
        return redirect(url_for("menu.menu_annotaties", menu_id=menu.id))

    if request.method == "GET":
        return render_template("annotatie_scan.html", org=org, menu=menu)

    # POST: genereer annotaties
    try:
        from tools.menu_annotator import annotate_menu

        annotatie_data = annotate_menu(menu.data, geheugen.data, segment.data)

        # Verwijder bestaande annotaties voor dit menu
        MenuAnnotatie.query.filter_by(menu_id=menu.id).delete()

        # Maak lookup van gerecht naam → gerecht record
        gerechten = Gerecht.query.filter_by(menu_id=menu.id).all()
        gerecht_lookup = {}
        for g in gerechten:
            gerecht_lookup[g.naam.lower().strip()] = g

        # Sla nieuwe annotaties op
        opgeslagen = 0
        for annot in annotatie_data:
            gerecht_naam = annot.get("gerecht_naam", "").lower().strip()
            gerecht = gerecht_lookup.get(gerecht_naam)

            if not gerecht:
                # Probeer fuzzy match
                for key, g in gerecht_lookup.items():
                    if gerecht_naam in key or key in gerecht_naam:
                        gerecht = g
                        break

            if not gerecht:
                continue  # Skip als we het gerecht niet kunnen matchen

            db_annot = MenuAnnotatie(
                organisatie_id=org.id,
                menu_id=menu.id,
                gerecht_id=gerecht.id,
                trend_geheugen_versie=geheugen.versie,
                status=annot.get("status", "HOUDEN"),
                score=annot.get("score", 5.0),
                data={
                    "opmerkingen": annot.get("opmerkingen", ""),
                    "suggesties": annot.get("suggesties", []),
                    "relevante_trends": annot.get("relevante_trends", []),
                    "positief": annot.get("positief", [])
                }
            )
            db.session.add(db_annot)
            opgeslagen += 1

        db.session.commit()
        print(f"[Annotatie] {opgeslagen} annotaties opgeslagen voor menu '{menu.naam}'")

        return redirect(url_for("menu.menu_annotaties", menu_id=menu.id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij annoteren: {type(e).__name__}: {str(e)}"
        return render_template("annotatie_scan.html", org=org, menu=menu, error=error)
