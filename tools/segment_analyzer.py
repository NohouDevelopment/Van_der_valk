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

from tools.ai_client import ai_call
from tools.prompt_loader import format_prompt


def analyze_segment(restaurant_naam: str, locatie: str) -> dict:
    """
    Analyseert een restaurant en geeft een menusegment-profiel terug.
    Gebruikt Gemini + Google Search voor actuele informatie.
    """
    prompt, model, temp = format_prompt("segment_analyzer", "analyze_segment",
                                        restaurant_naam=restaurant_naam, locatie=locatie)

    print(f"  Analyseer menusegment voor '{restaurant_naam}'...", end=" ", flush=True)

    try:
        result = ai_call(prompt, model=model, temperature=temp, json_mode=True)
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
