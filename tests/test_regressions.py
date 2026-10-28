import contextlib
import csv
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import bgg_parser
import check_bgg_changes as checker


ROOT = Path(__file__).resolve().parents[1]


class ExportTests(unittest.TestCase):
    def test_repeated_aspects_and_sync_timestamp(self):
        comments = [
            'Hulk Aggression + Thor Aggression vs Rhino Standard - won',
            'Spider-Woman Justice Justice Leadership vs Rhino Standard - won',
            'Adam Warlock vs Rhino Standard - won',
        ]
        xml = '<plays total="3">' + ''.join(
            f'<play id="{3-i}" date="2026-09-01" quantity="1" '
            f'incomplete="0" nowinstats="0"><comments>{escape(comment)}</comments></play>'
            for i, comment in enumerate(comments)
        ) + '</plays>'
        response = Mock(text=xml)
        before = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            try:
                os.chdir(tmp)
                with patch('requests.get', return_value=response), \
                        contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(ROOT / 'BGG_Export.py'), run_name='__main__')
                with open('heroes_aspects.csv', encoding='utf-8', newline='') as f:
                    aspects = {(r['Hero'], r['Aspect']): int(r['Count'])
                               for r in csv.DictReader(f, delimiter=';')}
                self.assertEqual(aspects, {
                    ('Hulk', 'Aggression'): 1,
                    ('Thor', 'Aggression'): 1,
                    ('Spider-Woman', 'Justice'): 1,
                    ('Spider-Woman', 'Leadership'): 1,
                    **{('Adam Warlock', a): 1 for a in
                       ['Aggression', 'Justice', 'Leadership', 'Protection']},
                })
                state = json.loads(Path('bgg_state.json').read_text(encoding='utf-8'))
                timestamp = datetime.fromisoformat(state['last_full_sync'])
                self.assertGreaterEqual(timestamp, before)
                self.assertLessEqual(timestamp, datetime.now(timezone.utc))
                self.assertEqual(state['total'], 3)
                self.assertEqual(state['last_play_id'], '3')
            finally:
                os.chdir(previous)


class ChangeCheckTests(unittest.TestCase):
    def test_sync_interval_and_legacy_states(self):
        now = datetime(2026, 9, 12, tzinfo=timezone.utc)
        for age, expected in [(timedelta(hours=23, minutes=59), False),
                              (timedelta(hours=24), True),
                              (timedelta(days=2), True),
                              (timedelta(seconds=-1), True)]:
            with self.subTest(age=age):
                self.assertEqual(checker.full_sync_due(
                    {'last_full_sync': (now - age).isoformat()}, now), expected)
        for state in [{}, {'last_full_sync': None}, {'last_full_sync': 'bad'},
                      {'last_full_sync': '2026-09-12T00:00:00'}]:
            with self.subTest(state=state):
                self.assertTrue(checker.full_sync_due(state, now))

    def test_old_state_forces_refresh_without_page1(self):
        state = {'total': 1, 'last_play_id': '10',
                 'last_full_sync': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
        with patch.object(checker, 'load_state', return_value=state), \
                patch.object(checker, 'fetch_page1') as fetch, \
                patch.object(checker, 'set_output') as output, \
                contextlib.redirect_stdout(io.StringIO()):
            checker.main()
        fetch.assert_not_called()
        output.assert_called_once_with('changed', 'true')

    def test_recent_state_still_checks_count_and_id(self):
        state = {'total': 1, 'last_play_id': '10',
                 'last_full_sync': datetime.now(timezone.utc).isoformat()}
        for total, play_id, expected in [(1, '10', 'false'), (2, '10', 'true'),
                                         (1, '11', 'true')]:
            with self.subTest(total=total, play_id=play_id), \
                    patch.object(checker, 'load_state', return_value=state), \
                    patch.object(checker, 'fetch_page1', return_value=
                                 f'<plays total="{total}"><play id="{play_id}"/></plays>'), \
                    patch.object(checker, 'set_output') as output, \
                    contextlib.redirect_stdout(io.StringIO()):
                checker.main()
                output.assert_called_once_with('changed', expected)


def _play(comment, players=()):
    """Eine <play>-Zeile wie von der BGG-API; players = [(userid, color), ...]."""
    players_xml = ''.join(f'<player userid="{uid}" color="{escape(color)}"/>' for uid, color in players)
    return ET.fromstring(
        '<play id="1" date="2026-09-01" quantity="1" length="0" incomplete="0" nowinstats="0">'
        f'<comments>{escape(comment)}</comments>'
        + (f'<players>{players_xml}</players>' if players else '') + '</play>')


class ParsePlayTests(unittest.TestCase):
    def test_multiplayer_marks_own_hero_and_adds_missing_teammates(self):
        parsed = bgg_parser.parse_play(_play(
            'Echo Protection Silk Protection vs Rhino Bomb Scare Expert Campaign - won',
            [('0', 'Silk'), ('250203', 'Echo'), ('0', 'Wolverine')]))
        self.assertEqual([(h['hero'], h['aspects'], h['is_mine']) for h in parsed['heroes']],
                         [('Echo', ['Protection'], True), ('Silk', ['Protection'], False),
                          ('Wolverine', [], False)])
        self.assertEqual(parsed['scenario'], 'Rhino')
        self.assertEqual(parsed['modulars'], ['Bomb Scare', 'Expert', 'Standard'])
        self.assertEqual((parsed['difficulty'], parsed['result'], parsed['is_campaign']),
                         ('Expert', 'win', True))
        self.assertEqual(parsed['problems'], [])

    def test_solo_heroes_are_all_mine_and_problems_are_reported(self):
        parsed = bgg_parser.parse_play(_play('Hulk Aggression + Thor Ally vs Nobody - lost',
                                             [('250203', '')]))
        self.assertEqual([(h['hero'], h['aspects'], h['is_mine']) for h in parsed['heroes']],
                         [('Hulk', ['Aggression'], True), ('Thor', ['Precon'], True)])
        self.assertIsNone(parsed['scenario'])
        self.assertEqual(parsed['result'], 'loss')
        self.assertIn("Aspekt nicht erkannt: 'ally'", parsed['problems'])
        self.assertIn("Szenario nicht erkannt: 'Nobody'", parsed['problems'])


if __name__ == '__main__':
    unittest.main()
