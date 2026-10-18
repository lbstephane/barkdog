"""Tests de l'enregistreur : catalogue, réglages, détection, masquage de la parole, épisodes, journal."""
import csv
import json
import os
import tempfile
import time
import types
import unittest
from pathlib import Path

import numpy as np

import fakes
fakes.install()
import bark_logger as b      # noqa: E402
import catalog               # noqa: E402
import config as cfgmod      # noqa: E402


class CatalogTest(unittest.TestCase):
    def test_classes_exist_in_yamnet(self):
        labels = set(fakes.labels())
        for p in catalog.PROFILES + catalog.EXCLUSIONS:
            self.assertFalse([c for c in p["classes"] if c not in labels], p["id"])
        self.assertFalse([c for c in catalog.SPEECH if c not in labels])

    def test_ids_unique(self):
        ids = catalog.PROFILE_IDS + catalog.EXCLUSION_IDS + ["niveau"]
        self.assertEqual(len(ids), len(set(ids)))


class ConfigTest(unittest.TestCase):
    def test_defaults_valid(self):
        self.assertEqual(cfgmod.validate({})["profils"], ["aboiement", "hurlement", "grognement"])

    def test_rejects_bad_values(self):
        for bad in ({"seuil": 2}, {"profils": ["inconnu"]}, {"audio": {"gain": "x"}}, {"parole": "?"},
                    {"exclusions": ["x"]}, {"audio": {"micro": True}}, {"audio": {"micro": "a\nb"}},
                    {"profils": [], "audio": {"seuil_niveau_dbfs": None}}, {"episodes": {"calme_s": 0}}):
            with self.assertRaises(cfgmod.ConfigError, msg=bad):
                cfgmod.validate(bad)

    def test_legacy_migration(self):
        c = cfgmod.from_legacy_args('--device default --gain 4 --highpass 200 --min-detections 3 --ignore "Duck;Quack"')
        self.assertEqual(c["audio"]["micro"], "default")
        self.assertEqual(c["audio"]["gain"], 4)
        self.assertEqual(c["audio"]["coupe_bas_hz"], 200)
        self.assertEqual(c["episodes"]["min_detections"], 3)
        self.assertEqual(c["exclusions"], ["canards"])

    def test_id_and_diff(self):
        a, c = cfgmod.validate({}), cfgmod.validate({"seuil": 0.4})
        self.assertNotEqual(cfgmod.config_id(a), cfgmod.config_id(c))
        self.assertEqual(cfgmod.diff(a, c), ["seuil : 0.3 -> 0.4"])

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c" / "config.json"
            saved = cfgmod.save(p, {"profils": ["coq"]})
            self.assertEqual(cfgmod.load(p), saved)
            p.write_text("{pas du json")
            with self.assertRaises(cfgmod.ConfigError):
                cfgmod.load(p)


class DetectorTest(unittest.TestCase):
    def setUp(self):
        self.labels = fakes.labels()
        self.idx = {l: i for i, l in enumerate(self.labels)}

    def vec(self, **named):
        s = np.full(len(self.labels), 0.01, dtype=np.float32)
        for k, v in named.items():
            s[self.idx[k.replace("_", " ")]] = v
        return s

    def test_threshold_and_exclusion(self):
        d = b.Detector(self.labels, cfgmod.validate({}))
        _, hits, _, _ = d.evaluate(self.vec(Bark=0.6), -30)
        self.assertEqual(hits, ["aboiement"])
        _, hits, ign, _ = d.evaluate(self.vec(Bark=0.4, Quack=0.8), -30)   # canard dominant : ignoré
        self.assertEqual(hits, [])
        self.assertAlmostEqual(ign, 0.8, places=5)
        _, hits, _, _ = d.evaluate(self.vec(Bark=0.2), -30)
        self.assertEqual(hits, [])

    def test_per_profile_threshold_and_multi_label(self):
        d = b.Detector(self.labels, cfgmod.validate({"profils": ["aboiement", "hurlement", "musique"],
                                                     "seuils_profils": {"musique": 0.6}}))
        _, hits, _, _ = d.evaluate(self.vec(Bark=0.5, Howl=0.5, Music=0.5), -30)
        self.assertEqual(sorted(hits), ["aboiement", "hurlement"])

    def test_level_trigger_and_speech(self):
        d = b.Detector(self.labels, cfgmod.validate({"audio": {"seuil_niveau_dbfs": -20}}))
        self.assertIn("niveau", d.categories)
        _, hits, _, sp = d.evaluate(self.vec(Speech=0.7), -10)
        self.assertEqual(hits, ["niveau"])
        self.assertAlmostEqual(sp, 0.7, places=5)


class MaskTest(unittest.TestCase):
    def test_speech_masked_with_fades_outside(self):
        blocks = [np.ones(8000, dtype=np.float32) * 0.5 for _ in range(6)]
        audio, secs, segs = b.mask_speech(blocks, [False, False, False, True, False, False])
        self.assertTrue(np.all(audio[16000:32000] == 0))          # blocs 2 et 3 entièrement muets
        self.assertAlmostEqual(secs, 1.0)
        self.assertEqual(segs, [(1.0, 2.0)])
        self.assertTrue(np.all(audio[:15800] == 0.5))             # avant le fondu : intact
        self.assertTrue(0 < audio[15950] < 0.5)                   # fondu juste avant la zone
        self.assertTrue(np.all(audio[32200:] == 0.5))

    def test_no_speech_untouched(self):
        blocks = [fakes.block(seed=i) for i in range(3)]
        audio, secs, segs = b.mask_speech(blocks, [False] * 3)
        self.assertTrue(np.array_equal(audio, np.concatenate(blocks)))
        self.assertEqual((secs, segs), (0.0, []))


class JournalUpgradeTest(unittest.TestCase):
    def test_v1_to_v2_with_backup(self):
        with tempfile.TemporaryDirectory() as d:
            v1 = ["debut", "fin", "duree_s", "categorie", "nb_detections", "score_max_aboiement",
                  "score_max_hurlement", "score_max_grognement", "niveau_crete_dBFS", "niveau_moyen_dBFS",
                  "horloge_synchronisee", "fichier", "sha256"]
            p = Path(d) / "journal_evenements.csv"
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, v1, delimiter=";")
                w.writeheader()
                w.writerow({k: "" for k in v1} | {"debut": "2026-10-16T05:00:00+02:00", "categorie": "aboiement",
                                                   "score_max_aboiement": "0.71", "score_max_hurlement": "0.2",
                                                   "score_max_grognement": "0.01", "fichier": "a.wav", "sha256": "ab"})
            b.Saver(d)
            rows = list(csv.DictReader(open(p, encoding="utf-8"), delimiter=";"))
            self.assertEqual(list(rows[0].keys()), b.CSV_FIELDS)
            self.assertEqual(rows[0]["scores_max"], "aboiement:0.71|hurlement:0.2|grognement:0.01")
            self.assertEqual(rows[0]["sha256"], "ab")
            self.assertTrue((Path(d) / "journal_evenements.v1.csv").exists())
            b.Saver(d)   # idempotent
            self.assertEqual(len(list(csv.DictReader(open(p, encoding="utf-8"), delimiter=";"))), 1)


class ListenerTest(unittest.TestCase):
    """Chaîne complète : blocs -> épisodes -> fichiers, avec un modèle scénarisé."""

    def make(self, d, scenario, **cfg):
        cfg_path = Path(d) / "config" / "config.json"
        cfg = cfgmod.save(cfg_path, cfg)
        a = types.SimpleNamespace(out=d, verbose=False)
        lst = b.Listener(a, fakes.FakeModel(scenario), b.Saver(d), cfg, cfg_path)
        return lst, cfg_path

    def run_blocks(self, lst, n, t0=1_000_000.0, speed=0.5):
        for i in range(n):
            lst.step(fakes.block(seed=i), t0 + i * speed)

    def wait_saved(self, d, expected):
        for _ in range(50):
            rows = list(csv.DictReader(open(Path(d) / "journal_evenements.csv", encoding="utf-8"), delimiter=";"))
            if len(rows) >= expected:
                return rows
            time.sleep(0.05)
        return rows

    def test_episode_saved_with_timeline_and_config_id(self):
        with tempfile.TemporaryDirectory() as d:
            sc = lambda n: {"Howl": 0.6} if 20 <= n < 26 else ({"Bark": 0.7} if 24 <= n < 40 else {})
            lst, _ = self.make(d, sc, episodes={"pre_s": 2, "calme_s": 3})
            self.run_blocks(lst, 60)
            rows = self.wait_saved(d, 1)
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual(r["categorie"], "aboiement+hurlement")
            self.assertEqual(r["reglages"], lst.cfg_id)
            self.assertIn("hurlement:0.60", r["scores_max"])
            tl = json.loads((Path(d) / r["fichier"]).with_suffix(".json").read_text())
            cats = {s["categorie"] for s in tl["segments"]}
            self.assertEqual(cats, {"aboiement", "hurlement"})
            self.assertEqual(tl["segments"][0]["debut_s"], 1.0)   # 2 s de pré-enregistrement, fenêtre ~1 s

    def test_isolated_detection_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            lst, _ = self.make(d, lambda n: {"Bark": 0.6} if n == 10 else {},
                               episodes={"min_detections": 3, "calme_s": 3})
            self.run_blocks(lst, 30)
            self.assertEqual(self.wait_saved(d, 0), [])
            ign = (Path(d) / "episodes_ignores.csv").read_text()
            self.assertIn("moins de 3 detections", ign)

    def test_speech_masked_in_file(self):
        with tempfile.TemporaryDirectory() as d:
            sc = lambda n: ({"Bark": 0.7} if 10 <= n < 20 else {}) | ({"Speech": 0.8} if n == 15 else {})
            lst, _ = self.make(d, sc, episodes={"pre_s": 1, "calme_s": 2})
            self.run_blocks(lst, 40)
            r = self.wait_saved(d, 1)[0]
            self.assertEqual(float(r["parole_masquee_s"]), 1.0)
            tl = json.loads((Path(d) / r["fichier"]).with_suffix(".json").read_text())
            self.assertEqual(len(tl["parole_masquee"]), 1)

    def test_speech_ignore_episode_mode(self):
        with tempfile.TemporaryDirectory() as d:
            sc = lambda n: {"Bark": 0.7, "Speech": 0.8} if 10 <= n < 20 else {}
            lst, _ = self.make(d, sc, parole="ignorer_episode", episodes={"pre_s": 1, "calme_s": 2})
            self.run_blocks(lst, 40)
            self.assertEqual(self.wait_saved(d, 0), [])
            self.assertIn("parole majoritaire", (Path(d) / "episodes_ignores.csv").read_text())

    def test_hot_reload_and_mic_change(self):
        with tempfile.TemporaryDirectory() as d:
            lst, p = self.make(d, lambda n: {})
            time.sleep(0.01)
            cfgmod.save(p, {"profils": ["coq"], "seuil": 0.4})
            os.utime(p, ns=(time.time_ns(), time.time_ns() + 10**9))
            lst.check_reload()
            self.assertEqual(lst.detector.categories, ["coq"])
            hist = (Path(d) / "historique_ecoute.csv").read_text()
            self.assertIn("modifie : profils", hist)
            cfgmod.save(p, {"profils": ["coq"], "seuil": 0.4, "audio": {"micro": "default"}})
            os.utime(p, ns=(time.time_ns(), time.time_ns() + 2 * 10**9))
            with self.assertRaises(SystemExit) as cm:
                lst.check_reload()
            self.assertEqual(cm.exception.code, b.EXIT_RESTART)

    def test_invalid_config_keeps_previous(self):
        with tempfile.TemporaryDirectory() as d:
            lst, p = self.make(d, lambda n: {})
            p.write_text('{"seuil": 7}')
            os.utime(p, ns=(time.time_ns(), time.time_ns() + 10**9))
            lst.check_reload()
            self.assertEqual(lst.cfg["seuil"], 0.3)
            self.assertIn("reglages invalides", (Path(d) / "historique_ecoute.csv").read_text())

    def test_live_payload(self):
        with tempfile.TemporaryDirectory() as d:
            lst, _ = self.make(d, lambda n: {"Bark": 0.6, "Quack": 0.1})
            live = lst.step(fakes.block(), 1_000_000.0)
            self.assertEqual(live["categories"], ["aboiement", "hurlement", "grognement"])
            self.assertTrue(live["episode"])
            json.dumps(live)   # sérialisable

    def test_devices_published(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "devices.json"
            b.publish_devices(p)
            names = [m["nom"] for m in json.loads(p.read_text())["micros"]]
            self.assertEqual(names, ["USB PnP Sound Device: Audio (hw:2,0)", "default"])


if __name__ == "__main__":
    unittest.main()
