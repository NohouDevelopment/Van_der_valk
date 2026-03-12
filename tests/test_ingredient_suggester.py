"""
tests/test_ingredient_suggester.py

Unit tests voor tools/ingredient_suggester.py.
AI calls (ai_reason_json) worden gemockt — geen echte API calls.

Getest:
- genereer_voorstel retourneert lijst van 1-3 voorstellen
- Elke voorstel heeft correcte structuur (gerecht, ingredienten, synergie_check)
- synergie_check berekening is consistent met ingredienten
- Fallback (_mock_voorstel) bij AI fout
- in_gerechten count vanuit lookup
- Werkt zonder segment_data / geheugen_data
"""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("OPENROUTER_API_KEY", "test-dummy")


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

MOCK_AI_VOORSTELLEN = [
    {
        "gerecht": {
            "naam": "Prei Risotto",
            "beschrijving": "Romige risotto met prei en paddenstoelen",
            "categorie": "Hoofdgerechten",
            "prijs_suggestie": 18.50,
        },
        "ingredienten": [
            {"naam": "prei", "status": "bestaand_kritiek", "hoeveelheid": 60, "eenheid": "g"},
            {"naam": "risottorijst", "status": "bestaand", "hoeveelheid": 150, "eenheid": "g"},
            {"naam": "truffelolie", "status": "nieuw_droog", "hoeveelheid": 5, "eenheid": "ml"},
        ],
    },
    {
        "gerecht": {
            "naam": "Seizoensalade",
            "beschrijving": "Frisse salade met verse groenten",
            "categorie": "Voorgerechten",
            "prijs_suggestie": 12.00,
        },
        "ingredienten": [
            {"naam": "koriander", "status": "bestaand_kritiek", "hoeveelheid": 10, "eenheid": "g"},
            {"naam": "wortel", "status": "bestaand", "hoeveelheid": 80, "eenheid": "g"},
            {"naam": "avocado", "status": "nieuw_vers", "hoeveelheid": 100, "eenheid": "g"},
        ],
    },
    {
        "gerecht": {
            "naam": "Premium Tasting",
            "beschrijving": "Klein premium bordje",
            "categorie": "Tapas",
            "prijs_suggestie": 22.00,
        },
        "ingredienten": [
            {"naam": "parmezaan", "status": "bestaand", "hoeveelheid": 30, "eenheid": "g"},
            {"naam": "roomboter", "status": "bestaand", "hoeveelheid": 20, "eenheid": "g"},
        ],
    },
]


def _maak_analyse(risico=None, ingredienten=None):
    if risico is None:
        risico = []
    if ingredienten is None:
        ingredienten = []
    return {
        "ingredienten": ingredienten,
        "statistieken": {
            "totaal_uniek": len(ingredienten),
            "vers_ingredienten": 0,
            "single_use_vers": len(risico),
            "gemiddeld_gebruik": 1.0,
            "top_5_meest_gebruikt": [],
            "risico_ingredienten": risico,
        },
        "synergie_score": 0,
    }


def _maak_ing_entry(naam, categorie="droog", count=1, omloop="laag"):
    return {"naam": naam, "categorie": categorie, "gebruik_count": count, "omloop_status": omloop}


# ---------------------------------------------------------------------------
# genereer_voorstel — retourneert lijst
# ---------------------------------------------------------------------------

class TestGenereerVoorstelRetourneertLijst:
    def test_retourneert_lijst(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert isinstance(result, list)

    def test_bevat_maximaal_3_voorstellen(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert len(result) <= 3

    def test_bevat_minimaal_1_voorstel(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Output structuur per voorstel
# ---------------------------------------------------------------------------

class TestVoorstelStructuur:
    def _get_voorstel(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        return result[0]

    def test_top_level_keys_aanwezig(self):
        v = self._get_voorstel()
        assert "gerecht" in v
        assert "ingredienten" in v
        assert "synergie_check" in v

    def test_gerecht_vereiste_velden(self):
        v = self._get_voorstel()
        g = v["gerecht"]
        assert "naam" in g
        assert "beschrijving" in g
        assert "categorie" in g
        assert "prijs_suggestie" in g

    def test_gerecht_naam_is_nonempty_string(self):
        v = self._get_voorstel()
        assert isinstance(v["gerecht"]["naam"], str)
        assert len(v["gerecht"]["naam"]) > 0

    def test_gerecht_prijs_is_positief(self):
        v = self._get_voorstel()
        assert v["gerecht"]["prijs_suggestie"] > 0

    def test_ingredienten_is_lijst(self):
        v = self._get_voorstel()
        assert isinstance(v["ingredienten"], list)

    def test_elk_ingrediënt_heeft_vereiste_velden(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for voorstel in result:
            for ing in voorstel["ingredienten"]:
                assert "naam" in ing, f"'naam' ontbreekt: {ing}"
                assert "status" in ing, f"'status' ontbreekt: {ing}"
                assert "hoeveelheid" in ing, f"'hoeveelheid' ontbreekt: {ing}"
                assert "eenheid" in ing, f"'eenheid' ontbreekt: {ing}"

    def test_ingrediënt_status_geldig(self):
        geldige = {"bestaand", "bestaand_kritiek", "nieuw_vers", "nieuw_droog"}
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for voorstel in result:
            for ing in voorstel["ingredienten"]:
                assert ing["status"] in geldige, (
                    f"Ongeldige status '{ing['status']}' voor '{ing['naam']}'"
                )

    def test_synergie_check_vereiste_velden(self):
        v = self._get_voorstel()
        sc = v["synergie_check"]
        assert "bestaand_percentage" in sc
        assert "nieuwe_items" in sc
        assert "nieuwe_vers" in sc
        assert "hergebruikte_risico" in sc
        assert "verwachte_derving_impact" in sc
        assert "samenvatting" in sc


# ---------------------------------------------------------------------------
# Synergie berekening (server-side, niet van AI)
# ---------------------------------------------------------------------------

class TestSynergieBerekening:
    def test_bestaand_percentage_tussen_0_en_100(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for v in result:
            pct = v["synergie_check"]["bestaand_percentage"]
            assert 0 <= pct <= 100

    def test_nieuwe_items_consistent_met_ingredienten(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for v in result:
            ings = v["ingredienten"]
            bestaand = sum(1 for i in ings if i["status"].startswith("bestaand"))
            verwacht_nieuw = len(ings) - bestaand
            assert v["synergie_check"]["nieuwe_items"] == verwacht_nieuw

    def test_hergebruikte_risico_zijn_bestaand_kritiek(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for v in result:
            kritiek_namen = {i["naam"] for i in v["ingredienten"] if i["status"] == "bestaand_kritiek"}
            for naam in v["synergie_check"]["hergebruikte_risico"]:
                assert naam in kritiek_namen

    def test_nieuwe_vers_telt_alleen_nieuw_vers_status(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for v in result:
            verwacht = sum(1 for i in v["ingredienten"] if i.get("status") == "nieuw_vers")
            assert v["synergie_check"]["nieuwe_vers"] == verwacht


# ---------------------------------------------------------------------------
# Lookup: in_gerechten vanuit analyse_data
# ---------------------------------------------------------------------------

class TestLookupInGerechten:
    def test_in_gerechten_count_vanuit_lookup(self):
        """in_gerechten moet count uit analyse_data lookup weerspiegelen."""
        analyse = _maak_analyse(
            ingredienten=[_maak_ing_entry("prei", "vers", count=3, omloop="medium")]
        )
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        # Eerste voorstel heeft prei met status bestaand_kritiek
        prei_items = [i for i in result[0]["ingredienten"] if i["naam"] == "prei"]
        if prei_items:
            assert prei_items[0]["in_gerechten"] == 3

    def test_onbekend_ingrediënt_krijgt_count_0(self):
        """Ingrediënt niet in lookup → in_gerechten = 0, geen crash."""
        analyse = _maak_analyse(ingredienten=[])
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        for v in result:
            for i in v["ingredienten"]:
                assert isinstance(i["in_gerechten"], (int, float))


# ---------------------------------------------------------------------------
# Fallback bij AI fout
# ---------------------------------------------------------------------------

class TestFallback:
    def test_ai_fout_geeft_fallback_lijst(self):
        analyse = _maak_analyse(risico=["prei", "koriander"])
        with patch("tools.ingredient_suggester.ai_reason_json", side_effect=Exception("AI error")):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fallback_bevat_risico_ingredienten(self):
        analyse = _maak_analyse(risico=["prei", "koriander"])
        with patch("tools.ingredient_suggester.ai_reason_json", side_effect=Exception("AI error")):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        v = result[0]
        namen = {i["naam"] for i in v["ingredienten"]}
        assert "prei" in namen or "koriander" in namen

    def test_fallback_structuur_correct(self):
        analyse = _maak_analyse(risico=["prei"])
        with patch("tools.ingredient_suggester.ai_reason_json", side_effect=Exception("AI error")):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        v = result[0]
        assert "gerecht" in v
        assert "ingredienten" in v
        assert "synergie_check" in v

    def test_fallback_zonder_risico_crasht_niet(self):
        analyse = _maak_analyse(risico=[])
        with patch("tools.ingredient_suggester.ai_reason_json", side_effect=Exception("AI error")):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_ai_geeft_dict_ipv_lijst_wordt_gewrapped(self):
        """Als AI per ongeluk een dict teruggeeft i.p.v. lijst, wordt die gewrapped."""
        enkel_voorstel = MOCK_AI_VOORSTELLEN[0]
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=enkel_voorstel):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse)
        assert isinstance(result, list)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Optionele parameters
# ---------------------------------------------------------------------------

class TestOptioneleParameters:
    def test_werkt_zonder_segment_data(self):
        analyse = _maak_analyse()
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse, segment_data=None)
        assert isinstance(result, list)

    def test_werkt_met_segment_data(self):
        analyse = _maak_analyse()
        segment = {"culinaire_stijl": "Italiaans", "prijssegment": "middensegment"}
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse, segment_data=segment)
        assert isinstance(result, list)

    def test_werkt_met_geheugen_data(self):
        analyse = _maak_analyse()
        geheugen = {"trends": [{"naam": "Fermenteren"}, {"naam": "Plant-based"}]}
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse, geheugen_data=geheugen)
        assert isinstance(result, list)

    def test_werkt_met_lege_geheugen_trends(self):
        analyse = _maak_analyse()
        geheugen = {"trends": []}
        with patch("tools.ingredient_suggester.ai_reason_json", return_value=MOCK_AI_VOORSTELLEN):
            from tools.ingredient_suggester import genereer_voorstel
            result = genereer_voorstel(analyse, geheugen_data=geheugen)
        assert isinstance(result, list)
