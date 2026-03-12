"""
conftest.py — Gedeelde pytest fixtures voor Menu Maker tests.

Bevat:
- Flask app met in-memory SQLite
- Test client + ingelogde client
- Gerecht mock helpers (SimpleNamespace, geen DB nodig voor unit tests)
- DB fixtures: organisatie, gebruiker, menu, gerechten
"""

import pytest
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Flask app fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Flask app geconfigureerd met in-memory SQLite voor tests."""
    import sys
    import os
    from pathlib import Path

    # Voeg project root toe aan sys.path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Zet dummy env vars zodat ai_client niet crasht bij import
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
    """In-memory database: aanmaken voor elke test, afbreken erna."""
    from models import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# DB fixtures: organisatie + gebruiker + menu
# ---------------------------------------------------------------------------

@pytest.fixture
def test_org(db, app):
    """Maak een test-organisatie aan."""
    from models import Organisatie
    with app.app_context():
        org = Organisatie(naam="Test Restaurant", adres="Teststraat 1", status="actief")
        db.session.add(org)
        db.session.commit()
        db.session.refresh(org)
        return org


@pytest.fixture
def test_gebruiker(db, app, test_org):
    """Maak een test-gebruiker aan."""
    from models import Gebruiker
    with app.app_context():
        gebruiker = Gebruiker(
            naam="Test Gebruiker",
            email="test@test.nl",
            organisatie_id=test_org.id,
            rol="gebruiker",
        )
        gebruiker.set_wachtwoord("test0000")
        db.session.add(gebruiker)
        db.session.commit()
        db.session.refresh(gebruiker)
        return gebruiker


@pytest.fixture
def test_menu(db, app, test_org):
    """Maak een test-menu aan."""
    from models import Menu
    with app.app_context():
        menu = Menu(
            organisatie_id=test_org.id,
            naam="Test Menu",
            bron_type="tekst",
            data={"categorieën": []},
            actief=True,
        )
        db.session.add(menu)
        db.session.commit()
        db.session.refresh(menu)
        return menu


@pytest.fixture
def ingelogde_client(client, app, test_gebruiker):
    """Test client met ingelogde gebruiker via session."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_gebruiker.id)
        sess["_fresh"] = True
    return client


# ---------------------------------------------------------------------------
# SimpleNamespace Gerecht helpers (geen DB nodig voor unit tests)
# ---------------------------------------------------------------------------

def maak_gerecht(naam: str, ingredienten: list, menu_id: int = 1, org_id: int = 1):
    """
    Maak een lichtgewicht Gerecht mock via SimpleNamespace.
    Gebruikt voor unit tests die geen database nodig hebben.

    Args:
        naam: Naam van het gerecht
        ingredienten: Lijst van ingrediënt dicts of strings
        menu_id: Optioneel menu ID
        org_id: Optioneel organisatie ID
    """
    return SimpleNamespace(
        naam=naam,
        ingredienten=ingredienten,
        menu_id=menu_id,
        organisatie_id=org_id,
    )


def maak_ingredienten_dict(naam: str, categorie: str = "droog",
                            hoeveelheid: float = None, eenheid: str = "") -> dict:
    """Helper om een ingrediënt dict aan te maken."""
    return {
        "naam": naam,
        "categorie": categorie,
        "hoeveelheid": hoeveelheid,
        "eenheid": eenheid,
    }


# ---------------------------------------------------------------------------
# Gerecht fixtures voor ingredient_analyzer tests
# ---------------------------------------------------------------------------

@pytest.fixture
def gerecht_prei_enkelvoudig():
    """Één gerecht met prei (vers, single-use → kritiek)."""
    return [
        maak_gerecht("Soep", [
            maak_ingredienten_dict("prei", "vers", 80, "g"),
        ]),
    ]


@pytest.fixture
def gerechten_prei_gedeeld():
    """Twee gerechten die prei delen (vers, 2x → medium)."""
    return [
        maak_gerecht("Soep", [
            maak_ingredienten_dict("prei", "vers", 80, "g"),
        ]),
        maak_gerecht("Risotto", [
            maak_ingredienten_dict("prei", "vers", 60, "g"),
            maak_ingredienten_dict("roomboter", "zuivel", 25, "g"),
        ]),
    ]


@pytest.fixture
def gerechten_prei_hoog():
    """Vier gerechten die prei delen (vers, 4x → hoog)."""
    return [
        maak_gerecht(f"Gerecht {i}", [
            maak_ingredienten_dict("prei", "vers", 50, "g"),
        ])
        for i in range(4)
    ]


@pytest.fixture
def gerechten_volledig():
    """Rijke set gerechten voor synergie en sortering tests."""
    return [
        maak_gerecht("Soep", [
            maak_ingredienten_dict("prei", "vers", 80, "g"),
            maak_ingredienten_dict("wortel", "vers", 100, "g"),
            maak_ingredienten_dict("bouillon", "droog", 10, "g"),
        ]),
        maak_gerecht("Risotto", [
            maak_ingredienten_dict("prei", "vers", 60, "g"),
            maak_ingredienten_dict("risottorijst", "droog", 150, "g"),
            maak_ingredienten_dict("roomboter", "zuivel", 25, "g"),
        ]),
        maak_gerecht("Pasta", [
            maak_ingredienten_dict("wortel", "vers", 50, "g"),
            maak_ingredienten_dict("roomboter", "zuivel", 20, "g"),
            maak_ingredienten_dict("koriander", "vers", 5, "g"),  # single-use vers
        ]),
        maak_gerecht("Quiche", [
            maak_ingredienten_dict("roomboter", "zuivel", 30, "g"),
            maak_ingredienten_dict("risottorijst", "droog", 0, "g"),
        ]),
    ]


# ---------------------------------------------------------------------------
# Mock AI response voor ingredient_suggester tests
# ---------------------------------------------------------------------------

MOCK_VOORSTEL_AI_RESPONSE = {
    "gerecht": {
        "naam": "Test Risotto",
        "beschrijving": "Test beschrijving",
        "categorie": "Vegetarisch",
        "prijs_suggestie": 15.00,
    },
    "ingredienten": [
        {"naam": "prei", "status": "bestaand_kritiek", "in_gerechten": 1, "hoeveelheid": 60, "eenheid": "g"},
        {"naam": "wortel", "status": "bestaand", "in_gerechten": 2, "hoeveelheid": 100, "eenheid": "g"},
        {"naam": "truffelolie", "status": "nieuw_droog", "in_gerechten": 0, "hoeveelheid": 5, "eenheid": "ml"},
    ],
    "synergie_check": {
        "bestaand_percentage": 67,
        "nieuwe_items": 1,
        "nieuwe_vers": 0,
        "hergebruikte_risico": ["prei"],
        "verwachte_derving_impact": "prei stijgt van Kritiek naar Medium.",
        "samenvatting": "Test samenvatting.",
    },
}
