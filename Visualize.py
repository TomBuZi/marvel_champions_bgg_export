import os
import webbrowser
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import savgol_filter

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


def build(mobile=False):
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
    if mobile:
        fig = make_subplots(
            rows=6, cols=1,
            subplot_titles=(
                'Top 10 Meistgespielte Helden',
                'Top 10 Meistgespielte Szenarien',
                'Verteilung der Aspekte',
                'Gesamt Gewinnrate',
                'Aspekt-Präferenz der Top 5 Helden',
                'Spielaktivität über die Zeit',
            ),
            specs=[
                [{'type': 'bar'}],
                [{'type': 'bar'}],
                [{'type': 'pie'}],
                [{'type': 'pie'}],
                [{'type': 'bar'}],
                [{'type': 'scatter'}],
            ],
            vertical_spacing=0.05,
        )
        r_heroes, r_scen, r_asp_pie, r_win_pie = 1, 2, 3, 4
        r_asp_bar, c_asp_bar = 5, 1
        r_time,    c_time    = 6, 1
    else:
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
        r_heroes, r_scen, r_asp_pie, r_win_pie = 1, 2, 1, 2
        r_asp_bar, c_asp_bar = 3, 1
        r_time,    c_time    = 3, 2

    c_heroes  = 1
    c_scen    = 1
    c_asp_pie = 1 if mobile else 2
    c_win_pie = 1 if mobile else 2

    # 1. Top 10 Helden (horizontaler Balken)
    fig.add_trace(go.Bar(
        x=top10_heroes['Count'],
        y=top10_heroes['Hero'],
        orientation='h',
        marker_color=MARVEL_RED,
        hovertemplate='<b>%{y}</b>: %{x} Spiele<extra></extra>',
    ), row=r_heroes, col=c_heroes)
    fig.update_yaxes(autorange='reversed', row=r_heroes, col=c_heroes)

    # 2. Aspekt-Donut
    aspect_colors_list = [ASPECT_COLORS.get(a, '#333333') for a in df_aspects['aspect']]
    fig.add_trace(go.Pie(
        labels=df_aspects['aspect'],
        values=df_aspects['count'],
        hole=0.6,
        marker=dict(colors=aspect_colors_list),
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
    ), row=r_asp_pie, col=c_asp_pie)

    # 3. Top 10 Szenarien (horizontaler Balken)
    fig.add_trace(go.Bar(
        x=top10_scenarios['count'],
        y=top10_scenarios['scenario'],
        orientation='h',
        marker_color='#5B2D8E',
        hovertemplate='<b>%{y}</b>: %{x} Spiele<extra></extra>',
    ), row=r_scen, col=c_scen)
    fig.update_yaxes(autorange='reversed', row=r_scen, col=c_scen)

    # 4. Gewinnrate (inkl. "Ohne Ergebnis" für nowinstats=1 oder kein Ergebnis)
    result_clean   = df_plays['result'].str.strip().str.lower()
    nowinstats_set = df_plays['nowinstats'].astype(str).str.strip() == '1'

    n_won   = ((result_clean == 'won')  & ~nowinstats_set).sum()
    n_lost  = ((result_clean == 'lost') & ~nowinstats_set).sum()
    n_other = nowinstats_set.sum()

    pie_labels = ['Gewonnen', 'Verloren', 'Ohne Ergebnis']
    pie_values = [n_won, n_lost, n_other]
    pie_colors = ['#4CAF50', '#F44336', '#9E9E9E']
    pie_pull   = [0.05, 0, 0]

    # Slices mit 0 ausblenden
    pie_labels, pie_values, pie_colors, pie_pull = zip(*(
        (l, v, c, p) for l, v, c, p in zip(pie_labels, pie_values, pie_colors, pie_pull)
        if v > 0
    ))

    fig.add_trace(go.Pie(
        labels=list(pie_labels),
        values=list(pie_values),
        marker=dict(colors=list(pie_colors)),
        pull=list(pie_pull),
        hovertemplate='<b>%{label}</b>: %{value} (%{percent})<extra></extra>',
    ), row=r_win_pie, col=c_win_pie)

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
            showlegend=False,
        ), row=r_asp_bar, col=c_asp_bar)
    fig.update_layout(barmode='stack')

    # 6. Spielaktivität über die Zeit
    df_plays['date'] = pd.to_datetime(df_plays['date'], errors='coerce')
    plays_per_month  = df_plays.resample('ME', on='date').size().reset_index()
    plays_per_month.columns = ['date', 'count']

    y_hist = plays_per_month['count'].values.astype(float)
    n_hist = len(y_hist)

    raw       = max(n_hist // 3, 9)
    sg_window = raw if raw % 2 == 1 else raw + 1
    sg_window = min(sg_window, n_hist if n_hist % 2 == 1 else n_hist - 1)
    y_smooth  = np.maximum(savgol_filter(y_hist, window_length=sg_window, polyorder=2), 0)

    n_fit    = min(12, n_hist)
    x_fit    = np.arange(n_hist - n_fit, n_hist)
    coeffs   = np.polyfit(x_fit, y_hist[n_hist - n_fit:], 1)
    lin      = np.poly1d(coeffs)

    n_fore     = 6
    x_fore     = np.arange(n_hist, n_hist + n_fore)
    y_fore     = np.maximum(lin(x_fore), 0)
    dates_fore = pd.date_range(plays_per_month['date'].iloc[-1], periods=n_fore + 1, freq='ME')[1:]

    x_link = [plays_per_month['date'].iloc[-1], dates_fore[0]]
    y_link = [y_smooth[-1], y_fore[0]]

    fig.add_trace(go.Scatter(
        x=plays_per_month['date'], y=plays_per_month['count'],
        mode='lines+markers', name='Monatliche Spiele',
        marker=dict(color=MARVEL_RED, size=6),
        line=dict(color=MARVEL_RED, width=2),
        hovertemplate='%{x|%b %Y}: %{y} Spiele<extra></extra>',
        showlegend=False,
    ), row=r_time, col=c_time)

    fig.add_trace(go.Scatter(
        x=plays_per_month['date'], y=y_smooth,
        mode='lines', name='Trend',
        line=dict(color='#FF8C00', width=2, dash='dash'),
        hovertemplate='%{x|%b %Y} Trend: %{y:.1f}<extra></extra>',
        showlegend=False,
    ), row=r_time, col=c_time)

    fig.add_trace(go.Scatter(
        x=x_link, y=y_link,
        mode='lines', line=dict(color='#FF8C00', width=2, dash='dash'),
        showlegend=False, hoverinfo='skip',
    ), row=r_time, col=c_time)

    fig.add_trace(go.Scatter(
        x=dates_fore, y=y_fore,
        mode='lines+markers', name='Prognose (6 Monate)',
        line=dict(color='#FF8C00', width=2, dash='dot'),
        marker=dict(color='#FF8C00', size=5, symbol='circle-open'),
        hovertemplate='%{x|%b %Y} Prognose: %{y:.1f}<extra></extra>',
        showlegend=False,
    ), row=r_time, col=c_time)

    # --- Layout ---
    height = 2200 if mobile else 1200

    fig.update_layout(
        title=dict(text='Marvel Champions — Statistik-Dashboard', font=dict(size=18)),
        height=height,
        dragmode=False,
        showlegend=False,
        template='plotly_white',
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'dashboard.html'
    fig.write_html(output, include_plotlyjs='cdn')
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
