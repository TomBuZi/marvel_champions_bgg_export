import os
import webbrowser
import numpy as np
import pandas as pd
import plotly.graph_objects as go

ASPECT_COLORS = {
    'Aggression': '#C8102E',
    'Justice':    '#FFD700',
    'Leadership': '#0072CE',
    'Protection': '#00A651',
    'Basic':      '#808080',
    "'Pool":      '#FF69B4',
    'Precon':     '#A0A0A0',
    'Total':      '#404040',
}

def make_band_colorscale(cols, intensity=0.55):
    """
    Teilt den Farbraum [0,1] in n gleiche Bänder auf.
    Jedes Band geht von Weiß (niedrig) zur Aspektfarbe (hoch).
    """
    n = len(cols)
    cs = []
    for j, col in enumerate(cols):
        h = ASPECT_COLORS.get(col, '#888888').lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r2 = int(r * intensity + 255 * (1 - intensity))
        g2 = int(g * intensity + 255 * (1 - intensity))
        b2 = int(b * intensity + 255 * (1 - intensity))
        color = f'#{r2:02x}{g2:02x}{b2:02x}'

        band_start = j / n
        band_end   = (j + 1) / n

        cs.append([band_start, '#ffffff'])
        cs.append([band_end - 1e-6, color])

    cs.append([1.0, cs[-1][1]])  # letzten Wert abschließen
    return cs


def normalize_to_bands(z_raw, n_cols):
    """Normiert jeden Spaltenwert in sein Band [j/n, (j+1)/n]."""
    z_norm = np.full_like(z_raw, np.nan, dtype=float)
    for j in range(n_cols):
        col = z_raw[:, j]
        col_max = np.nanmax(col[col > 0]) if np.any(col > 0) else 1
        z_norm[:, j] = np.where(
            col > 0,
            (j / n_cols) + (col / col_max) * (1 / n_cols) * 0.9999,
            np.nan
        )
    return z_norm


def build_args(sorted_df, all_cols):
    heroes = list(sorted_df.index)
    z_raw  = sorted_df[all_cols].values.astype(float)
    z_raw[z_raw == 0] = np.nan
    z_norm = normalize_to_bands(z_raw, len(all_cols))
    text   = [[str(int(v)) if not np.isnan(v) else '' for v in row] for row in z_raw]
    return heroes, z_norm.tolist(), text


def build():
    # --- Daten laden ---
    df = pd.read_csv('heroes_aspects.csv', sep=';')
    df = df[df['Count'] > 0]

    pivot = df.pivot_table(index='Hero', columns='Aspect', values='Count', aggfunc='sum', fill_value=0)
    aspect_order = ['Aggression', 'Justice', 'Leadership', 'Protection', 'Basic', "'Pool", 'Precon']
    aspects  = [a for a in aspect_order if a in pivot.columns]
    pivot    = pivot.reindex(columns=aspects, fill_value=0)
    pivot    = pivot[pivot.sum(axis=1) > 0]
    pivot['Total'] = pivot.sum(axis=1)
    all_cols = aspects + ['Total']

    colorscale = make_band_colorscale(all_cols)

    # Standard: Total absteigend
    heroes_0, z_0, text_0 = build_args(pivot.sort_values('Total', ascending=False), all_cols)

    fig = go.Figure(go.Heatmap(
        z=z_0,
        x=all_cols,
        y=heroes_0,
        text=text_0,
        customdata=text_0,
        texttemplate='%{text}',
        textfont=dict(size=12, color='black'),
        colorscale=colorscale,
        showscale=False,
        zmin=0, zmax=1,
        hovertemplate='<b>%{y}</b> – %{x}: %{customdata} Partien<extra></extra>',
    ))

    # Trennlinie zwischen Aspekten und Total
    fig.add_shape(
        type='line', xref='x', yref='paper',
        x0=len(aspects) - 0.5, x1=len(aspects) - 0.5,
        y0=0, y1=1,
        line=dict(color='#333333', width=2),
    )

    # Dropdown-Buttons
    sort_options = [
        ('Total',              'Total', False),
        ('Alphabetisch (A–Z)', 'Hero',  True),
    ] + [(a, a, False) for a in aspects]

    buttons = []
    for label, sort_key, asc in sort_options:
        heroes_s, z_s, text_s = build_args(pivot.sort_values(sort_key, ascending=asc), all_cols)
        buttons.append(dict(
            label=label,
            method='restyle',
            args=[{'z': [z_s], 'y': [heroes_s], 'text': [text_s], 'customdata': [text_s]}],
        ))

    row_height = 28
    fig.update_layout(
        title=dict(text='Helden × Aspekte — Anzahl Partien', font=dict(size=16)),
        height=max(500, len(pivot) * row_height + 200),
        xaxis=dict(side='top', tickangle=-30),
        yaxis=dict(autorange='reversed'),
        margin=dict(l=220, r=80, t=230, b=40),
        updatemenus=[dict(
            type='dropdown', buttons=buttons, direction='down', showactive=True,
            x=0.0, xanchor='left', y=1.12, yanchor='bottom',
            bgcolor='white', bordercolor='#aaaaaa', font=dict(size=12),
        )],
        annotations=[dict(
            text='<b>Sortierung:</b>', xref='paper', yref='paper',
            x=0.0, xanchor='left', y=1.16, yanchor='bottom',
            showarrow=False, font=dict(size=12),
        )],
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'hero_aspect_matrix.html'
    fig.write_html(output, include_plotlyjs='cdn')
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
