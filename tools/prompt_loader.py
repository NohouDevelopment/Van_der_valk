"""
Prompt Loader — laad en beheer AI-prompts uit YAML bestanden.

Functies:
  get_prompt(tool, name)          → {template, model, temperature, description}
  format_prompt(tool, name, **kw) → (formatted_prompt, resolved_model_id, temperature)
  get_all_prompts()               → {tool: {name: {...}}}
  save_prompt(tool, name, updates) → None
  reset_prompt(tool, name)        → None
  resolve_model(model_str)        → str

Laadvolgorde: YAML-bestand → overschrijft DEFAULTS.
Placeholders in templates: {variabele} — JSON-voorbeelden gebruiken {{ en }} voor letterlijke accolades.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_CHEAP         = os.getenv("MODEL_CHEAP",         "bytedance-seed/seed-2.0-mini")
MODEL_REASON        = os.getenv("MODEL_REASON",        "inception/mercury-2")
MODEL_SEARCH        = os.getenv("MODEL_SEARCH",        "perplexity/sonar")
MODEL_DEEP_RESEARCH = os.getenv("MODEL_DEEP_RESEARCH", "perplexity/sonar-deep-research")

_TIER_MAP = {
    "cheap":         MODEL_CHEAP,
    "reason":        MODEL_REASON,
    "search":        MODEL_SEARCH,
    "deep_research": MODEL_DEEP_RESEARCH,
}


def resolve_model(model_str: str) -> str:
    """Converteer tier-naam (cheap/reason/search) naar model-ID, of geef het ID direct terug."""
    return _TIER_MAP.get(model_str, model_str)


# ---------------------------------------------------------------------------
# DEFAULTS — exacte kopie van de prompts zoals ze in de tools stonden.
# Dienen als fallback als er geen YAML-bestand (of entry) bestaat.
# Gebruik {{ en }} in templates voor letterlijke accolades (JSON-voorbeelden).
# ---------------------------------------------------------------------------
DEFAULTS: dict = {

    "logo_extractor": {
        "find_website": {
            "description": "Zoek de officiële website URL van een bedrijf via AI",
            "model": "cheap",
            "temperature": 0.1,
            "template": (
                "Zoek de officiële website URL van dit bedrijf:\n"
                "Naam: {bedrijfsnaam}\n"
                "Adres: {adres}\n\n"
                "Antwoord ALLEEN met de URL (bijv. https://www.voorbeeld.nl), zonder verdere tekst.\n"
                "Als je geen website kunt vinden, antwoord dan met: NIET_GEVONDEN"
            ),
        },
    },

    "segment_analyzer": {
        "analyze_segment": {
            "description": "Analyseert restaurant type, segment, doelgroep via webzoekactie",
            "model": "search",
            "temperature": 0.1,
            "template": (
                "Analyseer dit restaurant en maak een compleet menusegment-profiel.\n\n"
                "Restaurant: {restaurant_naam}\n"
                "Locatie: {locatie}\n\n"
                "Zoek informatie op over dit restaurant: type, keuken, sfeer, doelgroep, prijsniveau, menukaart.\n\n"
                "Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):\n"
                "{{\n"
                '  "restaurant_naam": "{restaurant_naam}",\n'
                '  "restaurant_type": ["type1"],\n'
                '  "culinaire_stijl": ["stijl1", "stijl2"],\n'
                '  "doelgroep": ["segment1", "segment2"],\n'
                '  "prijssegment": "middensegment",\n'
                '  "waardepropositie": "Korte beschrijving (2-3 zinnen) van wat dit restaurant uniek maakt qua menu-aanbod, kwaliteit en positionering.",\n'
                '  "sfeer": "Korte beschrijving van de sfeer en ambiance.",\n'
                '  "menu_kenmerken": ["kenmerk1", "kenmerk2"],\n'
                '  "concurrenten": ["concurrent1", "concurrent2"],\n'
                '  "sterke_punten": ["punt1", "punt2"],\n'
                '  "verbeterpunten": ["punt1", "punt2"]\n'
                "}}\n\n"
                "Gebruik voor restaurant_type UITSLUITEND waarden uit deze vaste lijst:\n"
                "hotel restaurant, bistro, fine dining, casual dining, brasserie, strandtent, eetcafe, fastfood, foodtruck, grand cafe, pannenkoekhuis, pizzeria, steakhouse, sushi restaurant, wok restaurant, tapas bar\n\n"
                "Gebruik voor culinaire_stijl UITSLUITEND waarden uit deze vaste lijst:\n"
                "Frans, Italiaans, Aziatisch, Nederlands, Internationaal, Fusion, Mediterraan, Amerikaans, Japans, Mexicaans, Thais, Indonesisch, Grieks, Midden-Oosters, Scandinavisch, Klassiek Europees\n\n"
                "Gebruik voor doelgroep UITSLUITEND waarden uit deze vaste lijst:\n"
                "zakenreizigers, gezinnen, koppels, lokale bewoners, toeristen, studenten, senioren, groepen, hotelgasten, sporters, dagjesmensen, fijnproevers, young professionals\n\n"
                "Gebruik voor prijssegment UITSLUITEND een waarde uit:\n"
                "budget, middensegment, premium, fine dining\n\n"
                "Gebruik voor menu_kenmerken UITSLUITEND waarden uit deze vaste lijst:\n"
                "seizoensgebonden, lokale ingredienten, duurzaam, biologisch, plantaardig, glutenvrij opties, halal, kosher, huisgemaakt, a la carte, buffet, dagmenu, proeverijmenu, kindermenu, ontbijt, lunch, diner, high tea, bar snacks\n\n"
                "Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."
            ),
        },
    },

    "menu_parser": {
        "extract_image": {
            "description": "Lees menutekst uit een afbeelding via vision",
            "model": "cheap",
            "temperature": 0.1,
            "template": (
                "Lees deze menukaart-afbeelding en schrijf ALLE tekst over die je ziet.\n"
                "Behoud de structuur: categorieën, gerechtnamen, beschrijvingen, prijzen.\n"
                "Schrijf ALLEEN de menutekst, geen uitleg."
            ),
        },
        "parse_text": {
            "description": "Parseer ruwe menutekst naar gestructureerde JSON",
            "model": "cheap",
            "temperature": 0.1,
            "template": (
                "Analyseer deze menukaart-tekst en structureer het als JSON.\n\n"
                "MENUTEKST:\n"
                "---\n"
                "{ruwe_tekst}\n"
                "---\n\n"
                "Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):\n"
                "{{\n"
                '  "categorieën": [\n'
                "    {{\n"
                '      "naam": "Categorienaam (bijv. Voorgerechten, Hoofdgerechten, etc.)",\n'
                '      "gerechten": [\n'
                "        {{\n"
                '          "naam": "Naam van het gerecht",\n'
                '          "beschrijving": "Korte beschrijving of ingrediënten zoals op de kaart",\n'
                '          "prijs": 12.50,\n'
                '          "ingredienten": [{{"naam": "ingrediënt1", "categorie": "vers", "hoeveelheid": 100, "eenheid": "g"}}],\n'
                '          "tags": ["tag1"],\n'
                '          "dieet": ["vegetarisch"]\n'
                "        }}\n"
                "      ]\n"
                "    }}\n"
                "  ]\n"
                "}}\n\n"
                "Regels:\n"
                "- Behoud de oorspronkelijke categorieën van het menu\n"
                "- Als er geen duidelijke categorieën zijn, maak er logische aan (Voorgerechten, Hoofdgerechten, etc.)\n"
                "- Prijs als decimaal getal (bijv. 12.50), null als niet gevonden\n"
                '- Ingrediënten: geef als array van objects [{{"naam", "categorie", "hoeveelheid", "eenheid"}}]\n'
                '  Categorieën (exact): "vers" (groente/fruit/vlees/vis), "zuivel" (kaas/boter/room/melk), "droog" (pasta/rijst/meel/kruiden/noten), "saus" (sauzen/olie/dressings), "diepvries" (diepvriesproducten)\n'
                '  Hoeveelheid: getal per portie, null als onbekend. Eenheid: "g", "ml", "stuks" of ""\n'
                '- Tags: bijv. "klassiek", "seizoen", "signature", "nieuw", "populair"\n'
                '- Dieet: bijv. "vegetarisch", "veganistisch", "glutenvrij", "lactosevrij" — alleen als duidelijk\n\n'
                "Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."
            ),
        },
    },

    "trend_researcher": {
        "search_trends": {
            "description": "Zoek actuele food/horecatrends via Perplexity Deep Research per menucategorie-batch",
            "model": "deep_research",
            "temperature": 0.1,
            "template": (
                "Zoek actuele food trends en horeca innovaties voor 2025-2026 in Nederland en Europa.\n\n"
                "Restaurant context:\n"
                "- Type: {restaurant_type}\n"
                "- Culinaire stijl: {culinaire_stijl}\n"
                "- Prijssegment: {prijssegment}\n"
                "- Doelgroep: {doelgroep}\n\n"
                "Focus op deze menucategorieën: {cat_labels}"
                "{inspiratie_sectie}"
                "{focus_sectie}"
                "{custom_sectie}"
                "{menu_sectie}"
                "\n\nGeef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):\n"
                "{{\n"
                '  "trends": [\n'
                "    {{\n"
                '      "naam": "Korte trendnaam",\n'
                '      "beschrijving": "Beschrijving in 4-5 zinnen: wat is de trend, waar komt het vandaan, waarom groeit het, waarom relevant voor dit restaurant",\n'
                '      "categorie": "een van: {categories_json}",\n'
                '      "relevantie_score": 7.5,\n'
                '      "tags": ["tag1", "tag2"],\n'
                '      "inspiratiebron": "naam van de bron of null",\n'
                '      "broncontext": "Welke marktfactoren of consumentengedrag drijft deze trend (2-3 zinnen)",\n'
                '      "implementatie_voorbeelden": ["Concreet voorbeeld 1 hoe dit toe te passen", "Concreet voorbeeld 2", "Concreet voorbeeld 3"],\n'
                '      "restaurant_impact": "Specifieke impact en kans voor dit type restaurant en doelgroep (1-2 zinnen)"\n'
                "    }}\n"
                "  ],\n"
                '  "samenvatting": "Korte samenvatting (2-3 zinnen) van de belangrijkste trend-bewegingen"\n'
                "}}\n\n"
                "Regels:\n"
                "- Geef maximaal 5 trends per categorie\n"
                "- Score 1-10 op relevantie voor dit specifieke type restaurant\n"
                "- Categorie moet exact een van deze waarden zijn: {categories_json}\n"
                "- Tags: korte keywords die de trend beschrijven\n"
                "- Inspiratiebron: alleen invullen als de trend duidelijk gelinkt is aan een bron, anders null\n"
                "- Wees concreet: noem specifieke gerechten, ingrediënten of technieken\n"
                "- broncontext: leg uit welke maatschappelijke of marktfactoren de trend aandrijven\n"
                "- implementatie_voorbeelden: geef altijd 3 concrete, actionable voorbeelden die direct toepasbaar zijn\n"
                "- restaurant_impact: focus op de specifieke kans voor dit restaurant type en doelgroep\n"
                "- Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."
            ),
        },
    },

    "menu_annotator": {
        "annotate_menu": {
            "description": "Annoteer elk gerecht op basis van trends en restaurantprofiel (HOUDEN/AANPASSEN/VERVANGEN)",
            "model": "reason",
            "temperature": 0.2,
            "template": (
                "Analyseer elk gerecht op dit menu en geef een annotatie op basis van de actuele trends en het restaurantprofiel.\n\n"
                "RESTAURANTPROFIEL:\n"
                "{segment_context}\n\n"
                "ACTUELE TRENDS (gesorteerd op relevantie):\n"
                "{trends_context}\n\n"
                "MENU GERECHTEN:\n"
                "{gerechten_text}\n"
                "BESCHIKBARE INGREDIËNTEN IN DIT MENU:\n"
                "{ingredienten_context}\n"
                "{user_instructies_sectie}"
                "\nGeef per gerecht een annotatie. Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):\n"
                "{{\n"
                '  "annotaties": [\n'
                "    {{\n"
                '      "gerecht_naam": "Naam van het gerecht",\n'
                '      "categorie": "Categorie",\n'
                '      "status": "HOUDEN",\n'
                '      "score": 7.5,\n'
                '      "opmerkingen": "Korte uitleg waarom dit gerecht deze status krijgt",\n'
                '      "suggesties": ["Concrete suggestie 1", "Concrete suggestie 2"],\n'
                '      "relevante_trends": ["Trend 1", "Trend 2"],\n'
                '      "positief": ["Positief punt 1"]\n'
                "    }}\n"
                "  ]\n"
                "}}\n\n"
                "Regels:\n"
                "- Status is EXACT een van: HOUDEN, AANPASSEN, VERVANGEN\n"
                "  - HOUDEN: standaard voor klassieke, tijdloze of goed passende gerechten (score ≥ 6.5)\n"
                "  - AANPASSEN: alleen als er een CONCRETE, relevante trend is die dit specifieke gerecht direct verbetert (score 5.0–6.4)\n"
                "  - VERVANGEN: UITSLUITEND voor gerechten die fundamenteel niet bij het segment passen (score ≤ 4.9)\n"
                "- Streef naar een REALISTISCHE verdeling: minimaal 50% HOUDEN, max 30% AANPASSEN, max 20% VERVANGEN\n"
                "- Klassieke gerechten (salade, soep, steak, zalm, pasta, risotto, kip, kalfsvlees, etc.) krijgen standaard HOUDEN tenzij er een sterke reden is voor aanpassen\n"
                "- Elke trend mag MAXIMAAL 2x voorkomen als 'relevante_trend' over het TOTALE menu — wees selectief, niet elke trend bij elk gerecht\n"
                "- Stel NOOIT aanpassingen voor die het karakter of de identiteit van het gerecht verbreken (een Dame Blanche blijft een Dame Blanche, een Caesar Salade blijft een Caesar Salade)\n"
                "- Baseer suggesties op ingrediënten die AL in het menu voorkomen — introduceer max 1 nieuw ingrediënt per suggestie\n"
                "- Score 1–10: hoe goed past het gerecht bij huidige trends EN het restaurantsegment\n"
                "- Opmerkingen: max 2 zinnen, concreet en actionable\n"
                "- Suggesties: max 3 concrete verbetervoorstellen (leeg bij HOUDEN)\n"
                "- Relevante trends: welke trends zijn van toepassing op dit gerecht (max 3)\n"
                "- Positief: wat is goed aan dit gerecht (max 2 punten)\n"
                "- Houd rekening met het prijssegment en de doelgroep\n"
                "- Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."
            ),
        },
        "suggest_additions": {
            "description": "Suggereer 3-5 nieuwe gerechten op basis van trends en bestaande ingrediënten",
            "model": "reason",
            "temperature": 0.3,
            "template": (
                "Op basis van de actuele trends en de bestaande ingrediënten van dit menu, stel 3-5 NIEUWE gerechten voor die toegevoegd kunnen worden.\n\n"
                "RESTAURANTPROFIEL:\n"
                "{segment_context}\n\n"
                "ACTUELE TRENDS:\n"
                "{trends_context}\n\n"
                "BESCHIKBARE INGREDIËNTEN IN DIT MENU:\n"
                "{ingredienten_context}\n\n"
                "BESTAANDE GERECHTEN (niet dupliceren):\n"
                "{bestaande_str}"
                "{focus_trends_sectie}"
                "{focus_eigenschappen_sectie}"
                "{ingredient_context_sectie}"
                "{extra_instructie_sectie}"
                "\n\nGeef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):\n"
                "{{\n"
                '  "voorstellen": [\n'
                "    {{\n"
                '      "naam": "Naam van het nieuwe gerecht",\n'
                '      "categorie": "Menuonderdeel (bijv. Voorgerechten, Hoofdgerechten)",\n'
                '      "beschrijving": "Korte omschrijving in 1-2 zinnen",\n'
                '      "gebruikte_ingredienten": ["ingrediënt1", "ingrediënt2"],\n'
                '      "nieuwe_ingredienten": ["nieuw ingrediënt"],\n'
                '      "relevante_trend": "Naam van de trend waarop dit gebaseerd is",\n'
                '      "onderbouwing": "Waarom past dit gerecht bij het restaurant en de trend (1-2 zinnen)",\n'
                '      "marktfit": "Welke trend(s) dit ondersteunt en waarom relevant (1-2 zinnen)",\n'
                '      "conceptfit": "Waarom dit past bij het segment, de doelgroep en de propositie (1-2 zinnen)",\n'
                '      "operationele_fit": {{"ingrediënt_hergebruik_pct": 75, "derving_impact": "laag", "extra_inkoop": ["nieuw ingrediënt"]}}\n'
                "    }}\n"
                "  ]\n"
                "}}\n\n"
                "Regels:\n"
                "- Elk nieuw gerecht gebruikt MINIMAAL 2-3 ingrediënten die al in het menu voorkomen\n"
                "- Introduceer maximaal 1-2 nieuwe ingrediënten per gerecht (de rest is al beschikbaar)\n"
                "- Elk voorstel is onderbouwd door een specifieke trend uit het geheugen\n"
                "- Houd rekening met het prijssegment en de doelgroep van het restaurant\n"
                "- Kies namen in het Nederlands of de taal die past bij de restaurantstijl\n"
                "- marktfit: beschrijf welke trend(s) het voorstel ondersteunt en waarom dat relevant is\n"
                "- conceptfit: beschrijf hoe het voorstel past bij het segment en de doelgroep\n"
                "- operationele_fit: geef ingrediënt_hergebruik_pct (0-100), derving_impact (laag/middel/hoog), en extra_inkoop (lijst nieuwe ingrediënten)\n"
                "- Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."
            ),
        },
    },

    "ingredient_suggester": {
        "suggest_dishes": {
            "description": "Genereer 3 gerecht-voorstellen op basis van risico-ingrediënten en trends",
            "model": "reason",
            "temperature": 0.3,
            "template": (
                "Je bent een menu-consultant. Genereer EXACT 3 nieuwe gerecht-voorstellen als JSON array.\n\n"
                "CONTEXT:\n"
                "Risico-ingrediënten (single-use vers, dreigen te bederven): {risico}\n"
                "Top ingrediënten (al veel gebruikt): {top_5_namen}\n"
                "Alle beschikbare ingrediënten: {beschikbaar}"
                "{segment_tekst}"
                "{trend_tekst}"
                "{verkoop_tekst}"
                "\n\nREGELS:\n"
                "1. Elk voorstel MOET minimaal 2 risico-ingrediënten hergebruiken\n"
                "2. Maximaal 2 NIEUWE ingrediënten per gerecht (minimaliseer inkoop)\n"
                "3. Voorstel 1: focus op derving-reductie (hergebruik risico-ingrediënten)\n"
                "4. Voorstel 2: focus op trend/seizoen (past bij actuele trends)\n"
                "5. Voorstel 3: gebaseerd op ingrediënten van best verkopende gerechten (of premium variant als geen kassaboek data)\n\n"
                "Per ingrediënt in het voorstel, geef status:\n"
                '- "bestaand" = al in meerdere gerechten\n'
                '- "bestaand_kritiek" = single-use, wordt nu hergebruikt\n'
                '- "nieuw_vers" = nieuw vers ingrediënt\n'
                '- "nieuw_droog" = nieuw droog/lang houdbaar ingrediënt\n\n'
                "ANTWOORD als JSON array (GEEN markdown, GEEN uitleg):\n"
                "[\n"
                "  {{\n"
                '    "gerecht": {{\n'
                '      "naam": "Naam van het gerecht",\n'
                '      "beschrijving": "Korte beschrijving",\n'
                '      "categorie": "Categorie",\n'
                '      "prijs_suggestie": 18.50\n'
                "    }},\n"
                '    "ingredienten": [\n'
                '      {{"naam": "ingrediënt", "status": "bestaand", "hoeveelheid": 100, "eenheid": "g"}}\n'
                "    ]\n"
                "  }}\n"
                "]"
            ),
        },
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _load_yaml(tool: str) -> dict:
    """Laad YAML bestand voor een tool; geeft {} terug als niet gevonden."""
    yaml_path = PROMPTS_DIR / f"{tool}.yaml"
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def get_prompt(tool: str, name: str) -> dict:
    """
    Haal prompt-config op.
    YAML heeft prioriteit over DEFAULTS.
    Geeft {} terug als prompt niet bestaat.
    """
    yaml_data = _load_yaml(tool)
    if name in yaml_data:
        return yaml_data[name]
    return DEFAULTS.get(tool, {}).get(name, {})


def format_prompt(tool: str, name: str, **kwargs) -> tuple[str, str, float]:
    """
    Haal prompt op, vul placeholders in, resolve model.

    Returns:
        (formatted_prompt, resolved_model_id, temperature)
    """
    config = get_prompt(tool, name)
    if not config:
        raise ValueError(f"Prompt '{tool}/{name}' niet gevonden in YAML of DEFAULTS.")

    template = config.get("template", "")
    try:
        formatted = template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Ontbrekende placeholder in prompt '{tool}/{name}': {e}")

    model_id = resolve_model(config.get("model", "cheap"))
    temperature = float(config.get("temperature", 0.1))
    return formatted, model_id, temperature


def get_all_prompts() -> dict:
    """
    Geef alle prompts terug voor de admin UI.
    YAML overschrijft DEFAULTS per naam-entry.
    """
    result = {}
    for tool, defaults in DEFAULTS.items():
        result[tool] = {}
        yaml_data = _load_yaml(tool)
        for name, default_config in defaults.items():
            if name in yaml_data:
                result[tool][name] = yaml_data[name]
            else:
                result[tool][name] = default_config
    return result


def save_prompt(tool: str, name: str, updates: dict) -> None:
    """Sla prompt-wijzigingen op in het YAML bestand van de tool."""
    yaml_path = PROMPTS_DIR / f"{tool}.yaml"
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Begin met huidige waarden (YAML of DEFAULT), pas updates toe
    current = dict(get_prompt(tool, name))
    current.update(updates)
    data[name] = current

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
                  width=120, indent=2)


def reset_prompt(tool: str, name: str) -> None:
    """Herstel prompt naar default door de YAML-entry te verwijderen."""
    yaml_path = PROMPTS_DIR / f"{tool}.yaml"
    if not yaml_path.exists():
        return

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if name in data:
        del data[name]

    if data:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
                      width=120, indent=2)
    else:
        yaml_path.unlink()
