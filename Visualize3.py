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

SCENARIOS = load_config("scenarios.json")  # Reihenfolge beibehalten


def build():
    # --- Daten laden ---
    df = pd.read_csv('heroes_scenarios.csv', sep=';')
    df = df[df['Count'] > 0]

    pivot = df.pivot_table(index='Hero', columns='Scenario', values='Count', aggfunc='sum', fill_value=0)

    # Spalten: Szenarien in JSON-Reihenfolge, nur vorhandene
    scenario_cols = [s for s in SCENARIOS if s in pivot.columns]
    pivot = pivot.reindex(columns=scenario_cols, fill_value=0)

    # Zeilen: Helden alphabetisch, nur gespielte
    pivot = pivot[pivot.sum(axis=1) > 0]
    pivot = pivot.sort_index(ascending=True)

    heroes    = list(pivot.index)
    scenarios = list(pivot.columns)

    # --- Heatmap-Trace ---
    z_raw = pivot.values.astype(float)
    z_raw[z_raw == 0] = np.nan
    text = [[str(int(v)) if not np.isnan(v) else '' for v in row] for row in z_raw]

    heatmap = go.Heatmap(
        z=z_raw,
        x=scenarios,
        y=heroes,
        text=text,
        customdata=text,
        texttemplate='%{text}',
        textfont=dict(size=11, color='black'),
        colorscale='YlOrRd',
        showscale=True,
        colorbar=dict(title='Partien', thickness=15),
        hovertemplate='<b>%{y}</b> vs <b>%{x}</b>: %{customdata} Partien<extra></extra>',
        visible=True,
    )

    # --- Sunburst-Daten aufbauen: Root → Held → Szenario → Held ---
    sb_ids     = ['root']
    sb_labels  = ['Alle Helden']
    sb_parents = ['']
    sb_values  = [0]
    sb_colors  = [0]

    # Level 1: Helden
    for hero in heroes:
        hero_total = int(pivot.loc[hero].sum())
        sb_ids.append(hero)
        sb_labels.append(f"{hero}  ({hero_total})")
        sb_parents.append('root')
        sb_values.append(0)
        sb_colors.append(hero_total)

    # Level 2: Szenarien unter jedem Helden (nur gespielte)
    for hero in heroes:
        for scenario in scenarios:
            count = int(pivot.loc[hero, scenario])
            if count > 0:
                sb_ids.append(f"{hero}|{scenario}")
                sb_labels.append(f"{scenario}  ({count})")
                sb_parents.append(hero)
                sb_values.append(0)
                sb_colors.append(count)

    # Level 3: Alle Helden, die dasselbe Szenario gespielt haben
    for hero in heroes:
        for scenario in scenarios:
            if int(pivot.loc[hero, scenario]) > 0:
                for hero2 in heroes:
                    count2 = int(pivot.loc[hero2, scenario])
                    if count2 > 0:
                        sb_ids.append(f"{hero}|{scenario}|{hero2}")
                        sb_labels.append(f"{hero2}  ({count2})")
                        sb_parents.append(f"{hero}|{scenario}")
                        sb_values.append(count2)
                        sb_colors.append(count2)

    sunburst = go.Sunburst(
        ids=sb_ids,
        labels=sb_labels,
        parents=sb_parents,
        values=sb_values,
        branchvalues='remainder',
        maxdepth=2,
        domain=dict(x=[0, 1], y=[0, 1]),
        marker=dict(
            colors=sb_colors,
            colorscale='YlOrRd',
            showscale=False,
        ),
        textfont=dict(size=11),
        insidetextorientation='radial',
        hovertemplate='<b>%{label}</b><br>%{value} Partien<extra></extra>',
        visible=False,
    )

    col_width  = 36
    row_height = 26
    fig_width  = max(900, len(scenarios) * col_width + 250)
    fig_height = max(500, len(heroes)    * row_height + 150)

    fig = go.Figure(data=[heatmap, sunburst])

    fig.update_layout(
        title=dict(text='Helden × Schurken — Anzahl Partien', font=dict(size=16)),
        autosize=True,
        height=fig_height,
        dragmode=False,
        xaxis=dict(
            side='top',
            tickangle=-45,
            tickfont=dict(size=11),
            categoryorder='array',
            categoryarray=scenarios,
        ),
        yaxis=dict(
            autorange='reversed',
            tickfont=dict(size=11),
        ),
        margin=dict(l=220, r=80, t=160, b=40),
        updatemenus=[dict(
            type='buttons',
            buttons=[
                dict(
                    label='Kreuztabelle',
                    method='update',
                    args=[
                        {'visible': [True, False]},
                        {'title': {'text': 'Helden \u00d7 Schurken \u2014 Anzahl Partien'},
                         'height': fig_height,
                         'margin': {'l': 220, 'r': 80, 't': 160, 'b': 40}},
                    ],
                ),
                dict(
                    label='Sunburst',
                    method='update',
                    args=[
                        {'visible': [False, True]},
                        {'title': {'text': 'Helden \u2192 Szenarien \u2192 Helden'},
                         'height': 850,
                         'margin': {'l': 10, 'r': 10, 't': 100, 'b': 10}},
                    ],
                ),
            ],
            direction='right',
            x=0.0, xanchor='left', y=1.06, yanchor='bottom',
            bgcolor='white', bordercolor='#aaaaaa', font=dict(size=12),
            showactive=True,
        )],
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'hero_villain_matrix.html'
    fig.write_html(output, include_plotlyjs='cdn', full_html=True)
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
