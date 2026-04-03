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

# Zelldaten
z_raw  = pivot.values.astype(float)
z_raw[z_raw == 0] = np.nan
z_masked = z_raw.copy()
text = [[str(int(v)) if not np.isnan(v) else '' for v in row] for row in z_raw]

heroes    = list(pivot.index)
scenarios = list(pivot.columns)

col_width  = 36
row_height = 26
fig_width  = max(900, len(scenarios) * col_width + 250)
fig_height = max(500, len(heroes)    * row_height + 150)

fig = go.Figure(go.Heatmap(
    z=z_masked,
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
))

fig.update_layout(
    title=dict(text='Helden × Schurken — Anzahl Partien', font=dict(size=16)),
    width=fig_width,
    height=fig_height,
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
)

output = 'hero_villain_matrix.html'
fig.write_html(output, include_plotlyjs='cdn', full_html=True,
               config={'scrollZoom': True})
print(f'Gespeichert als: {output}')
webbrowser.open(f'file:///{os.path.abspath(output)}')
