"""
Ingredient Analyzer — analyseert ingrediënten over alle gerechten.

Berekent per ingrediënt:
- gebruik_count: in hoeveel gerechten
- gerechten_detail: per gerecht naam + hoeveelheid + eenheid
- omloop_status: hoog | medium | kritiek | laag
- geschatte_omloop: wekelijkse omloop op basis van kassaboek (of N/B)
- versheids_risico: hoog | medium | laag
- strategie: aanbeveling op basis van status + risico
- kleur: green | yellow | red | gray (voor UI)

Gebruik:
    from tools.ingredient_analyzer import analyseer_ingredienten
    analyse = analyseer_ingredienten(gerechten, verkoop_data=None)
"""


def _is_vers(categorie: str) -> bool:
    """Check of een ingrediënt-categorie bederfelijk is."""
    return categorie in ("vers", "zuivel")


def _omloop_status(count: int, vers: bool) -> tuple[str, str]:
    """Bepaal omloop-status en kleur op basis van gebruik en versheid.

    Returns: (status, kleur)
    """
    if vers:
        if count >= 4:
            return "hoog", "green"
        elif count >= 2:
            return "medium", "yellow"
        else:
            return "kritiek", "red"
    else:
        if count >= 2:
            return "hoog", "green"
        else:
            return "laag", "gray"


def _versheids_risico(categorie: str) -> str:
    """Bepaal versheidsrisico op basis van categorie."""
    if categorie == "vers":
        return "hoog"
    elif categorie == "zuivel":
        return "medium"
    elif categorie == "diepvries":
        return "laag"
    else:  # droog, saus
        return "laag"


def _strategie(omloop: str, categorie: str) -> str:
    """Bepaal strategie-advies op basis van omloop-status en categorie."""
    vers = _is_vers(categorie)

    if omloop == "hoog" and vers:
        return "Behouden: hoge rotatie voorkomt derving."
    elif omloop == "medium" and vers:
        return "Monitoring: bekijk of meer gerechten dit kunnen gebruiken."
    elif omloop == "kritiek":
        return "Saneren: zoek meer gerechten of verwijder van de kaart."
    elif omloop == "laag" and categorie in ("droog", "saus"):
        return "Luxe-item: geen dervingsgevaar, wel dode voorraad."
    elif omloop == "hoog" and not vers:
        return "Kern-ingrediënt: sterke basis van je menu."
    elif omloop == "laag" and categorie == "diepvries":
        return "Veilig: lang houdbaar in vriezer."
    else:
        return "Neutraal: geen direct risico."


def _geschatte_omloop(gerechten_detail: list, verkoop_data: dict | None) -> dict:
    """
    Bereken geschatte wekelijkse omloop per ingrediënt.

    Args:
        gerechten_detail: lijst van {gerecht, hoeveelheid, eenheid}
        verkoop_data: dict gerecht_naam -> gem_wekelijks_verkocht (of None)

    Returns:
        {"beschikbaar": bool, "waarde": float|None, "eenheid": str, "label": str}
    """
    if not verkoop_data:
        return {"beschikbaar": False, "waarde": None, "eenheid": "", "label": "N/B"}

    totaal = 0
    eenheid = ""
    for detail in gerechten_detail:
        if not eenheid and detail.get("eenheid"):
            eenheid = detail["eenheid"]
        h = detail.get("hoeveelheid") or 0
        verkocht = verkoop_data.get(detail["gerecht"], 0)
        totaal += h * verkocht

    if totaal == 0:
        return {"beschikbaar": True, "waarde": 0, "eenheid": eenheid, "label": f"0 {eenheid}/week"}

    if totaal >= 1000 and eenheid == "g":
        val = round(totaal / 1000, 1)
        return {"beschikbaar": True, "waarde": val, "eenheid": "kg/week", "label": f"~{val} kg/week"}
    elif totaal >= 1000 and eenheid == "ml":
        val = round(totaal / 1000, 1)
        return {"beschikbaar": True, "waarde": val, "eenheid": "L/week", "label": f"~{val} L/week"}
    else:
        val = round(totaal, 1)
        return {"beschikbaar": True, "waarde": val, "eenheid": f"{eenheid}/week", "label": f"~{val} {eenheid}/week"}


def analyseer_ingredienten(gerechten, verkoop_data=None) -> dict:
    """
    Analyseer ingrediënten over alle gerechten.

    Args:
        gerechten: lijst van Gerecht objecten met gevulde ingredienten JSON
        verkoop_data: optioneel dict {gerecht_naam: gem_wekelijks_verkocht}

    Returns:
        dict met ingredienten array, statistieken en synergie_score
    """
    # Stap 1: Verzamel alle ingrediënten en tel gebruik
    ingredient_data = {}  # naam -> {categorie, gerechten set, gerechten_detail list}

    totaal_gerechten = 0
    totaal_ingredienten_links = 0  # totaal aantal ingrediënt-gerecht koppelingen

    for gerecht in gerechten:
        ings = gerecht.ingredienten or []
        if not ings:
            continue

        totaal_gerechten += 1
        totaal_ingredienten_links += len(ings)

        for ing in ings:
            # Backwards-compat: oud formaat is een string, nieuw formaat is een dict
            if isinstance(ing, str):
                ing = {"naam": ing, "categorie": "droog"}
            naam = ing.get("naam", "").lower().strip()
            categorie = ing.get("categorie", "droog")
            if not naam:
                continue

            if naam not in ingredient_data:
                ingredient_data[naam] = {
                    "categorie": categorie,
                    "gerechten": set(),
                    "gerechten_detail": [],
                }
            ingredient_data[naam]["gerechten"].add(gerecht.naam)
            ingredient_data[naam]["gerechten_detail"].append({
                "gerecht": gerecht.naam,
                "hoeveelheid": ing.get("hoeveelheid"),
                "eenheid": ing.get("eenheid", ""),
            })

    # Stap 2: Bereken metrics per ingrediënt
    resultaat = []
    vers_count = 0
    single_use_vers = 0
    risico_ingredienten = []

    for naam, data in ingredient_data.items():
        count = len(data["gerechten"])
        cat = data["categorie"]
        vers = _is_vers(cat)
        omloop, kleur = _omloop_status(count, vers)
        risico = _versheids_risico(cat)
        strat = _strategie(omloop, cat)
        geschat = _geschatte_omloop(data["gerechten_detail"], verkoop_data)

        entry = {
            "naam": naam,
            "categorie": cat,
            "gebruik_count": count,
            "gerechten": sorted(data["gerechten"]),
            "gerechten_detail": data["gerechten_detail"],
            "omloop_status": omloop,
            "geschatte_omloop": geschat,
            "versheids_risico": risico,
            "strategie": strat,
            "kleur": kleur,
        }
        resultaat.append(entry)

        if vers:
            vers_count += 1
        if omloop == "kritiek":
            single_use_vers += 1
            risico_ingredienten.append(naam)

    # Sorteer: kritiek eerst, dan medium, dan hoog, dan laag
    status_order = {"kritiek": 0, "medium": 1, "hoog": 2, "laag": 3}
    resultaat.sort(key=lambda x: (status_order.get(x["omloop_status"], 9), -x["gebruik_count"]))

    # Stap 3: Statistieken
    totaal_uniek = len(ingredient_data)
    gemiddeld = round(totaal_ingredienten_links / max(totaal_gerechten, 1), 1)

    # Top 5 meest gebruikt
    top_5 = sorted(ingredient_data.items(), key=lambda x: -len(x[1]["gerechten"]))[:5]
    top_5_list = [{"naam": n, "count": len(d["gerechten"])} for n, d in top_5]

    # Synergie score: percentage ingrediënten dat in 2+ gerechten voorkomt
    # Hoe hoger, hoe meer overlap → efficiënter inkopen
    if totaal_uniek > 0:
        gedeeld = sum(1 for d in ingredient_data.values() if len(d["gerechten"]) >= 2)
        synergie = round((gedeeld / totaal_uniek) * 100)
    else:
        synergie = 0

    return {
        "ingredienten": resultaat,
        "statistieken": {
            "totaal_uniek": totaal_uniek,
            "vers_ingredienten": vers_count,
            "single_use_vers": single_use_vers,
            "gemiddeld_gebruik": gemiddeld,
            "top_5_meest_gebruikt": top_5_list,
            "risico_ingredienten": risico_ingredienten,
        },
        "synergie_score": synergie,
    }
