#!/usr/bin/env python3
"""
Intégrité du journal des épisodes (journal_evenements.csv).

Journal chaîné : chaque ligne porte, dans la colonne « chaine », l'empreinte SHA-256 de
    <chaine de la ligne précédente> ; <les autres colonnes de la ligne, dans l'ordre, séparées par « ; »>
La première ligne part de 64 zéros, ou de l'empreinte SHA-256 du journal 1.0 archivé
(journal_evenements_v1.csv) quand le journal a été mis à niveau. Modifier, insérer ou supprimer
une ligne après coup casse la chaîne à partir de cet endroit. Les fichiers WAV sont vérifiés
avec la colonne « sha256 ».

  .venv/bin/python integrite.py                 # vérifie le journal et tous les fichiers
  .venv/bin/python integrite.py --sans-fichiers # la chaîne seulement (rapide)

Ne modifie jamais rien.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOURNAL = "journal_evenements.csv"
JOURNAL_V1 = "journal_evenements_v1.csv"
TRASH = "corbeille"
ZERO = "0" * 64

# Colonnes du journal (l'ordre fait partie du calcul de la chaîne : ne jamais le changer, seulement ajouter).
FIELDS = [
    "debut", "fin", "duree_s", "categorie", "nb_detections", "scores_max",
    "niveau_crete_dBFS", "niveau_moyen_dBFS", "horloge_synchronisee",
    "parole_masquee_s", "reglages", "fichier", "sha256", "niveau_detections_dBFS", "chaine",
]
CHAINED = FIELDS[:-1]


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def link(prev, row):
    """Maillon de la chaîne pour une ligne (dict) du journal."""
    data = prev + ";" + ";".join(str(row.get(k, "") if row.get(k) is not None else "") for k in CHAINED)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def genesis(out_dir):
    """Point de départ de la chaîne : empreinte du journal 1.0 archivé s'il existe, sinon 64 zéros."""
    v1 = Path(out_dir) / JOURNAL_V1
    return file_sha256(v1) if v1.is_file() else ZERO


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def load_annotations(out_dir):
    try:
        return json.loads((Path(out_dir) / "annotations.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def verify(out_dir, check_files=True):
    """Vérifie la chaîne du journal et, si demandé, l'empreinte de chaque fichier WAV.
    Renvoie un dictionnaire (utilisé par la page web et par la ligne de commande)."""
    out_dir = Path(out_dir)
    res = {"ok": True, "lignes": 0, "chaine": "absente", "rupture_ligne": None,
           "journal_v1": None, "fichiers": None, "problemes": []}
    v1 = out_dir / JOURNAL_V1
    if v1.is_file():
        res["journal_v1"] = {"sha256": file_sha256(v1), "lignes": len(read_rows(v1))}
    p = out_dir / JOURNAL
    rows = read_rows(p) if p.is_file() else []
    res["lignes"] = len(rows)

    if rows and "chaine" in rows[0]:
        prev = res["journal_v1"]["sha256"] if res["journal_v1"] else ZERO
        res["chaine"] = "intacte"
        for n, r in enumerate(rows, start=2):            # n = numéro de ligne dans le fichier (1 = en-tête)
            if link(prev, r) != r.get("chaine"):
                res.update(ok=False, chaine="rompue", rupture_ligne=n)
                res["problemes"].append(f"chaîne rompue à la ligne {n} du journal ({r.get('debut', '?')})")
                break
            prev = r["chaine"]
    elif rows:
        res["chaine"] = "absente"
        res["problemes"].append("journal sans chaînage (format 1.0)")

    if check_files:
        ann = load_annotations(out_dir)
        f = {"verifies": 0, "supprimes_definitivement": 0, "absents": [], "modifies": []}
        all_rows = (read_rows(v1) if v1.is_file() else []) + rows
        for r in all_rows:
            rel = r.get("fichier") or ""
            if not rel:
                continue
            wav = next((b / rel for b in (out_dir, out_dir / TRASH) if (b / rel).is_file()), None)
            if wav is None:
                if ann.get(rel, {}).get("purge"):
                    f["supprimes_definitivement"] += 1       # suppression tracée dans annotations.json
                else:
                    f["absents"].append(rel)
                continue
            if file_sha256(wav) == r.get("sha256"):
                f["verifies"] += 1
            else:
                f["modifies"].append(rel)
        res["fichiers"] = f
        if f["absents"]:
            res["ok"] = False
            res["problemes"].append(f"{len(f['absents'])} fichier(s) absent(s) sans suppression tracée")
        if f["modifies"]:
            res["ok"] = False
            res["problemes"].append(f"{len(f['modifies'])} fichier(s) modifié(s) depuis l'enregistrement")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "enregistrements"), help="dossier des enregistrements")
    ap.add_argument("--sans-fichiers", action="store_true", help="ne vérifier que la chaîne du journal")
    ap.add_argument("--json", action="store_true", help="résultat au format JSON")
    a = ap.parse_args()
    r = verify(a.out, check_files=not a.sans_fichiers)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"Journal : {r['lignes']} épisode(s), chaîne {r['chaine']}")
        if r["journal_v1"]:
            print(f"Journal 1.0 archivé : {r['journal_v1']['lignes']} épisode(s), SHA-256 {r['journal_v1']['sha256']}")
        if r["fichiers"]:
            f = r["fichiers"]
            print(f"Fichiers : {f['verifies']} conformes, {f['supprimes_definitivement']} supprimé(s) définitivement "
                  f"(tracé), {len(f['absents'])} absent(s), {len(f['modifies'])} modifié(s)")
            for x in f["absents"]:
                print(f"  absent : {x}")
            for x in f["modifies"]:
                print(f"  MODIFIÉ : {x}")
        print("RÉSULTAT : " + ("intègre" if r["ok"] else "PROBLÈME — " + " ; ".join(r["problemes"])))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
