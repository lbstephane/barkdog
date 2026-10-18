#!/usr/bin/env python3
"""Synthèse du journal : épisodes et durée cumulée par jour, dont la nuit (22h-7h), par catégorie."""
import collections
import csv
import datetime as dt
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / "enregistrements" / "journal_evenements.csv")
rows = list(csv.DictReader(open(src, encoding="utf-8"), delimiter=";"))

days = collections.defaultdict(collections.Counter)
cats = set()
for r in rows:
    d = dt.datetime.fromisoformat(r["debut"])
    nuit = d.hour >= 22 or d.hour < 7          # tranche nocturne (tapage nocturne)
    k = days[d.date().isoformat()]
    k["evenements"] += 1
    k["duree_s"] += float(r["duree_s"] or 0)
    k["nuit"] += nuit
    k["duree_nuit_s"] += float(r["duree_s"] or 0) if nuit else 0
    for c in (r.get("categorie") or "").split("+"):
        if c:
            k[f"cat:{c}"] += 1
            cats.add(c)

cats = sorted(cats)
out = src.with_name("synthese_par_jour.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["jour", "evenements", "duree_totale_min", "evenements_22h_7h", "duree_22h_7h_min"] + cats)
    for j in sorted(days):
        k = days[j]
        w.writerow([j, k["evenements"], round(k["duree_s"] / 60, 1), k["nuit"], round(k["duree_nuit_s"] / 60, 1)]
                   + [k[f"cat:{c}"] for c in cats])
        print(f"{j} : {k['evenements']:3d} événements, {k['duree_s'] / 60:5.1f} min (dont {k['nuit']} entre 22h et 7h)")
print(f"\nSynthèse écrite dans {out}")
