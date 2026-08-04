import os
import json
import webbrowser
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

def load_config(filename):
    with open(os.path.join(CONFIG_DIR, filename), encoding="utf-8") as f:
        return json.load(f)

CAMPAIGNS = load_config("campaigns.json")

STATUS_COLORS = {
    "completed":   "#2E7D32",  # grün
    "in_progress": "#F9A825",  # amber
    "lost":        "#C62828",  # dunkelrot
    "abandoned":   "#757575",  # grau
}
STATUS_LABELS = {
    "completed":   "Abgeschlossen",
    "in_progress": "Laufend",
    "lost":        "Verloren",
    "abandoned":   "Abgebrochen",
}

RESULT_COLORS = {
    "win":        "#1B5E20",
    "loss":       "#B71C1C",
    "incomplete": "#455A64",
}
RESULT_SYMBOLS = {
    "win":        "circle",
    "loss":       "x",
    "incomplete": "square",
}
RESULT_LABELS = {
    "win":        "Sieg",
    "loss":       "Niederlage",
    "incomplete": "Unvollst\u00e4ndig",
}
RESULT_ICONS = {
    "win":        "\u2713",
    "loss":       "\u2717",
    "incomplete": "\u25CB",
}

CAMPAIGN_BG_COLORS = ["#FAFAFA", "#F0F0F0"]  # zebra background for campaign groups

# --- Zeitstrahl-Geometrie --- #
PLOT_DIV_ID   = "viz5-chart"   # feste Div-ID, damit das Zoom-JS den Plot findet
# Die Leinwand ist so breit wie das Fenster: dann bleibt die Heldenspalte links immer sichtbar
# und es gibt keinen horizontalen Scrollbalken. Die konkrete Breite setzt das JS beim
# Sichtbarwerden und bei jeder Fenstergrössenänderung; DEFAULT_CANVAS_W ist nur der Startwert
# (und die Breite der Standalone-Datei), MIN_CANVAS_W die Untergrenze für schmale Fenster —
# darunter scrollt der Wrapper wieder.
DEFAULT_CANVAS_W = 1600
MIN_CANVAS_W     = 900
INITIAL_MONTHS   = 12          # Startzeitraum; Doppelklick zeigt die ganze Historie
ROW_PITCH     = 22             # px pro Versuchszeile
MARGIN_LEFT   = 330
MARGIN_RIGHT  = 25
MARGIN_TOP    = 72             # Titel + einzeilige horizontale Legende
MARGIN_BOTTOM = 38             # Datums-Ticks (ohne Achsentitel)
X_PAD_DAYS    = 30             # Luft links/rechts, damit der erste/letzte Eintrag nicht am Rand klebt
# Engster Zoom. Bewusst so gross, dass Plotly als feinsten Tick noch ganze TAGE waehlt
# (Plotly zielt auf ~100 px pro Tick, 3045 px Plotbreite -> ~30 Ticks): Uhrzeiten sind in den
# BGG-Daten nicht erfasst, Stunden-Ticks waeren also erfunden.
MIN_ZOOM_DAYS = 30

# >0: spielfreie Lücken ab dieser Länge aus der Zeitachse entfernen. Die Achse ist dann
# nicht mehr proportional zur echten Zeit, dafür wird der Verlauf deutlich dichter
# (60 Tage: ~2150 -> ~790 Achsentage). 0 = aus.
GAP_COMPRESS_DAYS = 0

# Plotly-Config des Zeitstrahls — von Visualize_all.py und vom Standalone-HTML genutzt.
# scrollZoom bleibt aus: das normale Mausrad soll die Seite scrollen, gezoomt wird per
# Strg/Shift+Mausrad in zoom_js(). Wichtig: niemals "reset+autosize" für doubleClick —
# das schaltet die Achsen zurück auf autorange und das 5%-Scatter-Padding kehrt zurück.
# Alle Achsen-Buttons sind entfernt: jede Range-Aenderung soll durch zoom_js() laufen, das
# spannenerhaltend klemmt und MIN_ZOOM_DAYS respektiert. Plotlys eigene Zoom-Buttons wuerden
# beides umgehen (u.a. bis unter einen Tag zoomen).
TIMELINE_CONFIG = {
    "responsive": False,
    "scrollZoom": False,
    "doubleClick": False,        # Reset macht zoom_js selbst, siehe plotly_doubleclick dort
    "displayModeBar": "hover",
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d",
                               "zoom2d", "pan2d", "zoomIn2d", "zoomOut2d"],
    "toImageButtonOptions": {"filename": "kampagnen_zeitstrahl", "scale": 2},
}

# Interaktion des Zeitstrahls. Da die Leinwand genau so breit wie das Fenster ist, gibt es
# nur EINE Zoomachse: den Zeitraum. Ziehen verschiebt ihn, Strg/Shift+Mausrad spreizt bzw.
# staucht ihn um den Cursor herum, Doppelklick zeigt die ganze Historie.
_ZOOM_JS = """
(function () {
  var gd = document.getElementById('__DIV__');
  if (!gd || !window.Plotly) return;
  var MIN_SPAN = __MIN_DAYS__ * 864e5;
  var MIN_W    = __MIN_W__;
  var STEP     = 1.3;
  // Volle Spanne EINMALIG aus den harten Achsengrenzen, die Python gesetzt hat. Sie darf nicht
  // faul aus der aktuellen Range abgeleitet werden: wer vorher pannt oder ueber die Modebar
  // zoomt, wuerde sonst sein momentanes Fenster als "voll" einfrieren und danach nicht mehr
  // herauskommen.
  var FULL = (function () {
    var xa = gd._fullLayout.xaxis;
    var lo = xa.minallowed, hi = xa.maxallowed;
    if (lo == null || hi == null) {
      var r = xa.range;
      lo = r[0]; hi = r[1];
    }
    return [new Date(lo).getTime(), new Date(hi).getTime()];
  })();

  function fmt(ms) {
    // bewusst LOKALE Zeitkomponenten: Plotly liest die Achsenwerte als naive lokale
    // Zeitstempel, toISOString() wuerde die Range bei jedem Zoom um den UTC-Offset verschieben
    var d = new Date(ms), p = function (v, w) { return String(v).padStart(w || 2, '0'); };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' +
           p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + '.' +
           p(d.getMilliseconds(), 3);
  }
  function curRange() {
    var r = (gd.layout && gd.layout.xaxis && gd.layout.xaxis.range) ||
            (gd._fullLayout && gd._fullLayout.xaxis.range);
    return [new Date(r[0]).getTime(), new Date(r[1]).getTime()];
  }
  // Scroll-Container der Seite; im Standalone-HTML gibt es #viz5-scroll nicht
  function scroller()  { return document.getElementById('viz5-scroll') || gd.parentElement || gd; }
  function dragBox()   { var d = gd.querySelector('.nsewdrag'); return d && d.getBoundingClientRect(); }
  function curWidth()  { return (gd.layout && gd.layout.width) || gd._fullLayout.width; }
  function setRange(lo, span) {
    if (lo < FULL[0]) lo = FULL[0];
    if (lo + span > FULL[1]) lo = FULL[1] - span;
    return Plotly.relayout(gd, {'xaxis.range': [fmt(lo), fmt(lo + span)]});
  }

  // Die Ansicht bewegt sich auf ZWEI Wegen, und beide sind noetig:
  //   1. der Scroll-Container, solange die Leinwand breiter als das Fenster ist
  //   2. der Zeitraum, sobald er enger als die Vollspanne ist
  // Nur (2) reicht nicht: in der Standardansicht ist der Zeitraum voll, setRange() klemmt ihn
  // dann (korrekt) auf sich selbst und Ziehen bzw. Springen bliebe wirkungslos.
  function canScroll(sc) { return !!sc && sc.scrollWidth > sc.clientWidth + 1; }

  function moveByPixels(dx) {
    var sc = scroller();
    if (canScroll(sc)) {
      var before = sc.scrollLeft;
      sc.scrollLeft = before - dx;              // nach rechts ziehen = Inhalt nach rechts
      dx -= before - sc.scrollLeft;             // nur der ungenutzte Rest geht weiter
      if (Math.abs(dx) < 0.5) return;
    }
    var r = curRange(), box = dragBox();
    if (!box) return;
    var span = r[1] - r[0];
    setRange(r[0] - dx * (span / box.width), span);
  }

  // Zeitpunkt nach einer Range-Aenderung in die Fenstermitte scrollen
  function scrollInto(promise, centerMs) {
    return (promise || Promise.resolve()).then(function () {
      var sc = scroller(), xa = gd._fullLayout.xaxis;
      if (!canScroll(sc)) return;
      sc.scrollLeft = xa.d2p(new Date(centerMs)) + xa._offset - sc.clientWidth / 2;
    });
  }

  // Zoom um einen festen Ankerpunkt: der Zeitpunkt unter dem Cursor bleibt auf derselben
  // Pixelposition. Erst die Spanne klemmen, DANN das linke Ende aus Anker und Cursoranteil
  // ableiten — eine Neuzentrierung auf die Mitte wuerde den Anker verwerfen.
  function zoomAnchored(anchor, frac, factor) {
    var r = curRange();
    var span = Math.min(Math.max((r[1] - r[0]) * factor, MIN_SPAN), FULL[1] - FULL[0]);
    setRange(anchor - frac * span, span);
  }

  function zoomToSpan(t0, t1) {              // Klick auf Balken/Marker: Versuch heranzoomen
    var span = Math.min(Math.max(t1 - t0, MIN_SPAN), FULL[1] - FULL[0]);
    return setRange((t0 + t1) / 2 - span / 2, span);
  }

  function panTo(centerMs) {                 // hinspringen, Zoomstufe unveraendert lassen
    var r = curRange();
    var span = r[1] - r[0];
    return setRange(centerMs - span / 2, span);
  }

  // Leinwand auf die Containerbreite bringen. to_html setzt eine Inline-Breite auf dem
  // Graph-Div, die relayout NICHT mitzieht — ohne das Nachziehen bliebe der Wrapper breit und
  // wuerde weiter scrollen. Wird auch von Visualize_all beim Sichtbarwerden gerufen (beim
  // newPlot liegt der Div in einem display:none-Container und hat Breite 0).
  function fitWidth() {
    var sc = scroller();
    var avail = (sc && sc.clientWidth) || 0;
    var w = Math.max(MIN_W, Math.round(avail) - 2);
    if (Math.abs(w - curWidth()) < 2) return Promise.resolve();
    return Plotly.relayout(gd, {width: w}).then(function () { gd.style.width = w + 'px'; });
  }
  window.viz5Fit = fitWidth;
  fitWidth();

  var fitTimer = 0;
  window.addEventListener('resize', function () {
    clearTimeout(fitTimer);
    fitTimer = setTimeout(fitWidth, 150);
  });

  gd.addEventListener('wheel', function (e) {
    if (!e.ctrlKey && !e.shiftKey) return;   // ohne Modifier normal weiterscrollen
    e.preventDefault();                      // unterdrueckt Browser-Zoom (Strg) und
                                             // horizontales Scrollen (Shift)
    var box = dragBox();
    if (!box) return;
    // Shift+Mausrad meldet den Ausschlag je nach Browser in deltaX statt deltaY
    var delta = e.deltaY || e.deltaX;
    if (!delta) return;
    var frac = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    var r = curRange();
    zoomAnchored(r[0] + frac * (r[1] - r[0]), frac, delta > 0 ? STEP : 1 / STEP);
  }, {passive: false});

  function inPlot(e) {
    var box = dragBox();
    return !!box && e.clientX >= box.left && e.clientX <= box.right &&
                    e.clientY >= box.top  && e.clientY <= box.bottom;
  }

  // Eigenes Pannen. Plotlys Pan ist abgeschaltet, weil es zusammen mit minallowed/maxallowed
  // die beiden Achsenenden UNABHAENGIG klemmt: an der Grenze bleibt ein Ende stehen, das andere
  // laeuft weiter, das Ziehen zoomt also. In der Standardansicht ist die Range voll, dort stoesst
  // jedes Ziehen sofort an. setRange() klemmt dagegen spannenerhaltend.
  // downAt/dragged sind die gemeinsame Drag-Erkennung fuer ALLE Klick-Handler: mit
  // dragmode=False unterdrueckt Plotly den Klick nach einem Ziehen nicht mehr, ein Pan wuerde
  // sonst am Ende zusaetzlich einen Balken-Klick (= Zoom) ausloesen.
  var pan = null, downAt = null, dragged = false;

  function onDown(e) {
    if (e.button !== 0 || !gd.contains(e.target)) return;
    downAt = [e.clientX, e.clientY];
    dragged = false;
    if (!inPlot(e)) return;
    pan = {last: e.clientX, dx: 0, raf: 0};
    // KEIN preventDefault: das wuerde die aus pointerdown abgeleiteten Maus-Events
    // unterdruecken und damit Plotlys Klick-Erkennung (plotly_click) lahmlegen.
    // Gegen Text-Markieren beim Ziehen hilft user-select:none im Stylesheet unten.
  }
  function onMove(e) {
    if (downAt && Math.abs(e.clientX - downAt[0]) + Math.abs(e.clientY - downAt[1]) > 4) {
      dragged = true;
    }
    if (!pan) return;
    pan.dx += e.clientX - pan.last;           // zwischen zwei Frames aufsummieren
    pan.last = e.clientX;
    if (!pan.raf) {
      pan.raf = requestAnimationFrame(function () {
        if (!pan) return;
        pan.raf = 0;
        var d = pan.dx; pan.dx = 0;
        if (d) moveByPixels(d);
      });
    }
  }
  function onUp() {
    if (pan && pan.raf) cancelAnimationFrame(pan.raf);
    pan = null; downAt = null;
  }

  // Bewusst auf window in der CAPTURE-Phase: so laufen die Handler vor allem, was Plotly an
  // den Drag-Flaechen haengt, und koennen nicht durch stopPropagation() ausgehebelt werden.
  // Pointer-Events bevorzugt — ruft irgendwer preventDefault() auf pointerdown auf, liefert der
  // Browser die abgeleiteten Maus-Events gar nicht mehr aus.
  if (window.PointerEvent) {
    window.addEventListener('pointerdown',   onDown, true);
    window.addEventListener('pointermove',   onMove, true);
    window.addEventListener('pointerup',     onUp,   true);
    window.addEventListener('pointercancel', onUp,   true);
  } else {
    window.addEventListener('mousedown', onDown, true);
    window.addEventListener('mousemove', onMove, true);
    window.addEventListener('mouseup',   onUp,   true);
  }

  // Doppelklick setzt Zeitraum UND Leinwandbreite zurueck. Nicht ueber plotly_doubleclick:
  // das haengt am Drag-Layer, der mit dragmode=False nicht mehr aktiv ist. Nur innerhalb der
  // Plotflaeche, damit ein Doppelklick auf eine Beschriftung nicht alles zuruecksetzt.
  // Doppelklick zeigt die ganze Historie.
  // Plotly verschluckt das DOM-dblclick (ein eigener Listener auf gd feuert nie), liefert aber
  // plotly_doubleclick — auch bei config.doubleClick=false. Genau deshalb ist Plotlys Reset dort
  // abgeschaltet: sonst liefe sein relayout gegen unseres.
  gd.on('plotly_doubleclick', function () {
    setRange(FULL[0], FULL[1] - FULL[0]);
  });

  // Balken UND Szenario-Marker tragen [start, end] des Versuchs als customdata — die Marker
  // liegen ueber den Balken und gewinnen den Klick, deshalb darf hier nicht auf 'bar' geprueft
  // werden.
  gd.on('plotly_click', function (d) {
    if (dragged) return;                       // war ein Pan, kein Klick
    var p = d.points && d.points[0];
    if (!p || !p.customdata || p.customdata.length !== 2) return;
    centerOn(p.customdata[0], p.customdata[1]);
  });

  function centerOn(start, end) {            // Balken/Marker: heranzoomen und ins Fenster holen
    var t0 = new Date(start).getTime(), t1 = new Date(end).getTime();
    var pad = Math.max(2 * 864e5, (t1 - t0) * 0.4);
    scrollInto(zoomToSpan(t0 - pad, t1 + pad), (t0 + t1) / 2);
  }

  // y-Position -> [start, end] des Versuchs, direkt aus der customdata der Balken gelesen
  function rowSpans() {
    if (gd._rowSpans) return gd._rowSpans;
    var m = {};
    (gd.data || []).forEach(function (t) {
      if (t.type !== 'bar' || !t.customdata || !t.y) return;
      Array.prototype.forEach.call(t.y, function (yv, i) { m[yv] = t.customdata[i]; });
    });
    gd._rowSpans = m;
    return m;
  }

  // Klick auf die Beschriftung links springt zum Versuch, OHNE die Zoomstufe zu aendern
  // (die Balken selbst sind oft nur 1-2 px breit, deshalb dieser Trefferbereich).
  // Die Zeile kommt aus der Mausposition ueber die y-Achse, nicht aus dem Label-Text:
  // identische Beschriftungen kommen mehrfach vor.
  gd.addEventListener('click', function (e) {
    if (dragged) return;                                        // war ein Ziehen, kein Klick
    var box = dragBox();
    if (!box || e.clientX >= box.left) return;                  // nur die Label-Spalte
    if (e.clientY < box.top || e.clientY > box.bottom) return;  // nicht Legende/Modebar
    var row  = Math.round(gd._fullLayout.yaxis.p2d(e.clientY - box.top));
    var span = rowSpans()[row];
    if (!span) return;
    var mid = (new Date(span[0]).getTime() + new Date(span[1]).getTime()) / 2;
    scrollInto(panTo(mid), mid);              // Zeitraum verschieben UND ins Fenster scrollen
  });

  // Plotly legt neben der Pan-Flaeche (.nsewdrag) noch Ecken- und Kanten-Dragger an, die die
  // Achse EINSEITIG zoomen (.nwdrag etc. sind w-/e-resize-Handles). Bei fixierter y-Achse sind
  // das lauter x-Zoom-Griffe direkt am Plotrand — ein Ziehen dort verstellt die Zoomstufe und
  // laesst die beiden Bildhaelften unterschiedlich weit wandern. Wir wollen nur Pannen.
  var st = document.createElement('style');
  st.textContent =
    '#__DIV__ { -webkit-user-select: none; user-select: none; }' +
    '#__DIV__ .ytick text { cursor: pointer; }' +
    '#__DIV__ .nsewdrag { cursor: grab; }' +
    '#__DIV__ .nsewdrag:active { cursor: grabbing; }' +
    '#__DIV__ .nwdrag, #__DIV__ .nedrag, #__DIV__ .swdrag, #__DIV__ .sedrag,' +
    '#__DIV__ .wdrag,  #__DIV__ .edrag,  #__DIV__ .ewdrag,' +
    '#__DIV__ .ndrag,  #__DIV__ .sdrag,  #__DIV__ .nsdrag' +
    ' { pointer-events: none !important; }';
  document.head.appendChild(st);
})();
"""


def zoom_js(div_id=PLOT_DIV_ID):
    """JS-Snippet für die Zeitachsen-Interaktion, gebunden an eine konkrete Div-ID."""
    return (_ZOOM_JS
            .replace("__DIV__", div_id)
            .replace("__MIN_DAYS__", str(MIN_ZOOM_DAYS))
            .replace("__MIN_W__", str(MIN_CANVAS_W)))


def _parse_played(raw):
    """Wandelt das scenarios_played-Feld in eine Liste von Play-Dicts um."""
    if not isinstance(raw, str) or not raw:
        return []
    out = []
    for entry in raw.split(" | "):
        parts = entry.split("::", 2)
        if len(parts) == 3:
            out.append({"date": parts[0], "scenario": parts[1], "result": parts[2]})
    return out


def _short_heroes(heroes_str, limit=55):
    """K\u00fcrzt lange Heldenkombinationen f\u00fcr die y-Achsen-Beschriftung."""
    if len(heroes_str) <= limit:
        return heroes_str
    return heroes_str[: limit - 1] + "\u2026"


def _gap_rangebreaks(df, min_days):
    """Achsen-L\u00fccken f\u00fcr spielfreie Zeitr\u00e4ume ab min_days Tagen.

    Die L\u00fccken werden aus der *vereinigten* Menge aller Versuchszeitr\u00e4ume berechnet,
    deshalb kann kein Balken und kein Szenario-Marker in einen entfernten Bereich fallen.
    """
    if not min_days:
        return []
    merged = []
    for start, end in sorted(zip(df["start_dt"], df["end_dt"])):
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [
        dict(bounds=[(merged[i][1] + timedelta(days=1)).strftime("%Y-%m-%d"),
                     merged[i + 1][0].strftime("%Y-%m-%d")])
        for i in range(len(merged) - 1)
        if (merged[i + 1][0] - merged[i][1]).days > min_days
    ]


def build():
    df = pd.read_csv("marvel_champions_campaigns.csv", sep=";")
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Keine Kampagnen erkannt",
            template="plotly_white",
            width=DEFAULT_CANVAS_W,
            height=400,
        )
        return fig

    # Sortierung: Kampagnen in Konfig-Reihenfolge, dann Startdatum
    camp_order = {c: i for i, c in enumerate(CAMPAIGNS)}
    df["_camp_ord"] = df["campaign"].map(camp_order).fillna(999)
    df["start_dt"]  = pd.to_datetime(df["start_date"])
    df["end_dt"]    = pd.to_datetime(df["end_date"])
    df = df.sort_values(["_camp_ord", "start_dt"]).reset_index(drop=True)

    # Numerische y-Positionen, damit identische Labels (gleicher Kombi, mehrere Versuche)
    # nicht von Plotly zusammengelegt werden
    df["y_pos"] = range(len(df))
    tick_text = [
        f"{row['campaign']} \u2014 {_short_heroes(row['heroes'])} ({row.get('difficulty', 'Standard')})"
        for _, row in df.iterrows()
    ]

    # --- Zebra-Hintergrund pro Kampagne --- #
    shapes = []
    unique_campaigns = []
    for c in df["campaign"]:
        if c not in unique_campaigns:
            unique_campaigns.append(c)
    camp_color = {c: CAMPAIGN_BG_COLORS[i % 2] for i, c in enumerate(unique_campaigns)}
    for camp in unique_campaigns:
        rows = df[df["campaign"] == camp]
        y_min = rows["y_pos"].min() - 0.5
        y_max = rows["y_pos"].max() + 0.5
        shapes.append(dict(
            type="rect",
            xref="paper", x0=0, x1=1,
            yref="y",     y0=y_min, y1=y_max,
            fillcolor=camp_color[camp],
            line=dict(width=0),
            layer="below",
        ))

    fig = go.Figure()

    # --- Balken pro Status (Zeitspanne des Versuchs) --- #
    for status, status_label in STATUS_LABELS.items():
        rows = df[df["status"] == status]
        if rows.empty:
            continue

        durations_ms = []
        ys           = []
        bases        = []
        hovers       = []
        spans        = []          # [start, end] je Balken -> Klick-Zoom im JS

        for _, row in rows.iterrows():
            start = row["start_dt"]
            end   = row["end_dt"]
            # Mindestbreite 1 Tag, sonst w\u00e4ren Ein-Tages-Versuche unsichtbar
            if end == start:
                end = start + timedelta(days=1)

            plays = _parse_played(row["scenarios_played"])
            scen_lines = [
                f"{RESULT_ICONS[p['result']]} {p['date']}  {p['scenario']}"
                for p in plays
            ]
            date_range = (
                row["start_date"]
                if row["start_date"] == row["end_date"]
                else f"{row['start_date']} \u2192 {row['end_date']}"
            )
            hover = (
                f"<b>{row['campaign']}</b><br>"
                f"Helden: {row['heroes']}<br>"
                f"Schwierigkeit: {row.get('difficulty', 'Standard')}<br>"
                f"Status: {status_label}<br>"
                f"Zeitraum: {date_range}<br>"
                f"Partien: {row['play_count']}<br>"
                f"<br><b>Szenarien:</b><br>" + "<br>".join(scen_lines)
            )

            durations_ms.append((end - start).total_seconds() * 1000.0)
            ys.append(row["y_pos"])
            bases.append(start)
            hovers.append(hover)
            spans.append([start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")])

        fig.add_trace(go.Bar(
            x=durations_ms,
            y=ys,
            base=bases,
            orientation="h",
            marker=dict(
                color=STATUS_COLORS[status],
                opacity=0.55,
                line=dict(color=STATUS_COLORS[status], width=1),
            ),
            customdata=spans,
            hovertext=hovers,
            hoverinfo="text",
            name=status_label,
            showlegend=True,
            width=0.72,
        ))

    # --- Scatter-Marker: einzelne Szenarien innerhalb jedes Versuchs --- #
    scatter = {k: {"x": [], "y": [], "text": [], "span": []} for k in RESULT_COLORS}

    for _, row in df.iterrows():
        plays = _parse_played(row["scenarios_played"])
        # Zeitraum des Versuchs — die Marker liegen über den Balken und gewinnen den Klick,
        # also brauchen sie dieselbe customdata für den Klick-Zoom
        span = [row["start_date"], row["end_date"]]
        for p in plays:
            scatter[p["result"]]["x"].append(p["date"])
            scatter[p["result"]]["y"].append(row["y_pos"])
            scatter[p["result"]]["span"].append(span)
            scatter[p["result"]]["text"].append(
                f"<b>{p['scenario']}</b> ({row['campaign']})<br>"
                f"{p['date']}<br>"
                f"Helden: {row['heroes']}<br>"
                f"Schwierigkeit: {row.get('difficulty', 'Standard')}<br>"
                f"Ergebnis: {RESULT_LABELS[p['result']]}"
            )

    for result_key in ("win", "loss", "incomplete"):
        data = scatter[result_key]
        if not data["x"]:
            continue
        fig.add_trace(go.Scatter(
            x=data["x"],
            y=data["y"],
            mode="markers",
            marker=dict(
                symbol=RESULT_SYMBOLS[result_key],
                size=9,
                color=RESULT_COLORS[result_key],
                line=dict(color="white", width=1),
            ),
            customdata=data["span"],
            hovertext=data["text"],
            hoverinfo="text",
            name=RESULT_LABELS[result_key],
            showlegend=True,
        ))

    # --- Layout --- #
    # Beide Achsen bekommen eine explizite range. Die Scatter-Traces melden ihre Extremwerte
    # als "padded", wodurch Plotly bei autorange 5 % der Achsenl\u00e4nge an *beiden* Enden
    # zus\u00e4tzlich freih\u00e4lt \u2014 vertikal waren das ~85 px Leerraum \u00fcber der ersten und unter der
    # letzten Zeile, horizontal ~3,5 Monate je Seite.
    n      = len(df)
    height = MARGIN_TOP + MARGIN_BOTTOM + ROW_PITCH * n

    # Die Achse reicht bis zum Erstellungstag der Ansicht (nicht weiter in die Zukunft) und
    # bekommt an beiden Enden X_PAD_DAYS Luft, damit der erste/letzte Eintrag nicht am Rand klebt.
    today   = pd.Timestamp.today().normalize()
    last_dt = df["end_dt"].max()
    if last_dt > today:                 # defekte BGG-Daten sichtbar machen statt still abschneiden
        print(f"WARNUNG: Kampagnen-Daten reichen bis {last_dt.date()} "
              f"und damit über den Erstellungstag {today.date()} hinaus.")
    x_min = df["start_dt"].min() - timedelta(days=X_PAD_DAYS)
    x_max = max(today, last_dt)         + timedelta(days=X_PAD_DAYS)
    # Startansicht: die letzten INITIAL_MONTHS Monate. So bewirkt Ziehen sofort etwas —
    # bei voller Zeitachse gibt es nichts zu verschieben. Doppelklick zeigt alles.
    x_start = max(x_min, x_max - pd.DateOffset(months=INITIAL_MONTHS))

    fig.update_layout(
        # Titel und Legende links verankern: die Leinwand ist breiter als jedes Fenster,
        # rechtsb\u00fcndige Elemente w\u00e4ren erst nach ~1700 px Scrollen sichtbar
        title=dict(
            text="Marvel Champions \u2014 Gespielte Kampagnen (Zeitstrahl)",
            font=dict(size=16),
            xref="paper", x=0, xanchor="left",
            yref="container", y=1, yanchor="top", pad=dict(t=12),
        ),
        width=DEFAULT_CANVAS_W,
        height=height,
        barmode="overlay",
        xaxis=dict(
            type="date",
            range=[x_start, x_max],
            # Sicherheitsnetz gegen Achsenwerte ausserhalb der Daten. Reicht ALLEIN nicht:
            # Plotly klemmt beim Pannen beide Achsenenden unabhängig, an der Grenze bleibt
            # eines stehen und das andere läuft weiter — das Ziehen zoomt dann. Deshalb ist
            # Plotlys Pan abgeschaltet (dragmode=False) und zoom_js() pannt selbst.
            minallowed=x_min,
            maxallowed=x_max,
            rangebreaks=_gap_rangebreaks(df, GAP_COMPRESS_DAYS),
            showgrid=True,
            gridcolor="#e0e0e0",
            ticks="outside",
            ticklen=4,
            showspikes=True,
            spikemode="across",
            spikethickness=1,
            spikedash="dot",
            spikecolor="#9e9e9e",
            # fixedrange bleibt False -> Mausrad und Ziehen wirken nur auf die Zeitachse
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(df["y_pos"]),
            ticktext=tick_text,
            range=[n - 0.5, -0.5],   # absteigend == umgekehrt, aber ohne Autorange-Padding
            fixedrange=True,         # nie vertikal zoomen oder verschieben
            showgrid=False,
            ticks="",
            tickfont=dict(size=10),
        ),
        shapes=shapes,
        margin=dict(l=MARGIN_LEFT, r=MARGIN_RIGHT, t=MARGIN_TOP, b=MARGIN_BOTTOM),
        template="plotly_white",
        dragmode=False,              # Pannen macht zoom_js() selbst, siehe minallowed oben
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.005,
            xanchor="left",   x=0,
            font=dict(size=10),
        ),
    )

    return fig


def build_summary_html():
    """Kleine HTML-Zusammenfassung pro Kampagne f\u00fcr den mobilen Tab."""
    df = pd.read_csv("marvel_champions_campaigns.csv", sep=";")
    if df.empty:
        return "<p style='padding:20px'>Keine Kampagnen erkannt.</p>"

    camp_order = {c: i for i, c in enumerate(CAMPAIGNS)}
    df["_camp_ord"] = df["campaign"].map(camp_order).fillna(999)
    df = df.sort_values(["_camp_ord", "start_date"]).reset_index(drop=True)

    rows_html = []
    for camp in df["campaign"].drop_duplicates().tolist():
        sub = df[df["campaign"] == camp]
        total       = len(sub)
        completed   = int((sub["status"] == "completed").sum())
        in_progress = int((sub["status"] == "in_progress").sum())
        lost        = int((sub["status"] == "lost").sum())
        abandoned   = int((sub["status"] == "abandoned").sum())

        attempt_rows = []
        for _, row in sub.iterrows():
            color = STATUS_COLORS.get(row["status"], "#999")
            label = STATUS_LABELS.get(row["status"], row["status"])
            date_range = (
                row["start_date"]
                if row["start_date"] == row["end_date"]
                else f"{row['start_date']} \u2192 {row['end_date']}"
            )
            plays = _parse_played(row["scenarios_played"])
            played_inline = " ".join(
                f"<span title='{p['scenario']}&#10;{p['date']}&#10;{RESULT_LABELS[p['result']]}' "
                f"style='color:{RESULT_COLORS[p['result']]};font-weight:bold;cursor:default'>"
                f"{RESULT_ICONS[p['result']]}</span>"
                for p in plays
            )
            diff_val = row.get("difficulty", "Standard") if hasattr(row, "get") else getattr(row, "difficulty", "Standard")
            attempt_rows.append(
                f"<tr>"
                f"<td>{row['heroes']}</td>"
                f"<td style='text-align:center'>{diff_val}</td>"
                f"<td>{date_range}</td>"
                f"<td style='text-align:center'>{row['play_count']}</td>"
                f"<td style='text-align:center'>{played_inline}</td>"
                f"<td style='color:{color};font-weight:bold'>{label}</td>"
                f"</tr>"
            )

        # Stats-Zeile: nur anzeigen was > 0 ist
        stats_parts = [f"<span style='color:{STATUS_COLORS['completed']}'>{completed} abgeschlossen</span>"]
        if in_progress:
            stats_parts.append(f"<span style='color:{STATUS_COLORS['in_progress']}'>{in_progress} laufend</span>")
        if lost:
            stats_parts.append(f"<span style='color:{STATUS_COLORS['lost']}'>{lost} verloren</span>")
        if abandoned:
            stats_parts.append(f"<span style='color:{STATUS_COLORS['abandoned']}'>{abandoned} abgebrochen</span>")

        rows_html.append(
            f"<h3 style='margin:16px 8px 6px 8px;color:#16213e'>{camp}</h3>"
            f"<div style='padding:0 8px 4px 8px;font-size:12px;color:#666'>"
            f"{total} Versuch(e) &mdash; " + ", ".join(stats_parts) +
            f"</div>"
            f"<table class='sticky-table' style='margin:4px 8px 12px 8px;font-size:12px'>"
            f"<thead><tr>"
            f"<th>Helden</th><th>Schwierigkeit</th><th>Zeitraum</th><th>Partien</th><th>Szenarien</th><th>Status</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(attempt_rows)}</tbody>"
            f"</table>"
        )

    return "<div style='padding:8px 4px'>" + "".join(rows_html) + "</div>"


if __name__ == "__main__":
    fig = build()
    output = "campaigns_timeline.html"
    fig.write_html(
        output,
        include_plotlyjs="cdn",
        div_id=PLOT_DIV_ID,
        config=TIMELINE_CONFIG,
        post_script=zoom_js(),
    )
    print(f"Gespeichert als: {output}")
    webbrowser.open(f"file:///{os.path.abspath(output)}")
