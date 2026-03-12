# Workflow: AI-Gedreven Menuvoorstel

## Doel
Produceer een professioneel, volledig onderbouwd menuvoorstel voor Van der Valk Hotel Ridderkerk als zelfstandige HTML-pagina, in het Nederlands, geschikt voor presentatie aan het managementteam.

## Wanneer uitvoeren
- Kwartaalupdate (elke 3 maanden)
- Bij beschikbaarheid van nieuwe kassaboekdata
- Na een seizoenswissel (april, september)
- Op verzoek van management

## Vereiste inputs
- [ ] `menu_vandervalk.md` — actueel menu in markdown-formaat
- [ ] Kassaboekdata (optioneel — placeholder wordt weergegeven als afwezig)
- [ ] Seizoen/jaar-context (voor zoekqueries)

## Gebruikte tools
- WebSearch (ingebouwd in Claude Code) — webresearch
- Claude redenering — analyse en HTML-generatie
- Geen Python-scripts vereist voor deze workflow

## Outputbestanden
- `menu_voorstel_vandervalk.html` — hoofdresultaat (client-facing)
- `workflows/menu_proposal.md` — dit bestand (na elke run bijwerken)

---

## Stap-voor-stap procedure

### Fase 0 — Voorbereiding (2 min)
1. Controleer of `menu_vandervalk.md` bestaat en actueel is
2. Noteer de datum (voor bronvermeldingen)
3. Controleer of kassaboekdata beschikbaar is

### Fase 1 — Menu-analyse zonder webresearch (10 min)
**Voer dit uit VOOR de webresearch om confirmatievooroordeel te vermijden.**

Vanuit `menu_vandervalk.md`:
1. Bouw een ingrediëntoverlap-matrix
2. Tag elk gerecht: HOUDEN / AANPASSEN / VERVANGEN
3. Stel categoriebalans vast (aantallen per categorie)
4. Analyseer prijsdistributie per categorie

**Beslissingscriteria per gerecht:**
- Trendaansluiting (hoog gewicht)
- Ingrediëntenoverlap met andere gerechten (hoog gewicht)
- Prijslogica binnen de categorie (gemiddeld gewicht)
- Onderscheidend vermogen voor Van der Valk (gemiddeld gewicht)
- Herkenbaarheid voor het brede publiek (gemiddeld gewicht)

### Fase 2 — Restaurantprofiel EERST (10 min)
**De trendanalyse mag pas beginnen nadat het profiel volledig is.**

Voer de volgende WebSearch-queries uit:
1. `Van der Valk Hotel Ridderkerk type hotel ligging doelgroep faciliteiten`
2. `Ridderkerk Rotterdam regio zakelijk toerisme bedrijven industrie logistiek demografie`
3. `Van der Valk keten restaurant positionering doelgroep prijssegment merkidentiteit Nederland`

Stel vast:
- Restauranttype (hotel restaurant, captive audience)
- Gast-mix (zakelijk / familie / conferentie)
- Inkomenssegment (middel-hoog)
- Culinaire verwachting
- Prijspositionering

**Beslismoment:** Op basis van het profiel worden de queries voor Fase 3 bepaald. Als Van der Valk morgen een fine dining-tent zou worden, zouden de queries volledig anders zijn.

### Fase 3 — Gerichte trendanalyse (15 min)
**Alleen uitvoeren na Fase 2. Queries zijn afgeleid van het profiel.**

Standaard queries voor Van der Valk Ridderkerk (mid-upscale hotel restaurant):
4. `mid-upscale hotel restaurant menu trends Nederland 2025 casual fine dining comfort food elevated`
5. `horeca trends 2025 2026 Nederland restaurantmenu vernieuwing populaire gerechten consumentengedrag`
6. `vegan vegetarisch groei restaurant Nederland 2025 statistieken omzet plantaardig`
7. `seizoensgebonden lokaal inkopen restaurant trend Nederland 2025 duurzaamheid ingredienten`
8. `dessert trends restaurant Nederland 2025 pistachio minder suiker fruit seizoen`
9. `foodtrends 2025 2026 Nederland nostalgie comfort food elevated umami fermentatie zakelijk publiek`

Per resultaat noteren:
- Trendnaam
- Bron-URL
- Welke menucategorie het raakt
- Past dit bij het Van der Valk-profiel? (ja / nee + reden)

### Fase 4 — Menuvoorstel samenstellen (15 min)
Per categorie minimaal:
- **Voorgerechten**: 1–2 nieuw, 1–2 aanpassingen
- **Vis**: 1 nieuw, 1 aanpassing
- **Vegan/Veg**: 1–2 nieuw
- **Vlees**: 1 nieuw, 1–2 vervangen
- **Nagerechten**: 1–2 nieuw of aanpassen

Elk gerecht krijgt:
- Naam | Ingrediënten | Prijs
- Gedeelde basisingrediënten
- Onderbouwing (2–3 zinnen: trend + doelgroepfit)
- Trendtags
- Status (NIEUW / AANPASSING VAN / VERVANGER VAN)

**Prijsregel:** Nieuwe gerechten vallen binnen de bestaande prijsband van hun categorie, tenzij er een expliciete upgrade-reden is.

### Fase 5 — HTML genereren (20 min)
Bestandsnaam: `menu_voorstel_vandervalk.html` in de projectroot.

**Secties (in volgorde):**
0. Cover header (naam, datum, subtitle)
1. Restaurantprofiel (locatie, doelgroep, prijs-tabel)
2. Trendanalyse (trend-kaarten in grid, bronnen)
3. Analyse huidig menu (stats, beoordeling per gerecht)
4. Nieuw menuvoorstel (per categorie)
5. Ingrediëntenoverlapstrategie (matrix)
6. Kassaboek placeholder (of live data)
7. Bronvermelding (genummerd, URL + datum)
8. Footer

**Design-systeem (Van der Valk huisstijl):**
- Donker thema: `#0F0F0F` achtergrond
- Goud: `#C9A84C` als accent
- Tekst: `#E8E4DC`
- Kaarten: `#1A1A1A` + goudrand
- Fonts: Playfair Display (headings) + Inter (body)
- Max-breedte: 1200px, responsive

Zie `index.html` in de projectroot voor de volledige CSS-variabelenlijst en componentstijlen.

### Fase 6 — Workflow bijwerken (3 min)
Update dit bestand met:
- Nieuwe queries die betere resultaten gaven
- Gevonden beperkingen of taal-issues (Engels vs. Nederlands)
- Lessen voor de volgende run

---

## Edge cases en aantekeningen

**Als WebSearch voornamelijk Engelstalige resultaten geeft:** Engelstalige bronnen accepteren, inzichten vertalen, transparant vermelden in de HTML ("gebaseerd op internationale bronnen, vertaald naar Nederlandse context").

**Als trenddata ouder is dan 2 jaar:** In de HTML markeren als "gebaseerd op data uit [jaar] — aanbevolen wordt dit bij te werken."

**Als het menubestand een andere structuur heeft:** De ingredient-overlap-matrix handmatig opbouwen uit de tekst voor je verdergaat naar de webresearch.

**Kassaboek-integratie (toekomst):**
Wanneer kassaboekdata beschikbaar is, voeg Fase 3b toe:
1. Koppel elk gerecht aan omzet, marge en bestelfrequentie
2. Pas ABC-classificatie toe:
   - A = top 20% omzet → altijd houden
   - B = middelste 30% → beoordelen op trend-fit
   - C = onderste 50% + lage trend-fit = VERVANGEN

---

## Kwaliteitschecklist (voor oplevering HTML)
- [ ] Elk nieuw/aangepast gerecht heeft: naam, ingrediënten, prijs, onderbouwing, trendtags
- [ ] Alle bronnen staan in sectie 7 met URL
- [ ] Ingrediëntoverlap-tabel dekt alle nieuwe + handhaafde gerechten
- [ ] Kassaboek-sectie aanwezig (ook als placeholder)
- [ ] HTML opent correct in browser zonder externe fouten
- [ ] Alle tekst is in het Nederlands
- [ ] Prijsformattering consistent: €XX,XX

---

## Verbeterlog

| Datum | Wijziging | Reden |
|-------|-----------|-------|
| 2026-02-27 | Initiële versie | Eerste run; volledige flow doorlopen |
| 2026-02-27 | Profiel-eerst structuur | Gebruikersinstructie: trendanalyse moet altijd worden afgestemd op het profiel, niet andersom |
| 2026-03-02 | Parallelle webresearch | Profiel- en trendresearch parallel uitgevoerd via agents — halveert de doorlooptijd zonder kwaliteitsverlies (profiel was al bekend) |
| 2026-03-02 | Nederlandstalige bronnen excellent | Alle 6 trendqueries leverden rijke NL-bronnen (DeRestaurantKrant, Vinissima, ChefsCulinar, HorecaMagazine). Engelstalige fallback was niet nodig |
| 2026-03-02 | "Speciaal"-patroon als kritieke bevinding | Drie identieke bijgerechten (ui/spek/champignon) + vijf generieke "groenten/aardappelgarnituur" zijn de grootste differentiatie-zwakte — altijd checken bij volgende run |
| 2026-03-02 | Seizoensgebonden starters | Seizoenssalade moet per run worden bijgewerkt (pompoen=herfst, asperge=lente) — opnemen als standaard check in Fase 1 |
| 2026-03-02 | Vegan/veg sectie-balans | 5 items bij 11 vlees was scheef (ratio 1:2.2). Uitgebreid naar 7:11 (1:1.6). Marktgroei (13% vegetariër, 8% vegan) rechtvaardigt verdere uitbreiding in toekomstige runs |
