"""
Validators — output validatie voor AI-gegenereerde data.

Elk valideert structuur en geeft (is_valid, errors) terug.
Repareert NIET — als data ongeldig is, fail duidelijk.
"""


def validate_menu_parse(data: dict) -> tuple[bool, list[str]]:
    """Valideer geparsde menu data."""
    errors = []

    if not isinstance(data, dict):
        return False, ["Data is geen dict"]

    cats = data.get("categorieën")
    if not cats or not isinstance(cats, list):
        errors.append("Ontbrekende of lege 'categorieën' key")
        return False, errors

    for i, cat in enumerate(cats):
        if not isinstance(cat, dict):
            errors.append(f"Categorie {i} is geen dict")
            continue
        if not cat.get("naam"):
            errors.append(f"Categorie {i} mist 'naam'")
        gerechten = cat.get("gerechten")
        if not gerechten or not isinstance(gerechten, list):
            errors.append(f"Categorie {i} ({cat.get('naam', '?')}) heeft geen gerechten")
            continue
        for j, g in enumerate(gerechten):
            if not isinstance(g, dict):
                errors.append(f"Gerecht {j} in categorie {i} is geen dict")
                continue
            if not g.get("naam"):
                errors.append(f"Gerecht {j} in categorie {i} mist 'naam'")

    return len(errors) == 0, errors


def validate_annotatie(data: dict) -> tuple[bool, list[str]]:
    """Valideer een enkele annotatie."""
    errors = []

    if not isinstance(data, dict):
        return False, ["Data is geen dict"]

    status = data.get("status", "")
    if status not in ("HOUDEN", "AANPASSEN", "VERVANGEN"):
        errors.append(f"Ongeldige status: '{status}' (verwacht HOUDEN/AANPASSEN/VERVANGEN)")

    score = data.get("score")
    if score is None:
        errors.append("Ontbrekende 'score'")
    elif not isinstance(score, (int, float)) or score < 1 or score > 10:
        errors.append(f"Ongeldige score: {score} (verwacht 1-10)")

    return len(errors) == 0, errors


def validate_trend_research(data: dict) -> tuple[bool, list[str]]:
    """Valideer trend research output."""
    errors = []

    if not isinstance(data, dict):
        return False, ["Data is geen dict"]

    trends = data.get("trends")
    if not trends or not isinstance(trends, list):
        errors.append("Ontbrekende of lege 'trends' key")
        return False, errors

    for i, t in enumerate(trends):
        if not isinstance(t, dict):
            errors.append(f"Trend {i} is geen dict")
            continue
        if not t.get("naam"):
            errors.append(f"Trend {i} mist 'naam'")
        if not t.get("beschrijving"):
            errors.append(f"Trend {i} mist 'beschrijving'")

    return len(errors) == 0, errors


def validate_voorstel(data: dict) -> tuple[bool, list[str]]:
    """Valideer een voorstel voor een nieuw gerecht (gekoppeld aan UI-contract)."""
    errors = []

    if not isinstance(data, dict):
        return False, ["Data is geen dict"]

    for veld in ("naam", "beschrijving", "categorie"):
        if not data.get(veld):
            errors.append(f"Ontbrekend veld: '{veld}'")

    for fit_veld in ("marktfit", "conceptfit", "operationele_fit"):
        if not data.get(fit_veld):
            errors.append(f"Ontbrekend fit-veld: '{fit_veld}'")

    return len(errors) == 0, errors
