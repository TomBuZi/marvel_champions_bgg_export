"""BGG-Partien über bgg_parser.py aus dem Hauptordner des Repos.

bgg_parser lädt beim Import die .env im Hauptordner (BGG-Zugangsdaten), ohne bereits
gesetzte Variablen zu überschreiben.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bgg_parser  # noqa: E402

PAGE_DELAY = 2  # Sekunden zwischen zwei BGG-Seiten


def fetch_all_plays():
    """Alle Marvel-Champions-Partien als parse_play-Dicts plus die von BGG gemeldete Gesamtzahl."""
    plays, page, total = [], 1, None
    while True:
        page_plays, page_total = bgg_parser.parse_plays(
            bgg_parser.fetch_page(bgg_parser.USERNAME, bgg_parser.GAME_ID, page))
        if total is None:
            total = page_total
        plays.extend(page_plays)
        if not page_plays or len(plays) >= total:
            break
        page += 1
        time.sleep(PAGE_DELAY)
    return [bgg_parser.parse_play(p) for p in plays], total
