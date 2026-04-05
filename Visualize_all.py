import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Visualize
import Visualize2
import Visualize3
import Visualize4

TAB_LABELS = [
    ("Dashboard",            "dashboard"),
    ("Helden \u00d7 Aspekte",   "hero_aspect"),
    ("Helden \u00d7 Schurken",  "hero_villain"),
    ("Szenarien \u00d7 Modulars", "scenario_modulars"),
]

print("Baue Dashboard ...")
fig1 = Visualize.build()
print("Baue Helden \u00d7 Aspekte ...")
fig2 = Visualize2.build()
print("Baue Helden \u00d7 Schurken ...")
fig3 = Visualize3.build()
print("Baue Szenarien \u00d7 Modulars ...")
fig4 = Visualize4.build()
print("Alle Visualisierungen gebaut.")

figs = [fig1, fig2, fig3, fig4]

# Render each figure as an HTML fragment
divs = []
for i, fig in enumerate(figs):
    include_js = 'cdn' if i == 0 else False
    divs.append(fig.to_html(
        full_html=False,
        include_plotlyjs=include_js,
        config={'responsive': True},
    ))

tab_buttons = "\n    ".join(
    f'<button onclick="showTab({i})">{label}</button>'
    for i, (label, _) in enumerate(TAB_LABELS)
)

tab_panels = "\n  ".join(
    f'<div class="tab-content" id="tab-{slug}">{div}</div>'
    for (_, slug), div in zip(TAB_LABELS, divs)
)

html = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Marvel Champions \u2014 Statistiken</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; background: #f5f5f5; }

    .tab-bar {
      display: flex;
      align-items: center;
      background: #16213e;
      border-bottom: 3px solid #e62429;
      padding: 0 12px;
      position: sticky;
      top: 0;
      z-index: 100;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      flex-shrink: 0;
    }
    .tab-bar .title {
      color: #e62429;
      font-size: 15px;
      font-weight: bold;
      padding: 13px 20px 13px 4px;
      margin-right: 12px;
      border-right: 1px solid #334;
      white-space: nowrap;
    }
    .tab-bar button {
      background: transparent;
      border: none;
      color: #aaaaaa;
      cursor: pointer;
      font-size: 13px;
      font-weight: bold;
      padding: 14px 18px;
      border-bottom: 3px solid transparent;
      margin-bottom: -3px;
      transition: color 0.15s;
      white-space: nowrap;
    }
    .tab-bar button:hover { color: #ffffff; }
    .tab-bar button.active {
      color: #ffffff;
      border-bottom: 3px solid #e62429;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; overflow-x: auto; }

    @media (max-width: 600px) {
      .tab-bar .title { font-size: 12px; padding: 12px 10px 12px 4px; }
      .tab-bar button { padding: 12px 10px; font-size: 11px; }
    }
  </style>
</head>
<body>
  <div class="tab-bar">
    <span class="title">Marvel Champions</span>
    """ + tab_buttons + """
  </div>
  """ + tab_panels + """
  <script>
    function showTab(n) {
      document.querySelectorAll('.tab-bar button').forEach(function(b, i) {
        b.classList.toggle('active', i === n);
      });
      document.querySelectorAll('.tab-content').forEach(function(p, i) {
        p.classList.toggle('active', i === n);
      });
      // Plotly needs a resize call after a hidden div becomes visible
      var panel = document.querySelectorAll('.tab-content')[n];
      panel.querySelectorAll('.plotly-graph-div').forEach(function(div) {
        if (window.Plotly) { Plotly.Plots.resize(div); }
      });
    }
    showTab(0);
  </script>
</body>
</html>"""

output = os.path.join('docs', 'index.html')
os.makedirs('docs', exist_ok=True)
with open(output, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Gespeichert als: {output}')
if not os.environ.get('CI'):
    webbrowser.open(f'file:///{os.path.abspath(output)}')
