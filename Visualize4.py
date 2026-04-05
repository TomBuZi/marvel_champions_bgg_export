import json
import os
import webbrowser
import numpy as np
import pandas as pd
import plotly.graph_objects as go

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

def load_config(filename):
    with open(os.path.join(CONFIG_DIR, filename), encoding="utf-8") as f:
        return json.load(f)

SCENARIOS = load_config("scenarios.json")

_DIFFICULTY_ORDER = ["Standard", "Standard II", "Standard III", "Expert", "Expert II"]
_DIFFICULTY_RANK  = {m.lower(): i for i, m in enumerate(_DIFFICULTY_ORDER)}

def _modular_sort_key(name):
    k = name.lower()
    if k in _DIFFICULTY_RANK:
        return (0, _DIFFICULTY_RANK[k], "")
    return (1, 0, name.lower())


def _heat_color(v, max_v):
    if v <= 0 or max_v <= 0:
        return '#ffffff'
    t = min(v / max_v, 1.0)
    r = 255
    g = int(255 * (1 - t * 0.8))
    b = int(255 * (1 - t))
    return f'rgb({r},{g},{b})'


def _load_heatmap_pivot():
    df = pd.read_csv('marvel_champions_scenario_modular_combos.csv', sep=';')
    rows = []
    for _, row in df.iterrows():
        for mod in row['modulars'].split(' + '):
            rows.append({'scenario': row['scenario'], 'modular': mod.strip(), 'count': row['count']})
    df_exp = pd.DataFrame(rows)
    df_exp = df_exp.groupby(['scenario', 'modular'])['count'].sum().reset_index()
    pivot  = df_exp.pivot_table(index='scenario', columns='modular', values='count', fill_value=0)
    scenario_rows = [s for s in SCENARIOS if s in pivot.index]
    pivot = pivot.reindex(index=scenario_rows, fill_value=0)
    pivot = pivot[pivot.sum(axis=1) > 0]
    modular_cols = sorted(pivot.columns.tolist(), key=_modular_sort_key)
    pivot = pivot.reindex(columns=modular_cols, fill_value=0)
    return pivot


def build_table_html():
    """HTML-Tabelle mit sticky Row/Column-Headern für die mobile Kreuztabelle."""
    pivot    = _load_heatmap_pivot()
    scenarios = list(pivot.index)
    modulars  = list(pivot.columns)
    values    = pivot.values.tolist()
    max_v     = max(max(row) for row in values) if values else 1

    th_corner = '<th class="tbl-corner">Szenario / Modular</th>'
    th_cols   = ''.join(f'<th class="tbl-col">{m}</th>' for m in modulars)
    header    = f'<thead><tr>{th_corner}{th_cols}</tr></thead>'

    rows = []
    for i, scen in enumerate(scenarios):
        cells = [f'<th class="tbl-row">{scen}</th>']
        for v in values[i]:
            color = _heat_color(v, max_v)
            text  = str(int(v)) if v > 0 else ''
            cells.append(f'<td style="background:{color}">{text}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')

    tbody = '<tbody>' + ''.join(rows) + '</tbody>'
    return f'<div class="sticky-table-wrap"><table class="sticky-table">{header}{tbody}</table></div>'


def build():
    df       = pd.read_csv('marvel_champions_scenario_modular_combos.csv', sep=';')
    df_heroes = pd.read_csv('marvel_champions_scenario_modular_hero.csv', sep=';')

    scenario_totals = df.groupby('scenario')['count'].sum().reset_index()

    # --- Sunburst-Trace (Szenario → Modularkombination) ---
    sb_ids     = ['root']
    sb_labels  = ['Alle Szenarien']
    sb_parents = ['']
    sb_values  = [0]
    sb_colors  = [0]

    for _, row in scenario_totals.iterrows():
        sb_ids.append(row['scenario'])
        sb_labels.append(f"{row['scenario']}  ({row['count']})")
        sb_parents.append('root')
        sb_values.append(0)
        sb_colors.append(int(row['count']))

    for _, row in df.iterrows():
        sb_ids.append(f"{row['scenario']}|{row['modulars']}")
        sb_labels.append(f"{row['modulars']}  ({row['count']})")
        sb_parents.append(row['scenario'])
        sb_values.append(int(row['count']))
        sb_colors.append(int(row['count']))

    sunburst = go.Sunburst(
        ids=sb_ids,
        labels=sb_labels,
        parents=sb_parents,
        values=sb_values,
        branchvalues='remainder',
        maxdepth=2,
        marker=dict(
            colors=sb_colors,
            colorscale='YlOrRd',
            showscale=False,
        ),
        textfont=dict(size=12),
        insidetextorientation='radial',
        hovertemplate='<b>%{label}</b><br>%{value} Partien<extra></extra>',
        visible=True,
    )

    # --- Heatmap-Trace (Szenario × einzelne Modulars) ---
    rows = []
    for _, row in df.iterrows():
        for mod in row['modulars'].split(' + '):
            rows.append({'scenario': row['scenario'], 'modular': mod.strip(), 'count': row['count']})
    df_exp = pd.DataFrame(rows)
    df_exp = df_exp.groupby(['scenario', 'modular'])['count'].sum().reset_index()

    pivot = df_exp.pivot_table(index='scenario', columns='modular', values='count', fill_value=0)

    scenario_rows = [s for s in SCENARIOS if s in pivot.index]
    pivot = pivot.reindex(index=scenario_rows, fill_value=0)
    pivot = pivot[pivot.sum(axis=1) > 0]

    modular_cols = sorted(pivot.columns.tolist(), key=_modular_sort_key)
    pivot = pivot.reindex(columns=modular_cols, fill_value=0)

    z_raw = pivot.values.astype(float)
    z_raw[z_raw == 0] = np.nan
    text = [[str(int(v)) if not np.isnan(v) else '' for v in row] for row in z_raw]

    hm_scenarios = list(pivot.index)
    hm_modulars  = list(pivot.columns)

    col_width  = 34
    row_height = 26
    hm_width   = max(900, len(hm_modulars)  * col_width  + 250)
    hm_height  = max(500, len(hm_scenarios) * row_height + 180)

    heatmap = go.Heatmap(
        z=z_raw,
        x=hm_modulars,
        y=hm_scenarios,
        text=text,
        customdata=text,
        texttemplate='%{text}',
        textfont=dict(size=11, color='black'),
        colorscale='YlOrRd',
        showscale=True,
        colorbar=dict(title='Partien', thickness=15),
        hovertemplate='<b>%{y}</b> \u00d7 <b>%{x}</b>: %{customdata} Partien<extra></extra>',
        visible=False,
    )

    # --- Icicle-Trace (Baumansicht: Szenario → Modularkombination → Held) ---
    # Gleichmäßige Zeilenhöhe pro Szenario: normalisierte Werte (UNIFORM pro Szenario),
    # damit auch selten gespielte Szenarien anklickbar bleiben.
    UNIFORM    = 1000
    ic_height  = max(950, len(scenario_totals) * 52)

    ic_ids     = ['root']
    ic_labels  = ['Alle Szenarien']
    ic_parents = ['']
    ic_values  = [0]
    ic_colors  = [0]
    ic_custom  = [0]  # tatsächliche Spielanzahl für Hover

    for _, scen_row in scenario_totals.iterrows():
        scenario   = scen_row['scenario']
        scen_total = int(scen_row['count'])

        ic_ids.append(scenario)
        ic_labels.append(f"{scenario}  ({scen_total})")
        ic_parents.append('root')
        ic_values.append(0)
        ic_colors.append(scen_total)
        ic_custom.append(scen_total)

        scen_combos = df[df['scenario'] == scenario]

        for _, combo_row in scen_combos.iterrows():
            combo_str   = combo_row['modulars']
            combo_count = int(combo_row['count'])
            combo_norm  = (combo_count / scen_total * UNIFORM) if scen_total > 0 else UNIFORM

            # Lange Modularlisten umbrechen
            combo_label = combo_str.replace(' + ', '<br>')
            node_id     = f"{scenario}|{combo_str}"

            ic_ids.append(node_id)
            ic_labels.append(f"{combo_label}<br>({combo_count})")
            ic_parents.append(scenario)
            ic_values.append(0)
            ic_colors.append(combo_count)
            ic_custom.append(combo_count)

            hero_df    = df_heroes[(df_heroes['scenario'] == scenario) & (df_heroes['modulars'] == combo_str)]
            hero_total = int(hero_df['count'].sum()) if len(hero_df) > 0 else 1

            for _, hero_row in hero_df.iterrows():
                hero       = hero_row['hero']
                hero_count = int(hero_row['count'])
                hero_norm  = (hero_count / hero_total * combo_norm) if hero_total > 0 else combo_norm

                ic_ids.append(f"{node_id}|{hero}")
                ic_labels.append(f"{hero}  ({hero_count})")
                ic_parents.append(node_id)
                ic_values.append(hero_norm)
                ic_colors.append(hero_count)
                ic_custom.append(hero_count)

    icicle = go.Icicle(
        ids=ic_ids,
        labels=ic_labels,
        parents=ic_parents,
        values=ic_values,
        customdata=ic_custom,
        branchvalues='remainder',
        maxdepth=3,
        tiling=dict(orientation='h', pad=2),
        marker=dict(
            colors=ic_colors,
            colorscale='YlOrRd',
            showscale=False,
        ),
        textfont=dict(size=11),
        hovertemplate='<b>%{label}</b><br>%{customdata} Partien<extra></extra>',
        visible=False,
    )

    fig = go.Figure(data=[sunburst, heatmap, icicle])

    fig.update_layout(
        title=dict(text='Szenarien \u00d7 Modularkombinationen \u2014 Klick zum Reinzoomen', font=dict(size=16)),
        uniformtext=dict(mode='hide', minsize=8),
        dragmode=False,
        height=850,
        margin=dict(l=10, r=10, t=60, b=10),
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'scenario_modular_sunburst.html'
    fig.write_html(output, include_plotlyjs='cdn')
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
