"""
tests/test_ingredient_analyzer.py

Unit tests voor tools/ingredient_analyzer.py.
Tests dekken: _omloop_status, _versheids_risico, _strategie,
_geschatte_omloop en analyseer_ingredienten.
"""

import pytest
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.ingredient_analyzer import (
    analyseer_ingredienten,
    _omloop_status,
    _versheids_risico,
    _strategie,
    _geschatte_omloop,
)


def make_gerecht(naam, ingredienten, categorie="Hoofdgerechten"):
    """Helper: maak mock Gerecht object met SimpleNamespace."""
    return SimpleNamespace(naam=naam, ingredienten=ingredienten, categorie=categorie)


# ---------------------------------------------------------------------------
# _omloop_status
# ---------------------------------------------------------------------------

class TestOmloopStatus:
    def test_vers_hoog_count_4(self):
        status, kleur = _omloop_status(4, vers=True)
        assert status == "hoog"
        assert kleur == "green"

    def test_vers_hoog_count_meer_dan_4(self):
        status, kleur = _omloop_status(6, vers=True)
        assert status == "hoog"
        assert kleur == "green"

    def test_vers_medium_count_2(self):
        status, kleur = _omloop_status(2, vers=True)
        assert status == "medium"
        assert kleur == "yellow"

    def test_vers_medium_count_3(self):
        status, kleur = _omloop_status(3, vers=True)
        assert status == "medium"
        assert kleur == "yellow"

    def test_vers_kritiek_count_1(self):
        status, kleur = _omloop_status(1, vers=True)
        assert status == "kritiek"
        assert kleur == "red"

    def test_droog_hoog_count_2(self):
        status, kleur = _omloop_status(2, vers=False)
        assert status == "hoog"
        assert kleur == "green"

    def test_droog_laag_count_1(self):
        status, kleur = _omloop_status(1, vers=False)
        assert status == "laag"
        assert kleur == "gray"


# ---------------------------------------------------------------------------
# _versheids_risico
# ---------------------------------------------------------------------------

class TestVersheidsRisico:
    def test_vers_geeft_hoog(self):
        assert _versheids_risico("vers") == "hoog"

    def test_zuivel_geeft_medium(self):
        assert _versheids_risico("zuivel") == "medium"

    def test_diepvries_geeft_laag(self):
        assert _versheids_risico("diepvries") == "laag"

    def test_droog_geeft_laag(self):
        assert _versheids_risico("droog") == "laag"

    def test_saus_geeft_laag(self):
        assert _versheids_risico("saus") == "laag"


# ---------------------------------------------------------------------------
# _strategie
# ---------------------------------------------------------------------------

class TestStrategie:
    def test_hoog_vers_behouden(self):
        result = _strategie("hoog", "vers")
        assert "Behouden" in result
        assert "rotatie" in result.lower()

    def test_hoog_zuivel_behouden(self):
        # zuivel is vers (_is_vers returns True for zuivel)
        result = _strategie("hoog", "zuivel")
        assert "Behouden" in result

    def test_medium_vers_monitoring(self):
        result = _strategie("medium", "vers")
        assert "Monitoring" in result

    def test_kritiek_saneren(self):
        result = _strategie("kritiek", "vers")
        assert "Saneren" in result

    def test_kritiek_droog_ook_saneren(self):
        # kritiek check is category-agnostic
        result = _strategie("kritiek", "droog")
        assert "Saneren" in result

    def test_laag_droog_luxe_item(self):
        result = _strategie("laag", "droog")
        assert "Luxe-item" in result or "dode voorraad" in result.lower()

    def test_laag_saus_luxe_item(self):
        result = _strategie("laag", "saus")
        assert "Luxe-item" in result or "dode voorraad" in result.lower()

    def test_hoog_droog_kern_ingredient(self):
        result = _strategie("hoog", "droog")
        assert "Kern-ingrediënt" in result

    def test_laag_diepvries_veilig(self):
        result = _strategie("laag", "diepvries")
        assert "Veilig" in result or "vriezer" in result.lower()


# ---------------------------------------------------------------------------
# _geschatte_omloop
# ---------------------------------------------------------------------------

class TestGeschattteOmloop:
    def test_geen_verkoop_data_beschikbaar_false(self):
        detail = [{"gerecht": "Soep", "hoeveelheid": 100, "eenheid": "g"}]
        result = _geschatte_omloop(detail, verkoop_data=None)
        assert result["beschikbaar"] is False
        assert result["waarde"] is None
        assert result["label"] == "N/B"

    def test_lege_verkoop_dict_beschikbaar_false(self):
        detail = [{"gerecht": "Soep", "hoeveelheid": 100, "eenheid": "g"}]
        result = _geschatte_omloop(detail, verkoop_data={})
        assert result["beschikbaar"] is False

    def test_met_verkoop_data_berekening(self):
        detail = [{"gerecht": "Soep", "hoeveelheid": 100, "eenheid": "g"}]
        verkoop = {"Soep": 10}
        result = _geschatte_omloop(detail, verkoop_data=verkoop)
        assert result["beschikbaar"] is True
        assert result["waarde"] == 1.0  # 1000g → 1.0 kg

    def test_g_naar_kg_conversie_bij_1000(self):
        detail = [{"gerecht": "Soep", "hoeveelheid": 500, "eenheid": "g"}]
        verkoop = {"Soep": 3}  # 500 * 3 = 1500g → 1.5 kg
        result = _geschatte_omloop(detail, verkoop_data=verkoop)
        assert result["beschikbaar"] is True
        assert result["waarde"] == 1.5
        assert "kg" in result["eenheid"]

    def test_ml_naar_liter_conversie_bij_1000(self):
        detail = [{"gerecht": "Cocktail", "hoeveelheid": 250, "eenheid": "ml"}]
        verkoop = {"Cocktail": 5}  # 250 * 5 = 1250ml → 1.25L
        result = _geschatte_omloop(detail, verkoop_data=verkoop)
        assert result["beschikbaar"] is True
        assert result["waarde"] == 1.25
        assert "L" in result["eenheid"]

    def test_kleine_hoeveelheid_geen_conversie(self):
        detail = [{"gerecht": "Soep", "hoeveelheid": 10, "eenheid": "g"}]
        verkoop = {"Soep": 5}  # 10 * 5 = 50g, geen conversie
        result = _geschatte_omloop(detail, verkoop_data=verkoop)
        assert result["beschikbaar"] is True
        assert result["waarde"] == 50.0
        assert "kg" not in result["eenheid"]


# ---------------------------------------------------------------------------
# analyseer_ingredienten — basis
# ---------------------------------------------------------------------------

class TestAnalyseerBasis:
    def test_drie_gerechten_synergie_score(self):
        gerechten = [
            make_gerecht("Soep", [
                {"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"},
                {"naam": "wortel", "categorie": "vers", "hoeveelheid": 100, "eenheid": "g"},
            ]),
            make_gerecht("Risotto", [
                {"naam": "prei", "categorie": "vers", "hoeveelheid": 60, "eenheid": "g"},
                {"naam": "rijst", "categorie": "droog", "hoeveelheid": 150, "eenheid": "g"},
            ]),
            make_gerecht("Pasta", [
                {"naam": "wortel", "categorie": "vers", "hoeveelheid": 50, "eenheid": "g"},
                {"naam": "rijst", "categorie": "droog", "hoeveelheid": 100, "eenheid": "g"},
            ]),
        ]
        result = analyseer_ingredienten(gerechten)

        # prei, wortel en rijst worden elk in 2 gerechten gebruikt (alle 3 gedeeld)
        assert result["synergie_score"] == 100  # 3/3 = 100%

    def test_overlappende_ingredienten_gebruik_count(self):
        gerechten = [
            make_gerecht("A", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"}]),
            make_gerecht("B", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 60, "eenheid": "g"}]),
        ]
        result = analyseer_ingredienten(gerechten)
        prei_entry = next(i for i in result["ingredienten"] if i["naam"] == "prei")
        assert prei_entry["gebruik_count"] == 2

    def test_statistieken_aanwezig(self):
        gerechten = [
            make_gerecht("Soep", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"}]),
        ]
        result = analyseer_ingredienten(gerechten)
        stats = result["statistieken"]
        assert "totaal_uniek" in stats
        assert "vers_ingredienten" in stats
        assert "single_use_vers" in stats
        assert "gemiddeld_gebruik" in stats
        assert "top_5_meest_gebruikt" in stats
        assert "risico_ingredienten" in stats


# ---------------------------------------------------------------------------
# analyseer_ingredienten — leeg menu
# ---------------------------------------------------------------------------

class TestAnalyseerLeegMenu:
    def test_lege_lijst_geeft_nul_waarden(self):
        result = analyseer_ingredienten([])
        assert result["ingredienten"] == []
        assert result["statistieken"]["totaal_uniek"] == 0
        assert result["statistieken"]["vers_ingredienten"] == 0
        assert result["statistieken"]["single_use_vers"] == 0
        assert result["synergie_score"] == 0

    def test_gerechten_zonder_ingredienten(self):
        gerechten = [
            make_gerecht("Soep", []),
            make_gerecht("Pasta", None),
        ]
        result = analyseer_ingredienten(gerechten)
        assert result["ingredienten"] == []
        assert result["synergie_score"] == 0


# ---------------------------------------------------------------------------
# analyseer_ingredienten — string ingredienten (backwards-compat)
# ---------------------------------------------------------------------------

class TestAnalyseerStringIngredienten:
    def test_string_wordt_geconverteerd_naar_dict(self):
        """Strings als ingrediënt input moeten werken (Task #2 fix)."""
        gerechten = [
            make_gerecht("Soep", ["kaas", "prei"]),
        ]
        result = analyseer_ingredienten(gerechten)
        namen = [i["naam"] for i in result["ingredienten"]]
        assert "kaas" in namen
        assert "prei" in namen

    def test_string_ingredienten_categorie_is_droog(self):
        """String ingrediënten krijgen standaard categorie 'droog'."""
        gerechten = [
            make_gerecht("Soep", ["kaas"]),
        ]
        result = analyseer_ingredienten(gerechten)
        kaas_entry = next(i for i in result["ingredienten"] if i["naam"] == "kaas")
        assert kaas_entry["categorie"] == "droog"

    def test_mix_string_en_dict_ingredienten(self):
        """Mixen van string en dict ingrediënten werkt correct."""
        gerechten = [
            make_gerecht("Soep", [
                "bouillon",
                {"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"},
            ]),
        ]
        result = analyseer_ingredienten(gerechten)
        namen = [i["naam"] for i in result["ingredienten"]]
        assert "bouillon" in namen
        assert "prei" in namen


# ---------------------------------------------------------------------------
# analyseer_ingredienten — sortering kritiek eerst
# ---------------------------------------------------------------------------

class TestSorteringKritiekEerst:
    def test_kritiek_ingredienten_komen_eerst(self):
        """Ingrediënten met omloop_status 'kritiek' staan bovenaan in resultaat."""
        gerechten = [
            # prei: vers, 4x → hoog (green)
            make_gerecht("A", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 50, "eenheid": "g"}]),
            make_gerecht("B", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 50, "eenheid": "g"}]),
            make_gerecht("C", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 50, "eenheid": "g"}]),
            make_gerecht("D", [
                {"naam": "prei", "categorie": "vers", "hoeveelheid": 50, "eenheid": "g"},
                # koriander: vers, 1x → kritiek (red)
                {"naam": "koriander", "categorie": "vers", "hoeveelheid": 5, "eenheid": "g"},
            ]),
        ]
        result = analyseer_ingredienten(gerechten)
        ingredienten = result["ingredienten"]
        assert len(ingredienten) >= 2

        # Eerste item moet kritiek zijn
        assert ingredienten[0]["omloop_status"] == "kritiek"
        assert ingredienten[0]["naam"] == "koriander"

    def test_sortering_volgorde_kritiek_medium_hoog_laag(self):
        """Volgorde is: kritiek → medium → hoog → laag."""
        gerechten = [
            # droog_alleen: droog, 1x → laag
            make_gerecht("X", [{"naam": "zout", "categorie": "droog", "hoeveelheid": 5, "eenheid": "g"}]),
            # prei: vers, 1x → kritiek
            make_gerecht("Y", [{"naam": "prei", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"}]),
            # wortel: vers, 2x → medium
            make_gerecht("Z1", [{"naam": "wortel", "categorie": "vers", "hoeveelheid": 100, "eenheid": "g"}]),
            make_gerecht("Z2", [{"naam": "wortel", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"}]),
            # rijst: droog, 2x → hoog
            make_gerecht("W1", [{"naam": "rijst", "categorie": "droog", "hoeveelheid": 150, "eenheid": "g"}]),
            make_gerecht("W2", [{"naam": "rijst", "categorie": "droog", "hoeveelheid": 100, "eenheid": "g"}]),
        ]
        result = analyseer_ingredienten(gerechten)
        statussen = [i["omloop_status"] for i in result["ingredienten"]]

        status_order = {"kritiek": 0, "medium": 1, "hoog": 2, "laag": 3}
        volgorde_waarden = [status_order[s] for s in statussen]
        # Controleer dat de lijst gesorteerd is (niet-dalend)
        assert volgorde_waarden == sorted(volgorde_waarden)

    def test_risico_ingredienten_in_statistieken(self):
        """Kritieke ingrediënten staan ook in statistieken.risico_ingredienten."""
        gerechten = [
            make_gerecht("Soep", [
                {"naam": "koriander", "categorie": "vers", "hoeveelheid": 5, "eenheid": "g"},
            ]),
        ]
        result = analyseer_ingredienten(gerechten)
        assert "koriander" in result["statistieken"]["risico_ingredienten"]
        assert result["statistieken"]["single_use_vers"] == 1
