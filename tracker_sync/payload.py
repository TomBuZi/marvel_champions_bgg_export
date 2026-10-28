"""Baut aus einer BGG-Partie (bgg_parser.parse_play) den Tracker-Payload und vergleicht Logs."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

MARKER_RE = re.compile(r"\[BGG #(\d+)\]")

# BGG-Ergebnis (classify_result) → Tracker-Outcome. BGG kennt keinen Niederlagengrund.
OUTCOMES = {"win": "Win", "loss": "Loss to Other", "incomplete": "Not Applicable"}


def marker(play_id):
    return f"[BGG #{play_id}]"


def unescape_notes(text):
    """Wie das Tracker-Formular (rX): escapte Zeilenumbrüche und Zeichen zurückwandeln."""
    text = (text or "").replace("\r\n", "\n").replace("\\n", "\n")
    return re.sub(r"\\(.)", r"\1", text)


def bgg_id_of(log):
    """BGG-Play-ID aus dem Notiz-Marker eines Tracker-Logs, sonst None."""
    match = MARKER_RE.search(unescape_notes(log.get("notes")))
    return match.group(1) if match else None


def tracker_aspect(aspects):
    if len(aspects) > 1:
        return "Multi-Aspect"
    if not aspects or aspects[0] == "Precon":
        return "Not Applicable"
    return aspects[0]


def play_times(plays):
    """BGG kennt nur das Datum: 12:00 UTC, weitere Partien desselben Tages je +1 min (nach BGG-ID)."""
    by_date = defaultdict(list)
    for play in plays:
        by_date[play["date"]].append(play)
    times = {}
    for date, group in by_date.items():
        noon = datetime.fromisoformat(date).replace(hour=12, tzinfo=timezone.utc)
        for i, play in enumerate(sorted(group, key=lambda p: int(p["id"]))):
            times[play["id"]] = noon + timedelta(minutes=i)
    return times


def _by_order(items, order):
    return [x["name"] for x in sorted((x for x in items if x.get(order)), key=lambda x: x[order])]


def build_payload(play, when, catalog, settings):
    """Liefert (payload, errors, warnings). Bei errors ist payload None — die Partie wird übersprungen."""
    errors, warnings = [], list(play["problems"])

    heroes = []
    for h in play["heroes"]:
        hero = catalog.hero(h["hero"])
        if not hero:
            errors.append(f"Held nicht im Tracker: {h['hero']!r}")
            continue
        heroes.append({"hero": hero["name"], "aspect": tracker_aspect(h["aspects"]),
                       "decklist": "", "is_my_hero": h["is_mine"], "slot": len(heroes) + 1})
    if not play["heroes"]:
        errors.append("Kein Held erkannt")

    bgg_modulars = list(play["modulars"])
    scenario = play["scenario"]
    villain, mission_schemes = None, None
    if scenario is None:
        errors.append("Szenario nicht erkannt")
    elif scenario in catalog.missions:
        # Fear No Evil: BGG-Szenario = Mission (Main Scheme), Villain steht unter den Modulars
        villain_mod = next((m for m in bgg_modulars if catalog.villain_exact(m)), None)
        if villain_mod:
            villain = catalog.villain_exact(villain_mod)
            bgg_modulars.remove(villain_mod)
        else:
            errors.append(f"Mission {scenario!r} ohne erkennbaren Villain")
        mission = catalog.missions[scenario]
        mission_schemes = []
        if not mission:
            warnings.append(f"Variante von {scenario!r} unbekannt — kein Main Scheme gesetzt")
        elif villain and mission not in [s["name"] for s in villain["main_schemes"]]:
            warnings.append(f"Main Scheme {mission!r} gibt es bei {villain['name']!r} nicht")
        else:
            mission_schemes = [mission]
    else:
        villain = catalog.villain(scenario)
        if not villain:
            errors.append(f"Villain nicht im Tracker: {scenario!r}")

    if errors:
        return None, errors, warnings

    # Stages/Main Schemes wie der Button „Load“ im Tracker-Formular
    expert = play["difficulty"].startswith("Expert")
    order = "expert_order" if expert else "standard_order"

    modulars, seen = [], set()
    for name in bgg_modulars:
        if catalog.ignored("modulars", name):
            continue
        mod = catalog.modular(name)
        if not mod:
            warnings.append(f"Modular nicht im Tracker: {name!r}")
        elif mod["public_id"] not in seen:
            seen.add(mod["public_id"])
            modulars.append({"mod_name": mod["name"], "public_id": mod["public_id"]})

    payload = {
        "public_id": None,
        "origin": "completed",
        "game_title": "",
        "is_future": False,
        "datetime_happened": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "runtime": play["length"] or "",
        "environment": settings["environment"],
        "difficulty_mode": "Expert" if expert else "Standard",
        "heroic_level": "None",
        "is_published": settings.get("visibility") == "Unlisted",
        "outcome": OUTCOMES[play["result"]],
        "preplay_notes": "",
        "notes": f"{marker(play['id'])}\n\n{play['comment']}",
        "is_campaign": play["is_campaign"],
        "heroes": heroes,
        "villain_scenario": [villain],
        "villain": villain["name"],
        "villain_stages": _by_order(villain["stages"], order),
        "main_schemes": (mission_schemes if mission_schemes is not None
                         else _by_order(villain["main_schemes"], order)),
        "modulars": modulars,
    }
    if play["is_campaign"]:
        payload["campaign_notes"] = ""
    return payload, [], warnings


# --- Vergleich -------------------------------------------------------------------------------

def _name(x):
    """Name aus String oder Objekt ({name}, {mod_name} oder {hero: …})."""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for key in ("name", "mod_name"):
            if isinstance(x.get(key), str):
                return x[key]
        return _name(x.get("hero"))
    return ""


def parse_datetime(value):
    """ISO ('2026-08-06T12:00:00.000Z') oder HTTP-Datum ('Thu, 06 Aug 2026 12:00:00 GMT') → UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def signature(log):
    """Vergleichbare Kurzform eines Logs — gleich für Soll-Payload und Tracker-Antwort.

    Umgebung, Sichtbarkeit und Heroic-Level fehlen bewusst: sie kommen aus den Tracker-
    Einstellungen und sollen bei deren Änderung nicht alle Logs neu schreiben.
    """
    dt = parse_datetime(log.get("datetime_happened"))
    villain = log.get("villain") or log.get("villain_scenario")
    if isinstance(villain, list):
        villain = villain[0] if villain else ""
    runtime = str(log.get("runtime") or "").strip()
    heroes = sorted(log.get("heroes") or [], key=lambda h: h.get("slot") or 0)
    return {
        "datetime":        dt.strftime("%Y-%m-%dT%H:%M") if dt else None,
        "outcome":         log.get("outcome"),
        "difficulty_mode": log.get("difficulty_mode"),
        "notes":           unescape_notes(log.get("notes")).strip(),
        "is_campaign":     bool(log.get("is_campaign")),
        "runtime":         int(runtime) if runtime.isdigit() and int(runtime) else None,
        "heroes":          [(_name(h), h.get("aspect"), bool(h.get("is_my_hero"))) for h in heroes],
        "villain":         _name(villain),
        "villain_stages":  sorted(_name(s) for s in log.get("villain_stages") or []),
        "main_schemes":    sorted(_name(s) for s in log.get("main_schemes") or []),
        "modulars":        sorted(_name(m) for m in log.get("modulars") or []),
    }


def changed_fields(log, payload):
    old, new = signature(log), signature(payload)
    return [key for key in new if old[key] != new[key]]


@dataclass
class Plan:
    creates:   list = field(default_factory=list)   # Payloads
    updates:   list = field(default_factory=list)   # (Payload mit public_id, geänderte Felder)
    deletes:   list = field(default_factory=list)   # (BGG-ID, Log, Grund)
    unchanged: int = 0


def plan_changes(desired, bgg_ids, logs):
    """Abgleich BGG (führend) → Tracker.

    desired – {BGG-ID: Payload} aller übertragbaren Partien
    bgg_ids – IDs ALLER BGG-Partien; übersprungene Partien gelten nicht als gelöscht
    logs    – alle Tracker-Logs; nur Logs mit BGG-Marker werden angefasst
    """
    marked = defaultdict(list)
    for log in logs:
        bgg_id = bgg_id_of(log)
        if bgg_id:
            marked[bgg_id].append(log)

    plan = Plan()
    for bgg_id, payload in desired.items():
        found = marked.get(bgg_id)
        if not found:
            plan.creates.append(payload)
            continue
        keep, *duplicates = found
        plan.deletes.extend((bgg_id, log, "Duplikat") for log in duplicates)
        fields = changed_fields(keep, payload)
        if fields:
            plan.updates.append(({**payload, "public_id": keep["public_id"]}, fields))
        else:
            plan.unchanged += 1

    for bgg_id, found in marked.items():
        if bgg_id not in bgg_ids:
            plan.deletes.extend((bgg_id, log, "auf BGG gelöscht") for log in found)

    plan.creates.sort(key=lambda p: p["datetime_happened"])
    return plan
