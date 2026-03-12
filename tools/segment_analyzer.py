"""
Segment Analyzer — analyseert een restaurant/keten via Gemini en bepaalt:
- Restaurant type en culinaire stijl
- Doelgroep / klant-segment
- Prijssegment
- Waardepropositie van het menu
- Bijzonderheden (duurzaam, seizoensgebonden, etc.)

Gebruik:
  from tools.segment_analyzer import analyze_segment
  result = analyze_segment("Van der Valk Ridderkerk", "Ridderkerk, Zuid-Holland")
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from tools.ai_client import ai_search_json


def analyze_segment(restaurant_naam: str, locatie: str) -> dict:
    """
    Analyseert een restaurant en geeft een menusegment-profiel terug.
    Gebruikt Gemini + Google Search voor actuele informatie.
    """

    prompt = f"""Analyseer dit restaurant en maak een compleet menusegment-profiel.

Restaurant: {restaurant_naam}
Locatie: {locatie}

Zoek informatie op over dit restaurant: type, keuken, sfeer, doelgroep, prijsniveau, menukaart.

Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):
{{
  "restaurant_naam": "{restaurant_naam}",
  "restaurant_type": ["type1"],
  "culinaire_stijl": ["stijl1", "stijl2"],
  "doelgroep": ["segment1", "segment2"],
  "prijssegment": "middensegment",
  "waardepropositie": "Korte beschrijving (2-3 zinnen) van wat dit restaurant uniek maakt qua menu-aanbod, kwaliteit en positionering.",
  "sfeer": "Korte beschrijving van de sfeer en ambiance.",
  "menu_kenmerken": ["kenmerk1", "kenmerk2"],
  "concurrenten": ["concurrent1", "concurrent2"],
  "sterke_punten": ["punt1", "punt2"],
  "verbeterpunten": ["punt1", "punt2"]
}}

Gebruik voor restaurant_type UITSLUITEND waarden uit deze vaste lijst:
hotel restaurant, bistro, fine dining, casual dining, brasserie, strandtent, eetcafe, fastfood, foodtruck, grand cafe, pannenkoekhuis, pizzeria, steakhouse, sushi restaurant, wok restaurant, tapas bar

Gebruik voor culinaire_stijl UITSLUITEND waarden uit deze vaste lijst:
Frans, Italiaans, Aziatisch, Nederlands, Internationaal, Fusion, Mediterraan, Amerikaans, Japans, Mexicaans, Thais, Indonesisch, Grieks, Midden-Oosters, Scandinavisch, Klassiek Europees

Gebruik voor doelgroep UITSLUITEND waarden uit deze vaste lijst:
zakenreizigers, gezinnen, koppels, lokale bewoners, toeristen, studenten, senioren, groepen, hotelgasten, sporters, dagjesmensen, fijnproevers, young professionals

Gebruik voor prijssegment UITSLUITEND een waarde uit:
budget, middensegment, premium, fine dining

Gebruik voor menu_kenmerken UITSLUITEND waarden uit deze vaste lijst:
seizoensgebonden, lokale ingredienten, duurzaam, biologisch, plantaardig, glutenvrij opties, halal, kosher, huisgemaakt, a la carte, buffet, dagmenu, proeverijmenu, kindermenu, ontbijt, lunch, diner, high tea, bar snacks

Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."""

    print(f"  Analyseer menusegment voor '{restaurant_naam}'...", end=" ", flush=True)

    try:
        result = ai_search_json(prompt, temperature=0.1)
        print("OK")
        return result
    except json.JSONDecodeError:
        print("! JSON parse fout, gebruik fallback")
        return {
            "restaurant_naam": restaurant_naam,
            "restaurant_type": ["restaurant"],
            "culinaire_stijl": ["Internationaal"],
            "doelgroep": ["lokale bewoners", "gezinnen"],
            "prijssegment": "middensegment",
            "waardepropositie": "Kon profiel niet automatisch bepalen. Pas dit aan.",
            "sfeer": "onbekend",
            "menu_kenmerken": [],
            "concurrenten": [],
            "sterke_punten": [],
            "verbeterpunten": []
        }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)

    naam = sys.argv[1]
    locatie = sys.argv[2]

    result = analyze_segment(naam, locatie)
    print(json.dumps(result, ensure_ascii=False, indent=2))
