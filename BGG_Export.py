import json
import os
import re
import requests
import xml.etree.ElementTree as ET
import csv
import time
import html

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

USERNAME = os.environ.get("BGG_USERNAME", "Almecho")
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
HERO_ALIASES          = load_config("hero_aliases.json")
HERO_DEFAULT_ASPECTS  = load_config("hero_default_aspects.json")
SCENARIO_MODULARS         = load_config("scenario_modulars.json")
SCENARIO_DEFAULT_MODULARS = load_config("scenario_default_modulars.json")

# Nur Schwierigkeitsgrad-Modulars — gelten nicht als echte Modularauswahl
DIFFICULTY_MODULARS = {"standard", "standard ii", "standard iii", "expert", "expert ii"}

# Gewünschte Reihenfolge der Schwierigkeitsgrade in Modularkombinationen
_DIFFICULTY_ORDER = ["Standard", "Standard II", "Standard III", "Expert", "Expert II"]
_DIFFICULTY_RANK  = {m.lower(): i for i, m in enumerate(_DIFFICULTY_ORDER)}

def sort_modular_combo(modular_name):
    """Sortierschlüssel: Schwierigkeitsgrade zuerst (in fester Reihenfolge), dann alphabetisch."""
    key = modular_name.lower()
    if key in _DIFFICULTY_RANK:
        return (0, _DIFFICULTY_RANK[key], "")
    return (1, 0, modular_name.lower())

def find_all_hero_positions(text_lower, heroes):
    """Find all (pos, hero) occurrences for every hero in the text."""
    all_positions = []
    for hero in heroes:
        hero_lower = hero.lower()
        start = 0
        while True:
            pos = text_lower.find(hero_lower, start)
            if pos == -1:
                break
            all_positions.append((pos, hero))
            start = pos + 1
    return all_positions

def remove_covered_matches(positions):
    """Remove any match whose range is fully covered by a longer match."""
    result = []
    for i, (pos, hero) in enumerate(positions):
        end = pos + len(hero)
        covered = any(
            j != i and other_pos <= pos and other_pos + len(other) >= end
            for j, (other_pos, other) in enumerate(positions)
        )
        if not covered:
            result.append((pos, hero))
    return result

def count_modular(mod, modular_counts, matched_in_comments, counted_this_play, standard_found_ref):
    """Zählt ein Modular und aktualisiert alle Tracking-Strukturen."""
    modular_counts[mod] = modular_counts.get(mod, 0) + 1
    matched_in_comments.add(mod.lower())
    counted_this_play.append(mod)
    if mod in ["Standard", "Standard II", "Standard III"]:
        standard_found_ref[0] = True

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
        "SessionID":  os.environ.get("BGG_SESSION_ID", ""),
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

    plays_no_hero     = []  # (date, "", comment) — Heldenfeld komplett leer
    plays_no_villain  = []  # (date, "", comment) — Szenariofeld komplett leer
    unknown_heroes    = []  # (date, raw_text, comment) — Heldentext vorhanden, aber nicht erkannt
    unknown_scenarios = []  # (date, raw_text, comment) — Szenariotext vorhanden, aber nicht erkannt
    unknown_modulars  = []  # (date, raw_text, comment)
    missing_modulars  = []  # (date, scenario, comment) — bekanntes Szenario, kein Modular im Kommentar

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
    scenario_combo_counts      = {}  # (scenario, combo_tuple) -> count
    scenario_combo_hero_counts = {}  # (scenario, combo_tuple, hero) -> count

    # Durch alle geladenen Partien gehen und die matches zählen
    for play in all_plays:
        scenario_clean = play["scenario"].strip().lower()

        # Leeres Szenariofeld → eigene Kategorie
        if not scenario_clean:
            plays_no_villain.append((play["date"], "", play["comments"]))
            scenario_counts["unknown scenario"] += 1
            # Standard-Fallback zählen und nächste Partie
            count_modular("Standard", modular_counts, set(), [], [False])
            continue

        # Längstes Match ermitteln
        matched_scenario = find_longest_prefix_match(scenario_clean, SCENARIOS)

        if matched_scenario:
            scenario_counts[matched_scenario] += 1
            scenario_clean = scenario_clean[len(matched_scenario):].strip()

        if not matched_scenario:
            scenario_counts["unknown scenario"] += 1
            unknown_scenarios.append((play["date"], play["scenario"], play["comments"]))

        # Suchen nach Modulars, Wort für Wort
        standard_found_ref  = [False]
        matched_in_comments = set()   # Lowercase-Set für Deduplizierung
        counted_this_play   = []      # Originalnamen in Reihenfolge der Zählung

        while scenario_clean:
            # Führende Trennzeichen (Leerzeichen, +, Komma) überspringen
            scenario_clean = re.sub(r'^[\s+,]+', '', scenario_clean)
            if not scenario_clean:
                break

            matched_modular = find_longest_prefix_match(scenario_clean, MODULARS)
            if matched_modular:
                count_modular(matched_modular, modular_counts, matched_in_comments, counted_this_play, standard_found_ref)
                scenario_clean = scenario_clean[len(matched_modular):]
            else:
                # Erstes Wort nicht erkannt → einzeln melden, nächstes Wort versuchen
                m = re.match(r'(\S+)(.*)', scenario_clean, re.DOTALL)
                if m:
                    unknown_modulars.append((play["date"], m.group(1), play["comments"]))
                    scenario_clean = m.group(2)
                else:
                    break

        # Default-Modulars: wenn nichts oder nur Schwierigkeitsgrad-Modulars im Kommentar standen
        if matched_scenario and matched_in_comments.issubset(DIFFICULTY_MODULARS):
            if matched_scenario in SCENARIO_DEFAULT_MODULARS:
                for def_mod in SCENARIO_DEFAULT_MODULARS[matched_scenario]:
                    if def_mod.lower() not in matched_in_comments:
                        count_modular(def_mod, modular_counts, matched_in_comments, counted_this_play, standard_found_ref)

        # Automatisch inkludierte Modulars: immer ergänzen (sofern nicht schon gezählt)
        if matched_scenario and matched_scenario in SCENARIO_MODULARS:
            for auto_mod in SCENARIO_MODULARS[matched_scenario]:
                if auto_mod.lower() not in matched_in_comments:
                    count_modular(auto_mod, modular_counts, matched_in_comments, counted_this_play, standard_found_ref)

        # Fehlende Modulars: nur wenn nach beiden Schritten immer noch nichts gezählt wurde
        if matched_scenario and not matched_in_comments:
            missing_modulars.append((play["date"], matched_scenario, play["comments"]))

        if not standard_found_ref[0]:
            count_modular("Standard", modular_counts, matched_in_comments, counted_this_play, standard_found_ref)

        # Kombinations-Zähler aktualisieren
        if matched_scenario and counted_this_play:
            combo = tuple(sorted(counted_this_play, key=sort_modular_combo))
            key = (matched_scenario, combo)
            scenario_combo_counts[key] = scenario_combo_counts.get(key, 0) + 1

            # Helden für Baumansicht tracken
            hero_text_lower = (play["hero"] or "").strip().lower()
            hero_pos_list   = find_all_hero_positions(hero_text_lower, HEROES)
            hero_pos_list   = remove_covered_matches(hero_pos_list)
            for _, hero in hero_pos_list:
                canonical = HERO_ALIASES.get(hero, hero)
                hero_key  = (matched_scenario, combo, canonical)
                scenario_combo_hero_counts[hero_key] = scenario_combo_hero_counts.get(hero_key, 0) + 1

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

    # Szenario × Modularkombination CSV
    scenario_order = {s: i for i, s in enumerate(SCENARIOS)}
    OUTFILE_COMBOS = "marvel_champions_scenario_modular_combos.csv"
    with open(OUTFILE_COMBOS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["scenario", "modulars", "count"])
        for (scenario, combo), count in sorted(
            scenario_combo_counts.items(),
            key=lambda x: (scenario_order.get(x[0][0], 9999), -x[1])
        ):
            writer.writerow([scenario, " + ".join(combo), count])
    print(f"Statistik gespeichert als: {OUTFILE_COMBOS}")

    # Szenario × Modularkombination × Held CSV
    OUTFILE_COMBO_HEROES = "marvel_champions_scenario_modular_hero.csv"
    with open(OUTFILE_COMBO_HEROES, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["scenario", "modulars", "hero", "count"])
        for (scenario, combo, hero), count in sorted(
            scenario_combo_hero_counts.items(),
            key=lambda x: (scenario_order.get(x[0][0], 9999), -x[1])
        ):
            writer.writerow([scenario, " + ".join(combo), hero, count])
    print(f"Statistik gespeichert als: {OUTFILE_COMBO_HEROES}")

    # --- HERO-STATISTIK --- #

    # Gesamtzähler pro Held (kanonische Namen)
    canonical_hero_names = list(dict.fromkeys(
        HERO_ALIASES.get(h, h) for h in HEROES
    ))
    hero_counts = {hero: 0 for hero in canonical_hero_names}
    hero_first_played = {}  # canonical_hero -> earliest date string

    # Kombinationen (Held, Aspekt)
    hero_aspect_counts = {}   # key = (canonical_hero, aspect)

    for play in all_plays:

        text = (play["hero"] or "").strip()

        # Leeres Heldenfeld → eigene Kategorie
        if not text:
            plays_no_hero.append((play["date"], "", play["comments"]))
            continue

        text_lower = text.lower()

        # Alle Helden-Positionen finden, überlappende entfernen
        hero_positions = find_all_hero_positions(text_lower, HEROES)
        hero_positions = remove_covered_matches(hero_positions)
        hero_positions.sort()

        if not hero_positions:
            unknown_heroes.append((play["date"], text, play["comments"]))
            continue

        # Aspekte mit Positionen finden
        aspect_positions = []
        for asp in ASPECTS:
            pos = text_lower.find(asp.lower())
            if pos != -1:
                aspect_positions.append((pos, asp))

        aspect_positions.sort()

        # Helden den richtigen Aspekt zuordnen
        for idx, (hero_pos, hero) in enumerate(hero_positions):

            canonical = HERO_ALIASES.get(hero, hero)
            hero_counts[canonical] += 1
            date = play["date"] or ""
            if date and (canonical not in hero_first_played or date < hero_first_played[canonical]):
                hero_first_played[canonical] = date

            next_hero_pos = hero_positions[idx + 1][0] if idx + 1 < len(hero_positions) else float('inf')

            possible_aspects = [
                asp for pos, asp in aspect_positions
                if hero_pos < pos < next_hero_pos
            ]

            if canonical in HERO_DEFAULT_ASPECTS:
                # Multi-aspect hero: use all found aspects; fall back to defaults if none found
                aspects_to_count = possible_aspects or HERO_DEFAULT_ASPECTS[canonical]
            else:
                # Regular hero: use first found aspect only; fall back to Precon if none found
                aspects_to_count = [possible_aspects[0]] if possible_aspects else ["Precon"]

            for asp in aspects_to_count:
                key = (canonical, asp)
                hero_aspect_counts[key] = hero_aspect_counts.get(key, 0) + 1

    # CSV: Gesamtzahl pro Held
    with open("heroes_total.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Count", "First Played"])

        for hero, count in sorted(hero_counts.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([hero, count, hero_first_played.get(hero, "")])

    print("CSV geschrieben: heroes_total.csv")

    # CSV: Kombinationen Held + Aspekt
    with open("heroes_aspects.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Aspect", "Count"])

        for (hero, aspect), count in sorted(hero_aspect_counts.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([hero, aspect, count])

    print("CSV geschrieben: heroes_aspects.csv")

    # CSV: Kombinationen Held + Szenario (inkl. Win/Loss/Incomplete)
    WIN_KEYWORDS  = {"won", "win", "sieg", "victory", "gewonnen"}
    LOSS_KEYWORDS = {"lost", "loss", "lose", "defeat", "verloren", "niederlage"}

    def classify_result(play):
        if str(play.get("incomplete", "0")) == "1":
            return "incomplete"
        result_lower = (play.get("result") or "").strip().lower()
        if result_lower in WIN_KEYWORDS or any(result_lower.startswith(k) for k in WIN_KEYWORDS):
            return "win"
        if result_lower in LOSS_KEYWORDS or any(result_lower.startswith(k) for k in LOSS_KEYWORDS):
            return "loss"
        return "incomplete"  # Unklar → als ungewertet behandeln

    hero_scenario_counts  = {}   # (hero, scenario)           → total
    hero_scenario_results = {}   # (hero, scenario, result)   → count

    for play in all_plays:
        text = (play["hero"] or "").strip()
        text_lower = text.lower()

        hero_positions = find_all_hero_positions(text_lower, HEROES)
        hero_positions = remove_covered_matches(hero_positions)
        if not hero_positions:
            continue

        matched_scenario = find_longest_prefix_match(play["scenario"].strip(), SCENARIOS)
        if not matched_scenario:
            continue

        result_cat = classify_result(play)

        for _, hero in hero_positions:
            canonical = HERO_ALIASES.get(hero, hero)
            key = (canonical, matched_scenario)
            hero_scenario_counts[key] = hero_scenario_counts.get(key, 0) + 1
            rkey = (canonical, matched_scenario, result_cat)
            hero_scenario_results[rkey] = hero_scenario_results.get(rkey, 0) + 1

    with open("heroes_scenarios.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Scenario", "Count"])
        for (hero, scenario), count in sorted(hero_scenario_counts.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([hero, scenario, count])

    print("CSV geschrieben: heroes_scenarios.csv")

    with open("heroes_scenarios_results.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Hero", "Scenario", "Win", "Loss", "Incomplete"])
        # Alle (hero, scenario)-Paare sammeln und W/L/I auflösen
        for (hero, scenario), total in sorted(hero_scenario_counts.items(), key=lambda x: x[1], reverse=True):
            w = hero_scenario_results.get((hero, scenario, "win"),        0)
            l = hero_scenario_results.get((hero, scenario, "loss"),       0)
            i = hero_scenario_results.get((hero, scenario, "incomplete"), 0)
            writer.writerow([hero, scenario, w, l, i])

    print("CSV geschrieben: heroes_scenarios_results.csv")

    # --- ASPEKT-STATISTIK --- #
    # Direkt aus hero_aspect_counts ableiten, damit Defaults (z.B. Adam Warlock) korrekt gezählt werden

    aspect_counts = {asp: 0 for asp in ASPECTS}

    for (hero, aspect), count in hero_aspect_counts.items():
        if aspect in aspect_counts:
            aspect_counts[aspect] += count

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

    # --- UNBEKANNTE EINTRÄGE --- #

    def _print_unknowns(label, entries):
        if entries:
            print(f"{label} ({len(entries)}):")
            for date, value, comment in sorted(entries):
                print(f"  {date}  \"{value}\"  →  {comment}")
        else:
            print(f"{label} (0): keine")

    print("\n=== UNBEKANNTE / FEHLENDE EINTRÄGE ===")
    _print_unknowns("Plays ohne Held",          plays_no_hero)
    _print_unknowns("Plays ohne Villain",        plays_no_villain)
    _print_unknowns("Helden nicht erkannt",      unknown_heroes)
    _print_unknowns("Szenarien nicht erkannt",   unknown_scenarios)
    _print_unknowns("Modulars nicht erkannt",    unknown_modulars)
    _print_unknowns("Fehlende Modulars",         missing_modulars)

    OUTFILE_UNKNOWN = "unrecognized_report.csv"
    with open(OUTFILE_UNKNOWN, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["category", "date", "value", "comment"])
        for date, value, comment in sorted(plays_no_hero):
            writer.writerow(["Kein Held", date, value, comment])
        for date, value, comment in sorted(plays_no_villain):
            writer.writerow(["Kein Villain", date, value, comment])
        for date, value, comment in sorted(unknown_heroes):
            writer.writerow(["Held nicht erkannt", date, value, comment])
        for date, value, comment in sorted(unknown_scenarios):
            writer.writerow(["Szenario nicht erkannt", date, value, comment])
        for date, value, comment in sorted(unknown_modulars):
            writer.writerow(["Modular nicht erkannt", date, value, comment])
        for date, value, comment in sorted(missing_modulars):
            writer.writerow(["Fehlendes Modular", date, value, comment])

    if any([plays_no_hero, plays_no_villain, unknown_heroes,
            unknown_scenarios, unknown_modulars, missing_modulars]):
        print(f"\nBericht gespeichert als: {OUTFILE_UNKNOWN}")
