"""BGG → Marvel Champions Tracker: Partien abgleichen. BGG ist führend.

  python tracker_sync/sync.py validate                  Namenszuordnung prüfen, nichts schreiben
  python tracker_sync/sync.py sync                      Dry-Run: zeigt, was angelegt/geändert/gelöscht würde
  python tracker_sync/sync.py sync --apply [--limit N]  Änderungen ausführen

Zuordnung über den Marker '[BGG #<Play-ID>]' im Notizfeld. Logs ohne Marker werden nie angefasst.
Wann ein Sync nötig ist, entscheidet in GitHub Actions check_bgg_changes.py (siehe update.yml).
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import bgg_source  # noqa: E402
from mapping import Catalog, load_overrides  # noqa: E402
from payload import bgg_id_of, build_payload, plan_changes, play_times  # noqa: E402
from tracker_client import TrackerClient, TrackerError  # noqa: E402

MAX_DELETES = 10     # mehr Löschungen pro Lauf nur mit --allow-mass-delete
LIST_LIMIT = 15       # Einträge pro Abschnitt im Bericht (ohne --verbose)


def describe(play):
    return f'{play["date"]} #{play["id"]}  {play["comment"][:100]}'


def load_catalog(client):
    return Catalog(client.get_content("heroes"), client.get_content("villains"),
                   client.get_content("modulars"), load_overrides())


def build_all(plays, catalog, settings):
    """Payloads aller übertragbaren Partien, übersprungene Partien mit Gründen und Hinweise."""
    times = play_times(plays)
    desired, skipped, warnings = {}, [], []
    for play in plays:
        payload, errors, warns = build_payload(play, times[play["id"]], catalog, settings)
        warnings.extend((play, w) for w in warns)
        if payload:
            desired[play["id"]] = payload
        else:
            skipped.append((play, errors))
    return desired, skipped, warnings


def print_list(title, lines, verbose):
    print(f"\n{title} ({len(lines)}):")
    shown = lines if verbose else lines[:LIST_LIMIT]
    for line in shown:
        print(f"  {line}")
    if len(shown) < len(lines):
        print(f"  … {len(lines) - len(shown)} weitere (--verbose zeigt alle)")


def print_warnings(warnings):
    counts = Counter(w for _, w in warnings)
    print(f"\nHinweise ({len(warnings)}, Partien werden trotzdem übertragen):")
    for text, n in counts.most_common():
        print(f"  {n:4d}×  {text}")


def load_bgg(catalog, settings):
    print("Lade BGG-Partien ...")
    plays, total = bgg_source.fetch_all_plays()
    if not plays or len(plays) != total:
        sys.exit(f"ABBRUCH: BGG lieferte {len(plays)} von {total} Partien — unvollständiger Abruf.")
    return plays, *build_all(plays, catalog, settings)


# --- Befehle ---------------------------------------------------------------------------------

def cmd_validate(args):
    client = TrackerClient.from_env()
    catalog = load_catalog(client)
    plays, desired, skipped, warnings = load_bgg(catalog, client.get_settings()["game_logs"])
    print(f"\nBGG: {len(plays)} Partien, {len(desired)} übertragbar, {len(skipped)} übersprungen.")
    print_list("Übersprungen", [f"{describe(p)}\n      → {'; '.join(e)}" for p, e in skipped], True)
    print_warnings(warnings)


def cmd_sync(args):
    client = TrackerClient.from_env()
    catalog = load_catalog(client)
    plays, desired, skipped, warnings = load_bgg(catalog, client.get_settings()["game_logs"])
    print("Lade Tracker-Logs ...")
    logs = client.list_logs()
    plan = plan_changes(desired, {p["id"] for p in plays}, logs)
    manual = sum(1 for log in logs if not bgg_id_of(log))

    print(f"\nBGG:     {len(plays)} Partien — {len(desired)} übertragbar, {len(skipped)} übersprungen")
    print(f"Tracker: {len(logs)} Logs — {len(logs) - manual} mit BGG-Marker, {manual} ohne (bleiben unberührt)")
    print(f"Plan:    {len(plan.creates)} anlegen, {len(plan.updates)} ändern, "
          f"{len(plan.deletes)} löschen, {plan.unchanged} unverändert")

    print_list("Anlegen", [p["notes"].split("\n")[0] + "  " + p["datetime_happened"][:10] + "  "
                           + p["notes"].split("\n\n", 1)[-1][:90] for p in plan.creates], args.verbose)
    print_list("Ändern", [f'{p["notes"].split(chr(10))[0]}  {p["public_id"]}  Felder: {", ".join(f)}'
                          for p, f in plan.updates], args.verbose)
    print_list("Löschen", [f'[BGG #{bgg_id}] {log["public_id"]}  ({reason})'
                           for bgg_id, log, reason in plan.deletes], True)
    print_list("Übersprungen", [f"{describe(p)}\n      → {'; '.join(e)}" for p, e in skipped], True)
    if args.verbose:
        print_warnings(warnings)

    if len(plan.deletes) > MAX_DELETES and not args.allow_mass_delete:
        sys.exit(f"\nABBRUCH: {len(plan.deletes)} Löschungen (> {MAX_DELETES}). "
                 "Bitte prüfen und ggf. mit --allow-mass-delete bestätigen.")
    if not args.apply:
        print("\nDry-Run — nichts geändert. Mit --apply ausführen.")
        return

    failures = apply_plan(client, plan, args.limit)
    if failures:
        print(f"\n{failures} Fehler — siehe oben.")
        sys.exit(1)
    print("\nFertig.")


def apply_plan(client, plan, limit):
    ops = ([("Anlegen", p, None) for p in plan.creates]
           + [("Ändern", p, fields) for p, fields in plan.updates]
           + [("Löschen", log, reason) for _, log, reason in plan.deletes])
    if limit is not None:
        ops = ops[:limit]
    failures = 0
    for i, (kind, item, info) in enumerate(ops, 1):
        label = item["notes"].split("\n")[0] if kind != "Löschen" else f"{item['public_id']} ({info})"
        try:
            if kind == "Anlegen":
                label += f" → {client.create_log(item)['public_id']}"
            elif kind == "Ändern":
                client.update_log(item)
                label += f" {item['public_id']}: {', '.join(info)}"
            else:
                client.delete_log(item["public_id"])
            print(f"[{i}/{len(ops)}] {kind}: {label}")
        except TrackerError as e:
            failures += 1
            print(f"[{i}/{len(ops)}] FEHLER {kind}: {label}\n      {e}")
    return failures


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="BGG → Marvel Champions Tracker Sync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Namenszuordnung prüfen, nichts schreiben")
    p_sync = sub.add_parser("sync", help="Abgleich (ohne --apply nur Dry-Run)")
    p_sync.add_argument("--apply", action="store_true", help="Änderungen wirklich ausführen")
    p_sync.add_argument("--limit", type=int, help="höchstens N Schreibzugriffe (zum Testen)")
    p_sync.add_argument("--allow-mass-delete", action="store_true",
                        help=f"mehr als {MAX_DELETES} Löschungen erlauben")
    p_sync.add_argument("--verbose", action="store_true", help="alle Einträge und Hinweise zeigen")
    args = parser.parse_args()
    {"validate": cmd_validate, "sync": cmd_sync}[args.command](args)


if __name__ == "__main__":
    main()
