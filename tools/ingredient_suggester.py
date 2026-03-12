"""
Ingredient Suggester — genereert slimme gerecht-voorstellen via AI.
"""
from tools.ai_client import ai_reason_json


def genereer_voorstel(analyse_data: dict, segment_data: dict | None = None, geheugen_data: dict | None = None, verkoop_data: dict | None = None) -> list[dict]:
    """
    Genereer 2-3 slimme gerecht-voorstellen via AI.

    Args:
        analyse_data:  output van analyseer_ingredienten()
        segment_data:  MenuSegment.data (optioneel)
        geheugen_data: TrendGeheugen.data (optioneel)
        verkoop_data:  dict met top_5/flop_5 verkochte gerechten uit kassaboek (optioneel)

    Returns: list van dicts, elk met {gerecht, ingredienten, synergie_check}
    """
    risico = analyse_data.get("statistieken", {}).get("risico_ingredienten", [])
    top_5 = analyse_data.get("statistieken", {}).get("top_5_meest_gebruikt", [])

    # Bouw ingredient lookup
    lookup = {}
    for ing in analyse_data.get("ingredienten", []):
        lookup[ing["naam"]] = {
            "categorie": ing["categorie"],
            "count": ing["gebruik_count"],
            "omloop": ing["omloop_status"],
        }

    # Bouw context voor AI
    segment_tekst = ""
    if segment_data:
        segment_tekst = f"""
Restaurant profiel:
- Culinaire stijl: {segment_data.get('culinaire_stijl', 'onbekend')}
- Prijssegment: {segment_data.get('prijssegment', 'onbekend')}
- Doelgroep: {segment_data.get('doelgroep', 'onbekend')}"""

    trend_tekst = ""
    if geheugen_data and isinstance(geheugen_data, dict):
        trends = geheugen_data.get("trends", [])[:5]
        if trends:
            trend_namen = [t.get("naam", "") for t in trends if t.get("naam")]
            trend_tekst = f"\nActuele trends: {', '.join(trend_namen)}"

    verkoop_tekst = ""
    if verkoop_data and isinstance(verkoop_data, dict):
        best = [g["naam"] for g in verkoop_data.get("top_5", [])]
        slecht = [g["naam"] for g in verkoop_data.get("flop_5", [])]
        if best:
            verkoop_tekst += f"\nBest verkopende gerechten (afgelopen 4 weken): {', '.join(best)} — gebruik hun ingrediënten als basis voor nieuwe voorstellen."
        if slecht:
            verkoop_tekst += f"\nSlecht verkopende gerechten: {', '.join(slecht)} — overweeg deze te vervangen of hun ingrediënten in betere combinaties te hergebruiken."

    prompt = f"""Je bent een menu-consultant. Genereer EXACT 3 nieuwe gerecht-voorstellen als JSON array.

CONTEXT:
Risico-ingrediënten (single-use vers, dreigen te bederven): {risico}
Top ingrediënten (al veel gebruikt): {[t['naam'] for t in top_5]}
Alle beschikbare ingrediënten: {list(lookup.keys())}
{segment_tekst}
{trend_tekst}
{verkoop_tekst}

REGELS:
1. Elk voorstel MOET minimaal 2 risico-ingrediënten hergebruiken
2. Maximaal 2 NIEUWE ingrediënten per gerecht (minimaliseer inkoop)
3. Voorstel 1: focus op derving-reductie (hergebruik risico-ingrediënten)
4. Voorstel 2: focus op trend/seizoen (past bij actuele trends)
5. Voorstel 3: gebaseerd op ingrediënten van best verkopende gerechten (of premium variant als geen kassaboek data)

Per ingrediënt in het voorstel, geef status:
- "bestaand" = al in meerdere gerechten
- "bestaand_kritiek" = single-use, wordt nu hergebruikt
- "nieuw_vers" = nieuw vers ingrediënt
- "nieuw_droog" = nieuw droog/lang houdbaar ingrediënt

ANTWOORD als JSON array (GEEN markdown, GEEN uitleg):
[
  {{
    "gerecht": {{
      "naam": "Naam van het gerecht",
      "beschrijving": "Korte beschrijving",
      "categorie": "Categorie",
      "prijs_suggestie": 18.50
    }},
    "ingredienten": [
      {{"naam": "ingrediënt", "status": "bestaand", "hoeveelheid": 100, "eenheid": "g"}}
    ]
  }}
]"""

    try:
        raw_voorstellen = ai_reason_json(prompt, temperature=0.3)

        if not isinstance(raw_voorstellen, list):
            raw_voorstellen = [raw_voorstellen]

        # Bereken synergie_check server-side per voorstel
        resultaat = []
        for v in raw_voorstellen[:3]:
            ings = v.get("ingredienten", [])
            bestaand_count = sum(1 for i in ings if i.get("status", "").startswith("bestaand"))
            totaal = max(len(ings), 1)
            bestaand_pct = round((bestaand_count / totaal) * 100)
            nieuwe_items = totaal - bestaand_count
            nieuwe_vers = sum(1 for i in ings if i.get("status") == "nieuw_vers")
            hergebruikte_risico = [i["naam"] for i in ings if i.get("status") == "bestaand_kritiek"]

            # Voeg in_gerechten toe vanuit lookup
            for i in ings:
                i["in_gerechten"] = lookup.get(i["naam"], {}).get("count", 0)

            v["synergie_check"] = {
                "bestaand_percentage": bestaand_pct,
                "nieuwe_items": nieuwe_items,
                "nieuwe_vers": nieuwe_vers,
                "hergebruikte_risico": hergebruikte_risico,
                "verwachte_derving_impact": f"Omloop van {', '.join(hergebruikte_risico)} stijgt van Kritiek naar Medium." if hergebruikte_risico else "Geen directe dervingsreductie.",
                "samenvatting": f"Dit gerecht gebruikt {bestaand_pct}% bestaande ingrediënten. {nieuwe_items} nieuw item{'s' if nieuwe_items != 1 else ''} nodig."
            }
            resultaat.append(v)

        return resultaat

    except Exception as e:
        print(f"  ! AI voorstel fout: {e}, gebruik fallback")
        return [_mock_voorstel(analyse_data)]


def _mock_voorstel(analyse_data: dict) -> dict:
    """Fallback mock voorstel als AI faalt."""
    risico = analyse_data.get("statistieken", {}).get("risico_ingredienten", [])[:3]
    return {
        "gerecht": {
            "naam": "Seizoensgerecht (AI niet beschikbaar)",
            "beschrijving": f"Een gerecht dat {', '.join(risico)} hergebruikt.",
            "categorie": "Suggestie",
            "prijs_suggestie": 16.50,
        },
        "ingredienten": [
            {"naam": n, "status": "bestaand_kritiek", "in_gerechten": 1, "hoeveelheid": 100, "eenheid": "g"}
            for n in risico
        ],
        "synergie_check": {
            "bestaand_percentage": 100,
            "nieuwe_items": 0,
            "nieuwe_vers": 0,
            "hergebruikte_risico": risico,
            "verwachte_derving_impact": "Fallback voorstel — hergebruikt alleen risico-ingrediënten.",
            "samenvatting": "AI was niet beschikbaar. Dit is een basisvoorstel."
        },
    }
