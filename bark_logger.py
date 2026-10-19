#!/usr/bin/env python3
"""
Enregistreur horodaté de nuisances sonores (aboiements, coqs, musique, travaux…) pour Raspberry Pi.

- Écoute le micro en continu (16 kHz mono) et classe le son toutes les 0,5 s avec YAMNet
  (Google, 521 classes AudioSet), entièrement en local.
- Les nuisances à enregistrer, les sons à ignorer, le gain, le filtre… se règlent dans
  config/config.json (page Réglages) et sont relus à chaud.
- Chaque épisode produit un WAV (avec les secondes qui précèdent le déclenchement), sa
  chronologie (.json) et une ligne de journal avec l'empreinte SHA-256 et l'identifiant des réglages.
- Vie privée : les passages où l'IA entend une voix humaine sont rendus muets (par défaut).
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import logging
import os
import queue
import signal
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

import catalog
import config as cfgmod

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        from tensorflow.lite import Interpreter  # type: ignore

HERE = Path(__file__).resolve().parent
SR = 16000          # YAMNet attend du 16 kHz mono
WIN = 15600         # fenêtre d'analyse ~0,975 s
HOP = SR // 2       # analyse toutes les 0,5 s

CSV_FIELDS = [
    "debut", "fin", "duree_s", "categorie", "nb_detections", "scores_max",
    "niveau_crete_dBFS", "niveau_moyen_dBFS", "horloge_synchronisee",
    "parole_masquee_s", "reglages", "fichier", "sha256",
]
EXIT_RESTART = 3    # code de sortie : systemd relance l'écoute (changement de micro)

log = logging.getLogger("barkdog")


# --------------------------------------------------------------------------- utilitaires
def load_labels(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [row["display_name"] for row in csv.DictReader(f)]


def clock_synced():
    """Le Pi n'a pas d'horloge sauvegardée : on vérifie la synchro NTP."""
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return "oui" if out == "yes" else "NON"
    except Exception:
        return "inconnu"


def dbfs(x):
    v = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return round(20 * np.log10(max(v, 1e-9)), 1)


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def clean(text):
    """Les fichiers CSV sont séparés par « ; » : on n'en laisse pas passer dans les textes."""
    return str(text).replace(";", ",").replace("\n", " ")


def append_history(out_dir, evenement, origine):
    """Historique : démarrages, arrêts, réglages appliqués, mode test… Explique les périodes sans écoute."""
    p = Path(out_dir) / "historique_ecoute.csv"
    new = not p.exists()
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("date;evenement;origine\n")
        f.write(f"{now_iso()};{clean(evenement)};{clean(origine)}\n")


def append_ignored(out_dir, ev, raison):
    """Épisodes écartés (trop courts, parole…) : pas de WAV, mais une trace vérifiable."""
    p = Path(out_dir) / "episodes_ignores.csv"
    new = not p.exists()
    start = dt.datetime.fromtimestamp(ev.start_ts).astimezone().isoformat(timespec="seconds")
    smax = max(ev.max_scores.values()) if ev.max_scores else 0
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("debut;duree_s;categories;nb_detections;score_max;raison;reglages\n")
        f.write(f"{start};{ev.duration:.1f};{ev.category()};{ev.hit_blocks};{smax:.2f};{clean(raison)};{ev.cfg_id}\n")


def write_json_atomic(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def make_highpass(freq):
    """Filtre coupe-bas (Butterworth ordre 4) avec état conservé d'un bloc à l'autre :
    supprime le ronflement secteur (50/150 Hz) sans toucher aux nuisances (> 200 Hz)."""
    if not freq or freq <= 0:
        return None
    try:
        from scipy import signal as sps
    except ImportError:
        log.warning("Filtre coupe-bas ignoré : installer scipy (.venv/bin/pip install scipy)")
        return None
    sos = sps.butter(4, freq, "highpass", fs=SR, output="sos")
    state = {"zi": np.zeros((sos.shape[0], 2))}

    def process(block):
        y, state["zi"] = sps.sosfilt(sos, block, zi=state["zi"])
        return y.astype(np.float32)
    return process


def test_active(path):
    """Mode test demandé par la page web : fichier en mémoire vive avec une échéance (renouvelée par la page)."""
    if not path:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return time.time() < float(json.load(f).get("until", 0))
    except (OSError, ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------- chronologie
MERGE_GAP = 1.5   # deux détections d'une même catégorie à moins de 1,5 s = un seul passage


def add_mark(lst, start, end, score, gap=MERGE_GAP):
    """Ajoute une détection [start, end] (secondes dans le fichier), fusionnée avec la précédente si proche."""
    if lst and start - lst[-1][1] <= gap:
        lst[-1][1] = max(lst[-1][1], end)
        lst[-1][2] = max(lst[-1][2], score)
    else:
        lst.append([start, end, score])


def timeline_segments(marks):
    segs = [{"categorie": c, "debut_s": round(s, 1), "fin_s": round(e, 1), "score_max": round(v, 2)}
            for c, lst in marks.items() for s, e, v in lst]
    return sorted(segs, key=lambda x: (x["debut_s"], x["categorie"]))


def write_timeline(wav_path, duration, marks, masked=()):
    """Fichier .json à côté du WAV : à quels moments l'IA a entendu quoi, et où la parole a été masquée."""
    data = {"version": 2, "duree_s": round(duration, 1), "segments": timeline_segments(marks),
            "parole_masquee": [{"debut_s": round(a, 1), "fin_s": round(b, 1)} for a, b in masked]}
    Path(wav_path).with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- modèle et détection
class Model:
    """YAMNet (TFLite / LiteRT) : 521 scores indépendants par fenêtre de 0,975 s."""

    def __init__(self, model_path, labels, threads):
        self.labels = labels
        self.last = None
        self.it = Interpreter(model_path=str(model_path), num_threads=threads)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]
        self.out = self.it.get_output_details()[0]

    def infer(self, window):
        self.it.set_tensor(self.inp["index"], window.astype(np.float32).reshape(self.inp["shape"]))
        self.it.invoke()
        self.last = self.it.get_tensor(self.out["index"]).reshape(-1)
        return self.last

    def top(self, k=4):
        """Les k classes les plus probables (ce que l'IA « entend »)."""
        if self.last is None:
            return []
        idx = np.argsort(self.last)[-k:][::-1]
        return [[self.labels[i] if i < len(self.labels) else str(i), round(float(self.last[i]), 3)] for i in idx]


class Detector:
    """Traduit les 521 scores YAMNet en nuisances, selon la configuration."""

    def __init__(self, labels, cfg):
        idx = {l: i for i, l in enumerate(labels)}

        def indices(classes, what):
            found = [idx[c] for c in classes if c in idx]
            missing = [c for c in classes if c not in idx]
            if missing:
                log.warning("%s : classes absentes du modèle %s", what, missing)
            return found

        self.cats = {pid: indices(catalog.profile(pid)["classes"], pid) for pid in cfg["profils"]}
        self.thr = {pid: cfg["seuils_profils"].get(pid, cfg["seuil"]) for pid in cfg["profils"]}
        self.ignore_idx = sorted({i for e in catalog.EXCLUSIONS if e["id"] in cfg["exclusions"]
                                  for i in indices(e["classes"], e["id"])})
        self.speech_idx = indices(catalog.SPEECH, "parole")
        self.speech_on = cfg["parole"] != "desactive"
        self.speech_thr = cfg["seuil_parole"]
        self.level_thr = cfg["audio"]["seuil_niveau_dbfs"]
        self.categories = list(self.cats) + (["niveau"] if self.level_thr is not None else [])

    def evaluate(self, s, level_db):
        scores = {pid: (float(s[ix].max()) if ix else 0.0) for pid, ix in self.cats.items()}
        ignore = float(s[self.ignore_idx].max()) if self.ignore_idx else 0.0
        speech = float(s[self.speech_idx].max()) if self.speech_idx else 0.0
        # une nuisance compte si elle passe son seuil ET n'est pas dominée par un son à ignorer (canards…)
        hits = [pid for pid, v in scores.items() if v >= self.thr[pid] and v > ignore]
        if self.level_thr is not None:
            loud = level_db >= self.level_thr
            scores["niveau"] = 1.0 if loud else 0.0
            if loud:
                hits.append("niveau")
        return scores, hits, ignore, speech


# --------------------------------------------------------------------------- épisodes
class Event:
    def __init__(self, start_ts, items, cfg, cfg_id, now):
        self.start_ts = start_ts
        self.blocks = [b for b, _ in items]
        self.speech = [s for _, s in items]       # parole entendue dans chaque bloc
        self.last_hit = now                       # horloge du flux audio, pas l'horloge murale
        self.hits = collections.Counter()
        self.max_scores = collections.defaultdict(float)
        self.marks = collections.defaultdict(list)
        self.saved = False
        self.test_start = False    # épisode commencé pendant le mode test
        self.hit_blocks = 0        # nombre de demi-secondes avec détection
        self.cfg_id = cfg_id
        self.parole = cfg["parole"]

    def append(self, block, speech_flag):
        self.blocks.append(block)
        self.speech.append(speech_flag)

    def update_scores(self, scores):
        for c, v in scores.items():
            self.max_scores[c] = max(self.max_scores[c], v)

    def add_hits(self, cats, scores, now):
        """YAMNet est multi-étiquettes : un même bloc peut être aboiement ET hurlement."""
        t_end = self.duration                  # fin de la fenêtre analysée, en s depuis le début du fichier
        self.hit_blocks += 1
        for c in cats:
            self.hits[c] += 1
            add_mark(self.marks[c], max(0.0, t_end - WIN / SR), t_end, scores.get(c, 1.0))
        self.last_hit = now
        self.update_scores(scores)

    @property
    def duration(self):
        return sum(len(b) for b in self.blocks) / SR

    @property
    def speech_ratio(self):
        return sum(self.speech) / len(self.speech) if self.speech else 0.0

    def category(self):
        # Toute catégorie détectée au moins 2 fois (≈1 s), ou une fois avec un score net, apparaît dans le nom.
        cats = [c for c, n in self.hits.most_common() if n >= 2 or self.max_scores[c] >= 0.5]
        if not cats and self.hits:
            cats = [self.hits.most_common(1)[0][0]]
        return "+".join(cats) if cats else "inconnu"


def mask_speech(blocks, flags):
    """Rend muets les passages avec de la voix (le bloc analysé et le précédent, couverts par la fenêtre),
    avec des fondus de 10 ms pour éviter les clics. Renvoie (audio, secondes masquées, segments)."""
    audio = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
    if not any(flags):
        return audio, 0.0, []
    edges = np.cumsum([0] + [len(b) for b in blocks])
    keep = np.ones(len(audio), dtype=np.float32)
    for i, f in enumerate(flags):
        if f:
            keep[edges[max(0, i - 1)]:edges[i + 1]] = 0.0
    ramp = 160
    # fondu uniquement à l'extérieur des zones muettes : la parole reste entièrement masquée
    padded = np.pad(keep, (ramp // 2, ramp - ramp // 2 - 1), mode="edge")   # pas de fondu aux extrémités
    smooth = np.minimum(np.convolve(padded, np.ones(ramp) / ramp, mode="valid"), keep)
    segs, start = [], None
    for i, k in enumerate(keep[::HOP // 10]):           # résolution 50 ms
        t = i * (HOP // 10) / SR
        if k == 0 and start is None:
            start = t
        elif k != 0 and start is not None:
            segs.append((start, t)); start = None
    if start is not None:
        segs.append((start, len(audio) / SR))
    return audio * smooth, float((keep == 0).sum()) / SR, segs


class Saver:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.out_dir / "journal_evenements.csv"
        self.lock = threading.Lock()
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, CSV_FIELDS, delimiter=";").writeheader()

    def save(self, ev: Event):
        # thread non « daemon » : Python attend la fin de l'écriture avant de quitter
        ev.saved = True
        threading.Thread(target=self._save, args=(ev,)).start()

    def _save(self, ev: Event):
        flags = ev.speech if ev.parole == "masquer" else [False] * len(ev.blocks)
        audio, masked_s, masked_segs = mask_speech(ev.blocks, flags)
        start = dt.datetime.fromtimestamp(ev.start_ts).astimezone()
        end = start + dt.timedelta(seconds=len(audio) / SR)
        cat = ev.category()
        day_dir = self.out_dir / start.strftime("%Y-%m-%d")
        day_dir.mkdir(exist_ok=True)
        wav_path = day_dir / f"{start.strftime('%Y-%m-%d_%Hh%Mm%Ss')}_{cat}.wav"
        n = 1
        while wav_path.exists():          # deux épisodes dans la même seconde : jamais d'écrasement
            n += 1
            wav_path = day_dir / f"{start.strftime('%Y-%m-%d_%Hh%Mm%Ss')}_{cat}_{n}.wav"

        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        sha = hashlib.sha256(wav_path.read_bytes()).hexdigest()
        try:
            write_timeline(wav_path, len(audio) / SR, ev.marks, masked_segs)
        except OSError as e:
            log.warning("Chronologie non écrite : %s", e)

        row = {
            "debut": start.isoformat(timespec="seconds"),
            "fin": end.isoformat(timespec="seconds"),
            "duree_s": round(len(audio) / SR, 1),
            "categorie": cat,
            "nb_detections": ev.hit_blocks,
            "scores_max": "|".join(f"{c}:{v:.2f}" for c, v in sorted(ev.max_scores.items()) if v > 0),
            "niveau_crete_dBFS": round(20 * np.log10(max(float(np.abs(audio).max()) if audio.size else 0, 1e-9)), 1),
            "niveau_moyen_dBFS": dbfs(audio),
            "horloge_synchronisee": clock_synced(),
            "parole_masquee_s": round(masked_s, 1),
            "reglages": ev.cfg_id,
            "fichier": str(wav_path.relative_to(self.out_dir)),
            "sha256": sha,
        }
        with self.lock, open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, CSV_FIELDS, delimiter=";").writerow(row)
        log.info("Événement enregistré : %s %s (%.0f s%s)", row["debut"], cat, row["duree_s"],
                 f", parole masquée {masked_s:.1f} s" if masked_s else "")


# --------------------------------------------------------------------------- écoute
class Listener:
    def __init__(self, a, model, saver, cfg, cfg_path):
        self.a, self.model, self.saver, self.cfg_path = a, model, saver, Path(cfg_path)
        self.event = None
        self.last_outcome = None
        self.test_now = False
        self.window = np.zeros(WIN, dtype=np.float32)
        self.preroll = collections.deque(maxlen=1)
        self.cfg_mtime = self._mtime()
        self.apply(cfg)

    def _mtime(self):
        try:
            return self.cfg_path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def apply(self, cfg):
        self.cfg = cfg
        self.cfg_id = cfgmod.config_id(cfg)
        self.detector = Detector(self.model.labels, cfg)
        self.highpass = make_highpass(cfg["audio"]["coupe_bas_hz"])
        self.gain = cfg["audio"]["gain"]
        ep = cfg["episodes"]
        self.preroll = collections.deque(self.preroll, maxlen=max(1, int(ep["pre_s"] * SR / HOP)))
        log.info("Réglages %s : nuisances %s, seuil %g, gain %g, coupe-bas %s, parole %s, min %d détection(s), "
                 "exclusions %s", self.cfg_id, ",".join(self.detector.categories), cfg["seuil"], self.gain,
                 f"{cfg['audio']['coupe_bas_hz']} Hz" if self.highpass else "aucun", cfg["parole"],
                 ep["min_detections"], ",".join(cfg["exclusions"]) or "aucune")

    def summary(self):
        c, ep = self.cfg, self.cfg["episodes"]
        return (f"reglages {self.cfg_id} : nuisances {' '.join(self.detector.categories)}, seuil {c['seuil']:g}, "
                f"gain {c['audio']['gain']:g}, coupe-bas {c['audio']['coupe_bas_hz'] if self.highpass else 0} Hz, "
                f"parole {c['parole']}, min {ep['min_detections']} detection(s), "
                f"exclusions {' '.join(c['exclusions']) or 'aucune'}")

    def check_reload(self):
        """Relit config.json s'il a changé. Changement de micro : sortie, systemd relance l'écoute."""
        m = self._mtime()
        if m == self.cfg_mtime:
            return
        self.cfg_mtime = m
        try:
            new = cfgmod.load(self.cfg_path)
        except cfgmod.ConfigError as e:
            log.error("config.json invalide, réglages précédents conservés : %s", e)
            append_history(self.a.out, f"reglages invalides ignores ({e})", "enregistreur")
            return
        changes = cfgmod.diff(self.cfg, new)
        if not changes:
            return
        if new["audio"]["micro"] != self.cfg["audio"]["micro"]:
            log.info("Micro changé : redémarrage de l'écoute")
            append_history(self.a.out, f"changement de micro, redemarrage ({' / '.join(changes)})", "enregistreur")
            raise SystemExit(EXIT_RESTART)
        self.apply(new)
        append_history(self.a.out, f"{self.summary()} -- modifie : {' / '.join(changes)}", "enregistreur")

    def close_event(self):
        ev, ep = self.event, self.cfg["episodes"]
        if ev.hit_blocks < ep["min_detections"]:
            log.info("Épisode ignoré : %d détection(s) < %d", ev.hit_blocks, ep["min_detections"])
            append_ignored(self.a.out, ev, f"moins de {ep['min_detections']} detections")
            ev.saved, self.last_outcome = True, "ignore"
        elif ev.parole == "ignorer_episode" and ev.speech_ratio > 0.3:
            log.info("Épisode ignoré : parole dans %.0f %% des blocs", ev.speech_ratio * 100)
            append_ignored(self.a.out, ev, f"parole majoritaire ({ev.speech_ratio * 100:.0f} %)")
            ev.saved, self.last_outcome = True, "ignore"
        elif ev.test_start and self.test_now:
            # commencé ET terminé en mode test : rien n'est écrit, mais c'est tracé
            log.info("Mode test : épisode %s de %.0f s non enregistré", ev.category(), ev.duration)
            append_history(self.a.out, f"mode test : episode non enregistre ({ev.category()}, {ev.duration:.0f} s)",
                           "enregistreur")
            ev.saved, self.last_outcome = True, "test"
        else:
            self.saver.save(ev)
            self.last_outcome = "enregistre"
        self.event = None

    def step(self, block, now):
        """Traite un bloc de 0,5 s. Renvoie les informations pour le mode test."""
        block = block * self.gain
        if self.highpass:
            block = self.highpass(block)
        self.window = np.concatenate([self.window, block])[-WIN:]
        level = dbfs(block)
        s = self.model.infer(self.window)
        scores, hits, ignore, speech = self.detector.evaluate(s, level)
        speech_flag = self.detector.speech_on and speech >= self.detector.speech_thr
        ep = self.cfg["episodes"]

        if self.a.verbose:
            log.info("niveau %6.1f dBFS | %s | parole %.2f | ignorés %.2f", level,
                     "  ".join(f"{c}={v:.2f}" for c, v in scores.items()), speech, ignore)

        if self.event is None:
            self.preroll.append((block, speech_flag))
            if hits:
                start_ts = now - sum(len(b) for b, _ in self.preroll) / SR
                self.event = Event(start_ts, self.preroll, self.cfg, self.cfg_id, now)
                self.event.test_start = self.test_now
                self.preroll.clear()
                self.event.add_hits(hits, scores, now)
                log.info("Déclenchement : %s", ", ".join(f"{c} {scores[c]:.2f}" for c in hits))
        else:
            self.event.append(block, speech_flag)
            if hits:
                self.event.add_hits(hits, scores, now)
            else:
                self.event.update_scores(scores)
            if now - self.event.last_hit > ep["calme_s"] or self.event.duration >= ep["max_s"]:
                self.close_event()
        LISTEN_STATE["listener"] = self

        ev = self.event
        return {
            "ts": round(now, 2), "niveau_dBFS": level,
            "categories": self.detector.categories,
            "scores": {c: round(v, 3) for c, v in scores.items()},
            "seuils": {**self.detector.thr, **({"niveau": 1.0} if "niveau" in scores else {})},
            "seuil": self.cfg["seuil"], "detection": hits, "top": self.model.top(4),
            "parole": round(speech, 3), "parole_active": speech_flag,
            "parole_mode": self.cfg["parole"], "seuil_parole": self.detector.speech_thr,
            "ignore": round(ignore, 3),
            "episode": ev is not None, "episode_s": round(ev.duration, 1) if ev else 0,
            # épisode commencé pendant le test (et test toujours actif) : il ne sera pas enregistré
            "episode_test": bool(ev and ev.test_start and self.test_now),
            "episode_tags": [c for c in self.detector.categories if ev and ev.hits.get(c)],
            "test": self.test_now, "dernier": self.last_outcome, "reglages": self.cfg_id,
        }


LISTEN_STATE = {"listener": None}


def publish_devices(path):
    """Liste des micros pour la page Réglages (en mémoire vive)."""
    try:
        devs = [{"index": i, "nom": d["name"], "canaux": d["max_input_channels"],
                 "frequence": int(d["default_samplerate"])}
                for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
        write_json_atomic(path, {"ts": time.time(), "micros": devs})
    except Exception as e:
        log.warning("Liste des micros non publiée : %s", e)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", "--data", dest="out", default=str(HERE / "enregistrements"), help="dossier des enregistrements")
    p.add_argument("--config", default=str(HERE / "config" / "config.json"))
    p.add_argument("--model", default=str(HERE / "yamnet.tflite"))
    p.add_argument("--labels", default=str(HERE / "yamnet_class_map.csv"))
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--live-file", default="/dev/shm/barkdog-live.json",
                   help="scores en direct pour le mode test de la page web ('' pour désactiver)")
    p.add_argument("--test-file", default="/dev/shm/barkdog-test.json")
    p.add_argument("--devices-file", default="/dev/shm/barkdog-devices.json")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--verbose", action="store_true", help="affiche les scores en continu (réglage)")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.list_devices:
        print(sd.query_devices())
        return

    cfg_path = Path(a.config)
    if not cfg_path.exists():
        cfg = cfgmod.save(cfg_path, cfgmod.validate({}))
        log.info("config.json créé (valeurs par défaut)")
    else:
        try:
            cfg = cfgmod.load(cfg_path)
        except cfgmod.ConfigError as e:
            log.error("config.json invalide (%s) : valeurs par défaut utilisées", e)
            cfg = cfgmod.validate({})

    labels = load_labels(a.labels)
    model = Model(a.model, labels, a.threads)
    saver = Saver(a.out)
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=200)

    def callback(indata, frames, t, status):
        if status:
            log.warning("Audio : %s", status)
        try:
            q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            log.warning("Analyse trop lente, bloc audio perdu")

    def on_term(signum, frame):   # systemctl stop -> sortie propre (l'épisode en cours est sauvegardé)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, on_term)

    if a.devices_file:
        publish_devices(a.devices_file)
    listener = Listener(a, model, saver, cfg, cfg_path)
    LISTEN_STATE["listener"] = listener
    log.info("Horloge synchronisée : %s", clock_synced())
    try:
        listen(a, listener, q, callback)
    finally:
        ev = listener.event
        if ev is not None and not ev.saved:
            if ev.test_start and test_active(a.test_file):
                log.info("Arrêt pendant un épisode de test : non enregistré")
            elif ev.hit_blocks < listener.cfg["episodes"]["min_detections"]:
                log.info("Arrêt pendant un épisode trop court : ignoré")
                try:
                    append_ignored(a.out, ev, "arret pendant un episode trop court")
                except OSError:
                    pass
            else:
                log.info("Arrêt pendant un épisode : sauvegarde de l'enregistrement en cours")
                saver._save(ev)
        if a.live_file:
            try:
                os.remove(a.live_file)
            except OSError:
                pass
        try:
            append_history(a.out, "ecoute arretee", "enregistreur")
        except OSError:
            pass
        log.info("Écoute arrêtée")


def listen(a, listener, q, callback):
    last_heartbeat = last_beat_file = last_test_check = last_cfg_check = 0.0
    test_prev = False
    heartbeat = Path(a.out) / ".heartbeat"
    micro = listener.cfg["audio"]["micro"]
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=HOP, device=micro, callback=callback):
        log.info("En écoute (micro : %s, pré-enregistrement %g s)", micro if micro is not None else "par défaut",
                 listener.cfg["episodes"]["pre_s"])
        try:   # réglages notés : traçabilité du traitement appliqué aux enregistrements
            append_history(a.out, f"ecoute demarree ({listener.summary()})", "enregistreur")
        except OSError as e:
            log.warning("Historique non écrit : %s", e)
        while True:
            block = q.get()
            now = time.time()

            if now - last_cfg_check >= 2:       # réglages modifiés depuis la page ?
                listener.check_reload()
                last_cfg_check = now

            if now - last_beat_file > 30:       # signe de vie lu par l'interface web
                try:
                    heartbeat.write_text(now_iso())
                except OSError as e:
                    log.warning("Signe de vie non écrit : %s", e)
                last_beat_file = now

            if now - last_test_check >= 1:      # mode test (pas d'enregistrement) ?
                listener.test_now, last_test_check = test_active(a.test_file), now
                if listener.test_now != test_prev:
                    log.info("Mode test %s", "activé : pas d'enregistrement" if listener.test_now
                             else "terminé : enregistrement réactivé")
                    try:
                        append_history(a.out, "mode test debut (pas d'enregistrement)" if listener.test_now
                                       else "mode test fin (enregistrement reactive)", "page web")
                    except OSError:
                        pass
                    test_prev = listener.test_now

            if now - last_heartbeat > 3600:     # preuve que le système tournait
                log.info("Toujours en écoute (horloge synchro : %s)", clock_synced())
                last_heartbeat = now

            live = listener.step(block, now)
            if a.live_file:
                try:
                    write_json_atomic(a.live_file, live)
                except OSError as e:
                    log.warning("Mode test désactivé (%s)", e)
                    a.live_file = ""


if __name__ == "__main__":
    main()
