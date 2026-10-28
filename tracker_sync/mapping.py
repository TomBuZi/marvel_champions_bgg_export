"""Übersetzt BGG-Namen (config/*.json des Export-Repos) in Inhalte des Trackers.

Namen werden normalisiert verglichen ('Spider-Man * Peter Parker' == 'Spider-Man (Peter Parker)',
Groß/Klein, Akzente und Satzzeichen egal). mapping.json enthält nur die Ausnahmen.
"""

import json
import re
import unicodedata
from pathlib import Path

MAPPING_FILE = Path(__file__).with_name("mapping.json")


def normalize(name):
    """Vergleichsschlüssel für einen Namen."""
    if " * " in name:
        base, identity = name.split(" * ", 1)
        name = f"{base} ({identity})"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9()]", "", name.lower())


def load_overrides(path=MAPPING_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Catalog:
    """Helden, Villains und Modulars des Trackers mit Auflösung von BGG-Namen.

    overrides (mapping.json):
      heroes / villains / modulars – BGG-Name → Tracker-Name; null = im Tracker weglassen
      missions – BGG-Szenarien, die im Tracker ein Main Scheme sind (Fear No Evil). Der Villain
                 steht dann bei BGG unter den Modulars. Wert = Main-Scheme-Name, null = unbestimmt.
    """

    def __init__(self, heroes, villains, modulars, overrides=None):
        self.overrides = overrides or {}
        self.missions = self.overrides.get("missions", {})
        self._heroes   = {normalize(h["name"]): h for h in heroes}
        self._villains = {normalize(v["name"]): v for v in villains}
        self._modulars = {normalize(m["name"]): m for m in modulars}
        self._villain_aliases = {}
        for v in villains:
            for alias in (v.get("aka") or "").split(","):
                if alias.strip():
                    self._villain_aliases.setdefault(normalize(alias), v)

    def ignored(self, kind, bgg_name):
        """True, wenn mapping.json den Namen ausdrücklich weglässt (null)."""
        kind_overrides = self.overrides.get(kind, {})
        return bgg_name in kind_overrides and kind_overrides[bgg_name] is None

    def _target(self, kind, bgg_name):
        return self.overrides.get(kind, {}).get(bgg_name) or bgg_name

    def hero(self, bgg_name):
        return self._heroes.get(normalize(self._target("heroes", bgg_name)))

    def villain(self, bgg_name):
        key = normalize(self._target("villains", bgg_name))
        return self._villains.get(key) or self._villain_aliases.get(key)

    def villain_exact(self, name):
        """Nur über den Villain-Namen selbst (ohne 'aka') — 'Electro' ist sonst auch Sinister Six."""
        return self._villains.get(normalize(name))

    def modular(self, bgg_name):
        return self._modulars.get(normalize(self._target("modulars", bgg_name)))
