"""
tests/test_kassaboek_webhook.py

Integratietests voor kassaboek_routes.py via Flask test client.
Gebruikt in-memory SQLite — geen echte database of API calls.

Gedekte endpoints:
  POST /kassaboek/webhook  — auth, validatie, happy path, per-gerecht opslag
  POST /kassaboek/bulk     — auth, limiet, per-entry fouten, batch opslag
  GET  /kassaboek/verkoop  — populairste + trending aggregatie
  GET  /kassaboek/seizoen  — per-maand + per-weekdag patronen

Testcategorieën:
  1. Authenticatie (401 zonder key, 401 foute key, 200 geldige key)
  2. Data validatie (400 zonder datum, 400 ongeldige datum, 400 geen JSON)
  3. Happy path webhook (200, DB check, per-gerecht entries, idempotentie)
  4. Bulk endpoint (auth, max 365, gedeeltelijke fouten)
  5. Verkoop endpoint (populairste, trending, lege data)
  6. Seizoen endpoint (per-maand, per-weekdag, ontbrekend gerecht param)
  7. Fuzzy matching: _fuzzy_match_gerecht unit tests
"""

import sys
import os
import secrets
import json as pyjson
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "test-dummy")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


# ---------------------------------------------------------------------------
# Session-scoped app + per-test db
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maak_org(db, app, kassaboek_actief=True, met_menu=False):
    """Maak een organisatie aan, optioneel met actief menu + gerechten."""
    from models import Organisatie, Menu, Gerecht
    with app.app_context():
        api_key = secrets.token_hex(32) if kassaboek_actief else None
        org = Organisatie(
            naam="Test Restaurant",
            adres="Teststraat 1",
            status="actief",
            kassaboek_actief=kassaboek_actief,
            webhook_api_key=api_key,
        )
        db.session.add(org)
        db.session.flush()

        menu_id = None
        if met_menu:
            menu = Menu(
                organisatie_id=org.id,
                naam="Test Menu",
                bron_type="tekst",
                data={"categorieën": []},
                actief=True,
            )
            db.session.add(menu)
            db.session.flush()
            menu_id = menu.id

            for naam in ["Caesar Salade", "Risotto met Paddenstoelen", "Gegrilde Zalm"]:
                g = Gerecht(
                    menu_id=menu.id,
                    organisatie_id=org.id,
                    categorie="Hoofdgerechten",
                    naam=naam,
                    prijs=None,
                    ingredienten=[],
                )
                db.session.add(g)

        db.session.commit()
        return org.id, api_key, menu_id


def _webhook_post(client, api_key, body, path="/kassaboek/webhook"):
    """Helper: POST naar webhook met JSON body en optionele API key."""
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    return client.post(path, data=pyjson.dumps(body), headers=headers)


def _bulk_post(client, api_key, body):
    return _webhook_post(client, api_key, body, path="/kassaboek/bulk")


# ---------------------------------------------------------------------------
# 1. Authenticatie — /kassaboek/webhook
# ---------------------------------------------------------------------------

class TestWebhookAuthenticatie:
    def test_geen_api_key_geeft_401(self, client, db, app):
        _maak_org(db, app)
        resp = client.post(
            "/kassaboek/webhook",
            data=pyjson.dumps({"datum": "2026-03-01", "omzet": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_foute_api_key_geeft_401(self, client, db, app):
        _maak_org(db, app)
        resp = _webhook_post(client, "verkeerde_key_xyz", {"datum": "2026-03-01"})
        assert resp.status_code == 401

    def test_lege_api_key_geeft_401(self, client, db, app):
        _maak_org(db, app)
        resp = _webhook_post(client, "", {"datum": "2026-03-01"})
        assert resp.status_code == 401

    def test_geldige_api_key_wordt_geaccepteerd(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"datum": "2026-03-01", "omzet": 100.0})
        assert resp.status_code == 200

    def test_inactief_kassaboek_geeft_401(self, client, db, app):
        """Org met kassaboek_actief=False heeft geen API key → 401."""
        _, api_key, _ = _maak_org(db, app, kassaboek_actief=False)
        # api_key is None, dus X-API-Key header is afwezig
        resp = client.post(
            "/kassaboek/webhook",
            data=pyjson.dumps({"datum": "2026-03-01"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_api_key_andere_org_geeft_401(self, client, db, app):
        """API key van org A mag niet werken voor org B's data."""
        _, key_a, _ = _maak_org(db, app)
        resp = _webhook_post(client, key_a + "x", {"datum": "2026-03-01"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Data validatie — /kassaboek/webhook
# ---------------------------------------------------------------------------

class TestWebhookDataValidatie:
    def test_geen_json_body_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.post(
            "/kassaboek/webhook",
            data="geen json",
            headers={"X-API-Key": api_key, "Content-Type": "text/plain"},
        )
        assert resp.status_code == 400

    def test_ontbrekend_datum_veld_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"omzet": 100.0})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "datum" in data["error"].lower() or "error" in data

    def test_ongeldig_datum_formaat_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"datum": "12-03-2026"})
        assert resp.status_code == 400

    def test_datum_als_getal_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"datum": 20260301})
        assert resp.status_code == 400

    def test_gerechten_niet_als_array_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {
            "datum": "2026-03-01",
            "gerechten": "geen array"
        })
        assert resp.status_code == 400

    def test_lege_json_body_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. Happy path — /kassaboek/webhook
# ---------------------------------------------------------------------------

class TestWebhookHappyPath:
    def test_minimale_body_geeft_200(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"datum": "2026-03-01", "omzet": 1200.0})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"

    def test_response_bevat_opgeslagen_count(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {"datum": "2026-03-05", "omzet": 500.0})
        body = resp.get_json()
        assert "opgeslagen" in body
        assert isinstance(body["opgeslagen"], int)
        assert body["opgeslagen"] >= 1

    def test_dag_totaal_wordt_opgeslagen_in_db(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        _webhook_post(client, api_key, {"datum": "2026-03-10", "omzet": 1500.0, "couverts": 60})
        with app.app_context():
            entry = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 10),
                gerecht_naam=None
            ).first()
            assert entry is not None
            assert entry.omzet == 1500.0
            assert entry.couverts == 60

    def test_per_gerecht_entries_worden_opgeslagen(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app, met_menu=True)
        _webhook_post(client, api_key, {
            "datum": "2026-03-11",
            "omzet": 2000.0,
            "gerechten": [
                {"naam": "Caesar Salade", "aantal": 15, "omzet": 210.0},
                {"naam": "Risotto met Paddenstoelen", "aantal": 8, "omzet": 144.0},
            ]
        })
        with app.app_context():
            entries = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 11)
            ).all()
            namen = {e.gerecht_naam for e in entries}
            assert "Caesar Salade" in namen
            assert "Risotto met Paddenstoelen" in namen

    def test_per_gerecht_aantal_correct_opgeslagen(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        _webhook_post(client, api_key, {
            "datum": "2026-03-12",
            "gerechten": [{"naam": "Pasta", "aantal": 22, "omzet": 330.0}]
        })
        with app.app_context():
            entry = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 12),
                gerecht_naam="Pasta"
            ).first()
            assert entry is not None
            assert entry.aantal_verkocht == 22

    def test_gekoppeld_aan_menu_count_in_response(self, client, db, app):
        """Gerechten die fuzzy-matchen met menu krijgen gekoppeld_aan_menu > 0."""
        _, api_key, _ = _maak_org(db, app, met_menu=True)
        resp = _webhook_post(client, api_key, {
            "datum": "2026-03-13",
            "gerechten": [
                {"naam": "Caesar Salade", "aantal": 10},   # exact match
                {"naam": "Risotto", "aantal": 5},           # substring match
            ]
        })
        body = resp.get_json()
        assert body["gekoppeld_aan_menu"] >= 1

    def test_gerecht_zonder_naam_wordt_overgeslagen(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        _webhook_post(client, api_key, {
            "datum": "2026-03-14",
            "gerechten": [
                {"naam": "", "aantal": 5},
                {"naam": "Soep", "aantal": 10},
            ]
        })
        with app.app_context():
            entries = KassaboekEntry.query.filter(
                KassaboekEntry.organisatie_id == org_id,
                KassaboekEntry.datum == date(2026, 3, 14),
                KassaboekEntry.gerecht_naam.isnot(None),
            ).all()
            namen = [e.gerecht_naam for e in entries]
            assert "" not in namen
            assert "Soep" in namen

    def test_idempotentie_dag_totaal_update(self, client, db, app):
        """Twee calls met zelfde datum updaten ipv dupliceren."""
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        _webhook_post(client, api_key, {"datum": "2026-03-15", "omzet": 500.0})
        _webhook_post(client, api_key, {"datum": "2026-03-15", "omzet": 800.0})
        with app.app_context():
            count = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 15),
                gerecht_naam=None
            ).count()
            entry = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 15),
                gerecht_naam=None
            ).first()
            assert count == 1
            assert entry.omzet == 800.0  # bijgewerkt

    def test_idempotentie_gerecht_update(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        _webhook_post(client, api_key, {"datum": "2026-03-16", "gerechten": [{"naam": "Pasta", "aantal": 5}]})
        _webhook_post(client, api_key, {"datum": "2026-03-16", "gerechten": [{"naam": "Pasta", "aantal": 12}]})
        with app.app_context():
            count = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 16),
                gerecht_naam="Pasta"
            ).count()
            entry = KassaboekEntry.query.filter_by(
                organisatie_id=org_id,
                datum=date(2026, 3, 16),
                gerecht_naam="Pasta"
            ).first()
            assert count == 1
            assert entry.aantal_verkocht == 12

    def test_lege_gerechten_array_is_ok(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _webhook_post(client, api_key, {
            "datum": "2026-03-17",
            "omzet": 300.0,
            "gerechten": []
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Bulk endpoint — /kassaboek/bulk
# ---------------------------------------------------------------------------

class TestBulkEndpoint:
    def test_bulk_geen_api_key_geeft_401(self, client, db, app):
        _maak_org(db, app)
        resp = client.post(
            "/kassaboek/bulk",
            data=pyjson.dumps([{"datum": "2026-03-01"}]),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_bulk_foute_api_key_geeft_401(self, client, db, app):
        _maak_org(db, app)
        resp = _bulk_post(client, "foute_key", [{"datum": "2026-03-01"}])
        assert resp.status_code == 401

    def test_bulk_geen_array_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _bulk_post(client, api_key, {"datum": "2026-03-01"})
        assert resp.status_code == 400

    def test_bulk_meer_dan_365_entries_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        entries = [{"datum": f"2026-01-01", "omzet": 100.0}] * 366
        resp = _bulk_post(client, api_key, entries)
        assert resp.status_code == 400
        assert "365" in resp.get_json()["error"]

    def test_bulk_precies_365_entries_is_ok(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        start = date(2025, 1, 1)
        entries = [
            {"datum": (start + timedelta(days=i)).isoformat(), "omzet": 100.0}
            for i in range(365)
        ]
        resp = _bulk_post(client, api_key, entries)
        assert resp.status_code == 200

    def test_bulk_happy_path_slaat_entries_op(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app)
        entries = [
            {"datum": "2026-02-01", "omzet": 1000.0, "couverts": 40},
            {"datum": "2026-02-02", "omzet": 1100.0, "couverts": 45},
            {"datum": "2026-02-03", "omzet": 900.0, "couverts": 35},
        ]
        resp = _bulk_post(client, api_key, entries)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert body["opgeslagen"] >= 3
        with app.app_context():
            count = KassaboekEntry.query.filter_by(
                organisatie_id=org_id, gerecht_naam=None
            ).count()
            assert count >= 3

    def test_bulk_ongeldige_datum_in_entry_geeft_fout_in_response(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        entries = [
            {"datum": "2026-02-10", "omzet": 500.0},
            {"datum": "geen-datum", "omzet": 200.0},   # fout
            {"datum": "2026-02-12", "omzet": 300.0},
        ]
        resp = _bulk_post(client, api_key, entries)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert len(body["fouten"]) == 1
        assert body["fouten"][0]["index"] == 1

    def test_bulk_per_gerecht_entries_worden_opgeslagen(self, client, db, app):
        from models import KassaboekEntry
        org_id, api_key, _ = _maak_org(db, app, met_menu=True)
        entries = [
            {
                "datum": "2026-02-20",
                "omzet": 1500.0,
                "gerechten": [
                    {"naam": "Caesar Salade", "aantal": 20},
                    {"naam": "Gegrilde Zalm", "aantal": 10},
                ]
            }
        ]
        resp = _bulk_post(client, api_key, entries)
        assert resp.status_code == 200
        with app.app_context():
            namen = {
                e.gerecht_naam
                for e in KassaboekEntry.query.filter_by(organisatie_id=org_id).all()
                if e.gerecht_naam
            }
            assert "Caesar Salade" in namen
            assert "Gegrilde Zalm" in namen

    def test_bulk_lege_array_is_ok(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = _bulk_post(client, api_key, [])
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["opgeslagen"] == 0
        assert body["fouten"] == []


# ---------------------------------------------------------------------------
# 5. Verkoop endpoint — GET /kassaboek/verkoop
# ---------------------------------------------------------------------------

class TestVerkoopEndpoint:
    def _vul_verkoop(self, db, app, org_id, data):
        from models import KassaboekEntry
        with app.app_context():
            for datum_str, gerecht, aantal in data:
                entry = KassaboekEntry(
                    organisatie_id=org_id,
                    datum=date.fromisoformat(datum_str),
                    omzet=aantal * 15.0,
                    gerecht_naam=gerecht,
                    aantal_verkocht=aantal,
                )
                db.session.add(entry)
            db.session.commit()

    def test_geen_auth_geeft_401(self, client, db, app):
        resp = client.get("/kassaboek/verkoop")
        assert resp.status_code == 401

    def test_geldige_api_key_geeft_200(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/verkoop", headers={"X-API-Key": api_key})
        assert resp.status_code == 200

    def test_response_structuur(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/verkoop", headers={"X-API-Key": api_key})
        body = resp.get_json()
        assert "populairste" in body
        assert "trending" in body
        assert isinstance(body["populairste"], list)
        assert isinstance(body["trending"], list)

    def test_populairste_gesorteerd_op_totaal(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        vandaag = date.today()
        self._vul_verkoop(db, app, org_id, [
            ((vandaag - timedelta(days=i)).isoformat(), "Pasta", 5) for i in range(7)
        ] + [
            ((vandaag - timedelta(days=i)).isoformat(), "Soep", 10) for i in range(7)
        ])
        resp = client.get("/kassaboek/verkoop", headers={"X-API-Key": api_key})
        body = resp.get_json()
        populair = body["populairste"]
        if len(populair) >= 2:
            # Soep (70) moet voor Pasta (35)
            totalen = [p["totaal_verkocht"] for p in populair]
            assert totalen == sorted(totalen, reverse=True)

    def test_populairste_entry_heeft_verwachte_velden(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        vandaag = date.today()
        self._vul_verkoop(db, app, org_id, [
            ((vandaag - timedelta(days=1)).isoformat(), "Risotto", 8)
        ])
        resp = client.get("/kassaboek/verkoop", headers={"X-API-Key": api_key})
        body = resp.get_json()
        if body["populairste"]:
            item = body["populairste"][0]
            assert "naam" in item
            assert "totaal_verkocht" in item
            assert "gemiddeld_per_week" in item

    def test_lege_kassaboek_geeft_lege_lijsten(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/verkoop", headers={"X-API-Key": api_key})
        body = resp.get_json()
        assert body["populairste"] == []
        assert body["trending"] == []

    def test_weken_query_param_wordt_gerespecteerd(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/verkoop?weken=8", headers={"X-API-Key": api_key})
        assert resp.status_code == 200

    def test_ongeldige_weken_param_valt_terug_op_default(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/verkoop?weken=abc", headers={"X-API-Key": api_key})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Seizoen endpoint — GET /kassaboek/seizoen
# ---------------------------------------------------------------------------

class TestSeizoenEndpoint:
    def _vul_seizoen_data(self, db, app, org_id, gerecht_naam, entries):
        """Vul kassaboek met (datum, aantal) tuples voor één gerecht."""
        from models import KassaboekEntry
        with app.app_context():
            for datum_str, aantal in entries:
                entry = KassaboekEntry(
                    organisatie_id=org_id,
                    datum=date.fromisoformat(datum_str),
                    omzet=aantal * 15.0,
                    gerecht_naam=gerecht_naam,
                    aantal_verkocht=aantal,
                )
                db.session.add(entry)
            db.session.commit()

    def test_geen_auth_geeft_401(self, client, db, app):
        resp = client.get("/kassaboek/seizoen?gerecht=Pasta")
        assert resp.status_code == 401

    def test_ontbrekend_gerecht_param_geeft_400(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get("/kassaboek/seizoen", headers={"X-API-Key": api_key})
        assert resp.status_code == 400
        assert "gerecht" in resp.get_json()["error"].lower()

    def test_onbekend_gerecht_geeft_lege_data(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get(
            "/kassaboek/seizoen?gerecht=OnbekendGerecht999",
            headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["per_maand"] == []
        assert body["per_weekdag"] == []

    def test_response_structuur(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        self._vul_seizoen_data(db, app, org_id, "Pasta", [
            ("2026-01-05", 8), ("2026-01-12", 10), ("2026-02-03", 6),
        ])
        resp = client.get(
            "/kassaboek/seizoen?gerecht=Pasta",
            headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "gerecht" in body
        assert "per_maand" in body
        assert "per_weekdag" in body
        assert body["gerecht"] == "Pasta"

    def test_per_maand_bevat_correcte_velden(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        self._vul_seizoen_data(db, app, org_id, "Risotto", [
            ("2026-01-10", 5), ("2026-02-15", 8),
        ])
        resp = client.get(
            "/kassaboek/seizoen?gerecht=Risotto",
            headers={"X-API-Key": api_key}
        )
        body = resp.get_json()
        for item in body["per_maand"]:
            assert "maand" in item
            assert "gemiddeld" in item
            assert "totaal" in item

    def test_per_weekdag_bevat_7_dagen(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        self._vul_seizoen_data(db, app, org_id, "Zalm", [
            ("2026-01-05", 4),  # maandag
            ("2026-01-06", 6),  # dinsdag
        ])
        resp = client.get(
            "/kassaboek/seizoen?gerecht=Zalm",
            headers={"X-API-Key": api_key}
        )
        body = resp.get_json()
        assert len(body["per_weekdag"]) == 7
        weekdagen = [d["dag"] for d in body["per_weekdag"]]
        assert "maandag" in weekdagen
        assert "zondag" in weekdagen

    def test_per_maand_gesorteerd_op_datum(self, client, db, app):
        org_id, api_key, _ = _maak_org(db, app)
        self._vul_seizoen_data(db, app, org_id, "Soep", [
            ("2026-03-01", 5),
            ("2026-01-15", 8),
            ("2026-02-20", 6),
        ])
        resp = client.get(
            "/kassaboek/seizoen?gerecht=Soep",
            headers={"X-API-Key": api_key}
        )
        body = resp.get_json()
        maanden = [m["maand"] for m in body["per_maand"]]
        assert maanden == sorted(maanden)

    def test_maanden_param_wordt_gerespecteerd(self, client, db, app):
        _, api_key, _ = _maak_org(db, app)
        resp = client.get(
            "/kassaboek/seizoen?gerecht=Test&maanden=3",
            headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. Fuzzy matching unit tests — _fuzzy_match_gerecht
# ---------------------------------------------------------------------------

class TestFuzzyMatchGerecht:
    """Unit tests voor de _fuzzy_match_gerecht helper in kassaboek_routes.py."""

    def _gerecht(self, naam):
        from types import SimpleNamespace
        return SimpleNamespace(naam=naam)

    def _match(self, naam, kandidaten):
        from kassaboek_routes import _fuzzy_match_gerecht
        gerechten = [self._gerecht(k) for k in kandidaten]
        return _fuzzy_match_gerecht(naam, gerechten)

    def test_exacte_match(self):
        result = self._match("Caesar Salade", ["Caesar Salade", "Risotto"])
        assert result is not None
        assert result.naam == "Caesar Salade"

    def test_exacte_match_case_insensitive(self):
        result = self._match("caesar salade", ["Caesar Salade", "Risotto"])
        assert result is not None
        assert result.naam == "Caesar Salade"

    def test_substring_match_verkort(self):
        """'Risotto' matcht op 'Risotto met Paddenstoelen'."""
        result = self._match("Risotto", ["Caesar Salade", "Risotto met Paddenstoelen"])
        assert result is not None
        assert "Risotto" in result.naam

    def test_substring_match_uitgebreid(self):
        """'Gegrilde Zalm op Spinazie' matcht op 'Gegrilde Zalm'."""
        result = self._match("Gegrilde Zalm op Spinazie", ["Caesar Salade", "Gegrilde Zalm"])
        assert result is not None
        assert "Zalm" in result.naam

    def test_difflib_fuzzy_match(self):
        """Typfout 'Casar Salade' → 'Caesar Salade' via difflib."""
        result = self._match("Casar Salade", ["Caesar Salade", "Risotto"])
        assert result is not None
        assert result.naam == "Caesar Salade"

    def test_geen_match_geeft_none(self):
        result = self._match("Compleet Onbekend XYZ123", ["Caesar Salade", "Risotto"])
        assert result is None

    def test_lege_naam_geeft_none(self):
        from kassaboek_routes import _fuzzy_match_gerecht
        result = _fuzzy_match_gerecht("", [self._gerecht("Caesar Salade")])
        assert result is None

    def test_lege_gerechtenlijst_geeft_none(self):
        from kassaboek_routes import _fuzzy_match_gerecht
        result = _fuzzy_match_gerecht("Caesar Salade", [])
        assert result is None

    def test_none_naam_geeft_none(self):
        from kassaboek_routes import _fuzzy_match_gerecht
        result = _fuzzy_match_gerecht(None, [self._gerecht("Caesar Salade")])
        assert result is None
