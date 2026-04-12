# marvel_champions_bgg_export

Export Marvel Champions board game plays from BoardGameGeek (BGG) and create statistical visualizations.

## Overview

This project fetches Marvel Champions play data from the BGG XML API, parses structured information from play comments, and generates interactive Plotly visualizations. All four visualizations can be viewed together in a single tabbed HTML page.

---

## Setup

### Local

Install dependencies:

```
pip install requests pandas plotly scipy python-dotenv
```

Copy `.env.example` to `.env` and fill in your BGG credentials (the BGG API requires authentication even for public profiles):

```
BGG_USERNAME=...
BGG_SESSION_ID=...
BGG_PASSWORD=...
```

Both `BGG_SESSION_ID` and `BGG_PASSWORD` (the encrypted value) can be found in your browser cookies after logging in to boardgamegeek.com. `python-dotenv` is optional — if not installed, set the three variables as regular environment variables instead.

### GitHub Actions + GitHub Pages

The workflow in `.github/workflows/update.yml` runs every 15 minutes. It first performs a lightweight BGG check (`check_bgg_changes.py`) that fetches only page 1 of the API to compare total play count and the most recent play ID against the stored state in `bgg_state.json`. The full data fetch and page rebuild only runs when a change is detected (or on manual/push triggers). GitHub Pages then serves the rebuilt `docs/index.html` automatically.

**One-time setup:**

1. Add three repository secrets (Settings → Secrets and variables → Actions):
   - `BGG_USERNAME`, `BGG_SESSION_ID`, `BGG_PASSWORD`
2. Enable GitHub Pages (Settings → Pages → Source: main branch, `/docs` folder).
3. Trigger the workflow once manually (Actions tab → Run workflow) to generate the initial page.

The live page will be at `https://<your-username>.github.io/<repo-name>/`.

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
python Visualize5.py       # Campaign timeline
python Visualize6.py       # Sortable plays table (all individual plays)
```

**3. Check for BGG changes without a full data fetch (used by the GitHub Actions workflow):**
```
python check_bgg_changes.py
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
| `marvel_champions_campaigns.csv` | Campaign attempts — campaign, heroes, date range, status, scenarios played |
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
| `campaigns.json` | Campaign definitions — maps each campaign name to its ordered list of scenarios |

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

## Visualize5.py — Campaign Timeline

Gantt-style timeline of all detected campaign attempts.

**Detection logic** (in `BGG_Export.py`):
- Campaigns are defined in `config/campaigns.json` as ordered scenario lists
- Plays matching campaign scenarios are grouped by hero combination and campaign
- A new attempt starts whenever the first scenario of a campaign is played; mid-campaign plays without a preceding first-scenario play are ignored (noise filter)
- Attempts are split if consecutive plays are more than 180 days apart, or if scenario 0 is replayed after progress was made
- **Status** is assigned as:
  - `completed` — all scenarios won in order
  - `in_progress` — last play within 90 days of the most recent play in the dataset
  - `abandoned` — otherwise

**Timeline view** — horizontal bars (one per attempt), coloured by status. Scatter markers show individual scenario plays: ✓ win, ✗ loss, ○ incomplete.

**Zusammenfassung (summary) view** — mobile-friendly HTML table grouped by campaign, with per-attempt rows showing heroes, date range, play count, inline scenario icons, and status.

Output: `campaigns_timeline.html`

---

## Visualize6.py — Sortable Plays Table

Full chronological list of all individual plays. Columns: Datum, Held(en), Szenario, Ergebnis. Click any column header to sort ascending/descending. Plays marked as "not in stats" (`nowinstats=1`) are visually dimmed. The result column is colour-coded: green for wins, red for losses.

Output: `plays_table.html`

---

## check_bgg_changes.py — Lightweight BGG Change-Check

Fetches only page 1 of the BGG API (~1 second) to read the total play count and the ID of the most recent play. Compares them with the saved state in `bgg_state.json`. Used by the GitHub Actions workflow to skip the full data fetch when nothing changed.

`bgg_state.json` is updated by `BGG_Export.py` after a successful full fetch.

---

## Visualize_all.py — Combined Page

Builds all six visualizations and assembles them into a single HTML file with a sticky tab bar. Plotly JS is loaded once from CDN. Tabs: Dashboard, Helden × Aspekte, Helden × Schurken, Szenarien × Modulars, Kampagnen, Alle Partien.

The header shows the build timestamp ("Stand: DD.MM.YYYY HH:MM").

Output: `docs/index.html`
