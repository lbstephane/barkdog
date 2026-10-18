"""Faux micro et faux modèle : permettent de tester toute la chaîne sans matériel ni YAMNet."""
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(ROOT))


def install():
    """Remplace sounddevice et le moteur TFLite par des modules factices (avant d'importer bark_logger)."""
    sd = types.ModuleType("sounddevice")
    sd.query_devices = lambda: [
        {"name": "bcm2835 Headphones", "max_input_channels": 0, "default_samplerate": 48000.0},
        {"name": "USB PnP Sound Device: Audio (hw:2,0)", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "default", "max_input_channels": 32, "default_samplerate": 44100.0},
    ]
    sd.InputStream = None
    sys.modules["sounddevice"] = sd
    mi = types.ModuleType("tflite_runtime.interpreter")
    mi.Interpreter = object
    sys.modules["tflite_runtime"] = types.ModuleType("tflite_runtime")
    sys.modules["tflite_runtime.interpreter"] = mi


def labels():
    import csv
    with open(DATA / "yamnet_class_map.csv", newline="", encoding="utf-8") as f:
        return [r["display_name"] for r in csv.DictReader(f)]


class FakeModel:
    """Renvoie, pour chaque bloc, des scores définis par un scénario : {nom de classe: score}."""

    def __init__(self, scenario):
        self.labels = labels()
        self.idx = {l: i for i, l in enumerate(self.labels)}
        self.scenario = scenario     # fonction n -> dict
        self.n = 0
        self.last = None

    def infer(self, window):
        s = np.full(len(self.labels), 0.01, dtype=np.float32)
        for name, v in self.scenario(self.n).items():
            s[self.idx[name]] = v
        self.n += 1
        self.last = s
        return s

    def top(self, k=4):
        idx = np.argsort(self.last)[-k:][::-1]
        return [[self.labels[i], float(self.last[i])] for i in idx]


def block(amp=0.05, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(8000) * amp).astype(np.float32)
