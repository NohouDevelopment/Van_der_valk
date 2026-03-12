"""
Segment Blueprint — bekijken en bewerken van het menusegment-profiel.

Routes:
  /segment/          — Overzicht van het huidige menusegment
  /segment/bewerken  — Menusegment aanpassen via checkbox-grids
"""

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from models import db, MenuSegment

segment_bp = Blueprint("segment", __name__)


@segment_bp.route("/segment/")
@login_required
def segment_overzicht():
    """Toon het huidige menusegment-profiel."""
    org = current_user.organisatie
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()

    if not segment:
        return render_template("segment.html", org=org, segment=None, profiel=None)

    return render_template("segment.html", org=org, segment=segment, profiel=segment.data)


@segment_bp.route("/segment/bewerken", methods=["GET", "POST"])
@login_required
def segment_bewerken():
    """Bewerk het menusegment-profiel via checkbox-grids."""
    org = current_user.organisatie
    segment = MenuSegment.query.filter_by(organisatie_id=org.id).first()

    if not segment:
        return redirect(url_for("segment.segment_overzicht"))

    if request.method == "POST":
        from onboarding import _verwerk_approve_form
        profiel_data = _verwerk_approve_form(request, segment.data)
        segment.data = profiel_data
        db.session.commit()
        return redirect(url_for("segment.segment_overzicht"))

    return render_template("onboarding_approve.html",
                           profiel=segment.data,
                           naam=org.naam,
                           adres=org.adres,
                           bewerk_modus=True)
