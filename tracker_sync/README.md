# Tracker-Sync

Überträgt die Marvel-Champions-Partien von BoardGameGeek in den [Marvel Champions Tracker](https://marvelchampionstracker.com).
**BGG ist führend:** neue Partien werden angelegt, geänderte aktualisiert, auf BGG gelöschte im Tracker gelöscht.

Die Erkennung von Helden, Aspekten, Szenarien und Modulars kommt aus [`bgg_parser.py`](../bgg_parser.py) im
Hauptordner — Statistiken und Tracker sehen also dieselben Daten. Neue Helden/Szenarien/Modulars werden nur in
[`config/*.json`](../config) eingetragen; [`mapping.json`](mapping.json) braucht nur Namen, die im Tracker anders heißen.

## Automatischer Abgleich

Der Workflow [`update.yml`](../.github/workflows/update.yml) startet nach der Statistik einen eigenen Job `tracker`,
der `sync --apply` ausführt — immer dann, wenn `check_bgg_changes.py` eine Änderung meldet (neue Partie oder spätestens
alle 24 h, damit auch Korrekturen an älteren Partien ankommen) sowie bei Push und manuellem Start. Schlägt der Job fehl
(z. B. Tracker nicht erreichbar), ist die Statistik trotzdem aktuell; der Tracker holt beim nächsten Lauf auf.
Die Läufe sind serialisiert (`concurrency`), damit nie zwei Syncs gleichzeitig Logs anlegen.

Nötige Repository-Secrets zusätzlich zu den BGG-Secrets: `TRACKER_EMAIL`, `TRACKER_PASSWORD`.

## Zuordnung

Jedes Tracker-Log bekommt im Notizfeld eine Marker-Zeile mit der BGG-Play-ID und darunter den BGG-Kommentar:

```
[BGG #117183748]

Daredevil Justice vs Art Museum Heist Typhoid Mary Cops The Owl - won
```

Logs **ohne** Marker (selbst im Tracker eingetragen) fasst der Sync nie an.

## Einrichtung

```
pip install -r tracker_sync/requirements.txt
```

Die Zugangsdaten stehen in derselben `.env` im Hauptordner wie die BGG-Zugangsdaten:

| Variable | Bedeutung |
|---|---|
| `TRACKER_EMAIL`, `TRACKER_PASSWORD` | Tracker-Anmeldung (empfohlen) |
| `TRACKER_COOKIE_FILE` | Alternative ohne Passwort: Datei mit einer Zeile `Cookie: session=…; remember_token=…` aus den Browser-DevTools (läuft irgendwann ab) |
| `BGG_USERNAME`, `BGG_SESSION_ID`, `BGG_PASSWORD`, `BGG_API_TOKEN` | BGG-Zugang, wie für `BGG_Export.py` |
| `TRACKER_DELAY` | optional, Sekunden zwischen Tracker-Anfragen (Standard 1.0) |

## Nutzung

Aus dem Hauptordner des Repos:

```
python tracker_sync/sync.py validate                  # Namenszuordnung prüfen, nichts schreiben
python tracker_sync/sync.py sync                      # Dry-Run: was würde angelegt/geändert/gelöscht?
python tracker_sync/sync.py sync --apply              # ausführen
python tracker_sync/sync.py sync --apply --limit 5    # höchstens 5 Schreibzugriffe (zum Testen)
```

Der Sync gleicht jedes Mal vollständig ab. Eine komplette Neubefüllung (z. B. nach einem Tracker-Reset) ist also
einfach ein weiterer `sync --apply`. Er braucht ein paar Minuten, weil er alle Tracker-Logs seitenweise lädt.

**Sicherungen:** kein Abgleich, wenn BGG weniger Partien liefert als gemeldet; mehr als 10 Löschungen pro Lauf nur mit
`--allow-mass-delete`; Partien, die nicht erkannt werden, werden übersprungen (und gelten nicht als gelöscht).

## Abbildung BGG → Tracker

| Tracker | aus BGG |
|---|---|
| Datum | Partiedatum, 12:00 UTC; weitere Partien desselben Tages je +1 min (Reihenfolge nach BGG-ID) |
| Helden | alle Helden aus dem Kommentar, Mitspieler-Helden aus dem Spielerfeld „Farbe“; „My Hero“ = eigener BGG-Spieler |
| Aspekt | ein Aspekt → direkt; mehrere → `Multi-Aspect`; keiner/`Precon` → `Not Applicable` |
| Villain / Stages / Main Schemes | Szenario; Stages und Main Schemes wie der Button „Load“ im Tracker (Standard- bzw. Expert-Reihenfolge) |
| Modulars | Modulars des Parsers (explizit, Default, Auto, Schwierigkeitssets) |
| Schwierigkeit | `Expert` bei Expert/Expert II, sonst `Standard`; Heroic immer `None` |
| Ergebnis | won → `Win`, lost → `Loss to Other`, sonst `Not Applicable` |
| Kampagne | `Campaign`/`Kampagne` im Kommentar |
| Umgebung, Sichtbarkeit | aus den eigenen Tracker-Einstellungen |

### `mapping.json`

Namen werden normalisiert verglichen (`Spider-Man * Peter Parker` = `Spider-Man (Peter Parker)`). `mapping.json`
enthält nur Ausnahmen:

- `heroes` / `villains` / `modulars`: BGG-Name → Tracker-Name; `null` = im Tracker weglassen
- `missions`: *Fear No Evil* — bei BGG ist die Mission das Szenario und der Villain ein Modular, im Tracker ist der
  Villain der Villain und die Mission ein Main Scheme. Wert = Main-Scheme-Name, `null` = Variante unbekannt
  (Protection Racket hat im Tracker fünf Varianten).

`python tracker_sync/sync.py validate` listet alles, was noch nicht zugeordnet werden kann.

## Tests

Die Tests liegen bei den übrigen in `tests/test_tracker_sync.py` und laufen offline mit:

```
python -m unittest discover -s tests -v
```

## Hinweise

- Die Tracker-API ist inoffiziell (aus dem JavaScript der Website ermittelt) und kann sich ohne Ankündigung ändern.
- Die BGG XML API darf nur nicht-kommerziell genutzt werden; übertragen werden ausschließlich die eigenen Partien.
