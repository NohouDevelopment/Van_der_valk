"""
Menu Blueprint — menu uploaden, parsen, bekijken en annoteren.

Routes:
  /menu/                                    — Overzicht van alle menu's
  /menu/upload                              — Upload PDF/afbeelding of plak tekst
  /menu/<id>                                — Detail view van geparsed menu
  /menu/<id>/verwijder                      — Menu verwijderen
  /menu/<id>/naam                           — Menunaam aanpassen (POST)
  /menu/<id>/actief                         — Menu als actief instellen
  /menu/<id>/annotaties                     — Geannoteerd menu bekijken
  /menu/<id>/annotaties/genereer            — Annotaties genereren (GET=loading, POST=run)
  /menu/<id>/suggesties/genereer            — Slimme suggesties genereren (GET=loading, POST=run)
  /menu/<id>/suggestie/toevoegen            — Voorstel toevoegen aan menu (POST)
  /menu/<id>/gerecht/<gerecht_id>/verwijder — Gerecht verwijderen (POST)
"""

import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Menu, Gerecht, MenuAnnotatie, MenuSegment, TrendGeheugen, IngredientVoorstel

menu_bp = Blueprint("menu", __name__)

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _validate_file_magic(file_obj, ext: str) -> bool:
    """Valideer bestandstype via magic bytes (niet alleen extensie)."""
    file_obj.seek(0)
    header = file_obj.read(16)
    file_obj.seek(0)

    if ext == "pdf":
        return header[:5] == b'%PDF-'

    # Image validation via Pillow
    if ext in ("png", "jpg", "jpeg", "webp"):
        try:
            from PIL import Image
            file_obj.seek(0)
            img = Image.open(file_obj)
            img.verify()
            file_obj.seek(0)
            return True
        except Exception:
            file_obj.seek(0)
            return False

    return True


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
                elif not _validate_file_magic(bestand, filename.rsplit(".", 1)[1].lower()):
                    error = "Bestandsinhoud komt niet overeen met het bestandstype."
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

        # Sla context op in session voor de loading page
        tmp_dir = Path(__file__).parent / "data" / "uploads"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        if len(ruwe_tekst) > 40000:
            # Te groot voor session cookie — sla op als tijdelijk bestand
            import uuid
            tmp_id = uuid.uuid4().hex
            tmp_path = tmp_dir / f"tmp_{tmp_id}.txt"
            tmp_path.write_text(ruwe_tekst, encoding="utf-8")
            session["upload_context"] = {
                "menu_naam": menu_naam,
                "bron_type": bron_type,
                "bron_bestand": bron_bestand,
                "ruwe_tekst_pad": str(tmp_path),
            }
        else:
            session["upload_context"] = {
                "menu_naam": menu_naam,
                "bron_type": bron_type,
                "bron_bestand": bron_bestand,
                "ruwe_tekst": ruwe_tekst,
            }

        return redirect(url_for("menu.menu_upload_verwerken"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij verwerken: {type(e).__name__}: {str(e)}"
        return render_template("menu_upload.html", org=org, error=error,
                               menu_naam=menu_naam, upload_type=upload_type)


@menu_bp.route("/menu/upload/verwerken", methods=["GET", "POST"])
@login_required
def menu_upload_verwerken():
    """Loading page (GET) + AI-parsing en opslaan (POST)."""
    org = current_user.organisatie

    ctx = session.get("upload_context")
    if not ctx:
        return redirect(url_for("menu.menu_upload"))

    if request.method == "GET":
        return render_template("menu_upload_scan.html", org=org,
                               menu_naam=ctx.get("menu_naam", "Menu"))

    # POST: voer AI-parsing uit
    try:
        # Herstel ruwe_tekst
        if "ruwe_tekst_pad" in ctx:
            tmp_path = Path(ctx["ruwe_tekst_pad"])
            ruwe_tekst = tmp_path.read_text(encoding="utf-8")
            tmp_path.unlink(missing_ok=True)
        else:
            ruwe_tekst = ctx["ruwe_tekst"]

        menu_naam = ctx["menu_naam"]
        bron_type = ctx["bron_type"]
        bron_bestand = ctx.get("bron_bestand")

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

        _sla_gerechten_op(menu, data, org.id)

        db.session.commit()
        session.pop("upload_context", None)
        print(f"[Menu] Menu '{menu_naam}' opgeslagen (id={menu.id}, {bron_type})")

        return redirect(url_for("menu.menu_detail", menu_id=menu.id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij verwerken: {type(e).__name__}: {str(e)}"
        ctx = session.get("upload_context", {})
        return render_template("menu_upload_scan.html", org=org,
                               menu_naam=ctx.get("menu_naam", "Menu"), error=error)


@menu_bp.route("/menu/<int:menu_id>")
@login_required
def menu_detail(menu_id):
    """Toon een geparsed menu met alle categorieën en gerechten."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()
    gerechten = Gerecht.query.filter_by(menu_id=menu.id).all()
    gerecht_id_map = {g.naam.lower().strip(): g.id for g in gerechten}
    voorstel = IngredientVoorstel.query.filter_by(menu_id=menu.id).first()
    return render_template("menu_detail.html", org=org, menu=menu,
                           gerecht_id_map=gerecht_id_map, voorstel=voorstel)


@menu_bp.route("/menu/<int:menu_id>/naam", methods=["POST"])
@login_required
def menu_naam_aanpassen(menu_id):
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()
    nieuwe_naam = request.form.get("naam", "").strip()[:100]
    if nieuwe_naam:
        menu.naam = nieuwe_naam
        db.session.commit()
    return redirect(url_for("menu.menu_detail", menu_id=menu.id))


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

    # Verwijder eerst gerelateerde records zonder cascade
    MenuAnnotatie.query.filter_by(menu_id=menu.id).delete()
    IngredientVoorstel.query.filter_by(menu_id=menu.id).delete()

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
        custom_prompt = request.args.get("custom_prompt", "").strip()[:500]
        return render_template("annotatie_scan.html", org=org, menu=menu, custom_prompt=custom_prompt)

    # POST: genereer annotaties
    try:
        from tools.menu_annotator import annotate_menu

        custom_prompt = request.form.get("custom_prompt", "").strip()[:500]
        annotatie_data = annotate_menu(menu.data, geheugen.data, segment.data, user_instructions=custom_prompt)

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

        # Genereer TOEVOEGEN suggesties en sla op in menu.data
        try:
            from tools.menu_annotator import suggereer_toevoegingen
            toevoegen = suggereer_toevoegingen(menu.data, geheugen.data, segment.data)
            menu_data = dict(menu.data) if menu.data else {}
            menu_data["toevoegen_suggesties"] = toevoegen
            menu.data = menu_data
            db.session.commit()
            print(f"[Annotatie] {len(toevoegen)} toevoeg-suggesties opgeslagen")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Annotatie] Waarschuwing: toevoegingen mislukt: {e}")

        return redirect(url_for("menu.menu_annotaties", menu_id=menu.id))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij annoteren: {type(e).__name__}: {str(e)}"
        return render_template("annotatie_scan.html", org=org, menu=menu, error=error)


@menu_bp.route("/menu/<int:menu_id>/toevoegen/genereer", methods=["POST"])
@login_required
def toevoegen_genereer(menu_id):
    """Genereer nieuwe gerechtsuggesties met optionele focus op trends en eigenschappen."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
    geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

    if not segment or not geheugen or not menu.data:
        return redirect(url_for("menu.menu_annotaties", menu_id=menu.id))

    focus_trends = request.form.getlist("focus_trends")
    focus_eigenschappen = request.form.getlist("focus_eigenschappen")

    try:
        from tools.menu_annotator import suggereer_toevoegingen
        toevoegen = suggereer_toevoegingen(
            menu.data, geheugen.data, segment.data,
            focus_trends=focus_trends,
            focus_eigenschappen=focus_eigenschappen
        )
        menu_data = dict(menu.data)
        menu_data["toevoegen_suggesties"] = toevoegen
        menu.data = menu_data
        db.session.commit()
        print(f"[Toevoegen] {len(toevoegen)} suggesties opgeslagen (trends={focus_trends}, eigenschappen={focus_eigenschappen})")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Toevoegen] Fout: {e}")

    return redirect(url_for("menu.menu_annotaties", menu_id=menu.id))


# --- Slimme suggesties routes ---

@menu_bp.route("/menu/<int:menu_id>/suggesties/genereer", methods=["GET", "POST"])
@login_required
def menu_suggesties_genereer(menu_id):
    """Loading page (GET) + genereer slimme gerecht-suggesties via ingredient analyse (POST)."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    if request.method == "GET":
        return render_template("menu_suggesties_scan.html", org=org, menu=menu)

    try:
        from tools.ingredient_analyzer import analyseer_ingredienten
        from tools.ingredient_suggester import genereer_voorstel

        gerechten = Gerecht.query.filter_by(menu_id=menu.id).all()
        segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()
        geheugen = TrendGeheugen.query.filter_by(organisatie_id=org.id).first()

        analyse = analyseer_ingredienten(gerechten)
        segment_data = segment.data if segment else None
        geheugen_data = geheugen.data if geheugen else None

        voorstellen = genereer_voorstel(analyse, segment_data=segment_data, geheugen_data=geheugen_data)

        # Sla op / overschrijf IngredientVoorstel voor dit menu
        IngredientVoorstel.query.filter_by(menu_id=menu.id).delete()
        voorstel_db = IngredientVoorstel(
            organisatie_id=org.id,
            menu_id=menu.id,
            data=voorstellen,
        )
        db.session.add(voorstel_db)
        db.session.commit()
        print(f"[Suggesties] {len(voorstellen)} suggesties opgeslagen voor menu '{menu.naam}'")

        return redirect(url_for("menu.menu_detail", menu_id=menu.id, _anchor="suggesties"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = f"Fout bij genereren: {type(e).__name__}: {str(e)}"
        return render_template("menu_suggesties_scan.html", org=org, menu=menu, error=error)


@menu_bp.route("/menu/<int:menu_id>/suggestie/toevoegen", methods=["POST"])
@login_required
def menu_suggestie_toevoegen(menu_id):
    """Voeg een voorgesteld gerecht toe aan het menu."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()

    voorstel_db = IngredientVoorstel.query.filter_by(menu_id=menu.id).first_or_404()
    idx = int(request.form.get("voorstel_index", 0))
    voorstellen = list(voorstel_db.data)

    if idx < 0 or idx >= len(voorstellen):
        return redirect(url_for("menu.menu_detail", menu_id=menu.id))

    voorstel_item = voorstellen[idx]
    gerecht_data = voorstel_item.get("gerecht", {})

    naam = request.form.get("naam") or gerecht_data.get("naam", "Nieuw gerecht")
    beschrijving = request.form.get("beschrijving") or gerecht_data.get("beschrijving", "")
    categorie_naam = request.form.get("categorie") or gerecht_data.get("categorie", "Overig")
    prijs_raw = request.form.get("prijs") or gerecht_data.get("prijs_suggestie")
    try:
        prijs = float(prijs_raw) if prijs_raw else None
    except (ValueError, TypeError):
        prijs = None

    ing_namen = [i.get("naam", "") for i in voorstel_item.get("ingredienten", []) if i.get("naam")]

    nieuw_gerecht_data = {
        "naam": naam,
        "beschrijving": beschrijving,
        "prijs": prijs,
        "ingredienten": ing_namen,
        "tags": [],
        "dieet": []
    }

    # Voeg toe aan menu.data
    menu_data = dict(menu.data) if menu.data else {"categorieën": []}
    cat_gevonden = False
    for cat in menu_data.get("categorieën", []):
        if cat.get("naam") == categorie_naam:
            cat.setdefault("gerechten", []).append(nieuw_gerecht_data)
            cat_gevonden = True
            break
    if not cat_gevonden:
        menu_data.setdefault("categorieën", []).append({"naam": categorie_naam, "gerechten": [nieuw_gerecht_data]})
    menu.data = menu_data

    # Nieuw Gerecht record
    nieuw_gerecht = Gerecht(
        menu_id=menu.id,
        organisatie_id=org.id,
        categorie=categorie_naam,
        naam=naam,
        prijs=prijs,
        beschrijving=beschrijving,
        ingredienten=ing_namen,
        tags=[],
        dieet=[]
    )
    db.session.add(nieuw_gerecht)

    # Verwijder dit voorstel uit de lijst
    voorstellen.pop(idx)
    voorstel_db.data = voorstellen
    db.session.commit()
    print(f"[Suggestie] Gerecht '{naam}' toegevoegd aan menu '{menu.naam}'")

    return redirect(url_for("menu.menu_detail", menu_id=menu.id, _anchor="suggesties"))


@menu_bp.route("/menu/<int:menu_id>/gerecht/<int:gerecht_id>/verwijder", methods=["POST"])
@login_required
def menu_gerecht_verwijder(menu_id, gerecht_id):
    """Verwijder een gerecht uit het menu."""
    org = current_user.organisatie
    menu = Menu.query.filter_by(id=menu_id, organisatie_id=org.id).first_or_404()
    gerecht = Gerecht.query.filter_by(id=gerecht_id, menu_id=menu.id).first_or_404()

    # Verwijder annotaties voor dit gerecht
    MenuAnnotatie.query.filter_by(gerecht_id=gerecht.id).delete()

    # Update menu.data
    menu_data = dict(menu.data) if menu.data else {"categorieën": []}
    gerecht_naam = gerecht.naam
    for cat in menu_data.get("categorieën", []):
        cat["gerechten"] = [g for g in cat.get("gerechten", []) if g.get("naam") != gerecht_naam]
    menu_data["categorieën"] = [c for c in menu_data.get("categorieën", []) if c.get("gerechten")]
    menu.data = menu_data

    db.session.delete(gerecht)
    db.session.commit()
    print(f"[Gerecht] '{gerecht_naam}' verwijderd uit menu '{menu.naam}'")

    return redirect(url_for("menu.menu_detail", menu_id=menu.id))
