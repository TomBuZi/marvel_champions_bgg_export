# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Guidlines
- Always update the Readme.md when changing the solution

## Commands

```bash
# Fetch BGG data and regenerate all CSVs
python BGG_Export.py

# Build all four visualizations into one tabbed HTML page
python Visualize_all.py

# Build individual visualizations (each opens in browser)
python Visualize.py        # Dashboard
python Visualize2.py       # Hero × Aspect heatmap
python Visualize3.py       # Hero × Scenario heatmap + Sunburst toggle
python Visualize4.py       # Scenario × Modulars Sunburst + heatmap toggle
```

No test suite or linter is configured.

## Architecture

### Data pipeline

`BGG_Export.py` is the sole data-generation script. It fetches the BGG XML API (paginated), parses play comments in the format `<Hero(es)> vs <Scenario> [Difficulty] [Modular, ...] - <Result>`, and writes 9 CSV files. All static lists live in `config/*.json` and are loaded at module level.

**Key parsing algorithms:**
- `find_all_hero_positions` + `remove_covered_matches` — finds every hero name in the comment text, then removes matches fully covered by a longer match (solves She-Hulk/Hulk and Spider-Man/Miles Morales overlaps)
- `find_longest_prefix_match` — greedy prefix scan used for both scenario and modular detection; the remaining text after each match is passed to the next iteration
- `count_modular` — unified helper that deduplicates via a shared `matched_in_comments` set; called for explicit, default, and auto-modulars in sequence
- `sort_modular_combo` — sort key used when building the combo tuple: difficulty indicators first (Standard → Expert), then alphabetically

**Modular resolution order for each play:**
1. Explicit modulars parsed from the comment
2. Default modulars (`scenario_default_modulars.json`) — only if `matched_in_comments` is a subset of `DIFFICULTY_MODULARS`
3. Auto-modulars (`scenario_modulars.json`) — always appended if not already counted
4. `Standard` fallback — added if no difficulty marker was found at all

### Visualization layer

Each `Visualize*.py` exposes a `build()` function returning a `go.Figure`. The `if __name__ == '__main__':` block calls `build()`, writes a standalone HTML file, and opens it in the browser.

`Visualize_all.py` imports all four modules, calls `build()` on each, renders them as HTML fragments (`fig.to_html(full_html=False)`), and assembles a single tabbed HTML page. Plotly JS is loaded once via CDN on the first tab; subsequent tabs use `include_plotlyjs=False`. Tab switching calls `Plotly.Plots.resize()` on all `.plotly-graph-div` elements in the newly visible panel to fix the hidden-div rendering issue — except the campaign timeline, which is fixed-size (see below).

**Three Plotly.js traps this page has already hit:**
- `Plotly.Plots.resize()` is a **no-op** while `layout.width` *and* `layout.height` are both set, and **deletes both** as soon as only one is set, switching the figure to `autosize` against the container box. For fixed-size figures use `Plotly.relayout(div, {width: <px>})` and/or `Plotly.redraw(div)` — note that `Plotly.Plots.redraw` does **not** exist, the public method is `Plotly.redraw`.
- `go.Scatter` reports its extremes as `padded`, so an **autoranged** axis reserves 5 % of its pixel length at *both* ends. On a Gantt-style chart that shows up as a wide empty strip beyond the first/last row. Fix: set an explicit `range` (descending instead of `autorange="reversed"`), and keep `config.doubleClick="reset"` (not `"reset+autosize"`) plus no `autoScale2d` button so nothing switches autorange back on.
- `dragmode=False` does **not** disable scroll zoom; Plotly gates it only on `config.scrollZoom` and per-axis `fixedrange`. And `dragmode="pan"` does not mean *only* panning: Plotly also lays down corner/edge draggers (`.nwdrag`, `.ewdrag`, …) that zoom one end of the axis — switch them off with `pointer-events: none`. Worse, Plotly's pan clamps the two axis ends **independently** against `minallowed`/`maxallowed`, so panning into a boundary shrinks the range, i.e. the drag zooms. If a drag must never change the zoom, disable Plotly's pan and drive the range yourself with a span-preserving clamp. Note that `dragmode=False` then stops Plotly from suppressing the click that ends a drag (gate your click handlers on a movement threshold) and that the DOM `dblclick` never arrives — use `plotly_doubleclick`, which fires even with `config.doubleClick=False`.

**Visualize2 — band colorscale technique:** Each aspect column gets its own colour band in `[j/n, (j+1)/n]`. Values are normalised into their band with `normalize_to_bands()`, then a single `go.Heatmap` trace uses this as a continuous colour axis — avoiding the duplicate-column problem that occurs with one trace per column.

**Visualize3 / Visualize4 — dual-mode figures:** Both figures contain two traces (Heatmap + Sunburst) with one initially `visible=False`. `updatemenus` buttons use `method='update'` to toggle visibility and simultaneously relayout title, width, height, and margins. `width: None` does not work in Plotly.js relayout — always use a concrete pixel value.

### Config files

| File | Role |
|---|---|
| `heroes.json` | All hero name strings, including both bare (`Spider-Man`) and canonical dual-identity forms (`Spider-Man * Peter Parker`) |
| `hero_aliases.json` | Maps bare name → canonical name for the `heroes_total.csv` rollup |
| `scenarios.json` | Canonical display order used in all visualizations |
| `scenario_modulars.json` | `{ scenario: [modular, ...] }` — always auto-included |
| `scenario_default_modulars.json` | `{ scenario: [modular, ...] }` — used when only difficulty or nothing was noted |
| `non_modulars.json` | Names counted via the two files above that are **not** modular encounter sets — hidden in the Szenarien × Modulars cross-table only |

Adding a new hero: add the name to `heroes.json`. If it's a dual-identity, also add the bare form and an entry in `hero_aliases.json`.

Note that `count_modular` writes via `modular_counts.get(mod, 0) + 1`, so any name in `scenario_modulars.json` / `scenario_default_modulars.json` silently creates a new statistics entry even if it is absent from `modulars.json` — a typo there produces a phantom modular rather than an error.
