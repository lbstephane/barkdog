#!/usr/bin/env python3
"""
Recrée la chronologie (.json : à quel moment quelle nuisance) d'enregistrements existants,
avec les réglages actuels (nuisances choisies, seuils, exclusions).

  .venv/bin/python reanalyse.py              # seulement les WAV sans chronologie
  .venv/bin/python reanalyse.py --force      # tout recalculer (ex. après ajout d'une nuisance)

Les WAV et le journal ne sont jamais modifiés. Peut tourner pendant l'écoute (plus lent).
"""
import argparse
import json
import logging
import wave
from pathlib import Path

import numpy as np

import bark_logger as b
import config as cfgmod

HERE = Path(__file__).resolve().parent


def analyse(model, detector, wav_path):
    with wave.open(str(wav_path), "rb") as w:
        if w.getframerate() != b.SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("format inattendu (16 kHz mono 16 bits attendu)")
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    marks = {c: [] for c in detector.categories}
    window = np.zeros(b.WIN, dtype=np.float32)
    for i in range(0, len(x), b.HOP):          # même découpage que l'écoute en direct
        block = x[i:i + b.HOP]
        window = np.concatenate([window, block])[-b.WIN:]
        scores, hits, _, _ = detector.evaluate(model.infer(window), b.dbfs(block))
        t_end = (i + len(block)) / b.SR
        for c in hits:
            b.add_mark(marks[c], max(0.0, t_end - b.WIN / b.SR), t_end, scores.get(c, 1.0))
    # conserve la trace du masquage de la parole faite à l'enregistrement
    masked = []
    side = wav_path.with_suffix(".json")
    if side.exists():
        try:
            masked = [(m["debut_s"], m["fin_s"]) for m in json.loads(side.read_text(encoding="utf-8")).get("parole_masquee", [])]
        except (ValueError, KeyError):
            pass
    b.write_timeline(wav_path, len(x) / b.SR, marks, masked)
    return b.timeline_segments(marks)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(HERE / "enregistrements"))
    p.add_argument("--config", default=str(HERE / "config" / "config.json"))
    p.add_argument("--model", default=str(HERE / "yamnet.tflite"))
    p.add_argument("--labels", default=str(HERE / "yamnet_class_map.csv"))
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--force", action="store_true", help="recalculer même si la chronologie existe")
    a = p.parse_args()
    logging.basicConfig(level=logging.WARNING)

    labels = b.load_labels(a.labels)
    model = b.Model(a.model, labels, a.threads)
    detector = b.Detector(labels, cfgmod.load(a.config))
    wavs = sorted(w for w in Path(a.out).rglob("*.wav"))
    todo = [w for w in wavs if a.force or not w.with_suffix(".json").exists()]
    print(f"{len(todo)} enregistrement(s) à analyser sur {len(wavs)}")
    for n, w in enumerate(todo, 1):
        try:
            segs = analyse(model, detector, w)
            resume = ", ".join(f"{s['categorie']} {s['debut_s']:.0f}-{s['fin_s']:.0f}s" for s in segs[:6])
            print(f"[{n}/{len(todo)}] {w.name} : {resume or 'aucune détection'}")
        except Exception as e:
            print(f"[{n}/{len(todo)}] {w.name} : ERREUR {e}")


if __name__ == "__main__":
    main()
