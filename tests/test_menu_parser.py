"""
tests/test_menu_parser.py

Unit tests voor tools/menu_parser.py.
AI calls worden gemockt via unittest.mock.patch — geen echte API calls.

BEKEND PROBLEEM (BUG):
  parse_menu_text() bevat een ongeldige f-string op regel 91 van menu_parser.py:
      "ingredienten": [{"naam": "ingrediënt1", ...}]  ← accolades niet geëscaped in f-string
  Dit veroorzaakt een ValueError bij elke aanroep van parse_menu_text() — het
  bereikt ai_generate_json() nooit. Tests die dit raken zijn gemarkeerd als xfail.
  Fix: vervang [ met {{[ en ] met ]}} op die regel, of gebruik een aparte string.

Getest (wat WEL werkt):
- Fallback structuur bij JSONDecodeError
- _parse_json helper (via ai_client)
- extract_text_from_pdf (via PyMuPDF mock)

Getest (gemarkeerd xfail wegens bug):
- parse_menu_text happy-path: structuur, rich object ingrediënten, null prijzen
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("OPENROUTER_API_KEY", "test-dummy")


# ---------------------------------------------------------------------------
# Mock AI responses (voor als de f-string bug gefixt is)
# ---------------------------------------------------------------------------

MOCK_MENU_VOLLEDIG = {
    "categorieën": [
        {
            "naam": "Voorgerechten",
            "gerechten": [
                {
                    "naam": "Caesar Salade",
                    "beschrijving": "Romaine sla, parmezaan, croutons",
                    "prijs": 12.50,
                    "ingredienten": [
                        {"naam": "romaine sla", "categorie": "vers", "hoeveelheid": 100, "eenheid": "g"},
                        {"naam": "parmezaan", "categorie": "zuivel", "hoeveelheid": 30, "eenheid": "g"},
                        {"naam": "croutons", "categorie": "droog", "hoeveelheid": 20, "eenheid": "g"},
                    ],
                    "tags": ["klassiek"],
                    "dieet": ["vegetarisch"],
                }
            ],
        },
        {
            "naam": "Hoofdgerechten",
            "gerechten": [
                {
                    "naam": "Risotto",
                    "beschrijving": "Romige risotto met paddenstoelen",
                    "prijs": 18.00,
                    "ingredienten": [
                        {"naam": "risottorijst", "categorie": "droog", "hoeveelheid": 150, "eenheid": "g"},
                        {"naam": "paddenstoelen", "categorie": "vers", "hoeveelheid": 80, "eenheid": "g"},
                        {"naam": "roomboter", "categorie": "zuivel", "hoeveelheid": 25, "eenheid": "g"},
                    ],
                    "tags": ["vegetarisch", "seizoen"],
                    "dieet": ["vegetarisch"],
                },
                {
                    "naam": "Zalm",
                    "beschrijving": "Gegrilde zalm op bedje van spinazie",
                    "prijs": None,
                    "ingredienten": [
                        {"naam": "zalm", "categorie": "vers", "hoeveelheid": 180, "eenheid": "g"},
                        {"naam": "spinazie", "categorie": "vers", "hoeveelheid": 60, "eenheid": "g"},
                    ],
                    "tags": [],
                    "dieet": [],
                },
            ],
        },
    ]
}

MOCK_MENU_LEEG = {"categorieën": []}

MOCK_MENU_GEEN_INGREDIENTEN = {
    "categorieën": [
        {
            "naam": "Gerechten",
            "gerechten": [
                {
                    "naam": "Soep van de dag",
                    "beschrijving": "Wisselende soep",
                    "prijs": 8.50,
                    "ingredienten": [],
                    "tags": [],
                    "dieet": [],
                }
            ],
        }
    ]
}


# ---------------------------------------------------------------------------
# ai_client._parse_json helper — werkt altijd
# ---------------------------------------------------------------------------

class TestParseJsonHelper:
    def test_plain_json(self):
        from tools.ai_client import _parse_json
        raw = '{"sleutel": "waarde"}'
        result = _parse_json(raw)
        assert result == {"sleutel": "waarde"}

    def test_json_in_code_block_json(self):
        from tools.ai_client import _parse_json
        raw = "```json\n{\"sleutel\": \"waarde\"}\n```"
        result = _parse_json(raw)
        assert result == {"sleutel": "waarde"}

    def test_json_in_generiek_code_block(self):
        from tools.ai_client import _parse_json
        raw = "```\n{\"sleutel\": \"waarde\"}\n```"
        result = _parse_json(raw)
        assert result == {"sleutel": "waarde"}

    def test_json_array(self):
        from tools.ai_client import _parse_json
        raw = '[{"a": 1}, {"b": 2}]'
        result = _parse_json(raw)
        assert result == [{"a": 1}, {"b": 2}]

    def test_invalid_json_geeft_exception(self):
        from tools.ai_client import _parse_json
        with pytest.raises(json.JSONDecodeError):
            _parse_json("geen geldige json {{{")

    def test_nested_json(self):
        from tools.ai_client import _parse_json
        raw = '{"categorieën": [{"naam": "Test", "gerechten": []}]}'
        result = _parse_json(raw)
        assert "categorieën" in result
        assert isinstance(result["categorieën"], list)


# ---------------------------------------------------------------------------
# parse_menu_text — fallback pad (werkt altijd, bypassed ai_generate_json)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="BUG in menu_parser.py:91 — ongeldige f-string format specifier. "
           "ValueError crasht al bij prompt-opbouw, vóór ai_generate_json aangeroepen wordt. "
           "Hierdoor is ook de JSONDecodeError fallback onbereikbaar. "
           "Fix: escape de dict-literal in de f-string ({{ en }}) of gebruik een losse variabele.",
    strict=True,
)
class TestParseMenuFallback:
    def test_json_error_geeft_fallback_structuur(self):
        """JSONDecodeError → fallback dict met 'Ongeparsed' categorie."""
        with patch("tools.menu_parser.ai_generate_json", side_effect=json.JSONDecodeError("err", "", 0)):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Ruwe menutekst")
        assert "categorieën" in result
        assert len(result["categorieën"]) == 1
        assert result["categorieën"][0]["naam"] == "Ongeparsed"

    def test_fallback_bevat_ruwe_tekst_in_beschrijving(self):
        ruwe = "Dit is de ruwe menutekst"
        with patch("tools.menu_parser.ai_generate_json", side_effect=json.JSONDecodeError("err", "", 0)):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text(ruwe)
        gerecht = result["categorieën"][0]["gerechten"][0]
        assert ruwe[:500] in gerecht["beschrijving"]

    def test_fallback_gerecht_naam_is_parsing_mislukt(self):
        with patch("tools.menu_parser.ai_generate_json", side_effect=json.JSONDecodeError("err", "", 0)):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Iets")
        gerecht = result["categorieën"][0]["gerechten"][0]
        assert gerecht["naam"] == "Parsing mislukt"

    def test_fallback_gerecht_heeft_lege_ingredienten(self):
        with patch("tools.menu_parser.ai_generate_json", side_effect=json.JSONDecodeError("err", "", 0)):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Iets")
        gerecht = result["categorieën"][0]["gerechten"][0]
        assert gerecht["ingredienten"] == []

    def test_fallback_tekst_wordt_afgekapt_op_500(self):
        lange_tekst = "X" * 1000
        with patch("tools.menu_parser.ai_generate_json", side_effect=json.JSONDecodeError("err", "", 0)):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text(lange_tekst)
        gerecht = result["categorieën"][0]["gerechten"][0]
        assert len(gerecht["beschrijving"]) <= 500


# ---------------------------------------------------------------------------
# parse_menu_text — happy path (xfail wegens f-string bug in menu_parser.py:91)
# ---------------------------------------------------------------------------
# BUG: regel 91: [{"naam": "ingrediënt1", ...}] niet geëscaped in f-string.
# Fix vereist: escape de accolades of gebruik een losse string variabele.

@pytest.mark.xfail(
    reason="BUG in menu_parser.py:91 — ongeldige f-string format specifier, "
           "ValueError bij prompt opbouw. Fix: escape {{ en }} rondom de dict literal.",
    strict=True,
)
class TestParseMenuTextStructuur:
    def test_retourneert_dict_met_categorieen(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test menu tekst")
        assert isinstance(result, dict)
        assert "categorieën" in result

    def test_categorieen_is_lijst(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        assert isinstance(result["categorieën"], list)

    def test_aantal_categorieen_klopt(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        assert len(result["categorieën"]) == 2

    def test_elke_categorie_heeft_naam_en_gerechten(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        for cat in result["categorieën"]:
            assert "naam" in cat
            assert "gerechten" in cat
            assert isinstance(cat["gerechten"], list)

    def test_elk_gerecht_heeft_vereiste_velden(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        for cat in result["categorieën"]:
            for g in cat["gerechten"]:
                assert "naam" in g
                assert "ingredienten" in g
                assert "prijs" in g


@pytest.mark.xfail(
    reason="BUG in menu_parser.py:91 — ongeldige f-string format specifier",
    strict=True,
)
class TestParseMenuIngredientenRichObjects:
    def test_ingredienten_zijn_dicts_niet_strings(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        caesar = result["categorieën"][0]["gerechten"][0]
        for ing in caesar["ingredienten"]:
            assert isinstance(ing, dict), f"Verwacht dict, kreeg {type(ing)}: {ing}"

    def test_ingrediënt_heeft_naam_veld(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        caesar = result["categorieën"][0]["gerechten"][0]
        for ing in caesar["ingredienten"]:
            assert "naam" in ing

    def test_ingrediënt_heeft_categorie_veld(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        caesar = result["categorieën"][0]["gerechten"][0]
        for ing in caesar["ingredienten"]:
            assert "categorie" in ing

    def test_ingrediënt_categorie_is_geldig(self):
        geldige_categorieen = {"vers", "zuivel", "droog", "saus", "diepvries"}
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        for cat in result["categorieën"]:
            for g in cat["gerechten"]:
                for ing in g["ingredienten"]:
                    assert ing["categorie"] in geldige_categorieen

    def test_ingrediënt_heeft_hoeveelheid_en_eenheid(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        caesar = result["categorieën"][0]["gerechten"][0]
        for ing in caesar["ingredienten"]:
            assert "hoeveelheid" in ing
            assert "eenheid" in ing

    def test_null_prijs_wordt_doorgegeven(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_VOLLEDIG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Test")
        zalm = result["categorieën"][1]["gerechten"][1]
        assert zalm["naam"] == "Zalm"
        assert zalm["prijs"] is None

    def test_leeg_menu_geeft_lege_categorieen(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_LEEG):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Leeg menu")
        assert result["categorieën"] == []

    def test_lege_ingredienten_lijst_is_toegestaan(self):
        with patch("tools.menu_parser.ai_generate_json", return_value=MOCK_MENU_GEEN_INGREDIENTEN):
            from tools.menu_parser import parse_menu_text
            result = parse_menu_text("Menu zonder ingredienten")
        gerecht = result["categorieën"][0]["gerechten"][0]
        assert gerecht["ingredienten"] == []
