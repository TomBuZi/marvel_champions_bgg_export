import os
import webbrowser
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ASPECT_COLORS = {
    'Aggression': '#C8102E',
    'Protection': '#00A651',
    'Justice':    '#FFD700',
    'Leadership': '#0072CE',
    'Basic':      '#808080',
    'Precon':     '#A0A0A0',
    "'Pool":      '#FF69B4',
}
MARVEL_RED = '#E62429'

# --- Daten laden ---
df_heroes      = pd.read_csv('heroes_total.csv', sep=';')
df_aspects     = pd.read_csv('marvel_champions_aspect_stats.csv', sep=';')
df_scenarios   = pd.read_csv('marvel_champions_scenario_stats.csv', sep=';')
df_plays       = pd.read_csv('marvel_champions_plays.csv', sep=';')
df_hero_aspects = pd.read_csv('heroes_aspects.csv', sep=';')

df_aspects['aspect'] = df_aspects['aspect'].str.strip()

top10_heroes    = df_heroes.sort_values('Count', ascending=False).head(10)
top10_scenarios = df_scenarios.sort_values('count', ascending=False).head(10)

# --- Subplots ---
fig = make_subplots(
    rows=3, cols=2,
    subplot_titles=(
        'Top 10 Meistgespielte Helden',
        'Verteilung der Aspekte',
        'Top 10 Meistgespielte Szenarien',
        'Gesamt Gewinnrate',
        'Aspekt-Präferenz der Top 5 Helden',
        'Spielaktivität über die Zeit',
    ),
    specs=[
        [{'type': 'bar'},  {'type': 'pie'}],
        [{'type': 'bar'},  {'type': 'pie'}],
        [{'type': 'bar'},  {'type': 'scatter'}],
    ],
    vertical_spacing=0.12,
    horizontal_spacing=0.1,
)

# 1. Top 10 Helden (horizontaler Balken)
fig.add_trace(go.Bar(
    x=top10_heroes['Count'],
    y=top10_heroes['Hero'],
    orientation='h',
    marker_color=MARVEL_RED,
    hovertemplate='<b>%{y}</b>: %{x} Spiele<extra></extra>',
), row=1, col=1)
fig.update_yaxes(autorange='reversed', row=1, col=1)

# 2. Aspekt-Donut
aspect_colors_list = [ASPECT_COLORS.get(a, '#333333') for a in df_aspects['aspect']]
fig.add_trace(go.Pie(
    labels=df_aspects['aspect'],
    values=df_aspects['count'],
    hole=0.6,
    marker=dict(colors=aspect_colors_list),
    textinfo='label+percent',
    hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
), row=1, col=2)

# 3. Top 10 Szenarien (horizontaler Balken)
fig.add_trace(go.Bar(
    x=top10_scenarios['count'],
    y=top10_scenarios['scenario'],
    orientation='h',
    marker_color='#5B2D8E',
    hovertemplate='<b>%{y}</b>: %{x} Spiele<extra></extra>',
), row=2, col=1)
fig.update_yaxes(autorange='reversed', row=2, col=1)

# 4. Gewinnrate
win_loss = df_plays['result'].str.strip().value_counts()
if 'won' in win_loss.index and 'lost' in win_loss.index:
    fig.add_trace(go.Pie(
        labels=['Gewonnen', 'Verloren'],
        values=[win_loss['won'], win_loss['lost']],
        marker=dict(colors=['#4CAF50', '#F44336']),
        pull=[0.05, 0],
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
    ), row=2, col=2)
else:
    fig.add_annotation(text='Keine Win/Loss-Daten', row=2, col=2,
                       xref='paper', yref='paper', showarrow=False)

# 5. Aspekt-Präferenz Top-5-Helden (gestapelter Balken)
top5 = df_heroes.sort_values('Count', ascending=False).head(5)['Hero'].tolist()
df_top = df_hero_aspects[df_hero_aspects['Hero'].isin(top5)]
pivot  = df_top.pivot_table(index='Hero', columns='Aspect', values='Count', fill_value=0)
pivot['_total'] = pivot.sum(axis=1)
pivot  = pivot.sort_values('_total', ascending=False).drop(columns='_total')

for aspect in pivot.columns:
    fig.add_trace(go.Bar(
        name=aspect,
        x=list(pivot.index),
        y=pivot[aspect].tolist(),
        marker_color=ASPECT_COLORS.get(aspect, '#333333'),
        hovertemplate=f'<b>%{{x}}</b> – {aspect}: %{{y}}<extra></extra>',
        showlegend=True,
    ), row=3, col=1)
fig.update_layout(barmode='stack')

# 6. Spielaktivität über die Zeit
df_plays['date'] = pd.to_datetime(df_plays['date'], errors='coerce')
plays_per_month  = df_plays.resample('ME', on='date').size().reset_index()
plays_per_month.columns = ['date', 'count']

fig.add_trace(go.Scatter(
    x=plays_per_month['date'],
    y=plays_per_month['count'],
    mode='lines+markers',
    marker=dict(color=MARVEL_RED, size=6),
    line=dict(color=MARVEL_RED, width=2),
    hovertemplate='%{x|%b %Y}: %{y} Spiele<extra></extra>',
), row=3, col=2)

# --- Layout ---
fig.update_layout(
    title=dict(text='Marvel Champions — Statistik-Dashboard', font=dict(size=18)),
    height=1200,
    showlegend=True,
    legend=dict(title='Aspekt', x=1.02, y=0.17),
    template='plotly_white',
)

output = 'dashboard.html'
fig.write_html(output, include_plotlyjs='cdn')
print(f'Gespeichert als: {output}')
webbrowser.open(f'file:///{os.path.abspath(output)}')
