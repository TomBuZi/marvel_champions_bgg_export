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


def _load_pivot():
    df = pd.read_csv('heroes_scenarios.csv', sep=';')
    df = df[df['Count'] > 0]
    pivot = df.pivot_table(index='Hero', columns='Scenario', values='Count', aggfunc='sum', fill_value=0)
    scenario_cols = [s for s in SCENARIOS if s in pivot.columns]
    pivot = pivot.reindex(columns=scenario_cols, fill_value=0)
    pivot = pivot[pivot.sum(axis=1) > 0]
    pivot = pivot.sort_index(ascending=True)
    return pivot


def _load_results():
    """Gibt dict {(hero, scenario): (win, loss, incomplete)} zurück."""
    try:
        df = pd.read_csv('heroes_scenarios_results.csv', sep=';')
    except FileNotFoundError:
        return {}
    result = {}
    for _, row in df.iterrows():
        result[(row['Hero'], row['Scenario'])] = (
            int(row['Win']), int(row['Loss']), int(row['Incomplete'])
        )
    return result


def _fmt_result(total, w, l, i):
    """Formatiert Zellentext: N[W/L/I], N[W/L] oder N[N]."""
    if total == 0:
        return ''
    if i > 0:
        return f'{total}[{w}/{l}/{i}]'
    if l > 0:
        return f'{total}[{w}/{l}]'
    return f'{total}[{total}]'


def _heat_color(v, max_v):
    if v <= 0 or max_v <= 0:
        return '#ffffff'
    t = min(v / max_v, 1.0)
    r = 255
    g = int(255 * (1 - t * 0.8))
    b = int(255 * (1 - t))
    return f'rgb({r},{g},{b})'


def build_table_html():
    """Sortierbare HTML-Tabelle mit sticky Row/Column-Headern."""
    pivot     = _load_pivot()
    results   = _load_results()
    heroes    = list(pivot.index)
    scenarios = list(pivot.columns)
    values    = [[int(v) for v in row] for row in pivot.values.tolist()]
    max_v     = max(max(row) for row in values) if values else 1

    # Zellentexte mit W/L/I-Aufschlüsselung
    labels = []
    for hero in heroes:
        row_labels = []
        for scenario in scenarios:
            total = pivot.at[hero, scenario]
            w, l, i = results.get((hero, scenario), (0, 0, 0))
            row_labels.append(_fmt_result(total, w, l, i))
        labels.append(row_labels)

    heroes_js    = json.dumps(heroes,    ensure_ascii=False)
    scenarios_js = json.dumps(scenarios, ensure_ascii=False)
    values_js    = json.dumps(values)
    labels_js    = json.dumps(labels)

    return f"""<div class="sticky-table-wrap">
  <table class="sticky-table" id="viz3-crosstable"></table>
</div>
<script>
(function() {{
  var heroes    = {heroes_js};
  var scenarios = {scenarios_js};
  var values    = {values_js};
  var labels    = {labels_js};
  var maxV      = {int(max_v)};
  var state     = {{type: null, idx: -1}};

  function heatColor(v) {{
    if (v <= 0) return '#ffffff';
    var t = Math.min(v / maxV, 1.0);
    return 'rgb(255,' + Math.round(255*(1-t*0.8)) + ',' + Math.round(255*(1-t)) + ')';
  }}

  function render() {{
    var hi = heroes.map(function(_,i){{return i;}});
    var si = scenarios.map(function(_,i){{return i;}});
    if (state.type==='col') hi.sort(function(a,b){{return values[b][state.idx]-values[a][state.idx];}});
    if (state.type==='row') si.sort(function(a,b){{return values[state.idx][b]-values[state.idx][a];}});

    var h = '<thead><tr><th class="tbl-corner">Held / Szenario</th>';
    si.forEach(function(s) {{
      var act = state.type==='col' && state.idx===s;
      h += '<th class="tbl-col'+(act?' tbl-sort-active':'')+'" onclick="Viz3Sort.col('+s+')">'
           + scenarios[s] + (act?' \u2193':'') + '</th>';
    }});
    h += '</tr></thead><tbody>';
    hi.forEach(function(r) {{
      var act = state.type==='row' && state.idx===r;
      h += '<tr><th class="tbl-row'+(act?' tbl-sort-active':'')+'" onclick="Viz3Sort.row('+r+')">'
           + heroes[r] + (act?' \u2193':'') + '</th>';
      si.forEach(function(s) {{
        var v = values[r][s];
        h += '<td style="background:'+heatColor(v)+'">' + labels[r][s] + '</td>';
      }});
      h += '</tr>';
    }});
    h += '</tbody>';
    document.getElementById('viz3-crosstable').innerHTML = h;
  }}

  window.Viz3Sort = {{
    col: function(i) {{
      state = (state.type==='col'&&state.idx===i) ? {{type:null,idx:-1}} : {{type:'col',idx:i}};
      render();
    }},
    row: function(i) {{
      state = (state.type==='row'&&state.idx===i) ? {{type:null,idx:-1}} : {{type:'row',idx:i}};
      render();
    }}
  }};
  render();
}})();
</script>"""


def build():
    # --- Daten laden ---
    pivot = _load_pivot()

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
        visible=False,
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
        visible=True,
    )

    col_width  = 36
    row_height = 26
    fig_width  = max(900, len(scenarios) * col_width + 250)
    fig_height = max(500, len(heroes)    * row_height + 150)

    fig = go.Figure(data=[heatmap, sunburst])

    fig.update_layout(
        title=dict(text='Helden \u2192 Szenarien \u2192 Helden', font=dict(size=16)),
        autosize=True,
        height=850,
        dragmode=False,
        margin=dict(l=10, r=10, t=60, b=10),
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'hero_villain_matrix.html'
    fig.write_html(output, include_plotlyjs='cdn', full_html=True)
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
