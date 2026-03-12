"""
Trend Combiner — combineert een nieuwe trendanalyse met het bestaande trendgeheugen.

Eerste run: analyse wordt direct het initiële geheugen.
Volgende runs: semantische matching (difflib) + bevestigingsscores + recency-weging.

Gebruik:
  from tools.trend_combiner import combine_trends
  nieuw_geheugen = combine_trends(analyse_data, bestaand_geheugen_data)
"""

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

# Matching threshold: 0.75 = 75% overeenkomst in genormaliseerde naam
MATCH_THRESHOLD = 0.75


def _normalize_naam(naam: str) -> str:
    """Normaliseer trend naam voor matching: lowercase, strip, verwijder lidwoorden."""
    naam = naam.lower().strip()
    # Verwijder veel voorkomende lidwoorden en voegwoorden
    for woord in ["de ", "het ", "een ", "en ", "& ", "van ", "met ", "voor "]:
        naam = naam.replace(woord, "")
    # Verwijder extra spaties
    naam = re.sub(r"\s+", " ", naam).strip()
    return naam


def _match_score(naam1: str, naam2: str) -> float:
    """Bereken overeenkomst tussen twee trend namen via SequenceMatcher + substring check."""
    n1 = _normalize_naam(naam1)
    n2 = _normalize_naam(naam2)

    # Exacte match na normalisatie
    if n1 == n2:
        return 1.0

    # Substring match: als de ene naam volledig in de andere zit → hoge score
    if len(n1) >= 4 and len(n2) >= 4:
        if n1 in n2 or n2 in n1:
            return 0.9

    return SequenceMatcher(None, n1, n2).ratio()


def _maanden_verschil(datum_str: str, nu: datetime) -> float:
    """Bereken het aantal maanden tussen een ISO datum string en nu."""
    try:
        datum = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
        if datum.tzinfo is None:
            datum = datum.replace(tzinfo=timezone.utc)
        verschil = nu - datum
        return verschil.days / 30.44  # gemiddeld aantal dagen per maand
    except (ValueError, TypeError):
        return 0.0


def _recency_factor(maanden: float) -> float:
    """Bereken de recency factor op basis van maanden sinds laatste bevestiging."""
    if maanden < 1:
        return 1.0
    elif maanden < 3:
        return 0.85
    elif maanden < 6:
        return 0.6
    else:
        return 0.3


def _bevestigings_bonus(bevestigingen: int) -> float:
    """Bereken de bevestigingsbonus: 1.0 + (0.15 * min(bevestigingen-1, 4))."""
    return 1.0 + (0.15 * min(max(bevestigingen - 1, 0), 4))


def _bereken_effectieve_score(trend: dict, nu: datetime) -> float:
    """Bereken de effectieve score op basis van basis_score, recency en bevestigingen."""
    basis = trend.get("basis_score", 5.0)
    maanden = _maanden_verschil(trend.get("laatst_bevestigd", ""), nu)
    recency = _recency_factor(maanden)
    bonus = _bevestigings_bonus(trend.get("bevestigingen", 1))

    score = basis * recency * bonus
    # Cap op 10.0
    return round(min(score, 10.0), 1)


def _merge_lijsten(bestaand: list, nieuw: list) -> list:
    """Merge twee lijsten met unieke waarden (case-insensitive)."""
    gezien = {s.lower() for s in bestaand}
    result = list(bestaand)
    for item in nieuw:
        if item.lower() not in gezien:
            result.append(item)
            gezien.add(item.lower())
    return result


def combine_trends(nieuwe_analyse_data: dict, bestaand_geheugen_data: dict | None) -> dict:
    """
    Combineer een nieuwe trendanalyse met het bestaande geheugen.

    Args:
        nieuwe_analyse_data: TrendAnalyse.data (output van research_trends)
        bestaand_geheugen_data: TrendGeheugen.data of None (eerste run)

    Returns:
        dict met geüpdatet geheugen: trends array + statistieken
    """
    nu = datetime.now(timezone.utc)
    nu_iso = nu.isoformat()
    nieuwe_trends = nieuwe_analyse_data.get("trends", [])

    stats = {
        "totaal_actief": 0,
        "nieuw_deze_run": 0,
        "bevestigd_deze_run": 0,
        "verouderd": 0,
        "verlopen_verwijderd": 0
    }

    # --- Eerste run: alles is nieuw ---
    if bestaand_geheugen_data is None:
        geheugen_trends = []
        for trend in nieuwe_trends:
            geheugen_trends.append({
                "naam": trend.get("naam", "Onbekend"),
                "beschrijving": trend.get("beschrijving", ""),
                "categorie": trend.get("categorie", "overig"),
                "basis_score": trend.get("relevantie_score", 5.0),
                "effectieve_score": trend.get("relevantie_score", 5.0),
                "bevestigingen": 1,
                "eerste_gezien": nu_iso,
                "laatst_bevestigd": nu_iso,
                "tags": trend.get("tags", []),
                "bronnen": trend.get("bronnen", []),
                "status": "actief"
            })

        stats["nieuw_deze_run"] = len(geheugen_trends)
        stats["totaal_actief"] = len(geheugen_trends)

        # Sorteer op score
        geheugen_trends.sort(key=lambda t: t.get("effectieve_score", 0), reverse=True)

        print(f"  Geheugen aangemaakt: {len(geheugen_trends)} nieuwe trends")

        return {
            "trends": geheugen_trends,
            "statistieken": stats
        }

    # --- Volgende runs: match en combineer ---
    bestaande_trends = list(bestaand_geheugen_data.get("trends", []))
    gematchte_indices = set()  # indices van bestaande trends die gematcht zijn

    for nieuwe_trend in nieuwe_trends:
        nieuwe_naam = nieuwe_trend.get("naam", "")
        beste_match_idx = None
        beste_match_score = 0

        # Zoek de beste match in bestaande trends
        for i, bestaande_trend in enumerate(bestaande_trends):
            if i in gematchte_indices:
                continue  # Al gematcht met een andere nieuwe trend

            score = _match_score(nieuwe_naam, bestaande_trend.get("naam", ""))
            if score > beste_match_score:
                beste_match_score = score
                beste_match_idx = i

        if beste_match_score >= MATCH_THRESHOLD and beste_match_idx is not None:
            # Match gevonden: update bestaande trend
            bestaand = bestaande_trends[beste_match_idx]
            gematchte_indices.add(beste_match_idx)

            bestaand["bevestigingen"] = bestaand.get("bevestigingen", 1) + 1
            bestaand["laatst_bevestigd"] = nu_iso
            bestaand["beschrijving"] = nieuwe_trend.get("beschrijving", bestaand.get("beschrijving", ""))

            # Gemiddelde van oude en nieuwe basis_score
            oude_score = bestaand.get("basis_score", 5.0)
            nieuwe_score = nieuwe_trend.get("relevantie_score", 5.0)
            bestaand["basis_score"] = round((oude_score + nieuwe_score) / 2, 1)

            # Merge tags en bronnen
            bestaand["tags"] = _merge_lijsten(
                bestaand.get("tags", []),
                nieuwe_trend.get("tags", [])
            )
            bestaand["bronnen"] = _merge_lijsten(
                bestaand.get("bronnen", []),
                nieuwe_trend.get("bronnen", [])
            )

            bestaand["status"] = "actief"
            stats["bevestigd_deze_run"] += 1
        else:
            # Geen match: nieuwe trend toevoegen
            bestaande_trends.append({
                "naam": nieuwe_trend.get("naam", "Onbekend"),
                "beschrijving": nieuwe_trend.get("beschrijving", ""),
                "categorie": nieuwe_trend.get("categorie", "overig"),
                "basis_score": nieuwe_trend.get("relevantie_score", 5.0),
                "effectieve_score": nieuwe_trend.get("relevantie_score", 5.0),
                "bevestigingen": 1,
                "eerste_gezien": nu_iso,
                "laatst_bevestigd": nu_iso,
                "tags": nieuwe_trend.get("tags", []),
                "bronnen": nieuwe_trend.get("bronnen", []),
                "status": "actief"
            })
            stats["nieuw_deze_run"] += 1

    # Verwerk niet-gematchte bestaande trends (aging)
    for i, trend in enumerate(bestaande_trends):
        if i in gematchte_indices:
            continue  # Al bijgewerkt

        # Alleen aging toepassen op trends die al bestonden (niet net nieuw toegevoegd)
        if trend.get("eerste_gezien") == nu_iso:
            continue  # Net toegevoegd in deze run

        maanden = _maanden_verschil(trend.get("laatst_bevestigd", ""), nu)

        if maanden > 6:
            trend["status"] = "verlopen"
            stats["verlopen_verwijderd"] += 1
        elif maanden > 3:
            trend["status"] = "verouderd"
            stats["verouderd"] += 1
        # < 3 maanden: behoud huidige status

    # Herbereken effectieve scores voor alle trends
    for trend in bestaande_trends:
        trend["effectieve_score"] = _bereken_effectieve_score(trend, nu)

    # Sorteer: actief eerst (op score), dan verouderd, dan verlopen
    status_order = {"actief": 0, "verouderd": 1, "verlopen": 2}
    bestaande_trends.sort(
        key=lambda t: (status_order.get(t.get("status", "actief"), 9), -t.get("effectieve_score", 0))
    )

    # Tel actieve trends
    stats["totaal_actief"] = sum(1 for t in bestaande_trends if t.get("status") == "actief")

    print(f"  Geheugen bijgewerkt: {stats['bevestigd_deze_run']} bevestigd, "
          f"{stats['nieuw_deze_run']} nieuw, {stats['verouderd']} verouderd, "
          f"{stats['verlopen_verwijderd']} verlopen")

    return {
        "trends": bestaande_trends,
        "statistieken": stats
    }


if __name__ == "__main__":
    import json

    # Test: eerste run
    print("=== Test: Eerste run ===")
    analyse_1 = {
        "trends": [
            {"naam": "Fermentatie", "beschrijving": "Gefermenteerde groenten.", "categorie": "voorgerechten",
             "relevantie_score": 8.0, "tags": ["fermentatie", "umami"]},
            {"naam": "Plant-based burgers", "beschrijving": "Vleesvervangers.", "categorie": "vegan_veg",
             "relevantie_score": 7.5, "tags": ["plantaardig"]},
        ]
    }
    geheugen_1 = combine_trends(analyse_1, None)
    print(json.dumps(geheugen_1, ensure_ascii=False, indent=2))

    # Test: tweede run met overlap
    print("\n=== Test: Tweede run ===")
    analyse_2 = {
        "trends": [
            {"naam": "Fermentatie en preservering", "beschrijving": "Kimchi, miso, zuurdesem.", "categorie": "voorgerechten",
             "relevantie_score": 8.5, "tags": ["fermentatie", "preservering"]},
            {"naam": "Seizoensgebonden desserts", "beschrijving": "Nagerechten van het seizoen.", "categorie": "nagerechten",
             "relevantie_score": 6.0, "tags": ["seizoen"]},
        ]
    }
    geheugen_2 = combine_trends(analyse_2, geheugen_1)
    print(json.dumps(geheugen_2, ensure_ascii=False, indent=2))
