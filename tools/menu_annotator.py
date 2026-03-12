"""
Menu Annotator — genereert per-gerecht annotaties op basis van trendgeheugen en menusegment.

Per gerecht bepaalt de AI:
- Status: HOUDEN / AANPASSEN / VERVANGEN
- Score (1-10): hoe goed past dit gerecht bij trends
- Opmerkingen: concrete suggesties
- Relevante trends: welke trends zijn van toepassing

Gebruik:
  from tools.menu_annotator import annotate_menu
  annotaties = annotate_menu(menu_data, geheugen_data, segment_data)
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from tools.ai_client import ai_reason_json


def _build_trends_context(geheugen_data: dict) -> str:
    """Bouw een compacte samenvatting van actieve trends voor de prompt."""
    trends = geheugen_data.get("trends", [])
    actief = [t for t in trends if t.get("status") == "actief"]

    if not actief:
        return "Geen actieve trends beschikbaar."

    # Sorteer op effectieve score
    actief.sort(key=lambda t: t.get("effectieve_score", 0), reverse=True)

    lines = []
    for t in actief[:20]:  # Max 20 trends meegeven
        score = t.get("effectieve_score", 0)
        bev = t.get("bevestigingen", 1)
        tags = ", ".join(t.get("tags", [])[:4])
        lines.append(f"- {t['naam']} (score:{score}, {bev}x bevestigd, cat:{t.get('categorie','?')}, tags:{tags})")
        if t.get("beschrijving"):
            lines.append(f"  {t['beschrijving'][:150]}")

    return "\n".join(lines)


def _build_segment_context(segment_data: dict) -> str:
    """Bouw een compacte samenvatting van het menusegment voor de prompt."""
    parts = []
    if segment_data.get("restaurant_type"):
        parts.append(f"Type: {', '.join(segment_data['restaurant_type'])}")
    if segment_data.get("culinaire_stijl"):
        parts.append(f"Stijl: {', '.join(segment_data['culinaire_stijl'])}")
    if segment_data.get("prijssegment"):
        parts.append(f"Prijssegment: {segment_data['prijssegment']}")
    if segment_data.get("doelgroep"):
        parts.append(f"Doelgroep: {', '.join(segment_data['doelgroep'])}")
    if segment_data.get("waardepropositie"):
        parts.append(f"Waardepropositie: {segment_data['waardepropositie'][:200]}")
    return "\n".join(parts)


def _build_gerechten_lijst(menu_data: dict) -> list[dict]:
    """Extraheer een platte lijst van gerechten uit menu data."""
    gerechten = []
    for cat in menu_data.get("categorieën", []):
        cat_naam = cat.get("naam", "Overig")
        for g in cat.get("gerechten", []):
            gerechten.append({
                "categorie": cat_naam,
                "naam": g.get("naam", "Onbekend"),
                "beschrijving": g.get("beschrijving", ""),
                "prijs": g.get("prijs"),
                "tags": g.get("tags", []),
                "dieet": g.get("dieet", [])
            })
    return gerechten


def annotate_menu(menu_data: dict, geheugen_data: dict, segment_data: dict) -> list[dict]:
    """
    Genereer annotaties voor elk gerecht in het menu.

    Args:
        menu_data: Menu.data (categorieën → gerechten)
        geheugen_data: TrendGeheugen.data (actieve trends)
        segment_data: MenuSegment.data (restaurant profiel)

    Returns:
        list van annotatie dicts, een per gerecht:
        [
            {
                "gerecht_naam": "Caesar Salade",
                "categorie": "Voorgerechten",
                "status": "AANPASSEN",
                "score": 6.5,
                "opmerkingen": "Goed basisgerecht, maar kan moderner...",
                "suggesties": ["Voeg gefermenteerde groenten toe", "..."],
                "relevante_trends": ["Fermentatie", "Seizoensgebonden"],
                "positief": ["Klassieke keuze", "Breed gewaardeerd"]
            }
        ]
    """
    gerechten = _build_gerechten_lijst(menu_data)
    if not gerechten:
        return []

    trends_context = _build_trends_context(geheugen_data)
    segment_context = _build_segment_context(segment_data)

    # Bouw gerechten overzicht voor de prompt
    gerechten_text = ""
    for i, g in enumerate(gerechten):
        prijs_str = f" ({g['prijs']})" if g.get('prijs') else ""
        desc = f" — {g['beschrijving']}" if g.get('beschrijving') else ""
        gerechten_text += f"{i+1}. [{g['categorie']}] {g['naam']}{prijs_str}{desc}\n"

    prompt = f"""Analyseer elk gerecht op dit menu en geef een annotatie op basis van de actuele trends en het restaurantprofiel.

RESTAURANTPROFIEL:
{segment_context}

ACTUELE TRENDS (gesorteerd op relevantie):
{trends_context}

MENU GERECHTEN:
{gerechten_text}

Geef per gerecht een annotatie. Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):
{{
  "annotaties": [
    {{
      "gerecht_naam": "Naam van het gerecht",
      "categorie": "Categorie",
      "status": "HOUDEN",
      "score": 7.5,
      "opmerkingen": "Korte uitleg waarom dit gerecht deze status krijgt",
      "suggesties": ["Concrete suggestie 1", "Concrete suggestie 2"],
      "relevante_trends": ["Trend 1", "Trend 2"],
      "positief": ["Positief punt 1"]
    }}
  ]
}}

Regels:
- Status is EXACT een van: HOUDEN, AANPASSEN, VERVANGEN
  - HOUDEN: gerecht past goed bij trends en segment, geen grote wijzigingen nodig
  - AANPASSEN: gerecht heeft potentieel maar kan beter aansluiten bij trends
  - VERVANGEN: gerecht past niet meer bij trends of segment, overweeg vervanging
- Score 1-10: hoe goed past het gerecht bij huidige trends EN het restaurantsegment
- Opmerkingen: max 2 zinnen, concreet en actionable
- Suggesties: max 3 concrete verbetervoorstellen (leeg bij HOUDEN)
- Relevante trends: welke trends zijn van toepassing op dit gerecht (max 3)
- Positief: wat is goed aan dit gerecht (max 2 punten)
- Houd rekening met het prijssegment en de doelgroep
- Wees realistisch: niet alles hoeft te veranderen, een goed menu heeft een mix
- Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."""

    print(f"  Menu annoteren ({len(gerechten)} gerechten)...", end=" ", flush=True)

    try:
        result = ai_reason_json(prompt, temperature=0.2)
        annotaties = result.get("annotaties", [])
        statussen = {}
        for a in annotaties:
            s = a.get("status", "?")
            statussen[s] = statussen.get(s, 0) + 1
        status_str = ", ".join(f"{k}:{v}" for k, v in statussen.items())
        print(f"OK ({len(annotaties)} annotaties: {status_str})")
        return annotaties
    except json.JSONDecodeError:
        print("! JSON parse fout, gebruik fallback")
        return [{
            "gerecht_naam": g["naam"],
            "categorie": g["categorie"],
            "status": "HOUDEN",
            "score": 5.0,
            "opmerkingen": "Kon niet automatisch annoteren. Bekijk handmatig.",
            "suggesties": [],
            "relevante_trends": [],
            "positief": []
        } for g in gerechten]


if __name__ == "__main__":
    # Test met mock data
    test_menu = {
        "categorieën": [
            {
                "naam": "Voorgerechten",
                "gerechten": [
                    {"naam": "Caesar Salade", "beschrijving": "Romaine, parmezaan, croutons", "prijs": 12.50},
                    {"naam": "Tomatensoep", "beschrijving": "Huisgemaakt met basilicum", "prijs": 8.95}
                ]
            },
            {
                "naam": "Hoofdgerechten",
                "gerechten": [
                    {"naam": "Biefstuk", "beschrijving": "Black Angus, friet, bearnaise", "prijs": 24.50},
                    {"naam": "Zalm", "beschrijving": "Gebakken zalm, groenten", "prijs": 22.00}
                ]
            }
        ]
    }

    test_geheugen = {
        "trends": [
            {"naam": "Fermentatie", "beschrijving": "Gefermenteerde groenten", "categorie": "voorgerechten",
             "effectieve_score": 8.5, "bevestigingen": 3, "tags": ["fermentatie", "umami"], "status": "actief"},
            {"naam": "Plant-based", "beschrijving": "Plantaardige alternatieven", "categorie": "vegan_veg",
             "effectieve_score": 7.0, "bevestigingen": 2, "tags": ["plantaardig"], "status": "actief"},
        ]
    }

    test_segment = {
        "restaurant_type": ["hotel restaurant"],
        "culinaire_stijl": ["Internationaal"],
        "prijssegment": "middensegment",
        "doelgroep": ["zakenreizigers", "hotelgasten"]
    }

    annotaties = annotate_menu(test_menu, test_geheugen, test_segment)
    print(json.dumps(annotaties, ensure_ascii=False, indent=2))
