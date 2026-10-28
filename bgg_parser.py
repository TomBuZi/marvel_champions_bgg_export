"""BGG-Abruf und Kommentar-Parser für Marvel-Champions-Partien.

Wird von BGG_Export.py (Statistiken) und vom Tracker-Sync (mc-tracker-sync) gemeinsam genutzt,
damit beide Seiten Helden, Aspekte, Szenarien und Modulars identisch erkennen.
"""

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

USERNAME  = os.environ.get("BGG_USERNAME", "Almecho")
MY_USERID = "250203"             # Eigene BGG-User-ID — wird bei Mehrspielerparten genutzt
GAME_ID   = 285774               # Marvel Champions

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

# Schlagwörter, mit denen eine Partie im Kommentar als Kampagnen-Partie markiert wird
CAMPAIGN_TAG_WORDS = ("campaign", "kampagne")

# Schlagwörter im Szenariofeld, die keine Modulars sind (z. B. "... The Owl Campaign - lost")
MODULAR_NOISE_WORDS = set(CAMPAIGN_TAG_WORDS)

WIN_KEYWORDS  = {"won", "win", "sieg", "victory", "gewonnen"}
LOSS_KEYWORDS = {"lost", "loss", "lose", "defeat", "verloren", "niederlage"}

# HTTP-Status, bei denen BGG später erneut gefragt werden soll (202 = Anfrage in Warteschlange)
RETRY_STATUS = {202, 429, 500, 502, 503, 504}


def has_campaign_tag(comments_lower):
    """True, wenn der (bereits kleingeschriebene) Kommentar die Partie als Kampagnen-Partie markiert."""
    return any(w in comments_lower for w in CAMPAIGN_TAG_WORDS)

def difficulty_from_comments(comments_lower):
    """Erkennt den Schwierigkeitsgrad aus dem Kommentar-Text (lowercase).

    Reihenfolge: längste Variante zuerst, um Überschneidungen zu vermeiden
    (z.B. 'expert ii' vor 'expert').  Wenn kein Marker gefunden wird → 'Standard'.
    """
    for marker, label in [
        ("expert ii",    "Expert II"),
        ("expert",       "Expert"),
        ("standard iii", "Standard III"),
        ("standard ii",  "Standard II"),
        ("standard",     "Standard"),
    ]:
        if marker in comments_lower:
            return label
    return "Standard"

def classify_result(play):
    """'win', 'loss' oder 'incomplete' aus dem Ergebnisteil des Kommentars (Unklares = ungewertet)."""
    if str(play.get("incomplete", "0")) == "1":
        return "incomplete"
    result_lower = (play.get("result") or "").strip().lower()
    if result_lower in WIN_KEYWORDS or any(result_lower.startswith(k) for k in WIN_KEYWORDS):
        return "win"
    if result_lower in LOSS_KEYWORDS or any(result_lower.startswith(k) for k in LOSS_KEYWORDS):
        return "loss"
    return "incomplete"  # Unklar → als ungewertet behandeln

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

def find_longest_prefix_match(text, candidates):
    """Find the candidate whose name is the longest prefix match for text (case-insensitive)."""
    text_lower = text.strip().lower()
    best = None
    for candidate in candidates:
        if text_lower.startswith(candidate.lower()):
            if best is None or len(candidate) > len(best):
                best = candidate
    return best

def assign_hero_aspects(hero_text):
    """Ordnet jedem Helden im Heldentext seine Aspekte zu.

    Liefert eine Liste in Textreihenfolge mit je
      hero      – Treffer aus heroes.json
      canonical – kanonischer Name (hero_aliases.json)
      aspects   – zugeordnete Aspekte; Multi-Aspekt-Helden (hero_default_aspects.json) bekommen alle
                  gefundenen bzw. ihre Defaults, alle anderen den ersten gefundenen bzw. 'Precon'
      leftover  – Text im Aspekt-Bereich, der kein bekannter Aspekt ist ("" wenn keiner)
    """
    text_lower = hero_text.strip().lower()

    # Alle Helden-Positionen finden, überlappende entfernen
    hero_positions = find_all_hero_positions(text_lower, HEROES)
    hero_positions = remove_covered_matches(hero_positions)
    hero_positions.sort()

    # Aspekte mit Positionen finden
    aspect_positions = []
    for asp in ASPECTS:
        for match in re.finditer(re.escape(asp.lower()), text_lower):
            aspect_positions.append((match.start(), asp))

    aspect_positions.sort()

    # Helden den richtigen Aspekt zuordnen
    assigned = []
    for idx, (hero_pos, hero) in enumerate(hero_positions):

        canonical = HERO_ALIASES.get(hero, hero)
        next_hero_pos = hero_positions[idx + 1][0] if idx + 1 < len(hero_positions) else float('inf')

        possible_aspects = list(dict.fromkeys(
            asp for pos, asp in aspect_positions
            if hero_pos < pos < next_hero_pos
        ))

        if canonical in HERO_DEFAULT_ASPECTS:
            # Multi-aspect hero: use all found aspects; fall back to defaults if none found
            aspects = possible_aspects or HERO_DEFAULT_ASPECTS[canonical]
        else:
            # Regular hero: use first found aspect only; fall back to Precon if none found
            aspects = [possible_aspects[0]] if possible_aspects else ["Precon"]

        # Nicht-erkannte Aspekte: Text im Aspekt-Bereich, der kein bekannter Aspekt ist
        leftover = ""
        hero_end_pos = hero_pos + len(hero)
        region_end   = int(next_hero_pos) if next_hero_pos != float('inf') else len(text_lower)
        if hero_end_pos < region_end:
            leftover = text_lower[hero_end_pos:region_end]
            for pos, asp in aspect_positions:
                if hero_pos < pos < next_hero_pos:
                    leftover = leftover.replace(asp.lower(), '', 1)
            leftover = re.sub(r'[\s,&+\-–|/]+', ' ', leftover).strip()

        assigned.append({"hero": hero, "canonical": canonical,
                         "aspects": list(aspects), "leftover": leftover})
    return assigned

def match_scenario_and_modulars(scenario_text):
    """Erkennt Szenario und Modulars im Szenarioteil eines Kommentars.

    Modular-Reihenfolge: explizit im Kommentar → Default-Modulars (nur wenn höchstens
    Schwierigkeitsgrade notiert sind) → Auto-Modulars des Szenarios → 'Standard'-Fallback.
    Liefert ein Dict mit
      scenario          – kanonischer Szenarioname oder None
      modulars          – Originalnamen in Reihenfolge der Zählung
      unknown_words     – nicht erkannte Wörter im Modular-Teil
      modulars_missing  – bekanntes Szenario, aber weder explizite noch Default-/Auto-Modulars
    """
    scenario_clean = scenario_text.strip().lower()

    # Längstes Match ermitteln
    matched_scenario = find_longest_prefix_match(scenario_clean, SCENARIOS)
    if matched_scenario:
        scenario_clean = scenario_clean[len(matched_scenario):].strip()

    # Suchen nach Modulars, Wort für Wort
    modulars            = []      # Originalnamen in Reihenfolge der Zählung
    matched_in_comments = set()   # Lowercase-Set für Deduplizierung
    unknown_words       = []

    def add(mod):
        modulars.append(mod)
        matched_in_comments.add(mod.lower())

    while scenario_clean:
        # Führende Trennzeichen (Leerzeichen, +, Komma, Satzzeichen) überspringen.
        # Satzzeichen deckt Szenarien ab, die im Kommentar mit "!" o. Ä. notiert sind
        # (z. B. "Stop the Presses!" bei Szenarioname "Stop the Presses").
        scenario_clean = re.sub(r'^[\s+,!?.:;]+', '', scenario_clean)
        if not scenario_clean:
            break

        matched_modular = find_longest_prefix_match(scenario_clean, MODULARS)
        if matched_modular:
            add(matched_modular)
            scenario_clean = scenario_clean[len(matched_modular):]
        else:
            # Erstes Wort nicht erkannt → einzeln melden, nächstes Wort versuchen
            m = re.match(r'(\S+)(.*)', scenario_clean, re.DOTALL)
            if m:
                word = m.group(1)
                # Schlagwörter wie "Campaign" überspringen, ohne sie zu melden
                if word.strip('!?.:;,').lower() not in MODULAR_NOISE_WORDS:
                    unknown_words.append(word)
                scenario_clean = m.group(2)
            else:
                break

    # Default-Modulars: wenn nichts oder nur Schwierigkeitsgrad-Modulars im Kommentar standen
    if matched_scenario and matched_in_comments.issubset(DIFFICULTY_MODULARS):
        for def_mod in SCENARIO_DEFAULT_MODULARS.get(matched_scenario, []):
            if def_mod.lower() not in matched_in_comments:
                add(def_mod)

    # Automatisch inkludierte Modulars: immer ergänzen (sofern nicht schon gezählt)
    if matched_scenario:
        for auto_mod in SCENARIO_MODULARS.get(matched_scenario, []):
            if auto_mod.lower() not in matched_in_comments:
                add(auto_mod)

    # Fehlende Modulars: nur wenn nach beiden Schritten immer noch nichts gezählt wurde
    modulars_missing = bool(matched_scenario) and not matched_in_comments

    if not any(mod in ("Standard", "Standard II", "Standard III") for mod in modulars):
        add("Standard")

    return {"scenario": matched_scenario, "modulars": modulars,
            "unknown_words": unknown_words, "modulars_missing": modulars_missing}

def fetch_page(username, game_id, page, retries=5):
    url = (
        f"https://boardgamegeek.com/xmlapi2/plays?"
        f"username={username}&id={game_id}&type=thing&page={page}"
    )

    cookies = {
        "SessionID":  os.environ.get("BGG_SESSION_ID", ""),
        "bggpassword": os.environ.get("BGG_PASSWORD", ""),
        "bggusername": os.environ.get("BGG_USERNAME", username),
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    # Optional: Token einer registrierten BGG-Anwendung (boardgamegeek.com/applications)
    token = os.environ.get("BGG_API_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(retries):
        r = requests.get(url, cookies=cookies, headers=headers, timeout=60)
        if r.status_code not in RETRY_STATUS or attempt == retries - 1:
            break
        time.sleep(5 * 2 ** attempt)  # BGG drosselt — exponentiell länger warten
    if r.status_code == 202:
        raise RuntimeError(f"BGG hat Seite {page} auch nach {retries} Versuchen nicht geliefert (202)")
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

def play_comment(play):
    """Kommentar einer Partie: HTML-Entities aufgelöst, Zeilenumbrüche zu Leerzeichen, Anführungszeichen entfernt."""
    comments = (play.find("comments").text or "") if play.find("comments") is not None else ""
    comments = html.unescape(comments)
    return comments.replace("\n", " ").replace("\r", " ").strip().strip('"').strip()

def extract_play_data(play):
    comments = play_comment(play)

    hero, scenario, result = split_comment(comments)

    # Bei Mehrspielerparten: nur den Helden von MY_USERID berücksichtigen.
    # BGG listet jeden Mitspieler als <player>-Element; der gespielte Held
    # steht im Attribut "color".  Bei Einzelpartien bleibt der aus dem
    # Kommentar geparste Held unverändert.
    players_el = play.find("players")
    if players_el is not None:
        all_players = players_el.findall("player")
        if len(all_players) > 1:
            for p in all_players:
                if p.attrib.get("userid") == MY_USERID:
                    color = (p.attrib.get("color") or "").strip()
                    if color:
                        hero = color
                    break

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

def parse_play(play):
    """Vollständig aufgelöste Partie für den Tracker-Sync.

    Im Unterschied zu extract_play_data stehen hier ALLE Helden der Partie (aus dem Kommentar,
    ergänzt um Mitspieler-Helden aus dem color-Attribut, die im Kommentar fehlen). 'is_mine'
    markiert die Helden des eigenen Players (MY_USERID); bei Einzelpartien sind es alle.
    'problems' sammelt alles, was nicht eindeutig erkannt wurde.
    """
    comments = play_comment(play)
    comments_lower = comments.lower()
    hero_text, scenario_text, result_text = split_comment(comments)
    problems = []

    players = play.findall("players/player")
    my_heroes = None  # None = Einzelpartie → alle Helden gehören mir
    other_heroes = []
    if len(players) > 1:
        my_heroes = set()
        for p in players:
            color = (p.attrib.get("color") or "").strip()
            found = [HERO_ALIASES.get(h, h) for _, h in
                     remove_covered_matches(find_all_hero_positions(color.lower(), HEROES))]
            if p.attrib.get("userid") == MY_USERID:
                my_heroes.update(found)
            else:
                other_heroes.extend(found)

    heroes = []
    for entry in assign_hero_aspects(hero_text):
        if entry["leftover"]:
            problems.append(f"Aspekt nicht erkannt: {entry['leftover']!r}")
        heroes.append({"hero": entry["canonical"], "aspects": entry["aspects"],
                       "is_mine": my_heroes is None or entry["canonical"] in my_heroes})
    if hero_text and not heroes:
        problems.append(f"Held nicht erkannt: {hero_text!r}")
    for hero in other_heroes:
        if all(h["hero"] != hero for h in heroes):
            heroes.append({"hero": hero, "aspects": [], "is_mine": False})
    if heroes and not any(h["is_mine"] for h in heroes):
        heroes[0]["is_mine"] = True
        problems.append("Eigener Held nicht bestimmbar — erster Held als eigener markiert")

    matched = match_scenario_and_modulars(scenario_text)
    if not matched["scenario"]:
        problems.append(f"Szenario nicht erkannt: {scenario_text!r}")
    for word in matched["unknown_words"]:
        problems.append(f"Modular nicht erkannt: {word!r}")

    return {
        "id":          play.attrib.get("id"),
        "date":        play.attrib.get("date"),
        "length":      int(play.attrib.get("length") or 0),
        "comment":     comments,
        "heroes":      heroes,
        "scenario":    matched["scenario"],
        "modulars":    matched["modulars"],
        "difficulty":  difficulty_from_comments(comments_lower),
        "result":      classify_result({"incomplete": play.attrib.get("incomplete"),
                                        "result": result_text}),
        "is_campaign": has_campaign_tag(comments_lower),
        "problems":    problems,
    }
