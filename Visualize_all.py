import os
import sys
import webbrowser
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Visualize
import Visualize2
import Visualize3
import Visualize4
import Visualize5
import Visualize6

BUILD_TIMESTAMP = datetime.now().strftime("%d.%m.%Y %H:%M")

TAB_LABELS = [
    ("Dashboard",              "dashboard"),
    ("Helden \u00d7 Aspekte",     "hero_aspect"),
    ("Helden \u00d7 Schurken",    "hero_villain"),
    ("Szenarien \u00d7 Modulars", "scenario_modulars"),
    ("Kampagnen",              "campaigns"),
    ("Alle Partien",           "all_plays"),
]

PLOTLY_CONFIG = {'responsive': True, 'scrollZoom': False}

print("Baue Dashboard (Desktop) ...")
fig1d = Visualize.build(mobile=False)
print("Baue Dashboard (Mobile) ...")
fig1m = Visualize.build(mobile=True)
print("Baue Helden \u00d7 Aspekte ...")
fig2 = Visualize2.build()
print("Baue Helden \u00d7 Schurken ...")
fig3 = Visualize3.build()
print("Baue Szenarien \u00d7 Modulars ...")
fig4 = Visualize4.build()
print("Baue Kampagnen ...")
fig5 = Visualize5.build()
print("Baue HTML-Tabellen ...")
table3_html = Visualize3.build_table_html()
table4_html = Visualize4.build_table_html()
table5_html = Visualize5.build_summary_html()
table6_html = Visualize6.build_table_html()
print("Alle Visualisierungen gebaut.")

# --- Plotly HTML-Fragmente rendern ---
div1d = fig1d.to_html(full_html=False, include_plotlyjs='cdn', config=PLOTLY_CONFIG)
div1m = fig1m.to_html(full_html=False, include_plotlyjs=False,  config=PLOTLY_CONFIG)
div2  = fig2.to_html (full_html=False, include_plotlyjs=False,  config=PLOTLY_CONFIG)
div3  = fig3.to_html (full_html=False, include_plotlyjs=False,  config=PLOTLY_CONFIG)
div4  = fig4.to_html (full_html=False, include_plotlyjs=False,  config=PLOTLY_CONFIG)
div5  = fig5.to_html (full_html=False, include_plotlyjs=False,  config={'responsive': False, 'scrollZoom': True})

# Viz4: Baumansicht-Höhe für mobile JS übergeben
import pandas as pd
_sc_count = len(pd.read_csv('marvel_champions_scenario_modular_combos.csv', sep=';')['scenario'].unique())
ic_height_js = max(950, _sc_count * 52)

nav_buttons = "\n    ".join(
    f'<button onclick="showTab({i})">{label}</button>'
    for i, (label, _) in enumerate(TAB_LABELS)
)
tab_labels_js = "[" + ", ".join(f'"{label}"' for label, _ in TAB_LABELS) + "]"

html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Marvel Champions \u2014 Statistiken</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; }}

    /* ── Sticky Kopfleiste ── */
    .header {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: #16213e;
    }}
    .tab-bar {{
      display: flex;
      align-items: center;
      border-bottom: 3px solid #e62429;
      padding: 0 12px;
    }}
    .tab-bar .title {{
      color: #e62429;
      font-size: 15px;
      font-weight: bold;
      padding: 13px 4px;
      white-space: nowrap;
      flex: 1;
    }}
    .active-label {{
      color: #cccccc;
      font-size: 13px;
      padding: 0 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .burger-btn {{
      background: transparent;
      border: none;
      color: #ffffff;
      font-size: 22px;
      cursor: pointer;
      padding: 10px 4px 10px 12px;
      line-height: 1;
      flex-shrink: 0;
    }}
    .burger-btn:hover {{ color: #e62429; }}

    /* ── Dropdown-Navigationsmenü ── */
    .nav-menu {{ display: none; border-top: 1px solid #334; }}
    .nav-menu.open {{ display: block; }}
    .nav-menu button {{
      display: block; width: 100%;
      background: transparent; border: none; border-bottom: 1px solid #223;
      color: #aaaaaa; cursor: pointer; font-size: 14px; font-weight: bold;
      padding: 14px 20px; text-align: left;
      transition: color 0.15s, background 0.15s;
    }}
    .nav-menu button:hover  {{ color: #ffffff; background: #1e2d52; }}
    .nav-menu button.active {{ color: #e62429; }}

    /* ── Tab-Inhalte ── */
    .tab-content {{ display: none; }}
    .tab-content.active {{ display: block; }}

    /* ── Mobile View-Switcher (Viz 3 + 4) ── */
    .mobile-switch {{
      display: none;
      background: #f0f0f0;
      border-bottom: 2px solid #ccc;
      padding: 8px 12px;
      gap: 8px;
    }}
    .mobile-switch button {{
      background: white; border: 1px solid #ccc; border-radius: 3px;
      color: #444; cursor: pointer; font-size: 12px; font-weight: bold;
      padding: 7px 14px;
      transition: background 0.15s, color 0.15s;
    }}
    .mobile-switch button.active {{ background: #16213e; color: white; border-color: #16213e; }}

    /* ── Desktop-Plotly vs. Mobile-Plotly ── */
    .mobile-vis {{ display: none; }}

    /* ── Sticky HTML-Tabellen ── */
    .sticky-table-wrap {{
      overflow: auto;
      max-height: calc(100vh - 80px);
    }}
    .sticky-table {{
      border-collapse: collapse;
      min-width: max-content;
      font-size: 12px;
    }}
    .sticky-table th, .sticky-table td {{
      padding: 5px 10px;
      border: 1px solid #e0e0e0;
      white-space: nowrap;
    }}
    .sticky-table th {{
      background: #16213e;
      color: white;
      font-weight: bold;
      z-index: 3;
    }}
    .tbl-corner {{
      position: sticky; top: 0; left: 0;
      z-index: 5 !important;
      background: #0f1628 !important;
    }}
    .tbl-col  {{ position: sticky; top: 0;  z-index: 3; }}
    .tbl-row  {{ position: sticky; left: 0; z-index: 2; text-align: left; }}
    .sticky-table td {{ text-align: center; }}
    .sticky-table tbody tr:nth-child(even) td {{ background-color: inherit; }}

    /* ── Sortierbare Kreuztabellen ── */
    .tbl-col, .tbl-row {{ cursor: pointer; user-select: none; }}
    .tbl-col:hover {{ background: #1e3060 !important; }}
    .tbl-row:hover {{ background: #1e3060 !important; }}
    .tbl-sort-active {{ background: #9b1d20 !important; }}
    .tbl-sort-active:hover {{ background: #b52428 !important; }}

    /* ── Build-Timestamp ── */
    .build-info {{
      color: #666;
      font-size: 10px;
      font-weight: normal;
      white-space: nowrap;
    }}

    /* ── GitHub Update-Button ── */
    .update-btn {{
      background: transparent; border: 1px solid #555; border-radius: 4px;
      color: #cccccc; cursor: pointer; font-size: 16px; line-height: 1;
      padding: 5px 9px; margin-left: 8px; flex-shrink: 0;
      transition: color 0.15s, border-color 0.15s;
    }}
    .update-btn:hover:not(:disabled) {{ color: #e62429; border-color: #e62429; }}
    .update-btn:disabled {{ opacity: 0.5; cursor: default; }}

    /* ── Token-Modal ── */
    .gh-modal {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.65); z-index: 9000;
      align-items: center; justify-content: center;
    }}
    .gh-modal.open {{ display: flex; }}
    .gh-modal-box {{
      background: #fff; border-radius: 8px; padding: 24px 28px;
      max-width: 420px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }}
    .gh-modal-box h3 {{ margin-bottom: 10px; color: #16213e; }}
    .gh-modal-box p  {{ font-size: 13px; color: #444; margin-bottom: 14px; line-height: 1.5; }}
    .gh-modal-box input {{
      width: 100%; padding: 9px 10px; border: 1px solid #ccc;
      border-radius: 4px; font-size: 13px; margin-bottom: 16px;
    }}
    .gh-modal-actions {{ display: flex; gap: 10px; justify-content: flex-end; }}
    .gh-modal-actions button {{
      padding: 8px 18px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;
    }}
    .gh-btn-cancel {{ background: #eee; border: 1px solid #ccc; color: #444; }}
    .gh-btn-save   {{ background: #16213e; border: 1px solid #16213e; color: #fff; }}
    .gh-btn-save:hover {{ background: #e62429; border-color: #e62429; }}

    /* ── Viz3+Viz4+Viz5-Switch immer sichtbar (ersetzt Plotly-updatemenus) ── */
    #viz3-switch, #viz4-switch, #viz5-switch {{ display: flex; }}

    /* ── Standard: HTML-Tabelle/Zusammenfassung gezeigt, Plotly-Chart versteckt ── */
    .viz-plotly {{ display: none; }}
    .viz-table  {{ display: block; }}

    /* ── Kampagnen-Zeitstrahl: horizontales Scrollen ── */
    #viz5-plotly {{ overflow-x: auto; }}

    /* ── Mobile: Responsive-Anpassungen ── */
    @media (max-width: 768px) {{
      .desktop-vis  {{ display: none !important; }}
      .mobile-vis   {{ display: block; }}
      .mobile-switch {{ display: flex; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="tab-bar">
      <span class="title">Marvel Champions<br><span class="build-info">Stand: {BUILD_TIMESTAMP}</span></span>
      <span class="active-label" id="active-label"></span>
      <button class="update-btn" id="update-btn" onclick="ghUpdate()" title="Daten &amp; Visualisierung aktualisieren">&#x27F3;</button>
      <button class="burger-btn" id="burger-btn" onclick="toggleMenu()" aria-label="Navigation">&#9776;</button>
    </div>
    <nav class="nav-menu" id="nav-menu">
    {nav_buttons}
    </nav>
  </div>

  <!-- Tab 0: Dashboard -->
  <div class="tab-content" id="tab-dashboard">
    <div class="desktop-vis">{div1d}</div>
    <div class="mobile-vis">{div1m}</div>
  </div>

  <!-- Tab 1: Helden × Aspekte -->
  <div class="tab-content" id="tab-hero_aspect">
    {div2}
  </div>

  <!-- Tab 2: Helden × Schurken (Plotly + mobile HTML-Tabelle) -->
  <div class="tab-content" id="tab-hero_villain">
    <div class="mobile-switch" id="viz3-switch">
      <button data-view="table"    onclick="mobileSwitchView('viz3','table',this)">Kreuztabelle</button>
      <button data-view="sunburst" onclick="mobileSwitchView('viz3','sunburst',this)">Sunburst</button>
    </div>
    <div class="viz-plotly" id="viz3-plotly">{div3}</div>
    <div class="viz-table"  id="viz3-table">{table3_html}</div>
  </div>

  <!-- Tab 3: Szenarien × Modulars (Plotly + mobile HTML-Tabelle) -->
  <div class="tab-content" id="tab-scenario_modulars">
    <div class="mobile-switch" id="viz4-switch">
      <button data-view="table"       onclick="mobileSwitchView('viz4','table',this)">Kreuztabelle</button>
      <button data-view="sunburst"    onclick="mobileSwitchView('viz4','sunburst',this)">Sunburst</button>
      <button data-view="baumansicht" onclick="mobileSwitchView('viz4','baumansicht',this)">Baumansicht</button>
    </div>
    <div class="viz-plotly" id="viz4-plotly">{div4}</div>
    <div class="viz-table"  id="viz4-table">{table4_html}</div>
  </div>

  <!-- Tab 4: Kampagnen (Plotly-Zeitstrahl + mobile HTML-Zusammenfassung) -->
  <div class="tab-content" id="tab-campaigns">
    <div class="mobile-switch" id="viz5-switch">
      <button data-view="table"    onclick="mobileSwitchView('viz5','table',this)">Zusammenfassung</button>
      <button data-view="timeline" onclick="mobileSwitchView('viz5','timeline',this)">Zeitstrahl</button>
    </div>
    <div class="viz-plotly" id="viz5-plotly">{div5}</div>
    <div class="viz-table"  id="viz5-table">{table5_html}</div>
  </div>

  <!-- Tab 5: Alle Partien -->
  <div class="tab-content" id="tab-all_plays">
    {table6_html}
  </div>

  <!-- GitHub Token Modal -->
  <div class="gh-modal" id="gh-modal">
    <div class="gh-modal-box">
      <h3>GitHub Token einrichten</h3>
      <p>Damit der Update-Button den GitHub Actions Workflow starten kann, wird ein
         <strong>Personal Access Token</strong> mit dem Scope <code>workflow</code>
         ben&ouml;tigt.<br>Das Token wird nur lokal in deinem Browser gespeichert.</p>
      <input type="password" id="gh-token-input" placeholder="ghp_..." autocomplete="off">
      <div class="gh-modal-actions">
        <button class="gh-btn-cancel" onclick="ghCancelModal()">Abbrechen</button>
        <button class="gh-btn-save"   onclick="ghSaveToken()">Speichern &amp; Starten</button>
      </div>
    </div>
  </div>

  <script>
    var TAB_LABELS    = {tab_labels_js};
    var VIZ4_IC_HEIGHT = {ic_height_js};

    // ── Deep-Link-Hashes ──
    var TAB_HASHES = ['Dashboard', 'Helden-Aspekte', 'Helden-Schurken', 'Szenarien-Modulars', 'Kampagnen', 'Alle-Partien'];
    var VIZ_TAB    = {{'viz3': 2, 'viz4': 3, 'viz5': 4}};
    var VIEW_HASHES = {{
        'viz3': {{'table': 'Kreuztabelle', 'sunburst': 'Sunburst'}},
        'viz4': {{'table': 'Kreuztabelle', 'sunburst': 'Sunburst', 'baumansicht': 'Baumansicht'}},
        'viz5': {{'table': 'Zusammenfassung', 'timeline': 'Zeitstrahl'}}
    }};
    var VIEW_FROM_HASH = {{
        'viz3': {{'Kreuztabelle': 'table', 'Sunburst': 'sunburst'}},
        'viz4': {{'Kreuztabelle': 'table', 'Sunburst': 'sunburst', 'Baumansicht': 'baumansicht'}},
        'viz5': {{'Zusammenfassung': 'table', 'Zeitstrahl': 'timeline'}}
    }};

    function setHash(hash) {{
      try {{ history.replaceState(null, '', '#' + hash); }} catch(e) {{}}
    }}

    function getTabHash(n) {{
      var base = TAB_HASHES[n];
      for (var vid in VIZ_TAB) {{
        if (VIZ_TAB[vid] === n) {{
          var sw = document.getElementById(vid + '-switch');
          if (sw) {{
            var ab = sw.querySelector('button.active');
            if (ab) {{
              var vh = VIEW_HASHES[vid] && VIEW_HASHES[vid][ab.getAttribute('data-view')];
              if (vh) return base + '-' + vh;
            }}
          }}
        }}
      }}
      return base;
    }}

    function navigateToHash(hash) {{
      for (var i = 0; i < TAB_HASHES.length; i++) {{
        var tabHash = TAB_HASHES[i];
        if (hash === tabHash || hash.indexOf(tabHash + '-') === 0) {{
          showTab(i);
          var viewPart = hash.slice(tabHash.length + 1);
          if (viewPart) {{
            for (var vid in VIZ_TAB) {{
              if (VIZ_TAB[vid] === i) {{
                var view = VIEW_FROM_HASH[vid] && VIEW_FROM_HASH[vid][viewPart];
                if (view) {{
                  var sw2 = document.getElementById(vid + '-switch');
                  if (sw2) {{
                    var btn = sw2.querySelector('[data-view="' + view + '"]');
                    if (btn) mobileSwitchView(vid, view, btn);
                  }}
                }}
              }}
            }}
          }}
          return;
        }}
      }}
      showTab(0);
    }}

    function toggleMenu() {{
      document.getElementById('nav-menu').classList.toggle('open');
    }}

    function showTab(n) {{
      document.querySelectorAll('.nav-menu button').forEach(function(b, i) {{
        b.classList.toggle('active', i === n);
      }});
      document.querySelectorAll('.tab-content').forEach(function(p, i) {{
        p.classList.toggle('active', i === n);
      }});
      document.getElementById('active-label').textContent = TAB_LABELS[n];
      document.getElementById('nav-menu').classList.remove('open');
      setHash(getTabHash(n));
      // Plotly resize nur für sichtbare Divs
      var panel = document.querySelectorAll('.tab-content')[n];
      panel.querySelectorAll('.plotly-graph-div').forEach(function(div) {{
        if (window.Plotly && div.offsetParent !== null) {{
          Plotly.Plots.resize(div);
        }}
      }});
    }}

    // Menü bei Klick außerhalb schließen
    document.addEventListener('click', function(e) {{
      var menu = document.getElementById('nav-menu');
      var btn  = document.getElementById('burger-btn');
      if (menu.classList.contains('open') && !menu.contains(e.target) && e.target !== btn) {{
        menu.classList.remove('open');
      }}
    }});

    // Mobile View-Switcher für Viz3 + Viz4
    function mobileSwitchView(vizId, view, btn) {{
      var plotEl  = document.getElementById(vizId + '-plotly');
      var tableEl = document.getElementById(vizId + '-table');
      var switchEl = document.getElementById(vizId + '-switch');
      switchEl.querySelectorAll('button').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');

      if (view === 'table') {{
        plotEl.style.display  = 'none';
        tableEl.style.display = 'block';
      }} else {{
        plotEl.style.display  = 'block';
        tableEl.style.display = 'none';
        var plotDiv = plotEl.querySelector('.plotly-graph-div');
        if (plotDiv && window.Plotly) {{
          var restyle = null, relayout = null;
          if (vizId === 'viz3') {{
            // traces: [0]=heatmap, [1]=sunburst
            restyle  = {{visible: [false, true]}};
            relayout = {{'title.text': 'Helden \u2192 Szenarien \u2192 Helden',
                         height: 850, margin: {{l:10,r:10,t:100,b:10}}}};
          }} else if (vizId === 'viz4' && view === 'sunburst') {{
            // viz4 traces: [0]=sunburst, [1]=heatmap, [2]=icicle
            restyle  = {{visible: [true, false, false]}};
            relayout = {{'title.text': 'Szenarien \u00d7 Modularkombinationen',
                         height: 850, margin: {{l:10,r:10,t:60,b:10}}}};
          }} else if (vizId === 'viz4') {{
            restyle  = {{visible: [false, false, true]}};
            relayout = {{'title.text': 'Szenarien \u2192 Modulars \u2192 Helden',
                         height: VIZ4_IC_HEIGHT, margin: {{l:10,r:10,t:60,b:10}}}};
          }}
          // viz5: Timeline hat nur eine Ansicht, kein restyle nötig
          if (restyle) Plotly.update(plotDiv, restyle, relayout);
          Plotly.Plots.resize(plotDiv);
        }}
      }}
      // Hash aktualisieren
      if (VIZ_TAB[vizId] !== undefined) {{
        var vh = VIEW_HASHES[vizId] && VIEW_HASHES[vizId][view];
        setHash(TAB_HASHES[VIZ_TAB[vizId]] + (vh ? '-' + vh : ''));
      }}
    }}

    // ── GitHub Actions Trigger ──
    var GH_API = 'https://api.github.com/repos/TomBuZi/marvel_champions_bgg_export/actions/workflows/update.yml/dispatches';

    function ghUpdate() {{
      var token = localStorage.getItem('gh_token');
      if (token) {{
        triggerWorkflow(token);
      }} else {{
        document.getElementById('gh-modal').classList.add('open');
        document.getElementById('gh-token-input').focus();
      }}
    }}

    function ghSaveToken() {{
      var token = document.getElementById('gh-token-input').value.trim();
      if (!token) return;
      localStorage.setItem('gh_token', token);
      document.getElementById('gh-modal').classList.remove('open');
      triggerWorkflow(token);
    }}

    function ghCancelModal() {{
      document.getElementById('gh-modal').classList.remove('open');
    }}

    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter' && document.getElementById('gh-modal').classList.contains('open')) {{
        ghSaveToken();
      }}
    }});

    function triggerWorkflow(token) {{
      var btn = document.getElementById('update-btn');
      btn.disabled = true;
      btn.textContent = '\u23f3';
      fetch(GH_API, {{
        method: 'POST',
        headers: {{
          'Authorization': 'Bearer ' + token,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json'
        }},
        body: JSON.stringify({{ ref: 'main' }})
      }})
      .then(function(r) {{
        if (r.status === 204) {{
          btn.textContent = '\u2713';
          btn.title = 'Gestartet! GitHub Actions l\u00e4uft...';
          setTimeout(function() {{
            btn.textContent = '\u27f3';
            btn.title = 'Daten & Visualisierung aktualisieren';
            btn.disabled = false;
          }}, 4000);
        }} else if (r.status === 401) {{
          localStorage.removeItem('gh_token');
          btn.textContent = '\u27f3';
          btn.disabled = false;
          alert('Token ung\u00fcltig oder abgelaufen. Bitte erneut eingeben.');
          document.getElementById('gh-modal').classList.add('open');
        }} else {{
          r.json().then(function(d) {{
            btn.textContent = '\u27f3';
            btn.disabled = false;
            alert('Fehler ' + r.status + ': ' + (d.message || 'Unbekannter Fehler'));
          }});
        }}
      }})
      .catch(function(err) {{
        btn.textContent = '\u27f3';
        btn.disabled = false;
        alert('Netzwerkfehler: ' + err.message);
      }});
    }}

    // Standard-Ansicht: Tabelle/Zusammenfassung für alle Switcher aktiv setzen
    ['viz3', 'viz4', 'viz5'].forEach(function(vizId) {{
      var sw = document.getElementById(vizId + '-switch');
      if (!sw) return;
      sw.querySelectorAll('button').forEach(function(b) {{
        b.classList.toggle('active', b.getAttribute('data-view') === 'table');
      }});
    }});

    // Hash-basierte Navigation beim Laden
    var _initHash = window.location.hash.slice(1);
    if (_initHash) {{
      navigateToHash(_initHash);
    }} else {{
      showTab(0);
    }}
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
