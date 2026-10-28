import json
import sys
import csv
import time
from datetime import datetime, timezone

from bgg_parser import (
    USERNAME, MY_USERID, GAME_ID, load_config,
    HEROES, ASPECTS, SCENARIOS, MODULARS, HERO_ALIASES,
    difficulty_from_comments, has_campaign_tag, classify_result,
    find_all_hero_positions, remove_covered_matches, find_longest_prefix_match,
    assign_hero_aspects, match_scenario_and_modulars,
    fetch_page, parse_plays, extract_play_data,
)

OUTFILE = "marvel_champions_plays.csv"

CAMPAIGNS                 = load_config("campaigns.json")

def _normalize_campaign(spec):
    """Bringt die Kampagnenformen aus campaigns.json auf ein einheitliches Spec-Dict.

    Liste                    -> sequenzielle Kampagne: die Szenarien werden der Reihe nach gewonnen.
    Objekt mit 'scenarios'   -> ebenfalls sequenziell, nur als Objekt geschrieben, damit
                                zusätzliche Flags (require_tag) gesetzt werden können.
    Objekt mit 'pool'        -> Pool-Kampagne: beliebig viele Partien in zufälliger Reihenfolge
                                aus 'pool', danach das 'finale'-Szenario.  Ein gewonnenes
                                Pool-Szenario ist verbraucht und kann im selben Durchlauf
                                nicht erneut gespielt werden.

    'require_tag': nur ausdrücklich markierte Partien (Kommentar enthält 'campaign' bzw.
    'kampagne', siehe has_campaign_tag) zählen für diese Kampagne. Für Pool-Kampagnen ist
    das praktisch Pflicht: ohne feste Reihenfolge gibt es kein strukturelles Erkennungs-
    merkmal, jede freie Partie auf einem Pool-Szenario würde sonst in den laufenden
    Versuch gezogen.
    """
    if isinstance(spec, list):
        return {"mode": "sequential", "scenarios": spec, "require_tag": False}

    require_tag = bool(spec.get("require_tag"))

    if "pool" not in spec:
        return {"mode": "sequential", "scenarios": spec["scenarios"], "require_tag": require_tag}

    pool   = spec["pool"]
    finale = spec["finale"]
    return {
        "mode":      "pool",
        # Anzeigereihenfolge; scen_list[-1] muss das Finale sein (siehe _classify_incomplete)
        "scenarios": pool + [finale],
        "pool":      set(pool),
        "finale":    finale,
        "require_tag": require_tag,
    }

CAMPAIGN_SPECS = {_name: _normalize_campaign(_spec) for _name, _spec in CAMPAIGNS.items()}


def _play_id(play):
    """Play-ID als Zahl. BGG liefert sie als String-Attribut, sie kann fehlen."""
    try:
        return int(play["id"])
    except (KeyError, TypeError, ValueError):
        return 0


def sort_plays_for_output(plays, spec):
    """Anzeigereihenfolge der Partien eines Versuchs für das CSV-Feld scenarios_played.

    Sortiert nach Datum, dann Position des Szenarios innerhalb des Tages, dann Play-ID
    (aufsteigende ID = später erfasst). Innerhalb DERSELBEN (Tag, Szenario)-Gruppe kommt die
    gewonnene Partie zuletzt: wer ein Szenario an einem Tag mehrfach spielt, hat es verloren
    und wiederholt, der Sieg beendet es.

    Der Sieg-Rang steht bewusst NACH der Szenario-Position. Damit ist (date, scen_pos) ein
    Präfix des Schlüssels und der Rang wird nur zwischen Partien derselben Gruppe überhaupt
    verglichen. Stünde er davor, sortierte er Niederlagen *fremder* Szenarien vor die Siege:
        Rang vor Szenario-Position:  A/loss, B/loss, A/win   (falsch)
        Szenario-Position zuerst:    A/loss, A/win,  B/loss  (richtig)

    Szenario-Position je Modus:
      sequenziell -> Index in der Konfig-Reihenfolge (so gespielt, so angezeigt)
      pool        -> kleinste Play-ID desselben Szenarios an diesem Tag. Die Konfig-
                     Reihenfolge ist dort bedeutungslos (freie Szenariowahl), die
                     Erfassungsreihenfolge ist der einzige Anker. Der Anker gruppiert
                     zugleich Wiederholungen desselben Szenarios, damit "Sieg zuletzt"
                     überhaupt eine Gruppe hat, auf die es sich beziehen kann.

    Reine AUSGABE-Sortierung. Die beiden Vorsortierungen der Segmentierung
    (plays_list.sort(...)) dürfen nicht so umgestellt werden — siehe die Warnungen dort.

    Visualize5.py übernimmt diese Reihenfolge unverändert und spreizt Partien desselben Tages
    in genau dieser Folge auf; die Reihenfolge im CSV ist also bedeutungstragend.
    """
    if spec.get("mode") == "pool":
        anchor = {}
        for p in plays:
            key = (p["date"], p["scenario"])
            pid = _play_id(p)
            if key not in anchor or pid < anchor[key]:
                anchor[key] = pid
        scen_pos = lambda p: anchor[(p["date"], p["scenario"])]
    else:
        idx = {s: i for i, s in enumerate(spec.get("scenarios", []))}
        scen_pos = lambda p: idx.get(p["scenario"], len(idx))

    return sorted(plays, key=lambda p: (p["date"], scen_pos(p),
                                        p["result"] == "win", _play_id(p)))


# Gewünschte Reihenfolge der Schwierigkeitsgrade in Modularkombinationen
_DIFFICULTY_ORDER = ["Standard", "Standard II", "Standard III", "Expert", "Expert II"]
_DIFFICULTY_RANK  = {m.lower(): i for i, m in enumerate(_DIFFICULTY_ORDER)}

def sort_modular_combo(modular_name):
    """Sortierschlüssel: Schwierigkeitsgrade zuerst (in fester Reihenfolge), dann alphabetisch."""
    key = modular_name.lower()
    if key in _DIFFICULTY_RANK:
        return (0, _DIFFICULTY_RANK[key], "")
    return (1, 0, modular_name.lower())

if __name__ == "__main__":

    all_plays = []
    page = 1
    total_plays = None

    plays_no_hero     = []  # (date, "", comment) — Heldenfeld komplett leer
    plays_no_villain  = []  # (date, "", comment) — Szenariofeld komplett leer
    unknown_heroes    = []  # (date, raw_text, comment) — Heldentext vorhanden, aber nicht erkannt
    unknown_aspects   = []  # (date, raw_text, comment) — Text im Aspekt-Bereich, der kein bekannter Aspekt ist
    unknown_scenarios = []  # (date, raw_text, comment) — Szenariotext vorhanden, aber nicht erkannt
    unknown_modulars  = []  # (date, raw_text, comment)
    missing_modulars  = []  # (date, scenario, comment) — bekanntes Szenario, kein Modular im Kommentar
    player_mismatches = []  # (date, info, comment) — Abweichung zwischen Player-color und Kommentar

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
            play_data = extract_play_data(p)
            all_plays.append(play_data)

            # Player-Konsistenzcheck: läuft für alle Partien mit <players>-Block,
            # unabhängig von der Spieleranzahl.
            # (Die Datenextraktion — color statt Kommentar — findet nur bei
            # Mehrspielerparten statt, siehe extract_play_data.)
            _players_el = p.find("players")
            if _players_el is None:
                continue
            _all_players = _players_el.findall("player")

            _date    = play_data.get("date", "?")
            _comment = play_data.get("comments", "")
            _my_p    = next(
                (pl for pl in _all_players if pl.attrib.get("userid") == MY_USERID),
                None
            )

            if _my_p is None:
                _others = ", ".join(
                    pl.attrib.get("name") or pl.attrib.get("username") or "?"
                    for pl in _all_players
                )
                player_mismatches.append((_date, f"Eigener Player fehlt — Player: {_others}", _comment))
                continue

            _color_raw = _my_p.attrib.get("color")   # None = Attribut fehlt, "" = leer
            if _color_raw is None:
                player_mismatches.append((_date, "color-Attribut fehlt (kein Held eingetragen)", _comment))
                continue
            _color = _color_raw.strip()
            if not _color:
                player_mismatches.append((_date, "color leer (kein Held eingetragen)", _comment))
                continue

            # Helden aus color und aus Kommentar per Hero-Matching vergleichen
            _color_pos   = remove_covered_matches(find_all_hero_positions(_color.lower(),   HEROES))
            _comment_pos = remove_covered_matches(find_all_hero_positions(_comment.lower(), HEROES))
            _color_heroes   = [h for _, h in _color_pos]
            _comment_heroes = {h for _, h in _comment_pos}

            if not _color_heroes:
                player_mismatches.append((_date, f"Held in color nicht erkannt: \"{_color}\"", _comment))
                continue

            _missing = [h for h in _color_heroes if h not in _comment_heroes]
            if _missing:
                if len(_missing) == len(_color_heroes):
                    _info = f"Held(en) aus color nicht im Kommentar: \"{_color}\""
                else:
                    _info = f"Teilweise nicht im Kommentar: {', '.join(_missing)} (color: \"{_color}\")"
                player_mismatches.append((_date, _info, _comment))

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
            modular_counts["Standard"] = modular_counts.get("Standard", 0) + 1
            continue

        # Szenario + Modulars auflösen (explizit → Default → Auto → Standard-Fallback)
        resolved          = match_scenario_and_modulars(scenario_clean)
        matched_scenario  = resolved["scenario"]
        counted_this_play = resolved["modulars"]

        if matched_scenario:
            scenario_counts[matched_scenario] += 1
        else:
            scenario_counts["unknown scenario"] += 1
            unknown_scenarios.append((play["date"], play["scenario"], play["comments"]))

        for word in resolved["unknown_words"]:
            unknown_modulars.append((play["date"], word, play["comments"]))

        # Hinweis: Namen aus scenario_modulars.json / scenario_default_modulars.json, die in
        # modulars.json fehlen, legen hier stillschweigend einen neuen Statistik-Eintrag an.
        for mod in counted_this_play:
            modular_counts[mod] = modular_counts.get(mod, 0) + 1

        if resolved["modulars_missing"]:
            missing_modulars.append((play["date"], matched_scenario, play["comments"]))

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

        # Helden finden und ihnen die Aspekte zuordnen
        assigned = assign_hero_aspects(text)

        if not assigned:
            unknown_heroes.append((play["date"], text, play["comments"]))
            continue

        for entry in assigned:

            canonical = entry["canonical"]
            hero_counts[canonical] += 1
            date = play["date"] or ""
            if date and (canonical not in hero_first_played or date < hero_first_played[canonical]):
                hero_first_played[canonical] = date

            for asp in entry["aspects"]:
                key = (canonical, asp)
                hero_aspect_counts[key] = hero_aspect_counts.get(key, 0) + 1

            # Nicht-erkannte Aspekte: Text im Aspekt-Bereich, der kein bekannter Aspekt ist
            if entry["leftover"]:
                unknown_aspects.append((play["date"], entry["leftover"], play["comments"]))

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

    # --- KAMPAGNEN-ERKENNUNG --- #
    # Gespielte Kampagnen (Versuche) aus der chronologischen Spielhistorie ableiten
    # und pro (Heldenkombination, Kampagne) in Versuche aufteilen.

    from collections import defaultdict as _defaultdict
    from datetime import datetime as _dt

    # Szenario → Liste der Kampagnen, zu denen es gehört
    _scen_to_campaigns = {}
    for _camp, _spec in CAMPAIGN_SPECS.items():
        for _s in _spec["scenarios"]:
            _scen_to_campaigns.setdefault(_s, []).append(_camp)

    # (combo, campaign) → Liste von Play-Dicts
    _campaign_plays = _defaultdict(list)

    # Kampagne → Anzahl verworfener Partien ohne Kampagnen-Markierung (nur bei require_tag)
    _skipped_untagged = _defaultdict(int)

    for play in all_plays:
        _matched = find_longest_prefix_match(play["scenario"].strip(), SCENARIOS)
        if not _matched or _matched not in _scen_to_campaigns:
            continue

        _text_lower = (play.get("hero") or "").strip().lower()
        _positions  = find_all_hero_positions(_text_lower, HEROES)
        _positions  = remove_covered_matches(_positions)
        _combo      = tuple(sorted({HERO_ALIASES.get(h, h) for _, h in _positions}))
        if not _combo:
            continue

        _date = play.get("date") or ""
        if not _date:
            continue

        _res = classify_result(play)

        _comments = (play.get("comments") or "").lower()
        _diff     = difficulty_from_comments(_comments)
        _tagged   = has_campaign_tag(_comments)
        for _camp in _scen_to_campaigns[_matched]:
            # Kampagnen ohne feste Szenarioreihenfolge (require_tag) haben kein strukturelles
            # Erkennungsmerkmal — dort zählt nur eine ausdrücklich markierte Partie. Der Filter
            # greift schon hier und nicht erst in _qualifies: eine ungetaggte Partie darf gar
            # nicht Teil eines Versuchs werden, sonst verschiebt sie Versuchsgrenzen
            # (GAP_DAYS, won_pool, finale_played) und den play_count.
            if CAMPAIGN_SPECS[_camp].get("require_tag") and not _tagged:
                _skipped_untagged[_camp] += 1
                continue
            _campaign_plays[(_combo, _camp)].append({
                "date":       _date,
                "id":         play.get("id"),
                "scenario":   _matched,
                "result":     _res,
                "comments":   _comments,
                "difficulty": _diff,
            })

    # Spätestes Spieldatum im Gesamtdatensatz — für "in_progress" vs "abandoned"
    _all_dates = [p.get("date") for p in all_plays if p.get("date")]
    _max_date_str = max(_all_dates) if _all_dates else ""
    try:
        _max_dt = _dt.strptime(_max_date_str, "%Y-%m-%d")
    except ValueError:
        _max_dt = None

    def _finalize_attempt(att, status):
        att["status"]     = status
        att["start_date"] = att["plays"][0]["date"]
        att["end_date"]   = att["plays"][-1]["date"]

    campaign_attempts = []

    def _classify_incomplete(att, scen_list, still_recent=False):
        """Gibt 'in_progress', 'lost' oder 'abandoned' zurück.

        'lost': Expert/Expert-II-Partie, die am letzten Szenario der Kampagne
        scheiterte — die Kampagne gilt als gespielt und verloren, nicht als
        abgebrochen.  Diese Prüfung hat Vorrang vor 'still_recent', da eine
        Niederlage am letzten Szenario die Kampagne definitiv beendet.
        """
        last_scen = scen_list[-1]
        last_plays = [p for p in att["plays"] if p["scenario"] == last_scen]
        if (last_plays
                and any(p["result"] == "loss" for p in last_plays)
                and "expert" in att.get("difficulty", "").lower()):
            return "lost"
        if still_recent:
            return "in_progress"
        return "abandoned"

    def _qualifies(att, scen_list):
        """Gibt True zurück, wenn der Versuch als Kampagne zählt.

        Bedingung: mindestens die Hälfte der Szenarien wurde gespielt (egal ob
        Sieg oder Niederlage) ODER mindestens ein Play-Kommentar ist als
        Kampagnen-Partie markiert.  Andernfalls gilt es als Einzel-Szenario
        ohne Kampagnenbezug und wird aus der Visualisierung ausgeschlossen.

        Bei require_tag-Kampagnen ist die zweite Bedingung immer erfüllt — dort sind
        ungetaggte Partien schon vorher aussortiert.  Das ist gewollt: ein einzelner
        markierter Pool-Abend soll als laufender Versuch sichtbar sein.
        """
        unique_played = len(set(p["scenario"] for p in att["plays"]))
        if unique_played >= len(scen_list) / 2:
            return True
        return any(has_campaign_tag(p.get("comments", "")) for p in att["plays"])

    # Zwei Plays gehören zum selben Versuch, wenn sie < GAP_DAYS Tage auseinander liegen.
    # Größere Lücken → alter Versuch wird als abgebrochen markiert, neuer beginnt.
    GAP_DAYS = 60

    def _days_since_last(att, play):
        """Tage zwischen der letzten akzeptierten Partie des Versuchs und play."""
        try:
            _prev_dt = _dt.strptime(att["plays"][-1]["date"], "%Y-%m-%d")
            _play_dt = _dt.strptime(play["date"],             "%Y-%m-%d")
            return (_play_dt - _prev_dt).days
        except ValueError:
            return 0

    def _segment_pool_campaign(combo, camp_name, spec, plays_list):
        """Versuchserkennung für Pool-Kampagnen (z. B. Fear no Evil).

        Anders als bei sequenziellen Kampagnen gibt es keine feste Reihenfolge und keine
        feste Partienzahl — es wird daher nichts gezählt.  Die Abgrenzung zweier Durchläufe
        ergibt sich aus der Spielregel, dass ein gewonnenes Pool-Szenario verbraucht ist:
        taucht es erneut auf, muss ein neuer Durchlauf begonnen haben.
        """
        scen_list = spec["scenarios"]
        finale    = spec["finale"]

        # Datum, dann Play-ID (Erfassungsreihenfolge) — die Konfig-Reihenfolge wäre hier
        # als Tiebreaker falsch, da die Szenarien in zufälliger Reihenfolge gespielt werden.
        # NICHT auf die Anzeigereihenfolge (sort_plays_for_output) umstellen: das hier ist die
        # Eingabe der State Machine, eine Änderung verschiebt Versuchsgrenzen und Status.
        plays_list.sort(key=lambda p: (p["date"], int(p["id"] or 0)))

        current       = None
        won_pool      = set()   # gewonnene Pool-Szenarien → dürfen nicht wiederkehren
        finale_played = False
        current_diff  = None

        def _close(status):
            nonlocal current, won_pool, finale_played, current_diff
            _finalize_attempt(current, status)
            if _qualifies(current, scen_list):
                campaign_attempts.append(current)
            current       = None
            won_pool      = set()
            finale_played = False
            current_diff  = None

        for play in plays_list:
            scen      = play["scenario"]
            is_finale = scen == finale
            play_diff = play["difficulty"]

            # Laufenden Versuch beenden, wenn er nicht zu dieser Partie passen kann
            if current is not None:
                if (_days_since_last(current, play) > GAP_DAYS
                        or (not is_finale and scen in won_pool)
                        or (not is_finale and finale_played)):
                    _close(_classify_incomplete(current, scen_list))

            if current is None:
                # Ein Finale ohne vorangehenden Durchlauf startet keinen Versuch
                if is_finale:
                    continue
                current      = {"campaign": camp_name, "heroes": list(combo),
                                "plays": [], "difficulty": play_diff}
                current_diff = play_diff
            elif play_diff != current_diff:
                # Wie im sequenziellen Pfad: abweichende Schwierigkeit wird ignoriert
                continue

            current["plays"].append(play)

            if is_finale:
                finale_played = True
                if play["result"] == "win":
                    _close("completed")
                # Niederlage am Finale hält den Versuch offen (Wiederholung möglich)
            elif play["result"] == "win":
                won_pool.add(scen)

        if current is not None:
            try:
                _last_dt = _dt.strptime(current["plays"][-1]["date"], "%Y-%m-%d")
            except ValueError:
                _last_dt = None
            _still_recent = bool(_max_dt and _last_dt and (_max_dt - _last_dt).days <= 90)
            _close(_classify_incomplete(current, scen_list, _still_recent))

    # State Machine pro (combo, campaign): Plays chronologisch in Versuche aufteilen
    for (combo, camp_name), plays_list in _campaign_plays.items():
        _spec = CAMPAIGN_SPECS[camp_name]
        if _spec["mode"] == "pool":
            _segment_pool_campaign(combo, camp_name, _spec, plays_list)
            continue

        # Sekundärer Sortierschlüssel: Szenario-Index in der Kampagne.
        # BGG liefert bei mehreren Plays am gleichen Tag keine garantierte Reihenfolge;
        # für Kampagnen-Versuche ist die natürliche Szenarioreihenfolge zuverlässiger.
        #
        # ACHTUNG, keinen Play-ID-Tiebreaker ergänzen: der Sort ist stabil, innerhalb einer
        # (Datum, Szenario-Index)-Gruppe gilt damit die BGG-Reihenfolge (ID absteigend). Bei
        # mehrfach gespieltem Szenario kommt so der Sieg zuerst, hebt current_idx und die
        # Wiederholungen fallen unten in "if scen_idx < current_idx: continue". Aufsteigend
        # sortiert würden sie stattdessen angehängt und play_count stiege.
        # Die Anzeigereihenfolge macht sort_plays_for_output erst beim CSV-Schreiben.
        _scen_idx_map = {s: i for i, s in enumerate(_spec["scenarios"])}
        plays_list.sort(key=lambda p: (p["date"], _scen_idx_map.get(p["scenario"], 999)))
        scen_list = _spec["scenarios"]

        current      = None
        current_idx  = 0     # Index des als Nächstes zu gewinnenden Szenarios
        current_diff = None  # Schwierigkeitsgrad des laufenden Versuchs

        for play in plays_list:
            try:
                scen_idx = scen_list.index(play["scenario"])
            except ValueError:
                continue

            play_diff = play["difficulty"]

            # Prüfen, ob ein laufender Versuch beendet werden muss:
            #  - Zeitlücke > GAP_DAYS
            #  - Neustart ab Szenario 0 nach Fortschritt
            #  - Szenario übersprungen (scen_idx > current_idx = fehlende Partie in der Reihenfolge)
            # Schwierigkeitswechsel beendet den Versuch NICHT direkt — eine Partie mit
            # falscher Schwierigkeit am richtigen Szenarienplatz wird stattdessen ignoriert.
            if current is not None:
                try:
                    _prev_dt = _dt.strptime(current["plays"][-1]["date"], "%Y-%m-%d")
                    _play_dt = _dt.strptime(play["date"],                  "%Y-%m-%d")
                    _gap     = (_play_dt - _prev_dt).days
                except ValueError:
                    _gap = 0
                if (_gap > GAP_DAYS
                        or (scen_idx == 0 and current_idx > 0)
                        or scen_idx > current_idx):
                    _finalize_attempt(current, _classify_incomplete(current, scen_list))
                    if _qualifies(current, scen_list):
                        campaign_attempts.append(current)
                    current      = None
                    current_idx  = 0
                    current_diff = None

            if current is None:
                # Neuer Versuch nur starten, wenn das erste Szenario der Kampagne gespielt wird
                if scen_idx != 0:
                    continue
                current      = {"campaign": camp_name, "heroes": list(combo), "plays": [], "difficulty": play_diff}
                current_idx  = 0
                current_diff = play_diff
            else:
                # Laufender Versuch: Partien mit falscher Schwierigkeit oder bereits
                # gewonnenen Szenarien (Wiederholungen) werden stillschweigend ignoriert.
                if scen_idx < current_idx or play_diff != current_diff:
                    continue

            current["plays"].append(play)

            # Fortschritt nur bei Sieg auf dem nächsten erwarteten Szenario.
            # Siege auf späteren Szenarien (übersprungen) oder bereits gewonnenen
            # Szenarien verändern den Fortschritt nicht.
            if play["result"] == "win" and scen_idx == current_idx:
                current_idx += 1

            if current_idx >= len(scen_list):
                _finalize_attempt(current, "completed")
                if _qualifies(current, scen_list):
                    campaign_attempts.append(current)
                current     = None
                current_idx = 0

        if current is not None:
            try:
                _last_dt = _dt.strptime(current["plays"][-1]["date"], "%Y-%m-%d")
            except ValueError:
                _last_dt = None
            _still_recent = bool(_max_dt and _last_dt and (_max_dt - _last_dt).days <= 90)
            _finalize_attempt(current, _classify_incomplete(current, scen_list, _still_recent))
            if _qualifies(current, scen_list):
                campaign_attempts.append(current)

    # Sortierung: Kampagnen in Konfig-Reihenfolge, dann Startdatum aufsteigend
    _camp_order = {c: i for i, c in enumerate(CAMPAIGNS)}
    campaign_attempts.sort(key=lambda a: (_camp_order.get(a["campaign"], 9999), a["start_date"]))

    OUTFILE_CAMPAIGNS = "marvel_champions_campaigns.csv"
    with open(OUTFILE_CAMPAIGNS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "campaign", "heroes", "difficulty", "start_date", "end_date", "status",
            "play_count", "scenarios_played",
        ])
        for att in campaign_attempts:
            heroes_str = " & ".join(att["heroes"])
            # Ausgabereihenfolge ist bedeutungstragend: Visualize5 spreizt Partien desselben
            # Tages in genau dieser Reihenfolge auf. Sortierte Kopie, damit att["plays"]
            # unangetastet bleibt.
            _ordered = sort_plays_for_output(
                att["plays"], CAMPAIGN_SPECS.get(att["campaign"], {})
            )
            played_str = " | ".join(
                f'{p["date"]}::{p["scenario"]}::{p["result"]}'
                for p in _ordered
            )
            writer.writerow([
                att["campaign"], heroes_str, att.get("difficulty", "Standard"),
                att["start_date"], att["end_date"],
                att["status"], len(att["plays"]), played_str,
            ])

    print(f"Kampagnen-Statistik gespeichert als: {OUTFILE_CAMPAIGNS} ({len(campaign_attempts)} Versuche)")

    # Vergessene Kampagnen-Markierungen sichtbar machen — sonst fehlen die Partien stillschweigend
    for _camp, _n in _skipped_untagged.items():
        print(f"  Hinweis: {_camp}: {_n} Partie(n) ohne 'Campaign' im Kommentar übersprungen")

    print(f"FERTIG! Datei gespeichert als: {OUTFILE}")

    # --- BGG-STATE für Change-Detection --- #
    _state = {
        "total":        total_plays,
        "last_play_id": str(all_plays[0]["id"]) if all_plays else "0",
        "last_full_sync": datetime.now(timezone.utc).isoformat(),
    }
    with open("bgg_state.json", "w", encoding="utf-8") as _f:
        json.dump(_state, _f)
    print("BGG-State gespeichert als: bgg_state.json")

    # --- UNBEKANNTE EINTRÄGE --- #

    def _safe_print(line):
        """Druckt auch auf Konsolen ohne UTF-8 (Windows cp1252) ohne Abbruch."""
        try:
            print(line)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "ascii"
            print(line.encode(enc, errors="replace").decode(enc, errors="replace"))

    def _print_unknowns(label, entries):
        if entries:
            _safe_print(f"{label} ({len(entries)}):")
            for date, value, comment in sorted(entries):
                _safe_print(f"  {date}  \"{value}\"  ->  {comment}")
        else:
            _safe_print(f"{label} (0): keine")

    print("\n=== UNBEKANNTE / FEHLENDE EINTRÄGE ===")
    _print_unknowns("Plays ohne Held",          plays_no_hero)
    _print_unknowns("Plays ohne Villain",        plays_no_villain)
    _print_unknowns("Helden nicht erkannt",      unknown_heroes)
    _print_unknowns("Aspekte nicht erkannt",     unknown_aspects)
    _print_unknowns("Szenarien nicht erkannt",   unknown_scenarios)
    _print_unknowns("Modulars nicht erkannt",    unknown_modulars)
    _print_unknowns("Fehlende Modulars",         missing_modulars)
    _print_unknowns("Player-Abweichungen",       player_mismatches)

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
        for date, value, comment in sorted(unknown_aspects):
            writer.writerow(["Aspekt nicht erkannt", date, value, comment])
        for date, value, comment in sorted(unknown_scenarios):
            writer.writerow(["Szenario nicht erkannt", date, value, comment])
        for date, value, comment in sorted(unknown_modulars):
            writer.writerow(["Modular nicht erkannt", date, value, comment])
        for date, value, comment in sorted(missing_modulars):
            writer.writerow(["Fehlendes Modular", date, value, comment])
        for date, value, comment in sorted(player_mismatches):
            writer.writerow(["Player-Abweichung", date, value, comment])

    if any([plays_no_hero, plays_no_villain, unknown_heroes, unknown_aspects,
            unknown_scenarios, unknown_modulars, missing_modulars, player_mismatches]):
        print(f"\nBericht gespeichert als: {OUTFILE_UNKNOWN}")
