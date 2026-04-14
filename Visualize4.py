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
    """Sortierbare HTML-Tabelle mit sticky Row/Column-Headern."""
    pivot     = _load_heatmap_pivot()
    scenarios = list(pivot.index)
    modulars  = list(pivot.columns)
    values    = [[int(v) for v in row] for row in pivot.values.tolist()]
    max_v     = max(max(row) for row in values) if values else 1

    scenarios_js = json.dumps(scenarios, ensure_ascii=False)
    modulars_js  = json.dumps(modulars,  ensure_ascii=False)
    values_js    = json.dumps(values)

    return f"""<div class="sticky-table-wrap">
  <table class="sticky-table" id="viz4-crosstable"></table>
</div>
<script>
(function() {{
  var scenarios = {scenarios_js};
  var modulars  = {modulars_js};
  var values    = {values_js};
  var maxV      = {int(max_v)};
  var state     = {{type: null, idx: -1}};

  function heatColor(v) {{
    if (v <= 0) return '#ffffff';
    var t = Math.min(v / maxV, 1.0);
    return 'rgb(255,' + Math.round(255*(1-t*0.8)) + ',' + Math.round(255*(1-t)) + ')';
  }}

  function render() {{
    var si = scenarios.map(function(_,i){{return i;}});
    var mi = modulars.map(function(_,i){{return i;}});
    if (state.type==='col') si.sort(function(a,b){{return values[b][state.idx]-values[a][state.idx];}});
    if (state.type==='row') mi.sort(function(a,b){{return values[state.idx][b]-values[state.idx][a];}});

    var h = '<thead><tr><th class="tbl-corner">Szenario / Modular</th>';
    mi.forEach(function(m) {{
      var act = state.type==='col' && state.idx===m;
      h += '<th class="tbl-col'+(act?' tbl-sort-active':'')+'" onclick="Viz4Sort.col('+m+')">'
           + modulars[m] + (act?' \u2193':'') + '</th>';
    }});
    h += '</tr></thead><tbody>';
    si.forEach(function(r) {{
      var act = state.type==='row' && state.idx===r;
      h += '<tr><th class="tbl-row'+(act?' tbl-sort-active':'')+'" onclick="Viz4Sort.row('+r+')">'
           + scenarios[r] + (act?' \u2193':'') + '</th>';
      mi.forEach(function(m) {{
        var v = values[r][m];
        h += '<td style="background:'+heatColor(v)+'">'+(v>0?v:'')+'</td>';
      }});
      h += '</tr>';
    }});
    h += '</tbody>';
    document.getElementById('viz4-crosstable').innerHTML = h;
  }}

  window.Viz4Sort = {{
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
    df = pd.read_csv('marvel_champions_scenario_modular_combos.csv', sep=';')

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

    row_height = 26
    hm_height  = max(500, len(pivot.index) * row_height + 180)

    heatmap = go.Heatmap(
        z=z_raw,
        x=list(pivot.columns),
        y=list(pivot.index),
        text=text,
        customdata=text,
        texttemplate='%{text}',
        textfont=dict(size=11, color='black'),
        colorscale='YlOrRd',
        showscale=True,
        colorbar=dict(title='Partien', thickness=15),
        hovertemplate='<b>%{y}</b> \u00d7 <b>%{x}</b>: %{customdata} Partien<extra></extra>',
    )

    fig = go.Figure(data=[heatmap])

    fig.update_layout(
        title=dict(text='Szenarien \u00d7 Modulars \u2014 Kreuztabelle', font=dict(size=16)),
        dragmode=False,
        height=hm_height,
        margin=dict(l=10, r=10, t=60, b=10),
    )

    return fig


if __name__ == '__main__':
    fig = build()
    output = 'scenario_modular_sunburst.html'
    fig.write_html(output, include_plotlyjs='cdn')
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
