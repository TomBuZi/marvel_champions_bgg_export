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
python Visualize3.py       # Hero × Scenario matrix / Sunburst
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
- Leading separators and punctuation (`+ , ! ? . : ;`) are skipped between modulars, so a scenario noted with punctuation in the comment (`Stop the Presses!` for the scenario `Stop the Presses`) does not leave a bogus token
- Keywords in `MODULAR_NOISE_WORDS` (`Campaign`, `Kampagne`) are skipped silently instead of being reported as unrecognised modulars — they may appear before the `-` separator (`... The Owl Campaign - lost`)

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
| `non_modulars.json` | Card sets counted per scenario that are **not** modulars — excluded from the Szenarien × Modulars cross-table |
| `scenario_modulars.json` | Modulars that are always included automatically for specific scenarios |
| `scenario_default_modulars.json` | Modulars used when no explicit modular was noted for a scenario |
| `campaigns.json` | Campaign definitions — a list of scenarios for a sequential campaign, or a `{ "pool": [...], "finale": ... }` object for a pool campaign (random order, variable length). The object form also accepts `"require_tag": true`, which makes the `Campaign` / `Kampagne` comment keyword mandatory for that campaign |

---

## Visualize.py — Dashboard

Six-chart Plotly dashboard in a 3×2 grid:

1. **Top 10 Most Played Heroes** — horizontal bar chart
2. **Aspect Distribution** — donut chart with aspect colours
3. **Top 10 Most Played Scenarios** — horizontal bar chart
4. **Win Rate** — three-way pie (Won / Lost / Ohne Ergebnis)
5. **Aspect Preference — Top 5 Heroes** — stacked bar chart
6. **Play Activity Over Time** — switchable time granularity (Monthly / Yearly / Weekly) via buttons; each view includes a Savitzky-Golay trend curve

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

## Visualize3.py — Hero × Scenario Matrix / Sunburst

Toggle between two views via buttons:

**Kreuztabelle** — Heatmap of heroes (rows) × scenarios (columns). Scenarios appear in `scenarios.json` order; heroes alphabetically. Colour scale: YlOrRd.

The matrix is **complete**: every hero from `heroes.json` (dual identities folded via `hero_aliases.json`) and every scenario from `scenarios.json` is shown, including those with no plays at all — an empty row or column makes visible what is still unplayed. Both axes are the union of config and data, so a name that appears only in the CSVs is never dropped. Cells with 0 stay blank.

**Sunburst** — Three-level radial chart:
- Ring 1: Heroes (sized by total plays)
- Ring 2: Scenarios played by that hero
- Ring 3 (click to reveal): All heroes who played the same scenario, sized by their play count for it

Output: `hero_scenario_matrix.html`

---

## Visualize4.py — Scenario × Modulars

Toggle between two views via buttons:

**Sunburst** — Scenario → modular combination groups. Click a scenario to zoom in and see the distribution of all modular combinations used. Klick to zoom back out.

**Kreuztabelle** — Heatmap of scenarios (rows) × individual modulars (columns). Modular combinations are exploded into single entries and counts summed, so each cell shows how often a specific modular appeared in a specific scenario. Column order: Standard → Expert → remaining modulars alphabetically.

The matrix is **complete**: every scenario from `scenarios.json` and every modular from `modulars.json` is shown, including those with no plays at all. Cells with 0 stay blank.

Columns are `modulars.json` ∪ (names found in the data) − `non_modulars.json`:
- The **union** guards against silently dropping a name that the scenario configs count but `modulars.json` does not list.
- **`non_modulars.json`** removes card sets that are tracked per scenario but are not modular encounter sets (e.g. `Prelates`, `S.H.I.E.L.D. Executive Board`). They are still counted in `marvel_champions_modular_stats.csv` and appear in the combination strings — only this cross-table hides them.

Output: `scenario_modular_sunburst.html`

---

## Visualize5.py — Campaign Timeline

Gantt-style timeline of all detected campaign attempts.

**Detection logic** (in `BGG_Export.py`):
- Campaigns are defined in `config/campaigns.json`. Three shapes are supported, normalised at load time by `_normalize_campaign` into a spec dict (`CAMPAIGN_SPECS`):
  - **List** → *sequential* campaign (the default): the scenarios must be won one after another in exactly that order.
  - **Object** with `scenarios` → also sequential, written as an object so that flags can be added.
  - **Object** with `pool` + `finale` → *pool* campaign (see below).
- `"require_tag": true` (object form only) makes the campaign **opt-in per play**: only plays whose comment contains `campaign` / `kampagne` (`has_campaign_tag`) are considered for it at all. The filter runs *before* the attempts are built, so an untagged play cannot shift attempt boundaries (`GAP_DAYS`, `won_pool`, `finale_played`) or inflate `play_count`. `BGG_Export.py` prints one line per campaign counting the plays it skipped this way, so a forgotten keyword does not vanish silently.
- Plays matching campaign scenarios are grouped by hero combination and campaign
- Attempts are split if consecutive plays are more than `GAP_DAYS` (60) days apart
- An attempt is only exported if at least half of the campaign's scenarios were played **or** a play comment contains `campaign` / `kampagne` (`_qualifies`) — otherwise it counts as an unrelated single scenario. For a `require_tag` campaign the second condition always holds, so a single tagged evening already shows up as a (running) attempt
- **Status** is assigned as:
  - `completed` — campaign finished (sequential: all scenarios won in order; pool: finale won)
  - `lost` — the last scenario was lost at Expert / Expert II difficulty
  - `in_progress` — last play within 90 days of the most recent play in the dataset
  - `abandoned` — otherwise

**Sequential campaigns** additionally require: a new attempt starts only when the *first* scenario is played (mid-campaign plays without a preceding first-scenario play are ignored as noise), a replay of scenario 0 after progress starts a new attempt, and a forward skip ends the attempt.

**Pool campaigns** (`_segment_pool_campaign`) model a campaign whose scenarios are drawn in random order — currently *Fear no Evil*:

```json
"Fear no Evil": {
    "pool":        ["The Getaway", "Protection Racket", "Art Museum Heist",
                    "The Raft Breakout", "Stop the Presses"],
    "finale":      "Kingpin",
    "require_tag": true
}
```

- `require_tag` is practically **mandatory** here. A sequential campaign recognises itself by its fixed scenario order; a pool campaign has no such structure, so without the keyword *every* play of a pool scenario with the same hero combination would be pulled into the running attempt — including plays that had nothing to do with the campaign. Note that the **finale** needs the keyword too, otherwise the attempt never reaches `completed`
- Scenarios are played in **random order** and the number of plays per attempt is **variable** — nothing is counted, and there is no maximum
- A **won** pool scenario is used up and cannot be played again in the same attempt; a **lost** one may be repeated. Its reappearance is therefore what marks the boundary between two attempts
- Any pool scenario starts an attempt; a `finale` play without a preceding pool play does not
- The `finale` scenario ends the attempt when won. A lost finale keeps the attempt open so it can be retried; the next pool play then starts a new attempt
- Plays are ordered by date, then BGG play id. The scenario's position in the config must not be used as a same-day tiebreaker here, since the order is random

**Display order of `scenarios_played`** — `sort_plays_for_output()` (module level, so it is unit-testable without a BGG fetch) sorts each attempt's plays for the CSV field: date → position of the scenario within the day → play id, and within the **same (day, scenario)** group the **won** play comes last (you lose, retry, win, move on). The win rank sits deliberately *after* the scenario position, which makes `(date, scenario_position)` a prefix of the key so the rank only ever compares plays of the same scenario — in front of it, it would sort losses of *other* scenarios ahead of their wins. Scenario position is the config index for sequential campaigns and, for pool campaigns, the smallest play id of that scenario on that day (the config order carries no meaning there; the anchor also groups repeats so "win last" has a group to refer to).

Two things this must not be confused with:

- It is a pure **output** sort. The two `plays_list.sort()` calls that feed the segmentation state machine must keep their current keys. The sequential one is stable, so within a `(date, scenario_index)` group BGG's descending-id order survives — which makes a won scenario come *first*, advance `current_idx` and let the repeats fall into `if scen_idx < current_idx: continue`. Sorting ascending there would append those repeats instead and inflate `play_count`.
- The resulting **order in the CSV field is meaningful**: `Visualize5._spread_same_day()` fans same-day plays out in exactly that order, so `_parse_played()` must not re-sort. That is also why the field stays three-part — a fourth field (the play id) would be pulled silently into `result` by its `split("::", 2)`.

**Timeline view** — horizontal bars (one per attempt), coloured by status. Scatter markers show individual scenario plays: ✓ win, ✗ loss, ○ incomplete.

*Same-day plays* — BGG records no time of day, so several plays of one attempt on one date would land on the exact same pixel. That is the normal case, not an edge case: **40 of 79** (attempt, day) pairs hold more than one play, **31 of 40 rows** are affected, and the maximum is **5 plays in one day** (a whole campaign in an evening). `_spread_same_day()` therefore puts the i-th of k plays of a day at `day + i/k`:

- the first play stays exactly on its date, which is where the bar's left edge sits (`base=start`)
- the last one sits at `(k-1)/k`, so at least `1/k` day of air remains before the next day's first marker — the markers stay evenly dense *across* the day boundary and never slide onto the following day
- marker size drops from `MARKER_SIZE` (9) to `MARKER_SIZE_DENSE` (7) from `DENSE_DAY_PLAYS` (4) plays a day on, so even the densest days fan out. Plotly takes `marker.size` as a per-point array, so this needs no extra traces.

The offset lives in **data coordinates** and is therefore only visible when zoomed in — at 1660 px window width and 30-day zoom (43.5 px/day) two plays are 21.8 px apart and five are 8.7 px apart, while at the 12-month default view (3.6 px/day) they collapse again. That is deliberate: a pixel-constant offset would have to be recomputed on every relayout, and spreading any wider than one day would misplace plays onto neighbouring dates. This is also why `MIN_ZOOM_DAYS` matters twice over — zooming deeper than day ticks would make this pure display offset look like a real time of day.

The bar runs to `end_date + 1 day` so it covers the **whole** last day; otherwise that day's spread markers stick out to the right of it. That also replaces the old `if end == start` minimum-width special case. The bar's `customdata` keeps the **real** start/end dates — it drives the click-zoom and the label-click (`rowSpans()` in `zoom_js`).

*Geometry* — the canvas is **as wide as the window**. `fitWidth()` sets `layout.width` to the container's `clientWidth` on first reveal and on every window resize (floor: `MIN_CANVAS_W` = 900 px, below which `#viz5-scroll` scrolls again); `DEFAULT_CANVAS_W` is only the pre-measurement fallback and the width of the standalone file. That keeps the hero column permanently visible and removes the horizontal scrollbar — with a canvas wider than the window, scrolling drags the row labels out of view too, since they are part of the same SVG. The height is derived exactly from the row count: `MARGIN_TOP + MARGIN_BOTTOM + ROW_PITCH * n` (22 px per attempt → 990 px for 40 attempts).

The axis **bounds** run from the first campaign to **the day the page was built**, with `X_PAD_DAYS` (30) of air at each end so the first and last entry do not sit flush against the border. It never reaches further into the future than that buffer. `xaxis.minallowed` / `xaxis.maxallowed` pin those bounds for *every* interaction, so neither the modebar's zoom-out nor dragging can pull the axis into empty future years. If the CSV ever contains a date beyond today, `build()` prints a warning and extends the axis instead of silently cutting the data off.

Both axes get an **explicit `range`** instead of `autorange`. This is not cosmetic: `go.Scatter` reports its extremes as `padded`, which makes Plotly reserve **5 % of the axis length at *both* ends**. On the y axis that produced ~85 px of dead space above the first and below the last row (the zebra bands stop at `±0.5`, so the strip was visibly white); on the x axis it wasted ~3.5 months per side. `yaxis.range=[n-0.5, -0.5]` is descending, which replaces `autorange="reversed"` — the two must not be combined, `autorange` would win.

The **initial** range is the last `INITIAL_MONTHS` (12) months, not the whole history. At full range there is by definition nothing to pan — dragging would look broken. Double click shows everything.

*Interaction* — `yaxis.fixedrange=True` confines every gesture to the time axis, and since the canvas equals the window there is a single zoom axis: the date range.

| Gesture | Effect |
|---|---|
| **Strg/Shift + mouse wheel** | stretch/compress the time axis; the instant under the cursor keeps its pixel position |
| plain mouse wheel | scrolls the page (deliberately *not* captured) |
| drag | pan the time axis horizontally |
| click on the label column | jump to that attempt, **keeping** the current zoom level |
| click on a bar or a scenario marker | zoom in on that attempt |
| double click | show the whole history |

`moveByPixels()` still scrolls `#viz5-scroll` first and only passes the unused remainder on to the date range, and `scrollInto()` centres a clicked attempt in the window. Both are no-ops while the canvas fits the window; they only matter below `MIN_CANVAS_W`. Keep them: with a canvas wider than the window, moving *only* the range is silently dead whenever the range is already full.

**Panning is implemented here, not by Plotly** (`dragmode=False`). Plotly's own pan clamps the two axis ends *independently* against `minallowed`/`maxallowed`: at a boundary one end stops while the other keeps moving, so the drag silently **zooms** (measured: 2213 → 1953 days in a single drag). Since the default view shows the full range, *every* drag hits a boundary immediately — only a window strictly inside the bounds pans cleanly, which is why the bug survives a careless test. `setRange()` clamps span-preserving instead, so a drag stops at the border without changing the zoom.

The pan handlers listen to **pointer events on `window` in the capture phase**, which matters twice over. Capture-on-window runs before anything Plotly attaches to its drag surfaces, so `stopPropagation()` cannot disable it. And pointer events are the primary input: per the Pointer Events spec, a `preventDefault()` on `pointerdown` suppresses the *derived* mouse events, so handlers bound to `mousedown`/`mousemove` can silently never fire even though the drag is happening. For the same reason `onDown()` must **not** call `preventDefault()` itself — that killed Plotly's own click detection and with it the bar-click zoom. Text selection during a drag is suppressed with `user-select: none` instead.

Two consequences of `dragmode=False`:
- Plotly no longer suppresses the click that ends a drag, so a pan would additionally fire `plotly_click` and zoom to whatever bar it ended on. A shared `dragged` flag (set once the pointer moves > 4 px) gates *every* click handler.
- The DOM `dblclick` never reaches the graph div — Plotly swallows it — but `plotly_doubleclick` still fires, even with `config.doubleClick = False`. The reset lives in that handler. Note that two `Plotly.relayout` calls issued back to back race and the second one is lost, so anything that must change together has to go into one call.

The corner and edge draggers (`.nwdrag`, `.swdrag`, `.ewdrag`, …) are additionally switched off with `pointer-events: none`: with a fixed y axis they are all **one-sided x-zoom handles** sitting directly on the plot border — `.nwdrag` is a 20 × 20 px square right where the label column meets the plot area.

`modeBarButtonsToRemove` drops every axis button (`zoom2d`, `pan2d`, `zoomIn2d`, `zoomOut2d`, `autoScale2d`). They would bypass both the span-preserving clamp and `MIN_ZOOM_DAYS`, e.g. zooming below a single day.

`MIN_ZOOM_DAYS = 30` is not an arbitrary limit: Plotly aims for ~100 px per tick, so a full-width plot (~1300–3000 px) wants 13–30 ticks, and any span below ~30 days makes it fall back to **sub-day ticks**. BGG plays carry no time of day, so hour labels would be invented precision.

`FULL` (the outer bound used by every clamp) is derived **once** from `xaxis.minallowed` / `maxallowed`, not lazily from the current range. Deriving it lazily lets a pan or a modebar zoom that happens *before* the first scripted interaction freeze that momentary window in as "full", after which the clamps trap the view inside it.

The label-column click is suppressed when the mouse moved more than 4 px between `mousedown` and `click`, so a pan that happens to end over the labels does not also trigger a jump.


The label column is clickable because the bars are frequently only 1–2 px wide. The row is derived from the mouse position via `yaxis.p2d()`, *not* from the label text — identical labels occur several times (three attempts read "The Rise of Red Skull — Spider-Woman (Standard)"). The `[start, end]` spans are read back out of the bar traces' `customdata`, so there is no second copy of the data to keep in sync.

The wheel/click handlers live in `zoom_js()` (module-level `_ZOOM_JS`), so `Visualize_all.py` and the standalone HTML share one implementation. Notes for maintainers:
- `config.scrollZoom` stays **off** — Plotly's own scroll zoom cannot require a modifier key. `dragmode=False` does *not* disable it (Plotly gates scroll zoom only on `scrollZoom` + per-axis `fixedrange`), which is why the wheel used to zoom the whole picture.
- `config.doubleClick` must never be `"reset+autosize"` and `autoScale2d` must stay out of the modebar: both re-enable `autorange` and bring the 5 % padding back.
- The wheel listener is registered with `{passive: false}` so `preventDefault()` can suppress the browser's own Ctrl+wheel zoom (and Shift+wheel horizontal scrolling). Shift+wheel reports its delta in `deltaX` in some browsers, hence `e.deltaY || e.deltaX`.
- `zoomAnchored()` clamps the *span* first and only then derives the left edge from `anchor - frac * span`. Re-centering the clamped span on its midpoint (the earlier version) throws the cursor anchor away as soon as any clamp kicks in. `zoomToSpan()` is the centred variant used for the click-to-zoom.
- Bars **and** markers carry `customdata=[start, end]`. The markers sit on top of the bars and win the click, so the handler must not test for `type === 'bar'`.
- `fmt()` formats **local** time components; `toISOString()` would shift the range by the UTC offset on every zoom step.
- Title and legend are anchored **left** (`x=0`), which also survives the narrow-window case where the canvas is wider than the viewport. The legend carries no `legendgroup`, otherwise Plotly lays the groups out as vertical columns (~95 px tall) that collide with the title.

*Optional gap compression* — `GAP_COMPRESS_DAYS` (default `0` = off). When set to e.g. `60`, `_gap_rangebreaks()` removes play-free stretches from the axis via `xaxis.rangebreaks`, which shrinks the axis from ~2150 to ~790 days and roughly triples the pixels per day. The gaps are computed from the **merged union** of all attempt intervals, so no bar and no marker can fall into a removed window. Trade-off: axis distances are no longer proportional to real time and the year ticks become unevenly spaced.

**Zusammenfassung (summary) view** — mobile-friendly HTML table grouped by campaign, with per-attempt rows showing heroes, date range, play count, inline scenario icons, and status. This is the **default** view of the Kampagnen tab; the timeline is opt-in via the switch.

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

Builds all six visualizations and assembles them into a single HTML file with a sticky tab bar. Plotly JS is loaded once from CDN. Tabs: Dashboard, Helden × Aspekte, Helden × Szenarien, Szenarien × Modulars, Kampagnen, Alle Partien.

Only the Dashboard and Kampagnen tabs embed Plotly figures (`build()`); the cross-table tabs use the sortable HTML tables (`build_table_html()`). The `build()` heatmaps in `Visualize2/3/4.py` are therefore only rendered when those scripts are run standalone.

The header shows the build timestamp ("Stand: DD.MM.YYYY HH:MM").

**Kampagnen tab specifics** — the timeline is rendered with a fixed `div_id` (`Visualize5.PLOT_DIV_ID` = `viz5-chart`) and its own config (`Visualize5.TIMELINE_CONFIG`) instead of the page-wide `PLOTLY_CONFIG`. The markup is `#viz5-plotly` → `.viz-hint` (interaction hint, stays put) + `#viz5-scroll` (carries `overflow-x: auto`, which only engages below `MIN_CANVAS_W`). `viz5Reveal()` calls `window.viz5Fit()` (exported by `zoom_js`) so the canvas gets the container width — at `newPlot` time the div sits in a `display:none` container and measures 0. `Visualize5.zoom_js()` is injected into the page's script block through the `{viz5_zoom_js}` placeholder — deliberately **before** the hash navigation, so the handlers do not depend on `showTab`/`mobileSwitchView` completing without error.

`showTab()` and `mobileSwitchView()` skip the timeline when they call `Plotly.Plots.resize()` and call `viz5Reveal()` instead. Reason: `Plots.resize` is a no-op while `layout.width` **and** `layout.height` are both set, but it **deletes both** as soon as only one of them is set, switching the figure to `autosize` against a container that has no defined height. `viz5Reveal()` calls `Plotly.redraw()` once on first reveal (note: `Plotly.Plots.redraw` does not exist — the public API is `Plotly.redraw`), which repairs the text metrics that were measured as 0 while the div was still `display:none`, and which keeps width/height. The Dashboard figures set only `height`, so they keep using `Plots.resize` and stay responsive.

Output: `docs/index.html`
