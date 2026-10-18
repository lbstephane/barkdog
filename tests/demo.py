#!/usr/bin/env python3
"""
Démonstration sans matériel : lance le vrai enregistreur avec un faux micro et un faux modèle,
qui joue un scénario (hurlements puis aboiements, une voix, des canards…) en boucle.

  python3 tests/demo.py --out /tmp/demo/enregistrements --config /tmp/demo/config/config.json --speed 4
  python3 web.py --out /tmp/demo/enregistrements --config-dir /tmp/demo/config --no-service-control

Puis ouvrir http://localhost:8080 (mot de passe : python3 auth.py --config-dir /tmp/demo/config --set).
"""
import sys
import threading
import time
import types

import numpy as np

import fakes

SPEED = 1.0
for i, arg in enumerate(sys.argv):
    if arg == "--speed":
        SPEED = float(sys.argv[i + 1])
        del sys.argv[i:i + 2]
        break

LABELS = fakes.labels()
IDX = {l: i for i, l in enumerate(LABELS)}


def scenario(n):
    t = n % 120                     # cycle de 60 s (blocs de 0,5 s)
    s = {}
    if 10 <= t < 18:
        s["Howl"] = 0.62            # hurlements
    if 14 <= t < 30:
        s["Bark"] = 0.74            # puis aboiements (chevauchement)
    if t == 22:
        s["Speech"] = 0.8           # quelqu'un parle : masqué dans le fichier
    if 60 <= t < 66:
        s["Bark"], s["Quack"] = 0.4, 0.8   # canards confondus avec des aboiements : ignorés
    if t == 90:
        s["Bark"] = 0.6             # aboiement isolé
    s["Speech"] = max(s.get("Speech", 0), 0.12)
    return s


class Interp:
    n = 0

    def __init__(self, model_path, num_threads):
        pass

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{"shape": [15600], "index": 0}]

    def get_output_details(self):
        return [{"index": 1}]

    def set_tensor(self, i, x):
        pass

    def invoke(self):
        Interp.n += 1

    def get_tensor(self, i):
        v = np.full(len(LABELS), 0.01, dtype=np.float32)
        for k, x in scenario(Interp.n).items():
            v[IDX[k]] = x
        return v.reshape(1, -1)


class InputStream:
    def __init__(self, samplerate, channels, dtype, blocksize, device, callback):
        self.cb, self.bs = callback, blocksize

    def __enter__(self):
        def feed():
            k = 0
            while True:
                amp = 0.25 if 10 <= (k % 120) < 30 else 0.02
                self.cb((np.random.randn(self.bs, 1) * amp).astype("float32"), self.bs, None, None)
                k += 1
                time.sleep(0.5 / SPEED)
        threading.Thread(target=feed, daemon=True).start()
        return self

    def __exit__(self, *a):
        pass


fakes.install()
sys.modules["sounddevice"].InputStream = InputStream
sys.modules["tflite_runtime.interpreter"].Interpreter = Interp
sys.argv += ["--labels", str(fakes.DATA / "yamnet_class_map.csv"), "--model", "factice"]

import bark_logger  # noqa: E402
bark_logger.main()
