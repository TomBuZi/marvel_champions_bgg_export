# marvel_champions_bgg_export

Export Marvel Champions board game plays from BoardGameGeek (BGG) and create statistical visualizations.

## Overview

This project fetches Marvel Champions play data from the BGG XML API, parses structured information from play comments, and generates interactive Plotly visualizations. All four visualizations can be viewed together in a single tabbed HTML page.

---

## Setup

### Credentials

Copy `.env.example` to `.env` and fill in your BGG credentials:

```
BGG_SESSION_ID=...
BGG_USERNAME=...
BGG_PASSWORD=...
```

### Dependencies

```
pip install requests pandas plotly scipy python-dotenv
```

---

## Usage

**1. Fetch data and generate CSVs:**
```
python BGG_Export.py
```

**2a. Build all visualizations as a single tabbed page:**
```
python Visualize_all.py
```

**2b. Build individual visualizations:**
```
python Visualize.py        # Dashboard
python Visualize2.py       # Hero × Aspect matrix
python Visualize3.py       # Hero × Villain matrix / Sunburst
python Visualize4.py       # Scenario × Modulars Sunburst / matrix
```

---

## BGG_Export.py

Fetches all Marvel Champions plays for the configured BGG user via the BGG XML API and produces CSV statistics files.

### Comment format

Play comments are expected in the format:

```
<Hero(es)> vs <Scenario> [Difficulty] [Modular, Modular, ...] - <Result>
```

### Hero matching

- Longest-prefix-match against the `heroes.json` list
- Find-all-positions algorithm handles multiple heroes per play and substring overlaps (e.g. She-Hulk / Hulk)
- Alias mapping (`hero_aliases.json`) normalises bare names to canonical identities (e.g. `Spider-Man` → `Spider-Man * Peter Parker`)

### Modular matching

- Longest-prefix-match against `modulars.json`
- **Auto-modulars** (`scenario_modulars.json`): always added for certain scenarios regardless of comment
- **Default modulars** (`scenario_default_modulars.json`): added when only difficulty indicators (Standard / Expert) or nothing at all was noted
- `Standard` is always counted if no other difficulty marker was found
- Deduplication via a shared `matched_in_comments` set prevents double-counting

### Output files

| File | Description |
|---|---|
| `marvel_champions_plays.csv` | Full play history — id, date, hero, scenario, result, nowinstats, comments |
| `marvel_champions_scenario_stats.csv` | Play count per scenario |
| `marvel_champions_modular_stats.csv` | Play count per modular |
| `marvel_champions_scenario_modular_combos.csv` | Scenario × modular-combination groups with counts |
| `heroes_total.csv` | Play count + first-played date per hero |
| `heroes_aspects.csv` | Play count per hero × aspect combination |
| `heroes_scenarios.csv` | Play count per hero × scenario combination |
| `marvel_champions_aspect_stats.csv` | Overall play count per aspect |
| `unrecognized_report.csv` | Plays with unrecognised heroes, aspects, scenarios, or modulars (with date and full comment) |

### Config files (`config/`)

| File | Purpose |
|---|---|
| `heroes.json` | All hero names (including both bare and canonical dual-identity names) |
| `hero_aliases.json` | Maps bare names to canonical names (`Spider-Man` → `Spider-Man * Peter Parker`) |
| `aspects.json` | Recognised aspect names |
| `scenarios.json` | All scenario names in canonical display order |
| `modulars.json` | All modular encounter set names |
| `scenario_modulars.json` | Modulars that are always included automatically for specific scenarios |
| `scenario_default_modulars.json` | Modulars used when no explicit modular was noted for a scenario |

---

## Visualize.py — Dashboard

Six-chart Plotly dashboard in a 3×2 grid:

1. **Top 10 Most Played Heroes** — horizontal bar chart
2. **Aspect Distribution** — donut chart with aspect colours
3. **Top 10 Most Played Scenarios** — horizontal bar chart
4. **Win Rate** — three-way pie (Won / Lost / Ohne Ergebnis)
5. **Aspect Preference — Top 5 Heroes** — stacked bar chart
6. **Play Activity Over Time** — monthly line chart with Savitzky-Golay trend curve and 6-month linear forecast

Output: `dashboard.html`

---

## Visualize2.py — Hero × Aspect Matrix

Heatmap of heroes (rows) × aspects (columns) showing play counts.

- Each aspect column is coloured in its game colour (Aggression red, Justice gold, Leadership blue, Protection green, …)
- Band-normalisation technique: each column's values are normalised into its own colour band so all columns remain visually comparable
- **Total** column appended on the right
- Dropdown to sort rows by: Total, alphabetically, or by any individual aspect

Output: `hero_aspect_matrix.html`

---

## Visualize3.py — Hero × Villain Matrix / Sunburst

Toggle between two views via buttons:

**Kreuztabelle** — Heatmap of heroes (rows) × scenarios (columns). Scenarios appear in `scenarios.json` order; heroes alphabetically. Colour scale: YlOrRd.

**Sunburst** — Three-level radial chart:
- Ring 1: Heroes (sized by total plays)
- Ring 2: Scenarios played by that hero
- Ring 3 (click to reveal): All heroes who played the same scenario, sized by their play count for it

Output: `hero_villain_matrix.html`

---

## Visualize4.py — Scenario × Modulars

Toggle between two views via buttons:

**Sunburst** — Scenario → modular combination groups. Click a scenario to zoom in and see the distribution of all modular combinations used. Klick to zoom back out.

**Kreuztabelle** — Heatmap of scenarios (rows) × individual modulars (columns). Modular combinations are exploded into single entries and counts summed, so each cell shows how often a specific modular appeared in a specific scenario. Column order: Standard → Expert → remaining modulars alphabetically.

Output: `scenario_modular_sunburst.html`

---

## Visualize_all.py — Combined Page

Builds all four visualizations and assembles them into a single HTML file with a sticky tab bar. Plotly JS is loaded once from CDN.

Output: `marvel_champions_all.html`
