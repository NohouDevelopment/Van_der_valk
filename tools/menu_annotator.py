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
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

from tools.ai_client import ai_call
from tools.prompt_loader import format_prompt


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


def _build_ingredienten_context(menu_data: dict) -> str:
    """Extraheer alle unieke ingrediënten uit menu_data als platte string."""
    ingredienten = set()
    for cat in menu_data.get("categorieën", []):
        for g in cat.get("gerechten", []):
            # Beschrijving als bron
            if g.get("beschrijving"):
                # Voeg beschrijving keywords toe als rough ingrediëntenlijst
                for word in g["beschrijving"].split(","):
                    word = word.strip().lower()
                    if word and len(word) > 2:
                        ingredienten.add(word)
            # Expliciete ingrediëntenlijst
            for ing in g.get("ingredienten", []):
                if ing:
                    ingredienten.add(str(ing).strip().lower())
            # Tags kunnen ook ingrediënten bevatten
            for tag in g.get("tags", []):
                if tag:
                    ingredienten.add(str(tag).strip().lower())
    if not ingredienten:
        return "Geen expliciete ingrediënten beschikbaar."
    return ", ".join(sorted(ingredienten))


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


def annotate_menu(menu_data: dict, geheugen_data: dict, segment_data: dict, user_instructions: str = "") -> list[dict]:
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
    ingredienten_context = _build_ingredienten_context(menu_data)

    # Bouw gerechten overzicht voor de prompt
    gerechten_text = ""
    for i, g in enumerate(gerechten):
        prijs_str = f" ({g['prijs']})" if g.get('prijs') else ""
        desc = f" — {g['beschrijving']}" if g.get('beschrijving') else ""
        gerechten_text += f"{i+1}. [{g['categorie']}] {g['naam']}{prijs_str}{desc}\n"

    user_instructies_sectie = ""
    if user_instructions:
        user_instructies_sectie = (
            f"\nEXTRA INSTRUCTIE VAN DE GEBRUIKER (hogere prioriteit — verwerk dit in je analyse):\n"
            f"{user_instructions}\n"
        )

    prompt, model, temp = format_prompt(
        "menu_annotator", "annotate_menu",
        segment_context=segment_context,
        trends_context=trends_context,
        gerechten_text=gerechten_text,
        ingredienten_context=ingredienten_context,
        user_instructies_sectie=user_instructies_sectie,
    )

    logger.info("Menu annoteren (%d gerechten)...", len(gerechten))

    try:
        result = ai_call(prompt, model=model, temperature=temp, json_mode=True)
        annotaties = result.get("annotaties", [])
        statussen = {}
        for a in annotaties:
            s = a.get("status", "?")
            statussen[s] = statussen.get(s, 0) + 1
        status_str = ", ".join(f"{k}:{v}" for k, v in statussen.items())
        logger.info("OK (%d annotaties: %s)", len(annotaties), status_str)
        return annotaties
    except json.JSONDecodeError:
        logger.warning("JSON parse fout, gebruik fallback")
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


def suggereer_toevoegingen(menu_data: dict, geheugen_data: dict, segment_data: dict,
                           focus_trends: list[str] | None = None,
                           focus_eigenschappen: list[str] | None = None,
                           ingredient_context: str | None = None,
                           extra_instructie: str | None = None) -> list[dict]:
    """
    Genereer 3-5 suggesties voor nieuwe gerechten op basis van trends en bestaande ingrediënten.

    Args:
        ingredient_context: Samenvatting van ingrediënt-analyse (risico-ingrediënten etc.)
        extra_instructie: Vrije tekst van gebruiker

    Returns:
        list van voorstel dicts met explainability:
        [{"naam", "categorie", "beschrijving", "gebruikte_ingredienten", "nieuwe_ingredienten",
          "relevante_trend", "onderbouwing", "marktfit", "conceptfit", "operationele_fit"}]
    """
    ingredienten_ctx = _build_ingredienten_context(menu_data)
    trends_context = _build_trends_context(geheugen_data)
    segment_context = _build_segment_context(segment_data)

    # Bestaande gerechtnamen zodat AI ze niet dupliceert
    bestaande = []
    for cat in menu_data.get("categorieën", []):
        for g in cat.get("gerechten", []):
            if g.get("naam"):
                bestaande.append(g["naam"])
    bestaande_str = ", ".join(bestaande[:30]) if bestaande else "geen"

    focus_trends_sectie = ""
    if focus_trends:
        focus_trends_sectie = f"\n\nGEWENSTE TRENDS (baseer de voorstellen PRIMAIR op deze trends):\n" + "\n".join(f"- {t}" for t in focus_trends)

    focus_eigenschappen_sectie = ""
    if focus_eigenschappen:
        focus_eigenschappen_sectie = f"\n\nGEWENSTE EIGENSCHAPPEN (elk voorstel moet aan minstens één van deze eigenschappen voldoen):\n" + "\n".join(f"- {e}" for e in focus_eigenschappen)

    ingredient_context_sectie = ""
    if ingredient_context:
        ingredient_context_sectie = f"\n\nINGREDIËNT-ANALYSE (houd hier rekening mee bij ingrediëntkeuze):\n{ingredient_context}"

    extra_instructie_sectie = ""
    if extra_instructie:
        extra_instructie_sectie = f"\n\nEXTRA INSTRUCTIE VAN DE GEBRUIKER (hogere prioriteit):\n{extra_instructie}"

    prompt, model, temp = format_prompt(
        "menu_annotator", "suggest_additions",
        segment_context=segment_context,
        trends_context=trends_context,
        ingredienten_context=ingredienten_ctx,
        bestaande_str=bestaande_str,
        focus_trends_sectie=focus_trends_sectie,
        focus_eigenschappen_sectie=focus_eigenschappen_sectie,
        ingredient_context_sectie=ingredient_context_sectie,
        extra_instructie_sectie=extra_instructie_sectie,
    )

    logger.info("Toevoegingen suggereren...")

    try:
        result = ai_call(prompt, model=model, temperature=temp, json_mode=True)
        voorstellen = result.get("voorstellen", [])
        logger.info("OK (%d suggesties)", len(voorstellen))
        return voorstellen
    except json.JSONDecodeError:
        logger.warning("JSON parse fout bij toevoegingen")
        return []
    except Exception as e:
        logger.warning("Fout bij toevoegingen: %s", e)
        return []


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
