"""
Database models voor het Menu Maker platform.

Multi-tenant: meerdere organisaties (restaurants/ketens) met eigen gebruikers,
menu's, segmentanalyses, trendgeheugen en annotaties.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Organisatie(db.Model):
    """Een restaurant of keten die het platform gebruikt."""
    __tablename__ = "organisaties"

    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(200), nullable=False)
    adres = db.Column(db.String(300))
    website_url = db.Column(db.String(500))
    logo_pad = db.Column(db.String(300))
    beschrijving = db.Column(db.Text)
    status = db.Column(db.String(20), default="onboarding")
    kassaboek_actief = db.Column(db.Boolean, default=False, nullable=False)
    webhook_api_key = db.Column(db.String(64), unique=True, nullable=True)
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    gebruikers = db.relationship("Gebruiker", backref="organisatie", lazy=True)
    menu_segment = db.relationship("MenuSegment", backref="organisatie", uselist=False, lazy=True)
    menus = db.relationship("Menu", backref="organisatie", lazy=True)
    trend_analyses = db.relationship("TrendAnalyse", backref="organisatie", lazy=True)
    trend_geheugen = db.relationship("TrendGeheugen", backref="organisatie", uselist=False, lazy=True)
    trend_config = db.relationship("TrendConfig", backref="organisatie", uselist=False, lazy=True)
    kassaboek = db.relationship("KassaboekEntry", backref="organisatie", lazy=True)
    ingredient_voorstellen = db.relationship("IngredientVoorstel", backref="organisatie", lazy=True)

    def __repr__(self):
        return f"<Organisatie {self.naam}>"


class Gebruiker(db.Model, UserMixin):
    """Een gebruiker van het platform, gekoppeld aan een organisatie."""
    __tablename__ = "gebruikers"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    naam = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    wachtwoord_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), default="gebruiker")
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_wachtwoord(self, wachtwoord: str):
        self.wachtwoord_hash = generate_password_hash(wachtwoord)

    def check_wachtwoord(self, wachtwoord: str) -> bool:
        return check_password_hash(self.wachtwoord_hash, wachtwoord)

    def __repr__(self):
        return f"<Gebruiker {self.email}>"


class Menu(db.Model):
    """Een geupload en geparsed menu."""
    __tablename__ = "menus"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    naam = db.Column(db.String(200))
    bron_type = db.Column(db.String(20))  # 'pdf' | 'tekst' | 'afbeelding'
    bron_bestand = db.Column(db.String(300))
    ruwe_tekst = db.Column(db.Text)
    data = db.Column(db.JSON, nullable=False)
    actief = db.Column(db.Boolean, default=True)
    geupload_door = db.Column(db.Integer, db.ForeignKey("gebruikers.id"))
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    gerechten = db.relationship("Gerecht", backref="menu", cascade="all, delete-orphan", lazy=True)
    annotaties = db.relationship("MenuAnnotatie", backref="menu", lazy=True)
    ingredient_voorstellen = db.relationship("IngredientVoorstel", backref="menu", lazy=True)

    def __repr__(self):
        return f"<Menu {self.naam} org={self.organisatie_id}>"


class Gerecht(db.Model):
    """Individueel gerecht, gedenormaliseerd uit Menu.data voor queries."""
    __tablename__ = "gerechten"

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=False)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    categorie = db.Column(db.String(100))
    naam = db.Column(db.String(200), nullable=False)
    prijs = db.Column(db.Float)
    beschrijving = db.Column(db.Text)
    ingredienten = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    dieet = db.Column(db.JSON)

    annotaties = db.relationship("MenuAnnotatie", backref="gerecht", lazy=True)

    def __repr__(self):
        return f"<Gerecht {self.naam}>"


class MenuSegment(db.Model):
    """Keten-analyse profiel: waardepropositie, doelgroep, positionering."""
    __tablename__ = "menu_segmenten"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False)
    goedgekeurd_door = db.Column(db.Integer, db.ForeignKey("gebruikers.id"))
    goedgekeurd_op = db.Column(db.DateTime)
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MenuSegment org={self.organisatie_id}>"


class TrendAnalyse(db.Model):
    """Een enkele trendanalyse-run met resultaten."""
    __tablename__ = "trend_analyses"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    gegenereerd_door = db.Column(db.Integer, db.ForeignKey("gebruikers.id"))
    gegenereerd_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    config_snapshot = db.Column(db.JSON)
    data = db.Column(db.JSON, nullable=False)
    bronnen = db.Column(db.JSON)
    versie = db.Column(db.Integer, default=1)

    def __repr__(self):
        return f"<TrendAnalyse org={self.organisatie_id} v={self.versie}>"


class TrendGeheugen(db.Model):
    """Gecombineerd trendgeheugen dat evolueert over meerdere analyses."""
    __tablename__ = "trend_geheugens"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False)
    versie = db.Column(db.Integer, default=1)
    vorige_data = db.Column(db.JSON)
    laatst_bijgewerkt = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TrendGeheugen org={self.organisatie_id} v={self.versie}>"


class TrendConfig(db.Model):
    """Configureerbare prompt-elementen voor trendanalyse."""
    __tablename__ = "trend_configs"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False)
    aangepast_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TrendConfig org={self.organisatie_id}>"


class MenuAnnotatie(db.Model):
    """Trend-annotatie per gerecht: status, score, opmerkingen."""
    __tablename__ = "menu_annotaties"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=False)
    gerecht_id = db.Column(db.Integer, db.ForeignKey("gerechten.id"), nullable=False)
    trend_geheugen_versie = db.Column(db.Integer)
    status = db.Column(db.String(20))
    score = db.Column(db.Float)
    data = db.Column(db.JSON, nullable=False)
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MenuAnnotatie gerecht={self.gerecht_id} status={self.status}>"


class KassaboekEntry(db.Model):
    """Verkoopcijfers per dag/gerecht (toekomst)."""
    __tablename__ = "kassaboek"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    omzet = db.Column(db.Float)
    couverts = db.Column(db.Integer)
    gerecht_naam = db.Column(db.String(200))
    aantal_verkocht = db.Column(db.Integer)

    __table_args__ = (
        db.UniqueConstraint("organisatie_id", "datum", "gerecht_naam", name="uq_kassaboek_org_datum_gerecht"),
    )

    def __repr__(self):
        return f"<KassaboekEntry org={self.organisatie_id} datum={self.datum}>"


class IngredientVoorstel(db.Model):
    """Opgeslagen AI ingredient-voorstel, inclusief synergie-check resultaat."""
    __tablename__ = "ingredient_voorstellen"

    id = db.Column(db.Integer, primary_key=True)
    organisatie_id = db.Column(db.Integer, db.ForeignKey("organisaties.id"), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=False)
    data = db.Column(db.JSON, nullable=False)  # volledig voorstel incl synergie_check
    status = db.Column(db.String(20), default="nieuw")  # nieuw | geaccepteerd | afgewezen
    aangemaakt_op = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<IngredientVoorstel org={self.organisatie_id} status={self.status}>"
