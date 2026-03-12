"""
Trend Researcher — zoekt actuele food- en horecatrends via Gemini + Google Search.

Stappen:
1. Bouw zoekqueries op basis van TrendConfig (categorieën, inspiratie, focus)
2. Per batch een Gemini + Google Search grounded call
3. Merge en dedupliceer resultaten

Gebruik:
  from tools.trend_researcher import research_trends
  result = research_trends(segment_data, config_data, menu_data)
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from tools.ai_client import ai_search_json


# Vaste categorie-labels voor prompts
CATEGORIE_LABELS = {
    "voorgerechten": "Voorgerechten & starters",
    "soepen": "Soepen & bouillons",
    "vis": "Vis & zeevruchten",
    "vegan_veg": "Vegan & vegetarische gerechten",
    "vlees": "Vlees & gevogelte",
    "nagerechten": "Nagerechten & desserts",
    "dranken": "Dranken & cocktails"
}

# Inspiratiebron-labels voor zoekcontext
INSPIRATIE_LABELS = {
    # Chefs & Restaurants
    "michelin": "Michelin-sterrenzaken en fine dining trends",
    "ottolenghi": "Ottolenghi (Midden-Oosterse/Mediterrane fusion, groenten-first)",
    "ramsay": "Gordon Ramsay (technieken, presentatie, bistro-stijl)",
    "jamie_oliver": "Jamie Oliver (toegankelijk, seizoensgebonden, gezond)",
    "noma": "Noma, New Nordic, foraging, fermentatie, seizoenspurisme",
    "bottura": "Massimo Bottura (Italiaans, anti-voedselverspilling, creativiteit)",
    "worlds_50_best": "World's 50 Best Restaurants innovaties en trends",
    "momofuku": "David Chang (umami, Aziatisch-Amerikaans, bold flavours)",
    # Keukenstijlen
    "streetfood": "Streetfood-elevatie en food truck innovaties",
    "asian_fusion": "Aziatische fusion (umami, fermentatie, kruiden)",
    "nordic": "Nordic/Scandinavische keuken (puur, lokaal, minimalistisch)",
    "mediterranean": "Mediterrane keuken (olijfolie, verse kruiden, gedeelde gerechten)",
    "koreaans": "Koreaanse keuken (gochujang, kimchi, Korean BBQ, banchan)",
    "japans": "Japanse keuken (omakase, izakaya, ramen, precisie)",
    "midden_oosten": "Midden-Oosterse keuken (za'atar, tahini, flatbreads, mezze)",
    "latijns": "Latijns-Amerikaanse keuken (ceviche, mole, empanadas, chimichurri)",
    # Media & Platforms
    "tiktok": "TikTok food trends, virale recepten, social media hypes",
    "bon_appetit": "Bon Appétit, Eater, Food & Wine publicaties",
    "culy": "Culy.nl, 24Kitchen, Nederlandse food blogs en publicaties",
    # Industrie & Research
    "horeca_nl": "Misset Horeca, Thuisbezorgd trends, KHN, Nederlandse horeca-innovaties",
    "innova": "Innova Market Insights, Technomic, food industry forecasts",
    "gault_millau": "GaultMillau, Bib Gourmand, culinaire gidsen trends Nederland",
    "neo_bistro": "Neo-bistro, casual fine dining, bistronomy, accessible luxury",
}

# Focusthema-labels voor zoekcontext
FOCUS_LABELS = {
    # Ingrediënten & Bereiding
    "plantaardig": "plantaardige groei, plant-based alternatieven, vleesvervangers",
    "fermentatie": "fermentatie, preservering, umami, kimchi, miso, zuurdesem",
    "seizoen": "seizoensgebonden menu's, jaargetijden, vers van het land",
    "lokaal": "lokale leveranciers, ambachtelijke producten, korte keten, boerderij-naar-bord",
    "premium": "truffel, wagyu, kaviaar, high-end producten, luxe ingrediënten",
    "fusion": "cross-culturele fusion, hybride gerechten, onverwachte combinaties",
    # Beleving & Concept
    "nostalgie": "nostalgie, comfort food, klassiekers met een twist",
    "experience": "sharing plates, omakase-stijl, open keuken, theatraal serveren",
    "social_media": "instagrammable gerechten, visuele presentatie, food styling",
    "brunch": "all-day brunch, ontbijt-innovaties, brunch culture",
    "mocktails": "ambachtelijke cocktails, no/low alcohol, botanicals, mocktails",
    # Duurzaamheid & Gezondheid
    "duurzaamheid": "duurzaamheid, lokale ingrediënten, korte keten, CO2-reductie",
    "food_waste": "food waste reductie, zero waste koken, nose-to-tail, root-to-stem",
    "allergiebewust": "allergiebewust, glutenvrij, lactosevrij, notenvrij opties",
    "gezondheid": "functioneel eten, superfoods, gut health, anti-inflammatoir",
    "gen_z": "Gen Z eetcultuur, snackification, bold flavours, TikTok-recepten",
}


def _get_default_config() -> dict:
    """Return default TrendConfig wanneer geen config bestaat."""
    return {
        "categorieen": {
            "voorgerechten": True,
            "soepen": True,
            "vis": True,
            "vegan_veg": True,
            "vlees": True,
            "nagerechten": True,
            "dranken": True
        },
        "inspiratiebronnen": [],
        "focusthemas": [],
        "custom_prompt": ""
    }


def _extract_menu_context(menu_data: dict | None) -> str:
    """Extraheer relevante context uit het actieve menu voor de prompt."""
    if not menu_data:
        return ""

    lines = []
    for cat in menu_data.get("categorieën", []):
        cat_naam = cat.get("naam", "Overig")
        gerechten = [g.get("naam", "") for g in cat.get("gerechten", []) if g.get("naam")]
        if gerechten:
            lines.append(f"  {cat_naam}: {', '.join(gerechten[:8])}")

    if not lines:
        return ""

    return "Huidige menugerechten ter referentie:\n" + "\n".join(lines)


def _build_search_batches(config: dict, segment_data: dict, menu_data: dict | None) -> list[dict]:
    """Bouw zoekbatches op basis van config en segment."""
    categorieen = config.get("categorieen", {})

    # Groepeer enabled categorieën in batches
    batch_defs = [
        ("Hartige gerechten", ["voorgerechten", "soepen", "vis", "vlees"]),
        ("Plantaardig & zoet", ["vegan_veg", "nagerechten"]),
        ("Dranken", ["dranken"]),
    ]

    batches = []
    for batch_label, cat_keys in batch_defs:
        enabled = [k for k in cat_keys if categorieen.get(k, True)]
        if not enabled:
            continue

        cat_labels = [CATEGORIE_LABELS[k] for k in enabled]
        batches.append({
            "label": batch_label,
            "categories": enabled,
            "category_labels": cat_labels
        })

    return batches


def _build_prompt(batch: dict, config: dict, segment_data: dict, menu_context: str) -> str:
    """Bouw de Gemini prompt voor een zoekbatch."""
    # Segment context
    restaurant_type = ", ".join(segment_data.get("restaurant_type", ["restaurant"]))
    culinaire_stijl = ", ".join(segment_data.get("culinaire_stijl", ["Internationaal"]))
    prijssegment = segment_data.get("prijssegment", "middensegment")
    doelgroep = ", ".join(segment_data.get("doelgroep", ["lokale bewoners"]))

    cat_labels = ", ".join(batch["category_labels"])
    categories_json = json.dumps(batch["categories"])

    # Optionele secties
    inspiratie_sectie = ""
    inspiratie = config.get("inspiratiebronnen", [])
    if inspiratie:
        bronnen = [INSPIRATIE_LABELS.get(b, b) for b in inspiratie]
        inspiratie_sectie = f"\nLet specifiek op trends geïnspireerd door: {'; '.join(bronnen)}"

    focus_sectie = ""
    focus = config.get("focusthemas", [])
    if focus:
        themas = [FOCUS_LABELS.get(f, f) for f in focus]
        focus_sectie = f"\nExtra aandacht voor deze thema's: {'; '.join(themas)}"

    custom_sectie = ""
    custom = config.get("custom_prompt", "").strip()
    if custom:
        custom_sectie = f"\nExtra instructie van de gebruiker: {custom}"

    menu_sectie = ""
    if menu_context:
        menu_sectie = f"\n{menu_context}"

    prompt = f"""Zoek actuele food trends en horeca innovaties voor 2025-2026 in Nederland en Europa.

Restaurant context:
- Type: {restaurant_type}
- Culinaire stijl: {culinaire_stijl}
- Prijssegment: {prijssegment}
- Doelgroep: {doelgroep}

Focus op deze menucategorieën: {cat_labels}
{inspiratie_sectie}{focus_sectie}{custom_sectie}{menu_sectie}

Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):
{{
  "trends": [
    {{
      "naam": "Korte trendnaam",
      "beschrijving": "Beschrijving in 2-3 zinnen: wat is de trend, waarom relevant, hoe toepassen",
      "categorie": "een van: {categories_json}",
      "relevantie_score": 7.5,
      "tags": ["tag1", "tag2"],
      "inspiratiebron": "naam van de bron of null"
    }}
  ],
  "samenvatting": "Korte samenvatting (2-3 zinnen) van de belangrijkste trend-bewegingen"
}}

Regels:
- Geef maximaal 5 trends per categorie
- Score 1-10 op relevantie voor dit specifieke type restaurant
- Categorie moet exact een van deze waarden zijn: {categories_json}
- Tags: korte keywords die de trend beschrijven
- Inspiratiebron: alleen invullen als de trend duidelijk gelinkt is aan een bron, anders null
- Wees concreet: noem specifieke gerechten, ingrediënten of technieken
- Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."""

    return prompt


def _execute_search(prompt: str, label: str) -> dict:
    """Voer een AI search call uit via OpenRouter."""
    print(f"    Zoek: {label}...", end=" ", flush=True)

    try:
        result = ai_search_json(prompt, temperature=0.1)
        trend_count = len(result.get("trends", []))
        print(f"OK ({trend_count} trends)")
        return result

    except json.JSONDecodeError:
        print("! JSON parse fout")
        return {"trends": [], "samenvatting": ""}
    except Exception as e:
        print(f"! Fout: {e}")
        return {"trends": [], "samenvatting": ""}


def research_trends(segment_data: dict, config_data: dict | None, menu_data: dict | None) -> dict:
    """
    Hoofdfunctie: onderzoek food/horecatrends via Gemini + Google Search.

    Args:
        segment_data: MenuSegment.data (restaurant type, stijl, doelgroep, etc.)
        config_data: TrendConfig.data of None (gebruikt defaults)
        menu_data: Menu.data van het actieve menu of None

    Returns:
        dict met trends array, samenvatting, zoek_queries, timestamp
    """
    config = config_data or _get_default_config()

    print("  Trendanalyse starten...", flush=True)

    # Menu context extraheren
    menu_context = _extract_menu_context(menu_data)

    # Zoekbatches opbouwen
    batches = _build_search_batches(config, segment_data, menu_data)

    if not batches:
        print("  ! Geen categorieën enabled, skip analyse")
        return {
            "trends": [],
            "samenvatting": "Geen categorieën geselecteerd voor analyse.",
            "zoek_queries": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # Per batch een zoekoproep doen
    alle_trends = []
    alle_samenvattingen = []
    zoek_queries = []

    for batch in batches:
        prompt = _build_prompt(batch, config, segment_data, menu_context)
        zoek_queries.append(batch["label"])

        result = _execute_search(prompt, batch["label"])

        for trend in result.get("trends", []):
            # Valideer dat categorie geldig is
            if trend.get("categorie") not in batch["categories"]:
                trend["categorie"] = batch["categories"][0]
            alle_trends.append(trend)

        if result.get("samenvatting"):
            alle_samenvattingen.append(result["samenvatting"])

    # Dedupliceer op trend naam (case-insensitive)
    gezien = {}
    unieke_trends = []
    for trend in alle_trends:
        naam_lower = trend.get("naam", "").lower().strip()
        if naam_lower in gezien:
            # Behoud de versie met hogere score
            if trend.get("relevantie_score", 0) > gezien[naam_lower].get("relevantie_score", 0):
                unieke_trends = [t for t in unieke_trends if t.get("naam", "").lower().strip() != naam_lower]
                unieke_trends.append(trend)
                gezien[naam_lower] = trend
        else:
            gezien[naam_lower] = trend
            unieke_trends.append(trend)

    # Sorteer op score (hoog → laag)
    unieke_trends.sort(key=lambda t: t.get("relevantie_score", 0), reverse=True)

    # Combineer samenvattingen
    samenvatting = " ".join(alle_samenvattingen) if alle_samenvattingen else ""

    print(f"  Trendanalyse klaar: {len(unieke_trends)} unieke trends gevonden")

    return {
        "trends": unieke_trends,
        "samenvatting": samenvatting,
        "zoek_queries": zoek_queries,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    # Test met mock segment data
    test_segment = {
        "restaurant_type": ["hotel restaurant"],
        "culinaire_stijl": ["Internationaal", "Frans"],
        "doelgroep": ["zakenreizigers", "hotelgasten", "koppels"],
        "prijssegment": "middensegment"
    }

    test_config = {
        "categorieen": {
            "voorgerechten": True,
            "soepen": False,
            "vis": True,
            "vegan_veg": True,
            "vlees": True,
            "nagerechten": True,
            "dranken": False
        },
        "inspiratiebronnen": ["michelin", "ottolenghi"],
        "focusthemas": ["duurzaamheid", "seizoen"],
        "custom_prompt": ""
    }

    result = research_trends(test_segment, test_config, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
