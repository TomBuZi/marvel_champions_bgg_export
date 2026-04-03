import json
import os
import re
import requests
import xml.etree.ElementTree as ET
import csv
import time
import html

USERNAME = "Almecho"   # <-- HIER deinen BGG-Nutzernamen eintragen
GAME_ID = 285774                 # Marvel Champions
OUTFILE = "marvel_champions_plays.csv"

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

def load_config(filename):
    with open(os.path.join(CONFIG_DIR, filename), encoding="utf-8") as f:
        return json.load(f)

HEROES = load_config("heroes.json")
ASPECTS = load_config("aspects.json")
SCENARIOS = load_config("scenarios.json")
MODULARS = load_config("modulars.json")

def find_longest_prefix_match(text, candidates):
    """Find the candidate whose name is the longest prefix match for text (case-insensitive)."""
    text_lower = text.strip().lower()
    best = None
    for candidate in candidates:
        if text_lower.startswith(candidate.lower()):
            if best is None or len(candidate) > len(best):
                best = candidate
    return best

def fetch_page(username, game_id, page):
    url = (
        f"https://boardgamegeek.com/xmlapi2/plays?"
        f"username={username}&id={game_id}&type=thing&page={page}"
    )
    
    cookies = {
        "SessionID": os.environ.get("BGG_SESSION_ID", ""),
        "bggpassword": os.environ.get("BGG_PASSWORD", ""),
        "bggusername": os.environ.get("BGG_USERNAME", username),
    }

    r = requests.get(url, cookies=cookies, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text
    
def parse_plays(xml_text):
    root = ET.fromstring(xml_text)
    return root.findall("play"), int(root.attrib.get("total", 0))

def split_comment(comment):
    """
    Erwartetes Muster:
    <Teil 1> vs <Teil 2> - <Teil 3>

    Der erste Split erfolgt nur nach 'vs'
    (also nicht mehr ' vs ')
    und alle Teile werden nach dem Split getrimmt.
    """
    if not comment:
        return "", "", ""

    # 1) Split nach 'vs' (mit beliebigen Whitespaces davor/danach)
    parts = re.split(r'\s*vs\s*', comment, maxsplit=1)

    if len(parts) == 1:
        # kein "vs" gefunden
        return "", parts[0].strip(), ""

    part1 = parts[0].strip()
    rest = parts[1].strip()

    # 2) Zweiter Split nach ' - '
    if " - " not in rest:
        return part1, rest.strip(), ""

    part2, part3 = rest.split(" - ", 1)

    return part1.strip(), part2.strip(), part3.strip()
    
def extract_play_data(play):
    comments = (play.find("comments").text or "") if play.find("comments") is not None else ""
    comments = html.unescape(comments)
    comments = comments.replace("\n", " ").replace("\r", " ").strip().strip('"').strip()

    hero, scenario, result = split_comment(comments)

    # Basisdaten
    data = {
        "id": play.attrib.get("id"),
        "date": play.attrib.get("date"),
        "quantity": play.attrib.get("quantity"),
        "length": play.attrib.get("length"),
        "incomplete": play.attrib.get("incomplete"),
        "nowinstats": play.attrib.get("nowinstats"),
        "game_name": play.find("item").attrib.get("name") if play.find("item") is not None else "",
        "comments": comments,
        "hero": hero,
        "scenario": scenario,
        "result": result
    }

    # Dynamische Scenario-Felder
    scenario_clean = scenario.strip()

    # Dynamische Scenario-Felder initialisieren
    for scen in SCENARIOS:
        data[scen] = ""

    # Längstes Match ermitteln
    matched_scenario = find_longest_prefix_match(scenario_clean, SCENARIOS)

    # Gefundenes Szenario markieren
    if matched_scenario:
        data[matched_scenario] = "x"
        data["unknown scenario"] = ""
    else:
        data["unknown scenario"] = "x"

    return data
    
if __name__ == "__main__":

    all_plays = []
    page = 1
    total_plays = None

    while True:
        print(f"Lade Seite {page} ...")
        xml_data = fetch_page(USERNAME, GAME_ID, page)
        plays, total = parse_plays(xml_data)

        if total_plays is None:
            total_plays = total
            print(f"Insgesamt {total_plays} Partien gefunden.")

        if not plays:
            break

        for p in plays:
            all_plays.append(extract_play_data(p))

        if len(all_plays) >= total_plays:
            break

        page += 1
        time.sleep(1)  # API nicht überlasten

    print(f"Insgesamt geladen: {len(all_plays)} Partien.")

    if not all_plays:
        print("Keine Partien gefunden. Beende.")
        exit(0)

    # CSV schreiben
    with open(OUTFILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_plays[0].keys(), delimiter=';')
        writer.writeheader()
        writer.writerows(all_plays)

    # --- ZWEITE CSV: Szenario-Statistik erzeugen --- #

    scenario_counts = {scen: 0 for scen in SCENARIOS}
    scenario_counts["unknown scenario"] = 0

    modular_counts = {mod: 0 for mod in MODULARS}

    # Durch alle geladenen Partien gehen und die matches zählen
    for play in all_plays:
        scenario_clean = play["scenario"].strip().lower()

        # Längstes Match ermitteln
        matched_scenario = find_longest_prefix_match(scenario_clean, SCENARIOS)

        if matched_scenario:
            scenario_counts[matched_scenario] += 1
            scenario_clean = scenario_clean[len(matched_scenario):].strip()

        if not matched_scenario:
            scenario_counts["unknown scenario"] += 1

        # Suchen nach Modulars, bis keine mehr gefunden wurden
        modular_found = True
        standard_found = False
        while modular_found:
            modular_found = False
            matched_modular = find_longest_prefix_match(scenario_clean, MODULARS)
            if matched_modular:
                modular_found = True

            if matched_modular:
                modular_counts[matched_modular] += 1
                scenario_clean = scenario_clean[len(matched_modular):].strip()
                if matched_modular in ["Standard", "Standard II", "Standard III"]:
                    standard_found = True

            if not matched_modular and len(scenario_clean) > 0:
                modular_counts[scenario_clean] = modular_counts.get(scenario_clean, 0) + 1

        if not standard_found:
            modular_counts["Standard"] += 1

    # Sortieren nach Anzahl Partien (absteigend)
    sorted_stats = sorted(
        scenario_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Zweite CSV schreiben
    OUTFILE_STATS = "marvel_champions_scenario_stats.csv"
    with open(OUTFILE_STATS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["scenario", "count"])
        writer.writerows(sorted_stats)

    # Sortieren nach Anzahl Partien (absteigend)
    sorted_stats = sorted(
        modular_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Zweite CSV schreiben
    OUTFILE_STATS = "marvel_champions_modular_stats.csv"
    with open(OUTFILE_STATS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["modular", "count"])
        writer.writerows(sorted_stats)

    print(f"Statistik gespeichert als: {OUTFILE_STATS}")

    # --- HERO-STATISTIK --- #

    # Gesamtzähler pro Held
    hero_counts = {hero: 0 for hero in HEROES}

    # Kombinationen (Held, Aspekt)
    hero_aspect_counts = {}   # key = (hero, aspect)

    for play in all_plays:

        text = (play["hero"] or "").strip()
        text_lower = text.lower()

        # Helden mit Positionen finden
        hero_positions = []
        for hero in HEROES:
            pos = text_lower.find(hero.lower())
            if pos != -1:
                hero_positions.append((pos, hero))

        if not hero_positions:
            print(f"No Hero found in: {text_lower}")
            continue

        hero_positions.sort()

        # Aspekte mit Positionen finden
        aspect_positions = []
        for asp in ASPECTS:
            pos = text_lower.find(asp.lower())
            if pos != -1:
                aspect_positions.append((pos, asp))

        if not aspect_positions:
            print(f"No Aspect found in: {text_lower}")

        aspect_positions.sort()

        # Helden den richtigen Aspekt zuordnen
        for idx, (hero_pos, hero) in enumerate(hero_positions):

            hero_counts[hero] += 1

            next_hero_pos = hero_positions[idx + 1][0] if idx + 1 < len(hero_positions) else float('inf')

            assigned_aspect = ""

            possible_aspects = [
                (pos, asp) for (pos, asp) in aspect_positions
                if hero_pos < pos < next_hero_pos
            ]

            if possible_aspects:
                assigned_aspect = possible_aspects[0][1]

            key = (hero, assigned_aspect)
            hero_aspect_counts[key] = hero_aspect_counts.get(key, 0) + 1

    # CSV: Gesamtzahl pro Held
    with open("heroes_total.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Count"])

        for hero, count in sorted(hero_counts.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([hero, count])

    print("CSV geschrieben: heroes_total.csv")

    # CSV: Kombinationen Held + Aspekt
    with open("heroes_aspects.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Aspect", "Count"])

        for (hero, aspect), count in sorted(hero_aspect_counts.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([hero, aspect, count])

    print("CSV geschrieben: heroes_aspects.csv")

    # --- ASPEKT-STATISTIK --- #

    aspect_counts = {asp: 0 for asp in ASPECTS}

    for play in all_plays:
        hero_text = (play["hero"] or "").lower()

        for asp in ASPECTS:
            count = hero_text.count(asp.lower())
            aspect_counts[asp] += count

    sorted_aspect_stats = sorted(
        aspect_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    OUTFILE_ASPECTS = "marvel_champions_aspect_stats.csv"
    with open(OUTFILE_ASPECTS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["aspect", "count"])
        writer.writerows(sorted_aspect_stats)

    print(f"Aspekt-Statistik gespeichert als: {OUTFILE_ASPECTS}")

    print(f"FERTIG! Datei gespeichert als: {OUTFILE}")
