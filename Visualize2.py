import json
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
    'Undefined':  '#cccccc',
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
    df_totals = pd.read_csv('heroes_total.csv', sep=';').set_index('Hero')

    # Pivot aller Aspekte (inkl. leerem Aspekt für "Undefined")
    pivot_full = df.pivot_table(index='Hero', columns='Aspect', values='Count', aggfunc='sum', fill_value=0)

    aspect_order = ['Aggression', 'Justice', 'Leadership', 'Protection', 'Basic', "'Pool", 'Precon']
    aspects = [a for a in aspect_order if a in pivot_full.columns]
    pivot   = pivot_full.reindex(columns=aspects, fill_value=0)

    # Undefined-Spalte: Partien ohne erkannten Aspekt
    if '' in pivot_full.columns:
        pivot['Undefined'] = pivot_full['']
    else:
        pivot['Undefined'] = 0

    # Zeilen ohne jegliche Daten entfernen
    pivot = pivot[pivot.sum(axis=1) > 0]

    # Total aus heroes_total.csv — korrekte Spielanzahl auch für Multi-Aspekt-Helden
    pivot['Total'] = pivot.index.map(lambda h: int(df_totals.loc[h, 'Count']) if h in df_totals.index else 0)

    # Undefined-Spalte weglassen wenn keine undefined Partien vorhanden
    has_undefined = pivot['Undefined'].sum() > 0
    extra_cols = (['Undefined'] if has_undefined else []) + ['Total']
    all_cols   = aspects + extra_cols

    # Trennlinie vor Total (Index der Total-Spalte)
    separator_x = len(all_cols) - 1 - 0.5

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

    # Trennlinie vor Total
    fig.add_shape(
        type='line', xref='x', yref='paper',
        x0=separator_x, x1=separator_x,
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
        dragmode=False,
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


def build_table_html():
    """Sortierbare HTML-Kreuztabelle: Helden (Zeilen) × Aspekte (Spalten)."""
    df        = pd.read_csv('heroes_aspects.csv', sep=';')
    df_totals = pd.read_csv('heroes_total.csv',   sep=';').set_index('Hero')

    pivot_full = df.pivot_table(
        index='Hero', columns='Aspect', values='Count', aggfunc='sum', fill_value=0
    )

    aspect_order = ['Aggression', 'Justice', 'Leadership', 'Protection', 'Basic', "'Pool", 'Precon']
    aspects = [a for a in aspect_order if a in pivot_full.columns]
    pivot   = pivot_full.reindex(columns=aspects, fill_value=0)

    if '' in pivot_full.columns:
        pivot['Undefined'] = pivot_full['']
    else:
        pivot['Undefined'] = 0

    pivot = pivot[pivot.sum(axis=1) > 0]
    pivot['Total'] = pivot.index.map(
        lambda h: int(df_totals.loc[h, 'Count']) if h in df_totals.index else 0
    )

    has_undefined = pivot['Undefined'].sum() > 0
    extra_cols    = (['Undefined'] if has_undefined else []) + ['Total']
    all_cols      = aspects + extra_cols

    col_maxes = {col: int(pivot[col].max()) for col in all_cols if pivot[col].max() > 0}

    rows = []
    for hero, row in pivot.iterrows():
        entry = {'hero': str(hero)}
        for col in all_cols:
            entry[col] = int(row[col])
        rows.append(entry)

    data_json     = json.dumps(rows,     ensure_ascii=False).replace('</script>', r'<\/script>')
    cols_json     = json.dumps(all_cols, ensure_ascii=False)
    colors_json   = json.dumps(ASPECT_COLORS, ensure_ascii=False)
    col_maxes_json = json.dumps(col_maxes, ensure_ascii=False)
    total = len(rows)

    # Spaltennamen als HTML-sichere data-sort-Attribute (für Event-Delegation)
    # Wichtig: onclick-Attribute in dynamisch gebautem innerHTML vermeiden,
    # da Spaltennamen wie "'Pool" die JS-String-Begrenzer brechen würden.
    parts = []
    parts.append(f"""
<div style="padding:8px">
  <div style="margin-bottom:6px;font-size:12px;color:#666">
    {total} Helden &mdash; sortierbar per Klick auf Spalten&uuml;berschrift
  </div>
  <div class="sticky-table-wrap" style="max-height:calc(100vh - 130px)">
    <table class="sticky-table" id="aspect-table">
      <thead id="aspect-thead"></thead>
      <tbody id="aspect-tbody"></tbody>
    </table>
  </div>
</div>
<script>
(function() {{
  var ROWS      = {data_json};
  var COLS      = {cols_json};
  var COLORS    = {colors_json};
  var COL_MAXES = {col_maxes_json};
  var _sortCol  = "Total";
  var _sortAsc  = false;

  function sortAspect(col) {{
    if (_sortCol === col) {{
      _sortAsc = !_sortAsc;
    }} else {{
      _sortCol = col;
      _sortAsc = (col === "hero");
    }}
    renderTable();
  }}

  function hexToRgb(hex) {{
    hex = (hex || "888888").replace("#", "");
    return [parseInt(hex.substr(0,2),16), parseInt(hex.substr(2,2),16), parseInt(hex.substr(4,2),16)];
  }}

  function cellBg(col, val) {{
    if (!val || col === "Total" || col === "Undefined") return "";
    var color = COLORS[col];
    if (!color) return "";
    var max = COL_MAXES[col] || 1;
    var t = 0.65 * (val / max);
    var rgb = hexToRgb(color);
    var r = Math.round(rgb[0] * t + 255 * (1 - t));
    var g = Math.round(rgb[1] * t + 255 * (1 - t));
    var b = Math.round(rgb[2] * t + 255 * (1 - t));
    return "background:rgb(" + r + "," + g + "," + b + ")";
  }}

  function escHtml(s) {{
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}

  function ind(col) {{
    if (col !== _sortCol) return "";
    return _sortAsc ? " &#9650;" : " &#9660;";
  }}

  function renderTable() {{
    var thead = document.getElementById("aspect-thead");
    if (!thead) return;

    // Header: data-sort-Attribut trägt den Spaltennamen; click via Event-Delegation
    var hrow = "<tr>";
    hrow += "<th class=\\"tbl-corner tbl-col\\" data-sort=\\"hero\\">Held" + ind("hero") + "</th>";
    COLS.forEach(function(col) {{
      var border = (col === "Total") ? "border-left:2px solid #555;" : "";
      var active = (col === _sortCol) ? " tbl-sort-active" : "";
      hrow += "<th class=\\"tbl-col" + active + "\\" style=\\"" + border
            + "\\" data-sort=\\"" + escHtml(col) + "\\">"
            + escHtml(col) + ind(col) + "</th>";
    }});
    hrow += "</tr>";
    thead.innerHTML = hrow;

    // Event-Delegation: nach jedem innerHTML-Update neu anhängen
    thead.querySelectorAll("th[data-sort]").forEach(function(th) {{
      th.addEventListener("click", function() {{
        sortAspect(this.getAttribute("data-sort"));
      }});
    }});

    // Body
    var sorted = ROWS.slice().sort(function(a, b) {{
      var va = (_sortCol === "hero") ? (a.hero || "").toLowerCase() : (a[_sortCol] || 0);
      var vb = (_sortCol === "hero") ? (b.hero || "").toLowerCase() : (b[_sortCol] || 0);
      if (va < vb) return _sortAsc ? -1 : 1;
      if (va > vb) return _sortAsc ? 1 : -1;
      return 0;
    }});

    var tbody = document.getElementById("aspect-tbody");
    var html = "";
    sorted.forEach(function(row) {{
      html += "<tr><td class=\\"tbl-row\\">" + escHtml(row.hero) + "</td>";
      COLS.forEach(function(col) {{
        var val    = row[col] || 0;
        var bg     = cellBg(col, val);
        var border = (col === "Total") ? "border-left:2px solid #ccc;" : "";
        var style  = (bg || border) ? " style=\\"" + bg + (bg && border ? ";" : "") + border + "\\"" : "";
        html += "<td" + style + ">" + (val > 0 ? val : "") + "</td>";
      }});
      html += "</tr>";
    }});
    tbody.innerHTML = html;
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", renderTable);
  }} else {{
    renderTable();
  }}
}})();
</script>
""")
    return "".join(parts)


if __name__ == '__main__':
    fig = build()
    output = 'hero_aspect_matrix.html'
    fig.write_html(output, include_plotlyjs='cdn')
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
