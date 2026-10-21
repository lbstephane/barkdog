"""
Réglages de l'écoute : config/config.json, seule source de vérité.

- modifiés depuis la page Réglages (web.py) et relus à chaud par l'enregistreur ;
- validés et bornés ici, des deux côtés ;
- chaque version a un identifiant court (empreinte) noté dans le journal et l'historique :
  on sait toujours avec quels réglages un fichier a été produit.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import catalog

DEFAULT = {
    "version": 3,
    "profils": [p["id"] for p in catalog.PROFILES if p.get("defaut")],
    "perso": [],                   # nuisances personnalisées : [{"id", "label", "classes": [classes YAMNet]}]
    "exclusions": [e["id"] for e in catalog.EXCLUSIONS if e.get("defaut")],
    "seuil": 0.30,                 # score YAMNet mini pour compter une détection
    "seuils_profils": {},          # seuil propre à un profil, ex. {"musique": 0.5}
    "parole": "masquer",           # masquer | ignorer_episode | desactive
    "seuil_parole": 0.50,
    "audio": {
        "micro": None,             # None = périphérique par défaut ; sinon nom ou index (voir la page)
        "gain": 1.0,
        "coupe_bas_hz": 0,         # filtre coupe-bas contre le ronflement secteur (0 = aucun)
        "seuil_niveau_dbfs": None, # déclenchement sur le niveau seul (None = désactivé)
    },
    "episodes": {
        "pre_s": 10,               # secondes gardées avant le déclenchement
        "calme_s": 15,             # secondes de calme pour clore un épisode
        "max_s": 300,              # durée max d'un fichier
        "min_detections": 1,       # demi-secondes détectées mini (3 = ignore un son isolé)
    },
}

PAROLE_MODES = ("masquer", "ignorer_episode", "desactive")
PERSO_MAX = 10           # nuisances personnalisées
PERSO_CLASSES_MAX = 10   # classes YAMNet par nuisance personnalisée
PERSO_ID = re.compile(r"[a-z][a-z0-9_]{0,23}")   # sert aussi dans les noms de fichiers : rien d'autre


class ConfigError(ValueError):
    pass


def _num(v, lo, hi, name, integer=False):
    try:
        x = int(v) if integer else float(v)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} : nombre attendu")
    if not (lo <= x <= hi):
        raise ConfigError(f"{name} : doit être entre {lo} et {hi}")
    return x


def _perso(raw):
    """Nuisances personnalisées : identifiant sûr (noms de fichiers), nom lisible, classes YAMNet existantes."""
    if not isinstance(raw, list):
        raise ConfigError("nuisance personnalisée invalide")
    if len(raw) > PERSO_MAX:
        raise ConfigError(f"nuisances personnalisées : {PERSO_MAX} au maximum")
    known = set(catalog.yamnet_classes())
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigError("nuisance personnalisée invalide")
        pid, label, classes = item.get("id"), item.get("label"), item.get("classes")
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 40) or any(ord(c) < 32 for c in label):
            raise ConfigError("nuisance personnalisée : nom de 1 à 40 caractères")
        label = label.strip().replace(";", ",")
        if not isinstance(pid, str) or not PERSO_ID.fullmatch(pid):
            raise ConfigError("nuisance personnalisée invalide")
        if pid in catalog.RESERVED_IDS or pid in seen:
            raise ConfigError(f"identifiant déjà utilisé : {pid}")
        if (not isinstance(classes, list) or not (1 <= len(classes) <= PERSO_CLASSES_MAX)
                or not all(isinstance(c, str) for c in classes)):
            raise ConfigError(f"nuisance personnalisée « {label} » : choisir de 1 à {PERSO_CLASSES_MAX} sons")
        for c in classes:
            if (known and c not in known) or len(c) > 100 or any(ord(x) < 32 for x in c):
                raise ConfigError(f"nuisance personnalisée « {label} » : son inconnu « {c[:100]} »")
        seen.add(pid)
        out.append({"id": pid, "label": label, "classes": list(dict.fromkeys(classes))})
    return out


def validate(raw):
    """Fusionne avec les valeurs par défaut, contrôle types et bornes. Lève ConfigError."""
    if not isinstance(raw, dict):
        raise ConfigError("format invalide")
    cfg = copy.deepcopy(DEFAULT)
    for k in ("audio", "episodes"):
        if isinstance(raw.get(k), dict):
            cfg[k].update({kk: vv for kk, vv in raw[k].items() if kk in cfg[k]})
    for k in ("profils", "perso", "exclusions", "seuil", "seuils_profils", "parole", "seuil_parole"):
        if k in raw:
            cfg[k] = raw[k]

    cfg["perso"] = _perso(cfg["perso"])
    all_ids = catalog.PROFILE_IDS + [c["id"] for c in cfg["perso"]]
    if not isinstance(cfg["profils"], list) or not all(isinstance(p, str) for p in cfg["profils"]):
        raise ConfigError("profils : liste attendue")
    unknown = [p for p in cfg["profils"] if p not in all_ids]
    if unknown:
        raise ConfigError(f"profils inconnus : {', '.join(unknown)}")
    cfg["profils"] = [p for p in all_ids if p in cfg["profils"]]   # ordre du catalogue, puis perso, sans doublon
    if not isinstance(cfg["exclusions"], list) or any(e not in catalog.EXCLUSION_IDS for e in cfg["exclusions"]):
        raise ConfigError("exclusions inconnues")
    cfg["exclusions"] = [e for e in catalog.EXCLUSION_IDS if e in cfg["exclusions"]]
    for e in catalog.EXCLUSIONS:
        clash = [p for p in e.get("conflits", []) if e["id"] in cfg["exclusions"] and p in cfg["profils"]]
        if clash:
            raise ConfigError(f"« {catalog.profile(clash[0])['label']} » et le son à ignorer « {e['label']} » "
                              "s'excluent : décocher l'un des deux")

    cfg["seuil"] = _num(cfg["seuil"], 0.05, 0.95, "seuil")
    if not isinstance(cfg["seuils_profils"], dict):
        raise ConfigError("seuils_profils : objet attendu")
    cfg["seuils_profils"] = {p: _num(v, 0.05, 0.95, f"seuil {p}")
                             for p, v in cfg["seuils_profils"].items() if p in all_ids}
    if cfg["parole"] not in PAROLE_MODES:
        raise ConfigError("parole : masquer, ignorer_episode ou desactive")
    cfg["seuil_parole"] = _num(cfg["seuil_parole"], 0.1, 0.95, "seuil_parole")

    au = cfg["audio"]
    if au["micro"] in ("", "auto"):
        au["micro"] = None
    if au["micro"] is not None:
        if isinstance(au["micro"], bool) or not isinstance(au["micro"], (str, int)):
            raise ConfigError("micro : nom ou index attendu")
        if isinstance(au["micro"], str) and (len(au["micro"]) > 120 or any(ord(c) < 32 for c in au["micro"])):
            raise ConfigError("micro : nom invalide")
    au["gain"] = _num(au["gain"], 0.1, 20, "gain")
    au["coupe_bas_hz"] = _num(au["coupe_bas_hz"], 0, 400, "coupe_bas_hz", integer=True)
    if au["seuil_niveau_dbfs"] in ("", None):
        au["seuil_niveau_dbfs"] = None
    else:
        au["seuil_niveau_dbfs"] = _num(au["seuil_niveau_dbfs"], -80, 0, "seuil_niveau_dbfs")
    if not cfg["profils"] and au["seuil_niveau_dbfs"] is None:
        raise ConfigError("choisir au moins une nuisance (ou un seuil de niveau sonore)")

    ep = cfg["episodes"]
    ep["pre_s"] = _num(ep["pre_s"], 0, 60, "pre_s")
    ep["calme_s"] = _num(ep["calme_s"], 2, 120, "calme_s")
    ep["max_s"] = _num(ep["max_s"], 10, 1800, "max_s")
    ep["min_detections"] = _num(ep["min_detections"], 1, 60, "min_detections", integer=True)
    cfg["version"] = 3
    return cfg


def config_id(cfg):
    """Empreinte courte et stable d'une configuration."""
    canon = json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:10]


def load(path):
    """Config validée ; valeurs par défaut si le fichier est absent.
    Lève ConfigError si le fichier est invalide (l'appelant garde alors la config précédente)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT)
    try:
        return validate(json.loads(text))
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSON invalide : {e}")


def save(path, cfg):
    cfg = validate(cfg)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".cfg", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return cfg


def diff(old, new, prefix=""):
    """Liste lisible des changements, pour l'historique."""
    out = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if isinstance(a, dict) and isinstance(b, dict) and k != "seuils_profils":
            out += diff(a, b, f"{prefix}{k}.")
        elif k == "perso" and a != b:
            name = lambda lst: ", ".join(f"{c['label']} ({'+'.join(c['classes'])})" for c in lst or []) or "aucune"
            out.append(f"{prefix}perso : {name(a)} -> {name(b)}")
        elif a != b:
            out.append(f"{prefix}{k} : {a} -> {b}")
    return out


if __name__ == "__main__":   # lancé par install.sh : crée les réglages par défaut s'ils n'existent pas
    import sys
    ap = argparse.ArgumentParser(description="Crée config.json avec les réglages par défaut")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if Path(args.out).exists():
        print(f"{args.out} existe déjà, rien à faire")
        sys.exit(0)
    save(args.out, validate({}))
    print(f"Réglages par défaut créés dans {args.out}")
