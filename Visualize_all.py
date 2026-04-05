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
        config={'responsive': True, 'scrollZoom': False},
    ))

nav_buttons = "\n    ".join(
    f'<button onclick="showTab({i})">{label}</button>'
    for i, (label, _) in enumerate(TAB_LABELS)
)

tab_panels = "\n  ".join(
    f'<div class="tab-content" id="tab-{slug}">{div}</div>'
    for (_, slug), div in zip(TAB_LABELS, divs)
)

tab_labels_js = "[" + ", ".join(f'"{label}"' for label, _ in TAB_LABELS) + "]"

html = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Marvel Champions \u2014 Statistiken</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; background: #f5f5f5; }

    /* ── Sticky wrapper hält Tab-Bar + Nav-Menü zusammen ── */
    .header {
      position: sticky;
      top: 0;
      z-index: 100;
      background: #16213e;
    }

    .tab-bar {
      display: flex;
      align-items: center;
      border-bottom: 3px solid #e62429;
      padding: 0 12px;
    }
    .tab-bar .title {
      color: #e62429;
      font-size: 15px;
      font-weight: bold;
      padding: 13px 4px;
      white-space: nowrap;
      flex: 1;
    }
    .active-label {
      color: #cccccc;
      font-size: 13px;
      padding: 0 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .burger-btn {
      background: transparent;
      border: none;
      color: #ffffff;
      font-size: 22px;
      cursor: pointer;
      padding: 10px 4px 10px 12px;
      line-height: 1;
      flex-shrink: 0;
    }
    .burger-btn:hover { color: #e62429; }

    /* ── Dropdown-Navigationsmenü ── */
    .nav-menu {
      display: none;
      border-top: 1px solid #334;
    }
    .nav-menu.open { display: block; }
    .nav-menu button {
      display: block;
      width: 100%;
      background: transparent;
      border: none;
      border-bottom: 1px solid #223;
      color: #aaaaaa;
      cursor: pointer;
      font-size: 14px;
      font-weight: bold;
      padding: 14px 20px;
      text-align: left;
      transition: color 0.15s, background 0.15s;
    }
    .nav-menu button:hover  { color: #ffffff; background: #1e2d52; }
    .nav-menu button.active { color: #e62429; }

    .tab-content { display: none; }
    .tab-content.active { display: block; overflow-x: auto; }
  </style>
</head>
<body>
  <div class="header">
    <div class="tab-bar">
      <span class="title">Marvel Champions</span>
      <span class="active-label" id="active-label"></span>
      <button class="burger-btn" id="burger-btn" onclick="toggleMenu()" aria-label="Navigation">&#9776;</button>
    </div>
    <nav class="nav-menu" id="nav-menu">
    """ + nav_buttons + """
    </nav>
  </div>
  """ + tab_panels + """
  <script>
    var TAB_LABELS = """ + tab_labels_js + """;

    function toggleMenu() {
      document.getElementById('nav-menu').classList.toggle('open');
    }

    function showTab(n) {
      document.querySelectorAll('.nav-menu button').forEach(function(b, i) {
        b.classList.toggle('active', i === n);
      });
      document.querySelectorAll('.tab-content').forEach(function(p, i) {
        p.classList.toggle('active', i === n);
      });
      document.getElementById('active-label').textContent = TAB_LABELS[n];
      document.getElementById('nav-menu').classList.remove('open');
      // Plotly needs a resize call after a hidden div becomes visible
      var panel = document.querySelectorAll('.tab-content')[n];
      panel.querySelectorAll('.plotly-graph-div').forEach(function(div) {
        if (window.Plotly) { Plotly.Plots.resize(div); }
      });
    }

    // Menü schließen bei Klick außerhalb
    document.addEventListener('click', function(e) {
      var menu = document.getElementById('nav-menu');
      var btn  = document.getElementById('burger-btn');
      if (menu.classList.contains('open') && !menu.contains(e.target) && e.target !== btn) {
        menu.classList.remove('open');
      }
    });

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
