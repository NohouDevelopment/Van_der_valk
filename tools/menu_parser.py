"""
Menu Parser — extraheert tekst uit PDF/afbeelding en parst naar gestructureerde JSON.

Stappen:
1. Tekst extractie:
   - PDF: PyMuPDF (fitz)
   - Afbeelding: Gemini vision
   - Tekst: direct gebruiken
2. AI parsing: Gemini parst ruwe tekst → categorieën → gerechten → ingrediënten

Gebruik:
  from tools.menu_parser import extract_text_from_pdf, parse_menu_text
  tekst = extract_text_from_pdf("menu.pdf")
  data = parse_menu_text(tekst)
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from tools.ai_client import ai_generate, ai_generate_json, ai_generate_vision


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extraheer tekst uit een PDF bestand via PyMuPDF."""
    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages).strip()


def extract_text_from_image(image_path: str) -> str:
    """Extraheer menutekst uit een afbeelding via AI vision."""
    return ai_generate_vision(
        prompt="""Lees deze menukaart-afbeelding en schrijf ALLE tekst over die je ziet.
Behoud de structuur: categorieën, gerechtnamen, beschrijvingen, prijzen.
Schrijf ALLEEN de menutekst, geen uitleg.""",
        image_path=image_path,
        temperature=0.1
    )


def parse_menu_text(ruwe_tekst: str) -> dict:
    """
    Parst ruwe menutekst naar gestructureerde JSON via Gemini.

    Returns:
        dict met structuur:
        {
            "categorieën": [
                {
                    "naam": "Voorgerechten",
                    "gerechten": [
                        {
                            "naam": "Caesar Salade",
                            "beschrijving": "Romaine sla, parmezaan, croutons",
                            "prijs": 12.50,
                            "ingredienten": ["romaine sla", "parmezaan", "croutons"],
                            "tags": ["klassiek"],
                            "dieet": ["vegetarisch"]
                        }
                    ]
                }
            ]
        }
    """
    prompt = f"""Analyseer deze menukaart-tekst en structureer het als JSON.

MENUTEKST:
---
{ruwe_tekst}
---

Geef je antwoord als JSON met EXACT dit formaat (geen extra tekst eromheen):
{{
  "categorieën": [
    {{
      "naam": "Categorienaam (bijv. Voorgerechten, Hoofdgerechten, etc.)",
      "gerechten": [
        {{
          "naam": "Naam van het gerecht",
          "beschrijving": "Korte beschrijving of ingrediënten zoals op de kaart",
          "prijs": 12.50,
          "ingredienten": [{{"naam": "ingrediënt1", "categorie": "vers", "hoeveelheid": 100, "eenheid": "g"}}],
          "tags": ["tag1"],
          "dieet": ["vegetarisch"]
        }}
      ]
    }}
  ]
}}

Regels:
- Behoud de oorspronkelijke categorieën van het menu
- Als er geen duidelijke categorieën zijn, maak er logische aan (Voorgerechten, Hoofdgerechten, etc.)
- Prijs als decimaal getal (bijv. 12.50), null als niet gevonden
- Ingrediënten: geef als array van objects [{naam, categorie, hoeveelheid, eenheid}]
  Categorieën (exact): "vers" (groente/fruit/vlees/vis), "zuivel" (kaas/boter/room/melk), "droog" (pasta/rijst/meel/kruiden/noten), "saus" (sauzen/olie/dressings), "diepvries" (diepvriesproducten)
  Hoeveelheid: getal per portie, null als onbekend. Eenheid: "g", "ml", "stuks" of ""
- Tags: bijv. "klassiek", "seizoen", "signature", "nieuw", "populair"
- Dieet: bijv. "vegetarisch", "veganistisch", "glutenvrij", "lactosevrij" — alleen als duidelijk

Antwoord ALLEEN met de JSON, geen markdown, geen uitleg eromheen."""

    print("  Menu tekst parsen naar JSON...", end=" ", flush=True)

    try:
        result = ai_generate_json(prompt, temperature=0.1)
        gerechten_count = sum(len(cat.get("gerechten", [])) for cat in result.get("categorieën", []))
        print(f"OK ({len(result.get('categorieën', []))} categorieën, {gerechten_count} gerechten)")
        return result
    except json.JSONDecodeError:
        print("! JSON parse fout, gebruik fallback")
        return {
            "categorieën": [{
                "naam": "Ongeparsed",
                "gerechten": [{
                    "naam": "Parsing mislukt",
                    "beschrijving": ruwe_tekst[:500],
                    "prijs": None,
                    "ingredienten": [],
                    "tags": [],
                    "dieet": []
                }]
            }]
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    pad = sys.argv[1]
    if pad.lower().endswith(".pdf"):
        tekst = extract_text_from_pdf(pad)
    else:
        tekst = Path(pad).read_text(encoding="utf-8")

    print(f"Ruwe tekst ({len(tekst)} chars):\n{tekst[:500]}\n---")
    data = parse_menu_text(tekst)
    print(json.dumps(data, ensure_ascii=False, indent=2))
