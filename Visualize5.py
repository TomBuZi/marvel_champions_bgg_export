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


def build():
    df = pd.read_csv("marvel_champions_campaigns.csv", sep=";")
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Keine Kampagnen erkannt",
            template="plotly_white",
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
        f"{row['campaign']} \u2014 {_short_heroes(row['heroes'])}"
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
                f"Status: {status_label}<br>"
                f"Zeitraum: {date_range}<br>"
                f"Partien: {row['play_count']}<br>"
                f"<br><b>Szenarien:</b><br>" + "<br>".join(scen_lines)
            )

            durations_ms.append((end - start).total_seconds() * 1000.0)
            ys.append(row["y_pos"])
            bases.append(start)
            hovers.append(hover)

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
            hovertext=hovers,
            hoverinfo="text",
            name=status_label,
            legendgroup="status",
            legendgrouptitle_text="Status",
            showlegend=True,
            width=0.65,
        ))

    # --- Scatter-Marker: einzelne Szenarien innerhalb jedes Versuchs --- #
    scatter = {k: {"x": [], "y": [], "text": []} for k in RESULT_COLORS}

    for _, row in df.iterrows():
        plays = _parse_played(row["scenarios_played"])
        for p in plays:
            scatter[p["result"]]["x"].append(p["date"])
            scatter[p["result"]]["y"].append(row["y_pos"])
            scatter[p["result"]]["text"].append(
                f"<b>{p['scenario']}</b> ({row['campaign']})<br>"
                f"{p['date']}<br>"
                f"Helden: {row['heroes']}<br>"
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
                size=11,
                color=RESULT_COLORS[result_key],
                line=dict(color="white", width=1.5),
            ),
            hovertext=data["text"],
            hoverinfo="text",
            name=RESULT_LABELS[result_key],
            legendgroup="result",
            legendgrouptitle_text="Ergebnis",
            showlegend=True,
        ))

    # --- Layout --- #
    height = max(520, len(df) * 30 + 240)

    fig.update_layout(
        title=dict(
            text="Marvel Champions \u2014 Gespielte Kampagnen (Zeitstrahl)",
            font=dict(size=16),
        ),
        barmode="overlay",
        bargap=0.35,
        xaxis=dict(
            type="date",
            title="Datum",
            showgrid=True,
            gridcolor="#e0e0e0",
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(df["y_pos"]),
            ticktext=tick_text,
            autorange="reversed",
            showgrid=False,
            tickfont=dict(size=11),
        ),
        shapes=shapes,
        height=height,
        margin=dict(l=360, r=20, t=90, b=50),
        template="plotly_white",
        dragmode=False,
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            groupclick="toggleitem",
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
            attempt_rows.append(
                f"<tr>"
                f"<td>{row['heroes']}</td>"
                f"<td>{date_range}</td>"
                f"<td style='text-align:center'>{row['play_count']}</td>"
                f"<td style='text-align:center'>{played_inline}</td>"
                f"<td style='color:{color};font-weight:bold'>{label}</td>"
                f"</tr>"
            )

        rows_html.append(
            f"<h3 style='margin:16px 8px 6px 8px;color:#16213e'>{camp}</h3>"
            f"<div style='padding:0 8px 4px 8px;font-size:12px;color:#666'>"
            f"{total} Versuch(e) &mdash; "
            f"<span style='color:{STATUS_COLORS['completed']}'>{completed} abgeschlossen</span>, "
            f"<span style='color:{STATUS_COLORS['in_progress']}'>{in_progress} laufend</span>, "
            f"<span style='color:{STATUS_COLORS['abandoned']}'>{abandoned} abgebrochen</span>"
            f"</div>"
            f"<table class='sticky-table' style='margin:4px 8px 12px 8px;font-size:12px'>"
            f"<thead><tr>"
            f"<th>Helden</th><th>Zeitraum</th><th>Partien</th><th>Szenarien</th><th>Status</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(attempt_rows)}</tbody>"
            f"</table>"
        )

    return "<div style='padding:8px 4px'>" + "".join(rows_html) + "</div>"


if __name__ == "__main__":
    fig = build()
    output = "campaigns_timeline.html"
    fig.write_html(output, include_plotlyjs="cdn")
    print(f"Gespeichert als: {output}")
    webbrowser.open(f"file:///{os.path.abspath(output)}")
