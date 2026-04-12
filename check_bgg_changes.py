"""
Lightweight BGG Change-Check.

Ruft nur Seite 1 der BGG-API ab (ca. 1 Sek.) und vergleicht
  - Gesamtanzahl der Partien  (total)
  - ID der neuesten Partie    (last_play_id)
mit dem gespeicherten Stand in bgg_state.json.

Gibt "changed=true/false" als GitHub-Actions-Step-Output aus.
bgg_state.json wird NICHT von diesem Skript aktualisiert — das
erledigt BGG_Export.py nach dem vollständigen Datenabruf.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
import requests

USERNAME = os.environ.get("BGG_USERNAME", "Almecho")
GAME_ID  = 285774
STATE_FILE = "bgg_state.json"


def set_output(name: str, value: str) -> None:
    """Schreibt ein GitHub-Actions-Step-Output oder gibt es auf stdout aus."""
    gh_output = os.environ.get("GITHUB_OUTPUT", "")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def fetch_page1():
    url = (
        f"https://boardgamegeek.com/xmlapi2/plays?"
        f"username={USERNAME}&id={GAME_ID}&type=thing&page=1"
    )
    cookies = {
        "SessionID":   os.environ.get("BGG_SESSION_ID", ""),
        "bggpassword": os.environ.get("BGG_PASSWORD", ""),
        "bggusername": os.environ.get("BGG_USERNAME", USERNAME),
    }
    r = requests.get(url, cookies=cookies, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_page1(xml_text):
    root = ET.fromstring(xml_text)
    total = int(root.attrib.get("total", 0))
    plays = root.findall("play")
    last_id = plays[0].attrib.get("id") if plays else None
    return total, last_id


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def main():
    print("Prüfe BGG auf neue Partien (Seite 1)...")
    try:
        xml_text = fetch_page1()
    except Exception as e:
        print(f"FEHLER beim BGG-Abruf: {e}", file=sys.stderr)
        # Im Fehlerfall lieber ein Update durchführen
        set_output("changed", "true")
        return

    total, last_id = parse_page1(xml_text)
    print(f"BGG meldet: {total} Partien, neueste ID: {last_id}")

    state = load_state()
    if state is None:
        print("Kein gespeicherter State gefunden → Update erforderlich.")
        set_output("changed", "true")
        return

    stored_total   = state.get("total", -1)
    stored_last_id = str(state.get("last_play_id", ""))
    current_last_id = str(last_id) if last_id else ""

    if total != stored_total or current_last_id != stored_last_id:
        print(
            f"Änderung erkannt: total {stored_total} → {total}, "
            f"letzte ID {stored_last_id} → {current_last_id}"
        )
        set_output("changed", "true")
    else:
        print("Keine Änderung – kein Update nötig.")
        set_output("changed", "false")


if __name__ == "__main__":
    main()
