import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tracker_sync"))

from mapping import Catalog, load_overrides, normalize  # noqa: E402
from payload import (bgg_id_of, build_payload, changed_fields, plan_changes,  # noqa: E402
                     play_times, signature)

WHEN = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
SETTINGS = {"environment": "Legacy", "visibility": "Private"}


def villain(name, stages=(), schemes=()):
    return {"name": name, "aka": "", "public_id": name[:4],
            "stages": [{"name": n, "standard_order": s, "expert_order": e} for n, s, e in stages],
            "main_schemes": [{"name": n, "standard_order": s, "expert_order": e} for n, s, e in schemes]}


CATALOG = Catalog(
    heroes=[{"name": n} for n in ("Spider-Man (Peter Parker)", "Echo", "Silk", "Adam Warlock")],
    villains=[
        villain("Rhino", [("Rhino I", 1, None), ("Rhino II", 2, 1), ("Rhino III", None, 2)],
                [("The Break-In!", 1, 1)]),
        villain("Typhoid Mary", [("Typhoid Mary I", 1, None), ("Typhoid Mary II", None, 1)],
                [("Art Museum Heist", None, None), ("The Getaway", None, None)]),
        {**villain("Sinister Six"), "aka": "Doctor Octopus, Electro"},
        villain("Electro"),
    ],
    modulars=[{"name": n, "public_id": f"id-{i}"} for i, n in enumerate(
        ["Standard", "Expert", "Bomb Scare", "Cops", "The Owl", "The Doomsday Chair"])],
    overrides=load_overrides(),
)


def play(**overrides):
    base = {"id": "100", "date": "2026-08-06", "length": 0, "comment": "Spider-Man Justice vs Rhino - won",
            "heroes": [{"hero": "Spider-Man * Peter Parker", "aspects": ["Justice"], "is_mine": True}],
            "scenario": "Rhino", "modulars": ["Bomb Scare", "Standard"], "difficulty": "Standard",
            "result": "win", "is_campaign": False, "problems": []}
    return {**base, **overrides}


class MappingTests(unittest.TestCase):
    def test_normalize_and_lookup(self):
        self.assertEqual(normalize("Spider-Man * Peter Parker"), normalize("Spider-Man (Peter Parker)"))
        self.assertEqual(normalize("Dark Protégé"), normalize("dark protege"))
        self.assertEqual(CATALOG.villain("The Sinister Six")["name"], "Sinister Six")   # mapping.json
        self.assertEqual(CATALOG.villain("Doctor Octopus")["name"], "Sinister Six")     # aka
        self.assertEqual(CATALOG.villain("Electro")["name"], "Electro")                 # Name vor aka
        self.assertEqual(CATALOG.modular("Doomsday Chair")["name"], "The Doomsday Chair")
        self.assertTrue(CATALOG.ignored("modulars", "Dark Protégé"))


class PayloadTests(unittest.TestCase):
    def test_standard_play(self):
        payload, errors, warnings = build_payload(play(), WHEN, CATALOG, SETTINGS)
        self.assertEqual((errors, warnings), ([], []))
        self.assertEqual(payload["notes"], "[BGG #100]\n\nSpider-Man Justice vs Rhino - won")
        self.assertEqual(payload["datetime_happened"], "2026-08-06T12:00:00.000Z")
        self.assertEqual(payload["heroes"], [{"hero": "Spider-Man (Peter Parker)", "aspect": "Justice",
                                              "decklist": "", "is_my_hero": True, "slot": 1}])
        self.assertEqual((payload["villain"], payload["villain_stages"], payload["main_schemes"]),
                         ("Rhino", ["Rhino I", "Rhino II"], ["The Break-In!"]))
        self.assertEqual(payload["modulars"], [{"mod_name": "Bomb Scare", "public_id": "id-2"},
                                               {"mod_name": "Standard", "public_id": "id-0"}])
        self.assertEqual((payload["outcome"], payload["difficulty_mode"], payload["is_published"]),
                         ("Win", "Standard", False))
        self.assertNotIn("campaign_notes", payload)

    def test_expert_loss_multi_aspect_and_unknown_modular(self):
        payload, errors, warnings = build_payload(play(
            difficulty="Expert II", result="loss", is_campaign=True,
            modulars=["Bomb Scare", "Expert", "Mystery Set", "Standard"],
            heroes=[{"hero": "Adam Warlock", "aspects": ["Aggression", "Justice"], "is_mine": True},
                    {"hero": "Echo", "aspects": ["Precon"], "is_mine": False}]), WHEN, CATALOG, SETTINGS)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["Modular nicht im Tracker: 'Mystery Set'"])
        self.assertEqual([(h["hero"], h["aspect"], h["is_my_hero"], h["slot"]) for h in payload["heroes"]],
                         [("Adam Warlock", "Multi-Aspect", True, 1), ("Echo", "Not Applicable", False, 2)])
        self.assertEqual((payload["difficulty_mode"], payload["villain_stages"]), ("Expert", ["Rhino II", "Rhino III"]))
        self.assertEqual((payload["outcome"], payload["campaign_notes"]), ("Loss to Other", ""))

    def test_fear_no_evil_mission_takes_villain_from_modulars(self):
        payload, errors, warnings = build_payload(play(
            scenario="Art Museum Heist", modulars=["Typhoid Mary", "Cops", "The Owl", "Standard"]),
            WHEN, CATALOG, SETTINGS)
        self.assertEqual((errors, warnings), ([], []))
        self.assertEqual(payload["villain"], "Typhoid Mary")
        self.assertEqual(payload["main_schemes"], ["Art Museum Heist"])
        self.assertEqual(payload["villain_stages"], ["Typhoid Mary I"])
        self.assertEqual([m["mod_name"] for m in payload["modulars"]], ["Cops", "The Owl", "Standard"])

    def test_unrecognised_play_is_skipped(self):
        payload, errors, _ = build_payload(play(scenario=None, heroes=[{"hero": "Nobody", "aspects": [],
                                                                        "is_mine": True}]),
                                           WHEN, CATALOG, SETTINGS)
        self.assertIsNone(payload)
        self.assertEqual(errors, ["Held nicht im Tracker: 'Nobody'", "Szenario nicht erkannt"])

    def test_play_times_order_same_day_by_id(self):
        times = play_times([play(id="7"), play(id="12"), play(id="9", date="2026-08-07")])
        self.assertEqual([times[i].strftime("%d %H:%M") for i in ("7", "12", "9")],
                         ["06 12:00", "06 12:01", "07 12:00"])


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.payload, _, _ = build_payload(play(), WHEN, CATALOG, SETTINGS)

    def tracker_log(self, public_id, payload, **changes):
        """Log so, wie der Tracker es zurückgibt: HTTP-Datum, Objekte statt Namen, escapte Notizen."""
        return {**payload, "public_id": public_id,
                "datetime_happened": "Thu, 06 Aug 2026 12:00:00 GMT",
                "notes": payload["notes"].replace("\n", "\\n"),
                "villain_scenario": {"name": payload["villain"]},
                "villain_stages": [{"name": n} for n in payload["villain_stages"]],
                "modulars": [{"name": m["mod_name"]} for m in payload["modulars"]],
                **changes}

    def test_signature_matches_tracker_shape(self):
        log = self.tracker_log("a", self.payload)
        del log["villain"]
        self.assertEqual(bgg_id_of(log), "100")
        self.assertEqual(signature(log), signature(self.payload))

    def test_create_update_delete_and_manual_logs(self):
        other, _, _ = build_payload(play(id="200", comment="Echo vs Rhino - won"), WHEN, CATALOG, SETTINGS)
        logs = [
            self.tracker_log("same", self.payload),
            self.tracker_log("dupe", self.payload),
            self.tracker_log("changed", other, outcome="Loss to Other"),
            self.tracker_log("orphan", {**self.payload, "notes": "[BGG #999]\n\nweg"}),
            self.tracker_log("manual", {**self.payload, "notes": "selbst eingetragen"}),
        ]
        new, _, _ = build_payload(play(id="300"), WHEN, CATALOG, SETTINGS)
        plan = plan_changes({"100": self.payload, "200": other, "300": new}, {"100", "200", "300"}, logs)
        self.assertEqual([p["notes"][:11] for p in plan.creates], ["[BGG #300]\n"])
        self.assertEqual([(p["public_id"], f) for p, f in plan.updates], [("changed", ["outcome"])])
        self.assertEqual([(log["public_id"], reason) for _, log, reason in plan.deletes],
                         [("dupe", "Duplikat"), ("orphan", "auf BGG gelöscht")])
        self.assertEqual(plan.unchanged, 1)

    def test_skipped_bgg_play_is_not_deleted(self):
        plan = plan_changes({}, {"100"}, [self.tracker_log("keep", self.payload)])
        self.assertEqual((plan.creates, plan.updates, plan.deletes), ([], [], []))

    def test_changed_fields_lists_differences(self):
        log = self.tracker_log("a", self.payload, modulars=[{"name": "Standard"}])
        self.assertEqual(changed_fields(log, self.payload), ["modulars"])


class ClientRetryTests(unittest.TestCase):
    def test_timeouts_retry_reads_but_not_creates(self):
        import requests
        from unittest.mock import Mock, patch
        from tracker_client import TrackerClient, TrackerError
        client = TrackerClient(email="x", password="y", delay=0)
        ok = Mock(status_code=200)
        with patch("tracker_client.time.sleep"):
            client.session.request = Mock(side_effect=[requests.ReadTimeout("t"), ok])
            self.assertIs(client._request("GET", "/api/x"), ok)
            client.session.request = Mock(side_effect=[requests.ReadTimeout("t"), ok])
            with self.assertRaises(TrackerError):
                client._request("POST", "/api/x")
            self.assertEqual(client.session.request.call_count, 1)


class ModuleTests(unittest.TestCase):
    def test_sync_imports_bgg_parser_from_repo_root(self):
        import sync
        self.assertEqual(Path(sync.bgg_source.bgg_parser.__file__).resolve().parent,
                         Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
