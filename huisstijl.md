# Huisstijl Van der Valk — Design System

Gebruik dit bestand als referentie bij het genereren van HTML-pagina's voor dit project. Alle kleuren, typografie en componenten zijn afgeleid van de officiële huisstijl.

---

## CSS Variabelen

```css
:root {
  --gold:       #C9A84C;
  --gold-light: #E8C96A;
  --gold-dim:   rgba(201,168,76,.15);
  --dark:       #0F0F0F;   /* pagina-achtergrond */
  --dark-2:     #1A1A1A;   /* kaart-achtergrond */
  --dark-3:     #242424;   /* kaart-header / geneste elementen */
  --mid:        #3A3A3A;
  --text:       #E8E4DC;
  --text-dim:   #9A9590;
  --border:     rgba(201,168,76,.2);
  --ease:       cubic-bezier(.16,1,.32,1);
}
```

---

## Kleurpalet

| Rol | Kleur | Hex / Waarde |
|-----|-------|--------------|
| Primair accent | Goud | `#C9A84C` |
| Goud licht | Goud licht | `#E8C96A` |
| Goud transparant | Goud dim | `rgba(201,168,76,.15)` |
| Pagina-achtergrond | Donker | `#0F0F0F` |
| Kaart-achtergrond | Donker 2 | `#1A1A1A` |
| Kaart-header | Donker 3 | `#242424` |
| Subtiele achtergrond | Mid | `#3A3A3A` |
| Primaire tekst | Licht | `#E8E4DC` |
| Secundaire tekst | Gedimpt | `#9A9590` |
| Rand | Goud rand | `rgba(201,168,76,.2)` |

**Statuskleuren (voor badges/labels):**
| Status | Achtergrond | Rand | Tekstkleur |
|--------|-------------|------|------------|
| Positief / Houden | `rgba(76,175,80,.15)` | `rgba(76,175,80,.4)` | `#4CAF50` |
| Waarschuwing / Aanpassen | `rgba(255,152,0,.15)` | `rgba(255,152,0,.4)` | `#FF9800` |
| Negatief / Vervangen | `rgba(229,57,53,.15)` | `rgba(229,57,53,.4)` | `#ef5350` |
| Nieuw / Info | `rgba(100,149,237,.15)` | `rgba(100,149,237,.4)` | `#6495ED` |

---

## Typografie

**Fonts (Google Fonts CDN):**
```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
```

| Gebruik | Font | Gewicht | Notities |
|---------|------|---------|---------|
| Paginatitel (H1) | Playfair Display | 700 | `clamp(2rem, 4vw, 3.4rem)`, line-height 1.1 |
| Sectietitels (H2) | Playfair Display | 700 | `clamp(1.5rem, 2.5vw, 2rem)` |
| Kaart- en gerechtnamen (H3) | Playfair Display | 600 | `1rem–1.15rem` |
| Body tekst | Inter | 400 | `15px`, line-height 1.6 |
| Labels / badges | Inter | 600 | `0.68–0.78rem`, uppercase, letter-spacing `.07–.1em` |
| Secundaire tekst | Inter | 300 | Kleur: `var(--text-dim)` |

---

## Componenten

### Navigatie
```css
position: sticky; top: 0; z-index: 100;
height: 64px;
background: rgba(15,15,15,.92);
backdrop-filter: blur(16px);
border-bottom: 1px solid var(--border);
```

### Kaarten (cards)
```css
background: var(--dark-2);
border: 1px solid var(--border);
border-radius: 14–16px;
```
- **Kaart-header:** `background: var(--dark-3)`, `border-bottom: 1px solid var(--border)`, padding `1rem 1.5rem`
- **Kaart-body:** padding `1.5rem`

### Badges / Pills
```css
/* Goud badge */
background: var(--gold-dim);
border: 1px solid var(--border);
color: var(--gold);
font-size: .68–.78rem;
font-weight: 600;
letter-spacing: .07–.1em;
text-transform: uppercase;
padding: .25–.35rem .7–.9rem;
border-radius: 100px;
```

### Prijsbadge (gerechten)
```css
background: var(--gold-dim);
border: 1px solid var(--border);
color: var(--gold);
font-size: .8rem;
font-weight: 700;
padding: .25rem .7rem;
border-radius: 100px;
```

### Knoppen
```css
background: var(--dark-2);
color: var(--gold);
border: 1px solid var(--border);
border-radius: 8px;
padding: .5rem 1.1rem;
transition: background .15s var(--ease);
```
- Hover: `background: var(--dark-3)`
- Disabled: `opacity: .3`

### Tabellen
```css
/* Header */
background: var(--dark-3);
color: var(--text-dim);
font-size: .7rem; font-weight: 600;
letter-spacing: .08em; text-transform: uppercase;
padding: .75rem 1rem;
border-bottom: 1px solid var(--border);

/* Rijen */
border-bottom: 1px solid rgba(201,168,76,.08);
padding: .7rem 1rem;

/* Hover */
background: rgba(201,168,76,.04);
```

### Callout box
```css
background: var(--gold-dim);
border: 1px solid var(--border);
border-radius: 12px;
padding: 1rem 1.5rem;
font-size: .9rem;
```

### Placeholder box (gestippeld)
```css
border: 2px dashed var(--mid);
border-radius: 16px;
padding: 3rem 2rem;
text-align: center;
background: rgba(58,58,58,.15);
```

---

## Layout

- **Max-breedte content:** `1200px`, gecentreerd
- **Pagina-padding:** `0 2rem` (desktop), `0 1.25rem` (mobiel)
- **Sectie-padding:** `5rem 0`
- **Grid-gap kaarten:** `1rem–1.25rem`
- **Kaart-grid:** `repeat(auto-fill, minmax(320–340px, 1fr))`

### Responsive (mobiel ≤ 768px)
- Navigatielinks verbergen
- Alle grids: `grid-template-columns: 1fr`
- Sectie-padding verkleinen naar `3rem 0`

### Print-stijlen
```css
@media print {
  nav { position: static; }
  body { background: white; color: black; }
  .card, .dish-card, .trend-card {
    background: white; border-color: #ccc; box-shadow: none;
  }
}
```

---

## Animaties & Overgangen

- **Easing:** `cubic-bezier(.16,1,.32,1)` — zacht en premium
- **Snelle overgang:** `.15s` (knoppen, achtergronden)
- **Medium overgang:** `.2s–.25s` (modals, slides)
- **Hover-effect kaarten:** `transform: scale(1.02)` met `box-shadow`

---

## Algemene stijlprincipes

1. **Donker luxe-thema** — donkere achtergronden, goud als enige accentkleur
2. **Hoog contrast** — lichte tekst op donkere achtergrond, goud voor interactieve elementen
3. **Meerdere donkerlagen** — `--dark`, `--dark-2`, `--dark-3` creëren visuele diepte
4. **Serif voor prestige** — Playfair Display geeft de pagina een luxe-uitstraling
5. **Sans-serif voor leesbaarheid** — Inter voor alle bodytekst
6. **Subtiele goudrand** — `rgba(201,168,76,.2)` als randkleur op alle kaarten
7. **Geen afbeeldingen nodig** — het design werkt volledig met kleur, typografie en CSS-decoraties
