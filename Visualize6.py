import os
import json
import webbrowser
import pandas as pd

def build_table_html():
    df = pd.read_csv('marvel_champions_plays.csv', sep=';')

    cols = ['id', 'date', 'hero', 'scenario', 'result', 'incomplete', 'nowinstats']
    df = df[cols].fillna('')

    # Standard-Sortierung: Datum absteigend
    df = df.sort_values('date', ascending=False)

    rows = []
    for _, row in df.iterrows():
        rows.append({
            'date':       str(row['date']),
            'hero':       str(row['hero']),
            'scenario':   str(row['scenario']),
            'result':     str(row['result']),
            'nowinstats': 1 if str(row['nowinstats']).strip() == '1' else 0,
            'incomplete': 1 if str(row['incomplete']).strip() == '1' else 0,
        })

    total = len(rows)

    # JSON sicher für Einbettung in <script>-Tag machen
    data_json = json.dumps(rows, ensure_ascii=False).replace('</script>', r'<\/script>')

    return f"""
<div style="padding:8px">
  <div style="margin-bottom:8px;font-size:12px;color:#666">
    {total} Partien &mdash; sortierbar per Klick auf Spalten&uuml;berschrift
    &nbsp;&nbsp;<span style="opacity:0.5;font-style:italic">&#9679; = nicht in Statistik</span>
  </div>
  <div class="sticky-table-wrap" style="max-height:calc(100vh - 130px)">
    <table class="sticky-table" id="plays-table">
      <thead>
        <tr>
          <th class="tbl-col" onclick="sortPlays('date')">
            Datum <span id="sort-ind-date">&#9660;</span>
          </th>
          <th class="tbl-col" onclick="sortPlays('hero')">
            Held(en) <span id="sort-ind-hero"></span>
          </th>
          <th class="tbl-col" onclick="sortPlays('scenario')">
            Szenario <span id="sort-ind-scenario"></span>
          </th>
          <th class="tbl-col" onclick="sortPlays('result')">
            Ergebnis <span id="sort-ind-result"></span>
          </th>
        </tr>
      </thead>
      <tbody id="plays-tbody"></tbody>
    </table>
  </div>
</div>
<script>
(function() {{
  var PLAYS_DATA = {data_json};
  var _sortCol = 'date';
  var _sortAsc = false;

  window.sortPlays = function(col) {{
    if (_sortCol === col) {{
      _sortAsc = !_sortAsc;
    }} else {{
      _sortCol = col;
      _sortAsc = (col !== 'date');
    }}
    renderPlays();
  }};

  function renderPlays() {{
    var sorted = PLAYS_DATA.slice().sort(function(a, b) {{
      var va = (a[_sortCol] || '').toLowerCase();
      var vb = (b[_sortCol] || '').toLowerCase();
      if (va < vb) return _sortAsc ? -1 : 1;
      if (va > vb) return _sortAsc ? 1 : -1;
      return 0;
    }});

    ['date', 'hero', 'scenario', 'result'].forEach(function(col) {{
      var ind = document.getElementById('sort-ind-' + col);
      if (ind) ind.innerHTML = col === _sortCol ? (_sortAsc ? '&#9650;' : '&#9660;') : '';
    }});

    var tbody = document.getElementById('plays-tbody');
    if (!tbody) return;
    var html = '';
    sorted.forEach(function(row) {{
      var rowStyle = row.nowinstats ? 'opacity:0.5;font-style:italic' : '';

      var rl = (row.result || '').toLowerCase();
      var resultHtml = escHtml(row.result || '');
      if (rl.indexOf('won') === 0) {{
        resultHtml = '<span style="color:#2e7d32">' + resultHtml + '</span>';
      }} else if (rl.indexOf('lost') === 0) {{
        resultHtml = '<span style="color:#c62828">' + resultHtml + '</span>';
      }}
      if (row.incomplete) {{
        resultHtml = '<span style="color:#e65100" title="Unvollst\u00e4ndig">[unvollst.] </span>' + resultHtml;
      }}

      var scenFull = escHtml(row.scenario || '');
      var scenDisplay = scenFull.length > 55
        ? '<span title="' + scenFull + '">' + scenFull.substring(0, 52) + '&hellip;</span>'
        : scenFull;

      html += '<tr style="' + rowStyle + '">'
            + '<td style="white-space:nowrap">' + escHtml(row.date) + '</td>'
            + '<td>' + escHtml(row.hero) + '</td>'
            + '<td>' + scenDisplay + '</td>'
            + '<td>' + resultHtml + '</td>'
            + '</tr>';
    }});
    tbody.innerHTML = html;
  }}

  function escHtml(s) {{
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }}

  // Erst rendern wenn DOM bereit ist
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', renderPlays);
  }} else {{
    renderPlays();
  }}
}})();
</script>
"""


if __name__ == '__main__':
    table_html = build_table_html()
    output = 'plays_table.html'
    with open(output, 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alle Partien</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; }}
    .sticky-table-wrap {{ overflow: auto; max-height: calc(100vh - 80px); }}
    .sticky-table {{ border-collapse: collapse; min-width: max-content; font-size: 12px; }}
    .sticky-table th, .sticky-table td {{ padding: 5px 10px; border: 1px solid #e0e0e0; white-space: nowrap; }}
    .sticky-table th {{ background: #16213e; color: white; font-weight: bold; position: sticky; top: 0; z-index: 3; }}
    .tbl-col {{ cursor: pointer; user-select: none; }}
    .tbl-col:hover {{ background: #1e3060 !important; }}
  </style>
</head>
<body>
{table_html}
</body>
</html>""")
    print(f'Gespeichert als: {output}')
    webbrowser.open(f'file:///{os.path.abspath(output)}')
