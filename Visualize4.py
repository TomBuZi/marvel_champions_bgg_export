import os
import webbrowser
import pandas as pd
import plotly.graph_objects as go

df = pd.read_csv('marvel_champions_scenario_modular_combos.csv', sep=';')

scenario_totals = df.groupby('scenario')['count'].sum().reset_index()

# Treemap-Struktur aufbauen: Root → Szenario → Kombination
ids     = ['root']
labels  = ['Alle Szenarien']
parents = ['']
values  = [0]
colors  = [0]

for _, row in scenario_totals.iterrows():
    ids.append(row['scenario'])
    labels.append(f"{row['scenario']}  ({row['count']})")
    parents.append('root')
    values.append(0)  # Größe wird aus Kindern berechnet
    colors.append(int(row['count']))

for _, row in df.iterrows():
    ids.append(f"{row['scenario']}|{row['modulars']}")
    labels.append(f"{row['modulars']}  ({row['count']})")
    parents.append(row['scenario'])
    values.append(int(row['count']))
    colors.append(int(row['count']))

fig = go.Figure(go.Treemap(
    ids=ids,
    labels=labels,
    parents=parents,
    values=values,
    branchvalues='remainder',
    maxdepth=2,
    marker=dict(
        colors=colors,
        colorscale='YlOrRd',
        showscale=True,
        colorbar=dict(title='Partien', thickness=15),
    ),
    textfont=dict(size=13),
    hovertemplate='<b>%{label}</b><br>%{value} Partien<extra></extra>',
    pathbar=dict(visible=True),
))

fig.update_layout(
    title=dict(text='Szenarien × Modularkombinationen — Klick zum Reinzoomen', font=dict(size=16)),
    height=850,
    margin=dict(l=10, r=10, t=70, b=10),
)

output = 'scenario_modular_treemap.html'
fig.write_html(output, include_plotlyjs='cdn')
print(f'Gespeichert als: {output}')
webbrowser.open(f'file:///{os.path.abspath(output)}')
