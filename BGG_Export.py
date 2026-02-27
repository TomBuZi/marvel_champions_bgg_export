import requests
import xml.etree.ElementTree as ET
import csv
import time
import html

USERNAME = "Almecho"   # <-- HIER deinen BGG-Nutzernamen eintragen
GAME_ID = 285774                 # Marvel Champions
OUTFILE = "marvel_champions_plays.csv"

HEROES = [
    "Captain America", "Iron Man", "Spider-Man", "She-Hulk",
    "Captain Marvel", "Black Panther", "Doctor Strange",
    "Hulk", "Ms. Marvel", "Black Widow", "Hawkeye",
    "Scarlet Witch", "Ant-Man", "Wasp", "Spectrum",
    "Quicksilver", "Gamora", "Drax", "Star-Lord",
    "Venom", "Nebula", "Groot", "Rocket Raccoon",
    "Ghost-Spider", "Miles Morales", "Storm", "Cyclops",
    "Wolverine", "Colossus", "Shadowcat", "Rogue", "Gambit",
    "Phoenix", "Cable", "Domino", "Psylocke", "X-23", "Jubilee",
	"Spider-Woman", "Nightcrawler", "Iceman", "Thor",
	"Valkyrie", "Ironheart", "Nova", "Vision", "Adam Warlock",
	"Spider-Ham", "SP//dr", "Angel", "Deadpool", "Magik",
	"Bishop", "Magneto", "Nick Fury", "Maria Hill",
	"Silk", "Falcon", "Winter Soldier", "Tigra", "War Machine"
]

ASPECTS = ["Aggression", "Justice", "Leadership", "Protection", "Basic", "'Pool", "Precon"]

SCENARIOS = [
    "Rhino",
    "Klaw",
    "Ultron",
    "Risky Business",
    "Mutagen Formula",
    "Wrecking Crew",
    "Crossbones",
    "Absorbing Man",
    "Taskmaster",
    "Zola",
    "Red Skull",
    "Kang",
    "Brotherhood of Badoon",
    "Infiltrate the Museum",
    "Escape the Museum",
    "Nebula",
    "Ronan the Accuser",
    "Ebony Maw",
    "Tower Defense",
    "Thanos",
    "Hela",
    "Loki",
    "The Hood",
    "Sandman",
    "Venom",
    "Mysterio",
    "The Sinister Six",
    "Venom Goblin",
    "Sabretooth",
    "Project Wideawake",
    "Master Mold",
    "Mansion Attack",
    "Magneto",
    "Magog",
    "Spiral",
    "Mojo",
    "Morlock Siege",
    "On the Run",
    "Juggernaut",
    "Mister Sinister",
    "Stryfe",
    "Unus",
    "Four Horsemen",
    "Apocalypse",
    "Dark Beast",
    "En Sabah Nur",
    "Black Widow",
    "Batroc",
    "M.O.D.O.K.",
    "Thunderbolts",
    "Baron Zemo",
    "Enchantress",
    "God of Lies",
    "Iron Man",
    "Captain Marvel",
    "Captain America",
    "Spider-Woman",
	"She-Hulk",
	"Vision"
]

MODULARS = [
    "Campaign",
    "Standard",
    "Standard II",
    "Standard III",
    "Expert",
    "Expert II",
    "Kree Fanatic",
    "Bomb Scare",
    "Masters of Evil",
    "Under Attack",
    "Legions of Hydra",
    "Doomsday Chair",
    "Goblin Gimmicks",
    "A Mess of Things",
    "Power Drain",
    "Running Interference",
    "Experimental Weapons",
    "Hydra Assault",
    "Weapon Master",
    "Hydra Patrol",
    "Temporal",
    "Anachronauts",
    "Master of Time",
    "Band of Badoon",
    "Galactic Artifacts",
    "Kree Militants",
    "Menagerie Medley",
    "Space Pirates",
    "Ship Command",
    "Power Stone",
    "Badoon Headhunter",
    "Black Order",
    "Armies of Titan",
    "Children of Thanos",
    "Infinity Gauntlet",
    "Legions of Hel",
    "Frost Giants",
    "Enchantress",
    "Beasty Boys",
    "Brothers Grimm",
    "Crossfire's Crew",
    "Mister Hyde",
    "Ransacked Armory",
    "Sinister Syndicate",
    "State of Emergency",
    "Streets of Mayhem",
    "Wrecking Crew",
    "City in Chaos",
    "Down to Earth",
    "Goblin Gear",
    "Guerrilla Tactics",
    "Osborn Tech",
    "Personal Nightmare",
    "Sinister Assault",
    "Symbiotic Strength",
    "Whispers of Paranoia",
    "Armadillo",
    "Zzzax",
    "The Inheritors",
    "Iron Spider's Sinister Six",
    "Brotherhood",
    "Mystique",
    "Zero Tolerance",
    "Sentinels",
    "Acolytes",
    "Future Past",
    "Deathstrike",
    "Shadow King",
    "Exodus",
    "Reavers",
    "Crime",
    "Fantasy",
    "Horror",
    "Sci-Fi",
    "Sitcom",
    "Western",
    "Longshot",
    "Military Grade",
    "Mutant Slayers",
    "Nasty Boys",
    "Black Tom Cassady",
    "Flight",
    "Super Strength",
    "Telepathy",
    "Extreme Measures",
    "Mutant Insurrection",
    "Dreadpool",
    "Infinites",
    "Dystopian Nightmare",
    "Hounds",
    "Dark Riders",
    "Savage Land",
    "Genosha",
    "Blue Moon",
    "Celestial Tech",
    "Clan Akkaba",
    "Sauron",
    "Arcade",
    "Crazy Gang",
    "Hellfire",
    "A.I.M. Abduction",
    "A.I.M. Science",
    "Batroc's Brigade",
    "Scientist Supreme",
    "Gravitational Pull",
    "Hard Sound",
    "Pale Little Spider",
    "Power of the Atom",
    "Supersonic",
    "The Leaper",
    "S.H.I.E.L.D.",
    "Extreme Risk",
    "Growing Strong",
    "Techno",
    "Whiteout",
    "Trickster Magic",
    "Mighty Avengers",
    "The Initiative",
    "Maria Hill",
    "Dangerous Recruits",
    "Cape Killer",
    "Martial Law",
    "Heroes for Hire",
    "Paladin",
    "New Avengers",
    "Secret Avengers",
    "Namor",
    "Atlanteans",
    "Spider-Man",
    "Defenders",
    "Hell's Kitchen",
    "Cloak & Dagger",
	"Scarlet Twins",
	"Moon Knight",
	"Young Avengers",
	"Royal Guard",
	"Deadly Duo",
	"Thunderbolts",
	"Taskmaster",
	"S.H.I.E.L.D. Ops",
]

def fetch_page(username, game_id, page):
    url = (
        f"https://boardgamegeek.com/xmlapi2/plays?"
        f"username={username}&id={game_id}&type=thing&page={page}"
    )
    
    cookies = {
        "SessionID": "5470802078119cf272aff7a4eda2507ac71866f1u250203",
        "bggpassword": "utxfz2uevwxzeiv2xj5sigsc63f10gjdo",
        "bggusername": "Almecho"
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
    import re
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
    matched_scenario = None
    for scen in SCENARIOS:
        if scenario_clean.lower().startswith(scen.lower()):
            if matched_scenario is None:
                matched_scenario = scen
            else:
                # Prüfen, ob aktuelles Szenario längeres Präfix ist als bisheriges Match
                if len(scen) > len(matched_scenario):
                    matched_scenario = scen

    # Gefundenes Szenario markieren
    if matched_scenario:
        data[matched_scenario] = "x"
        data["unknown scenario"] = ""
    else:
        data["unknown scenario"] = "x"

    return data
    
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
    matched_scenario = None
    for scen in SCENARIOS:
        if scenario_clean.lower().startswith(scen.lower()):
            if matched_scenario is None:
                matched_scenario = scen
            else:
                # Prüfen, ob aktuelles Szenario längeres Präfix ist als bisheriges Match
                if len(scen) > len(matched_scenario):
                    matched_scenario = scen

    if matched_scenario:
        scenario_counts[matched_scenario] += 1
        scenario_clean = scenario_clean[len(matched_scenario):].strip()
    
    if not matched_scenario:
        scenario_counts["unknown scenario"] += 1
    
    # Suchen nach Modulars, bis keine mehr gefunden wurden
    modular_found = True
    standard_found = False
    while (modular_found):
        modular_found = False
        matched_modular = None
        for mod in MODULARS:
            if scenario_clean.lower().startswith(mod.lower()):
                modular_found = True
                if matched_modular is None:
                    matched_modular = mod
                else:
                    # Prüfen, ob aktuelles Szenario längeres Präfix ist als bisheriges Match
                    if len(mod) > len(matched_modular):
                        matched_modular = mod

        if matched_modular:
            modular_counts[matched_modular] += 1
            scenario_clean = scenario_clean[len(matched_modular):].strip()
            if matched_modular in ["Standard","Standard II","Standard III"]:
                standard_found = True
    
        if not matched_modular and len(scenario_clean)>0:
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

############################################################
# ZÄHLER INITIALISIEREN
############################################################

# Gesamtzähler pro Held
hero_counts = {hero: 0 for hero in HEROES}

# Kombinationen (Held, Aspekt)
hero_aspect_counts = {}   # key = (hero, aspect)

############################################################
# HAUPTLOGIK: HELDEN & ASPEKTE PRO PARTIE EXTRAHIEREN
############################################################

for play in all_plays:

    text = (play["hero"] or "").strip()
    text_lower = text.lower()

    # -------------------------------------------------------
    # 1) Helden mit Positionen finden
    # -------------------------------------------------------
    hero_positions = []
    for hero in HEROES:
        pos = text_lower.find(hero.lower())
        if pos != -1:
            hero_positions.append((pos, hero))

    # Wenn keine Helden gefunden → nächster Datensatz
    if not hero_positions:
        print(f"No Hero found in: {text_lower}")
        continue

    hero_positions.sort()  # nach Position

    # -------------------------------------------------------
    # 2) Aspekte mit Positionen finden
    # -------------------------------------------------------
    aspect_positions = []
    for asp in ASPECTS:
        pos = text_lower.find(asp.lower())
        if pos != -1:
            aspect_positions.append((pos, asp))

    # Wenn keine Helden gefunden → nächster Datensatz
    if not aspect_positions:
        print(f"No Aspect found in: {text_lower}")

    aspect_positions.sort()

    # -------------------------------------------------------
    # 3) Helden den richtigen Aspekt zuordnen
    # -------------------------------------------------------
    for idx, (hero_pos, hero) in enumerate(hero_positions):

        hero_counts[hero] += 1  # Gesamtzähler Held erhöhen

        # nächsten Helden finden (falls existiert)
        next_hero_pos = hero_positions[idx + 1][0] if idx + 1 < len(hero_positions) else float('inf')

        assigned_aspect = ""

        # Aspekte suchen, die:
        # pos > hero_pos  UND  pos < next_hero_pos
        possible_aspects = [
            (pos, asp) for (pos, asp) in aspect_positions
            if hero_pos < pos < next_hero_pos
        ]

        # Wenn vorhanden → der erste im Text gehört zu diesem Helden
        if possible_aspects:
            assigned_aspect = possible_aspects[0][1]

        # Zähler für Held-Aspekt-Kombination
        key = (hero, assigned_aspect)
        hero_aspect_counts[key] = hero_aspect_counts.get(key, 0) + 1

############################################################
# CSV AUSGABE 1: Gesamtzahl pro Held
############################################################

with open("heroes_total.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Hero", "Count"])

    for hero, count in sorted(hero_counts.items(), key=lambda x: x[1], reverse=True):
        writer.writerow([hero, count])

print("CSV geschrieben: heroes_total.csv")

############################################################
# CSV AUSGABE 2: Kombinationen Held + Aspekt
############################################################

with open("heroes_aspects.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Hero", "Aspect", "Count"])

    for (hero, aspect), count in sorted(hero_aspect_counts.items(), key=lambda x: x[1], reverse=True):
        writer.writerow([hero, aspect, count])

print("CSV geschrieben: heroes_aspects.csv")

# --- ASPEKT-STATISTIK --- #

ASPECTS = ["Aggression", "Justice", "Leadership ", "Protection", "'Pool", "Basic", "Precon"]

aspect_counts = {asp: 0 for asp in ASPECTS}

for play in all_plays:
    hero_text = (play["hero"] or "").lower()

    for asp in ASPECTS:
        # Anzahl der Vorkommen zählen (case-insensitive)
        count = hero_text.count(asp.lower())
        aspect_counts[asp] += count

# Sortieren nach Anzahl (absteigend)
sorted_aspect_stats = sorted(
    aspect_counts.items(),
    key=lambda x: x[1],
    reverse=True
)

# CSV schreiben
OUTFILE_ASPECTS = "marvel_champions_aspect_stats.csv"
with open(OUTFILE_ASPECTS, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(["aspect", "count"])
    writer.writerows(sorted_aspect_stats)

print(f"Aspekt-Statistik gespeichert als: {OUTFILE_ASPECTS}")


print(f"FERTIG! Datei gespeichert als: {OUTFILE}")
