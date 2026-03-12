"""
tests/test_kassaboek_en_fuzzy.py

Integratietests voor:
1. Kassaboek webhook authenticatie en data validatie (app.py admin toggle + KassaboekEntry model)
2. Kassaboek aggregatie queries (ingredient_routes.py verkoop_data query)
3. Fuzzy matching gerecht_naam → Gerecht (menu_routes.py annotatie logica)
4. Edge cases: leeg menu, geen kassaboek data, geen trends

Gebruikt in-memory SQLite via de conftest app/db fixtures.
"""

import sys
import os
import json
import secrets
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Flask app met in-memory SQLite."""
    import os
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key-dummy")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")

    from app import app as flask_app
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="test-secret-key",
        SERVER_NAME=None,
    )
    return flask_app


@pytest.fixture
def db(app):
    from models import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def org_met_kassaboek(db, app):
    """Organisatie met kassaboek_actief=True en een webhook_api_key."""
    from models import Organisatie
    with app.app_context():
        org = Organisatie(
            naam="Kassaboek Test Restaurant",
            adres="Teststraat 1",
            status="actief",
            kassaboek_actief=True,
            webhook_api_key=secrets.token_hex(32),
        )
        db.session.add(org)
        db.session.commit()
        db.session.refresh(org)
        return org.id, org.webhook_api_key


@pytest.fixture
def org_zonder_kassaboek(db, app):
    """Organisatie met kassaboek_actief=False."""
    from models import Organisatie
    with app.app_context():
        org = Organisatie(
            naam="Geen Kassaboek Restaurant",
            adres="Teststraat 2",
            status="actief",
            kassaboek_actief=False,
        )
        db.session.add(org)
        db.session.commit()
        db.session.refresh(org)
        return org.id


@pytest.fixture
def org_met_gerechten(db, app):
    """Organisatie met menu en gerechten voor fuzzy matching tests."""
    from models import Organisatie, Menu, Gerecht
    with app.app_context():
        org = Organisatie(naam="Fuzzy Test", adres="Fuzzystraat 3", status="actief")
        db.session.add(org)
        db.session.flush()

        menu = Menu(
            organisatie_id=org.id,
            naam="Test Menu",
            bron_type="tekst",
            data={"categorieën": []},
            actief=True,
        )
        db.session.add(menu)
        db.session.flush()

        gerechten_data = [
            ("Caesar Salade", "Voorgerechten"),
            ("Risotto met Paddenstoelen", "Hoofdgerechten"),
            ("Gegrilde Zalm", "Hoofdgerechten"),
            ("Chocolade Mousse", "Desserts"),
        ]
        gerecht_ids = {}
        for naam, cat in gerechten_data:
            g = Gerecht(
                menu_id=menu.id,
                organisatie_id=org.id,
                categorie=cat,
                naam=naam,
                prijs=None,
                ingredienten=[],
            )
            db.session.add(g)
            db.session.flush()
            gerecht_ids[naam] = g.id

        db.session.commit()
        return org.id, menu.id, gerecht_ids


# ---------------------------------------------------------------------------
# 1. KassaboekEntry model — basis CRUD
# ---------------------------------------------------------------------------

class TestKassaboekEntryModel:
    def test_entry_aanmaken_en_ophalen(self, db, app, org_met_kassaboek):
        from models import KassaboekEntry
        org_id, _ = org_met_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 1),
                omzet=1200.0,
                couverts=45,
                gerecht_naam="Caesar Salade",
                aantal_verkocht=12,
            )
            db.session.add(entry)
            db.session.commit()

            gevonden = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 1),
                gerecht_naam="Caesar Salade",
            ).first()
            assert gevonden is not None
            assert gevonden.aantal_verkocht == 12
            assert gevonden.omzet == 1200.0

    def test_unique_constraint_org_datum_gerecht(self, db, app, org_met_kassaboek):
        """Dubbele entry voor zelfde org+datum+gerecht mag niet."""
        from models import KassaboekEntry
        from sqlalchemy.exc import IntegrityError
        org_id, _ = org_met_kassaboek
        with app.app_context():
            e1 = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 2),
                omzet=500.0,
                gerecht_naam="Risotto",
                aantal_verkocht=8,
            )
            e2 = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 2),
                omzet=600.0,
                gerecht_naam="Risotto",
                aantal_verkocht=10,
            )
            db.session.add(e1)
            db.session.flush()
            db.session.add(e2)
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()

    def test_entry_zonder_gerecht_naam_toegestaan(self, db, app, org_met_kassaboek):
        """Kassaboek entry zonder gerecht_naam (omzet-only) mag wel."""
        from models import KassaboekEntry
        org_id, _ = org_met_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 3),
                omzet=2000.0,
                couverts=80,
                gerecht_naam=None,
                aantal_verkocht=None,
            )
            db.session.add(entry)
            db.session.commit()

            gevonden = KassaboekEntry.query.filter_by(
                organisatie_id=org_id, datum=date(2026, 3, 3)
            ).first()
            assert gevonden is not None
            assert gevonden.gerecht_naam is None


# ---------------------------------------------------------------------------
# 2. Kassaboek webhook authenticatie (admin toggle)
# ---------------------------------------------------------------------------

class TestKassaboekWebhookAuth:
    def test_kassaboek_actief_false_by_default(self, db, app, org_zonder_kassaboek):
        from models import Organisatie
        org_id = org_zonder_kassaboek
        with app.app_context():
            org = Organisatie.query.get(org_id)
            assert org.kassaboek_actief is False
            assert org.webhook_api_key is None

    def test_kassaboek_actief_true_heeft_api_key(self, db, app, org_met_kassaboek):
        from models import Organisatie
        org_id, api_key = org_met_kassaboek
        with app.app_context():
            org = Organisatie.query.get(org_id)
            assert org.kassaboek_actief is True
            assert org.webhook_api_key is not None
            assert len(org.webhook_api_key) == 64  # 32 bytes hex = 64 chars

    def test_api_key_is_uniek_per_org(self, db, app):
        from models import Organisatie
        with app.app_context():
            org1 = Organisatie(naam="Org1", adres="A1", status="actief",
                               kassaboek_actief=True, webhook_api_key=secrets.token_hex(32))
            org2 = Organisatie(naam="Org2", adres="A2", status="actief",
                               kassaboek_actief=True, webhook_api_key=secrets.token_hex(32))
            db.session.add_all([org1, org2])
            db.session.commit()
            assert org1.webhook_api_key != org2.webhook_api_key

    def test_kassaboek_data_lookup_via_api_key(self, db, app, org_met_kassaboek):
        """Simuleer webhook-auth: zoek org op via webhook_api_key."""
        from models import Organisatie
        org_id, api_key = org_met_kassaboek
        with app.app_context():
            org = Organisatie.query.filter_by(webhook_api_key=api_key).first()
            assert org is not None
            assert org.id == org_id

    def test_ongeldige_api_key_geeft_geen_org(self, db, app):
        from models import Organisatie
        with app.app_context():
            org = Organisatie.query.filter_by(webhook_api_key="ongeldige_key_xyz").first()
            assert org is None


# ---------------------------------------------------------------------------
# 3. Kassaboek data validatie
# ---------------------------------------------------------------------------

class TestKassaboekDataValidatie:
    def test_datum_is_verplicht(self, db, app, org_met_kassaboek):
        from models import KassaboekEntry
        from sqlalchemy.exc import IntegrityError
        org_id, _ = org_met_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=None,  # verplicht veld
                omzet=100.0,
            )
            db.session.add(entry)
            with pytest.raises((IntegrityError, Exception)):
                db.session.flush()
            db.session.rollback()

    def test_omzet_kan_float_zijn(self, db, app, org_met_kassaboek):
        from models import KassaboekEntry
        org_id, _ = org_met_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 10),
                omzet=1234.56,
                gerecht_naam=None,
            )
            db.session.add(entry)
            db.session.commit()
            gevonden = KassaboekEntry.query.filter_by(
                organisatie_id=org_id, datum=date(2026, 3, 10)
            ).first()
            assert abs(gevonden.omzet - 1234.56) < 0.01

    def test_aantal_verkocht_kan_nul_zijn(self, db, app, org_met_kassaboek):
        from models import KassaboekEntry
        org_id, _ = org_met_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 11),
                omzet=0.0,
                gerecht_naam="Soep",
                aantal_verkocht=0,
            )
            db.session.add(entry)
            db.session.commit()
            gevonden = KassaboekEntry.query.filter_by(
                organisatie_id=org_id, datum=date(2026, 3, 11), gerecht_naam="Soep"
            ).first()
            assert gevonden.aantal_verkocht == 0


# ---------------------------------------------------------------------------
# 4. Kassaboek aggregatie query (ingredient_routes logica)
# ---------------------------------------------------------------------------

class TestKassaboekAggregatie:
    def _vul_kassaboek(self, db, app, org_id, gerechten_verkoop):
        """Helper: schrijf testsales voor de afgelopen 4 weken."""
        from models import KassaboekEntry
        with app.app_context():
            vandaag = date.today()
            for dag_offset in range(28):
                dag = vandaag - timedelta(days=dag_offset)
                for gerecht_naam, per_dag in gerechten_verkoop.items():
                    entry = KassaboekEntry(
                        organisatie_id=org_id,
                        datum=dag,
                        omzet=per_dag * 15.0,
                        gerecht_naam=gerecht_naam,
                        aantal_verkocht=per_dag,
                    )
                    db.session.add(entry)
            db.session.commit()

    def test_gemiddeld_verkocht_per_gerecht(self, db, app, org_met_kassaboek):
        from models import KassaboekEntry
        from sqlalchemy import func
        org_id, _ = org_met_kassaboek
        self._vul_kassaboek(db, app, org_id, {"Risotto": 5, "Caesar Salade": 10})

        with app.app_context():
            vier_weken_geleden = date.today() - timedelta(weeks=4)
            verkoop = db.session.query(
                KassaboekEntry.gerecht_naam,
                func.avg(KassaboekEntry.aantal_verkocht).label("gem")
            ).filter(
                KassaboekEntry.organisatie_id == org_id,
                KassaboekEntry.datum >= vier_weken_geleden,
                KassaboekEntry.gerecht_naam.isnot(None),
            ).group_by(KassaboekEntry.gerecht_naam).all()

            verkoop_dict = {v.gerecht_naam: v.gem for v in verkoop}
            assert "Risotto" in verkoop_dict
            assert "Caesar Salade" in verkoop_dict
            assert abs(verkoop_dict["Risotto"] - 5.0) < 0.1
            assert abs(verkoop_dict["Caesar Salade"] - 10.0) < 0.1

    def test_wekelijkse_omloop_berekening(self, db, app, org_met_kassaboek):
        """gem_per_dag * 7 = wekelijkse omloop (zoals in ingredient_routes.py)."""
        from models import KassaboekEntry
        from sqlalchemy import func
        org_id, _ = org_met_kassaboek
        self._vul_kassaboek(db, app, org_id, {"Pasta": 3})

        with app.app_context():
            vier_weken_geleden = date.today() - timedelta(weeks=4)
            verkoop = db.session.query(
                KassaboekEntry.gerecht_naam,
                func.avg(KassaboekEntry.aantal_verkocht).label("gem")
            ).filter(
                KassaboekEntry.organisatie_id == org_id,
                KassaboekEntry.datum >= vier_weken_geleden,
                KassaboekEntry.gerecht_naam.isnot(None),
            ).group_by(KassaboekEntry.gerecht_naam).all()

            verkoop_data = {v.gerecht_naam: round(v.gem * 7, 1) for v in verkoop}
            # 3 per dag * 7 = 21 per week
            assert abs(verkoop_data["Pasta"] - 21.0) < 0.5

    def test_geen_kassaboek_data_geeft_leeg_resultaat(self, db, app):
        from models import Organisatie, KassaboekEntry
        from sqlalchemy import func
        with app.app_context():
            org = Organisatie(naam="Leeg Kassaboek", adres="Leeg 1", status="actief")
            db.session.add(org)
            db.session.commit()

            vier_weken_geleden = date.today() - timedelta(weeks=4)
            verkoop = db.session.query(
                KassaboekEntry.gerecht_naam,
                func.avg(KassaboekEntry.aantal_verkocht).label("gem")
            ).filter(
                KassaboekEntry.organisatie_id == org.id,
                KassaboekEntry.datum >= vier_weken_geleden,
                KassaboekEntry.gerecht_naam.isnot(None),
            ).group_by(KassaboekEntry.gerecht_naam).all()

            assert verkoop == []

    def test_data_buiten_4_weken_niet_meegenomen(self, db, app, org_met_kassaboek):
        """Entries ouder dan 4 weken worden niet opgenomen in de aggregatie."""
        from models import KassaboekEntry
        from sqlalchemy import func
        org_id, _ = org_met_kassaboek
        with app.app_context():
            oud = date.today() - timedelta(weeks=5)
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=oud,
                omzet=500.0,
                gerecht_naam="Oud Gerecht",
                aantal_verkocht=99,
            )
            db.session.add(entry)
            db.session.commit()

            vier_weken_geleden = date.today() - timedelta(weeks=4)
            verkoop = db.session.query(
                KassaboekEntry.gerecht_naam,
                func.avg(KassaboekEntry.aantal_verkocht).label("gem")
            ).filter(
                KassaboekEntry.organisatie_id == org_id,
                KassaboekEntry.datum >= vier_weken_geleden,
                KassaboekEntry.gerecht_naam.isnot(None),
            ).group_by(KassaboekEntry.gerecht_naam).all()

            namen = [v.gerecht_naam for v in verkoop]
            assert "Oud Gerecht" not in namen


# ---------------------------------------------------------------------------
# 5. Fuzzy matching gerecht_naam → Gerecht model
# ---------------------------------------------------------------------------

class TestFuzzyMatchingGerechten:
    """
    Test de fuzzy matching logica uit menu_routes.py annotatie flow.
    De lookup logica: exact match → substring match → skip.
    """

    def _bouw_lookup(self, gerechten):
        """Bouw gerecht_lookup zoals menu_routes.py dat doet."""
        lookup = {}
        for g in gerechten:
            lookup[g.naam.lower().strip()] = g
        return lookup

    def _fuzzy_find(self, gerecht_naam, lookup):
        """Replica van de fuzzy match logica uit menu_routes.py."""
        naam_lower = gerecht_naam.lower().strip()
        # Exact match
        if naam_lower in lookup:
            return lookup[naam_lower]
        # Substring match
        for key, g in lookup.items():
            if naam_lower in key or key in naam_lower:
                return g
        return None

    def test_exacte_match_werkt(self, db, app, org_met_gerechten):
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("Caesar Salade", lookup)
            assert result is not None
            assert result.naam == "Caesar Salade"

    def test_exacte_match_case_insensitive(self, db, app, org_met_gerechten):
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("caesar salade", lookup)
            assert result is not None
            assert result.naam == "Caesar Salade"

    def test_substring_match_verkort(self, db, app, org_met_gerechten):
        """'Risotto' matcht op 'Risotto met Paddenstoelen'."""
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("Risotto", lookup)
            assert result is not None
            assert "Risotto" in result.naam

    def test_substring_match_uitgebreid(self, db, app, org_met_gerechten):
        """'Gegrilde Zalm op Spinazie' matcht op 'Gegrilde Zalm' via substring."""
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("Gegrilde Zalm op Spinazie", lookup)
            assert result is not None
            assert "Zalm" in result.naam

    def test_geen_match_geeft_none(self, db, app, org_met_gerechten):
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("Compleet Onbekend Gerecht XYZ", lookup)
            assert result is None

    def test_lege_naam_geeft_geen_crash(self, db, app, org_met_gerechten):
        from models import Gerecht
        org_id, menu_id, _ = org_met_gerechten
        with app.app_context():
            gerechten = Gerecht.query.filter_by(menu_id=menu_id).all()
            lookup = self._bouw_lookup(gerechten)
            result = self._fuzzy_find("", lookup)
            # Lege string is substring van alles — dit is OK als het een gerecht oplevert
            # maar mag zeker niet crashen
            # (gedrag: "" in "caesar salade" → True → eerste item in lookup)
            # We checken alleen dat er geen exception is
            assert True  # geen crash

    def test_lookup_met_leeg_menu(self):
        """Lege gerechtenlijst → lege lookup → altijd None."""
        lookup = self._bouw_lookup([])
        result = self._fuzzy_find("Caesar Salade", lookup)
        assert result is None


# ---------------------------------------------------------------------------
# 6. Edge cases: leeg menu, geen kassaboek, geen trends
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_analyseer_ingredienten_leeg_menu(self):
        """analyseer_ingredienten met lege lijst crasht niet."""
        from tools.ingredient_analyzer import analyseer_ingredienten
        result = analyseer_ingredienten([])
        assert result["ingredienten"] == []
        assert result["synergie_score"] == 0
        assert result["statistieken"]["totaal_uniek"] == 0

    def test_analyseer_ingredienten_zonder_kassaboek(self):
        """Zonder verkoop_data: geschatte_omloop.beschikbaar == False."""
        from tools.ingredient_analyzer import analyseer_ingredienten
        from types import SimpleNamespace
        gerechten = [
            SimpleNamespace(naam="Soep", ingredienten=[
                {"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"}
            ])
        ]
        result = analyseer_ingredienten(gerechten, verkoop_data=None)
        prei = result["ingredienten"][0]
        assert prei["geschatte_omloop"]["beschikbaar"] is False
        assert prei["geschatte_omloop"]["label"] == "N/B"

    def test_genereer_voorstel_zonder_risico_ingredienten(self):
        """genereer_voorstel werkt ook als er geen risico-ingrediënten zijn."""
        from tools.ingredient_suggester import genereer_voorstel
        analyse = {
            "ingredienten": [],
            "statistieken": {"risico_ingredienten": []},
            "synergie_score": 0,
        }
        result = genereer_voorstel(analyse)
        assert "gerecht" in result
        assert isinstance(result["synergie_check"]["hergebruikte_risico"], list)

    def test_kassaboek_entry_voor_inactieve_org(self, db, app, org_zonder_kassaboek):
        """KassaboekEntry kan worden aangemaakt ook als kassaboek_actief=False (model-niveau)."""
        from models import KassaboekEntry
        org_id = org_zonder_kassaboek
        with app.app_context():
            entry = KassaboekEntry(
                organisatie_id=org_id,
                datum=date(2026, 3, 5),
                omzet=300.0,
                gerecht_naam="Soep",
                aantal_verkocht=5,
            )
            db.session.add(entry)
            db.session.commit()
            assert KassaboekEntry.query.filter_by(organisatie_id=org_id).count() >= 1

    def test_ingredient_voorstel_model_aanmaken(self, db, app):
        """IngredientVoorstel kan worden aangemaakt en opgehaald."""
        from models import Organisatie, Menu, IngredientVoorstel
        with app.app_context():
            org = Organisatie(naam="Voorstel Org", adres="V1", status="actief")
            db.session.add(org)
            db.session.flush()
            menu = Menu(
                organisatie_id=org.id,
                naam="Test",
                bron_type="tekst",
                data={"categorieën": []},
                actief=True,
            )
            db.session.add(menu)
            db.session.flush()

            voorstel_data = {
                "gerecht": {"naam": "Test Risotto", "prijs_suggestie": 18.0},
                "ingredienten": [],
                "synergie_check": {"bestaand_percentage": 75},
            }
            voorstel = IngredientVoorstel(
                organisatie_id=org.id,
                menu_id=menu.id,
                data=voorstel_data,
                status="nieuw",
            )
            db.session.add(voorstel)
            db.session.commit()

            gevonden = IngredientVoorstel.query.filter_by(organisatie_id=org.id).first()
            assert gevonden is not None
            assert gevonden.status == "nieuw"
            assert gevonden.data["gerecht"]["naam"] == "Test Risotto"

    def test_ingredient_voorstel_status_update(self, db, app):
        """IngredientVoorstel status kan worden bijgewerkt naar geaccepteerd."""
        from models import Organisatie, Menu, IngredientVoorstel
        with app.app_context():
            org = Organisatie(naam="Status Org", adres="S1", status="actief")
            db.session.add(org)
            db.session.flush()
            menu = Menu(
                organisatie_id=org.id, naam="M", bron_type="tekst",
                data={"categorieën": []}, actief=True,
            )
            db.session.add(menu)
            db.session.flush()
            voorstel = IngredientVoorstel(
                organisatie_id=org.id, menu_id=menu.id,
                data={"gerecht": {}}, status="nieuw",
            )
            db.session.add(voorstel)
            db.session.commit()

            voorstel.status = "geaccepteerd"
            db.session.commit()

            bijgewerkt = IngredientVoorstel.query.get(voorstel.id)
            assert bijgewerkt.status == "geaccepteerd"
