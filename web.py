#!/usr/bin/env python3
"""
Interface web de consultation et de réglage (bibliothèque standard Python uniquement).

Sécurité :
- connexion par mot de passe (haché, voir auth.py), session par cookie HttpOnly + SameSite=Strict ;
- toute requête POST exige l'en-tête X-Requested-With et une origine identique (anti-CSRF) ;
- en-têtes de sécurité (CSP sans script inline, anti-iframe, nosniff, no-referrer) ;
- chemins de fichiers strictement confinés au dossier des enregistrements ;
- actions sensibles (suppression, réglages, marche/arrêt, mot de passe) tracées dans l'historique.
Ne pas exposer directement sur Internet : passer par un VPN (Tailscale, WireGuard).
"""
import argparse
import csv
import datetime as dt
import ipaddress
import json
import re
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import catalog
import config as cfgmod
from auth import Auth

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
ANN_LOCK = threading.Lock()
CFG_LOCK = threading.Lock()
TRASH = "corbeille"
SYSTEMCTL = shutil.which("systemctl") or "/usr/bin/systemctl"
TEST_LEASE_S = 300      # la page doit renouveler le mode test, sinon il expire seul (5 min)
TEST_MAX_S = 30 * 60    # durée maximale d'un mode test
COOKIE = "session"
APP_HEADER = ("X-Requested-With", "barkdog")

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/login": ("login.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/login.js": ("login.js", "text/javascript; charset=utf-8"),
    "/static/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
}
PUBLIC = {"/login", "/static/app.css", "/static/login.js", "/static/i18n.js", "/api/login", "/api/session"}

SECURITY_HEADERS = [
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
]


# --------------------------------------------------------------------------- données
def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def clock_synced():
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out == "yes"
    except Exception:
        return None


def append_history(out_dir, evenement, origine):
    p = Path(out_dir) / "historique_ecoute.csv"
    new = not p.exists()
    clean = lambda t: str(t).replace(";", ",").replace("\n", " ")
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("date;evenement;origine\n")
        f.write(f"{now_iso()};{clean(evenement)};{clean(origine)}\n")


def load_annotations(out_dir):
    try:
        return json.loads((out_dir / "annotations.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_annotations(out_dir, data):
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".ann", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o644)
    os.replace(tmp, out_dir / "annotations.json")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_test(path):
    d = read_json(path)
    try:
        return d if d and time.time() < float(d.get("until", 0)) else None
    except (TypeError, ValueError):
        return None


def parse_scores(r):
    """Scores max par catégorie, colonne scores_max (« aboiement:0.71|hurlement:0.2 »)."""
    out = {}
    for part in (r.get("scores_max") or "").split("|"):
        k, _, v = part.partition(":")
        try:
            out[k] = float(v)
        except ValueError:
            pass
    return out


def event_tags(r, scores, thr):
    """Catégorie d'origine + toute catégorie dont le score max a dépassé le seuil (épisodes mixtes)."""
    tags = [c for c in (r.get("categorie") or "").split("+") if c and c != "inconnu"]
    for c, s in scores.items():
        if s >= thr and c not in tags and catalog.profile(c):
            tags.append(c)
    return tags or ["inconnu"]


def read_events(out_dir, thr):
    p = out_dir / "journal_evenements.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    ann = load_annotations(out_dir)
    events = []
    for r in rows:
        try:
            d = dt.datetime.fromisoformat(r["debut"])
        except (KeyError, TypeError, ValueError):
            continue
        a = ann.get(r.get("fichier", ""), {})
        if a.get("purge"):
            continue  # supprimé définitivement : reste dans le journal brut, plus dans la page
        scores = parse_scores(r)
        e = {k: r.get(k, "") for k in ("debut", "fin", "categorie", "fichier", "sha256", "niveau_crete_dBFS",
                                        "horloge_synchronisee", "reglages", "parole_masquee_s")}
        e.update(scores=scores, tags=event_tags(r, scores, thr), faux_positif=bool(a.get("faux_positif")),
                 note=a.get("note", ""), supprime=bool(a.get("supprime")), nuit=d.hour >= 22 or d.hour < 7)
        try:
            e["duree_s"] = float(r.get("duree_s") or 0)
        except ValueError:
            e["duree_s"] = 0.0
        wav = (out_dir / TRASH if e["supprime"] else out_dir) / e["fichier"]
        e["present"] = wav.is_file()
        side = read_json(wav.with_suffix(".json"))
        e["segments"] = side.get("segments", []) if side else None   # None : pas de chronologie (reanalyse.py)
        e["parole_masquee"] = side.get("parole_masquee", []) if side else []
        events.append(e)
    return events


# --------------------------------------------------------------------------- serveur
class Handler(BaseHTTPRequestHandler):
    server_version = "BarkDog"
    sys_version = ""
    protocol_version = "HTTP/1.1"   # connexions persistantes, mieux pour la lecture audio sur iPhone
    timeout = 60                    # pas de connexion pendante indéfiniment

    def version_string(self):
        return "BarkDog"         # ni version de Python ni du serveur

    @property
    def S(self):
        return self.server

    @property
    def out(self) -> Path:
        return self.S.out_dir

    def log_message(self, fmt, *args):
        pass  # silencieux ; les refus de connexion sont journalisés à part

    def log_security(self, msg):
        print(f"[sécurité] {now_iso()} {self.client_ip()} {msg}", flush=True)

    def from_local_proxy(self):
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def client_ip(self):
        """Adresse du client. X-Forwarded-For n'est cru que derrière un proxy local (tailscale serve)."""
        if self.from_local_proxy():
            fwd = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if fwd:
                return fwd[:64]
        return self.client_address[0]

    # ---- réponses
    def end_headers(self):
        for k, v in SECURITY_HEADERS:
            self.send_header(k, v)
        super().end_headers()

    def send_json(self, obj, status=200, cookie=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def lang(self):
        v = (self.headers.get("X-Lang") or "").strip().lower()
        if v in ("fr", "en"):
            return v
        accept = (self.headers.get("Accept-Language") or "").lower()
        return "fr" if accept.startswith("fr") or not accept else "en"

    def send_error_json(self, status, message):
        self.send_json({"erreur": translate_message(message, self.lang())}, status)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def send_file(self, path: Path, ctype, download_name=None, cache="private, max-age=3600"):
        """Envoi avec prise en charge des requêtes Range (indispensable pour Safari/iPhone)."""
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            s, _, e = rng[6:].split(",")[0].strip().partition("-")
            try:
                if s == "":
                    start = max(0, size - int(e))
                else:
                    start = int(s)
                    end = int(e) if e else size - 1
                end = min(end, size - 1)
                if start > end or start < 0:
                    raise ValueError
                status = 206
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download_name:
            safe = "".join(c for c in download_name if c.isalnum() or c in "._-+") or "fichier"
            self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # ---- session et anti-CSRF
    def session_token(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        return c[COOKIE].value if COOKIE in c else None

    def authenticated(self):
        return self.S.auth.verify_token(self.session_token())

    def https(self):
        return self.S.secure_cookies or (self.from_local_proxy()
                                         and self.headers.get("X-Forwarded-Proto", "").lower() == "https")

    def cookie(self, token, max_age):
        parts = [f"{COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
        if self.https():
            parts.append("Secure")
        return "; ".join(parts)

    def same_origin(self):
        """Requête issue de la page elle-même : en-tête applicatif + Origin (ou Referer) identique à Host."""
        if self.headers.get(APP_HEADER[0]) != APP_HEADER[1]:
            return False
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if origin:
            return urlparse(origin).netloc == host
        return True   # navigateurs anciens sans Origin : l'en-tête applicatif impose déjà une requête de même origine

    def read_body(self, limit=64_000):
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            n = -1
        if n <= 0 or n > limit:
            self.close_connection = True     # corps non lu : la connexion ne peut pas être réutilisée
            raise ValueError("taille")
        data = json.loads(self.rfile.read(n))
        if not isinstance(data, dict):
            raise ValueError("objet attendu")
        return data

    # ---- chemins
    def clean_rel(self, rel):
        """Chemin relatif d'un WAV, sans sortie du dossier ni accès direct à la corbeille."""
        rel = unquote(str(rel))
        if "\x00" in rel:
            return None
        p = (self.out / rel).resolve()
        if self.out not in p.parents or p.suffix.lower() != ".wav":
            return None
        rel = p.relative_to(self.out).as_posix()
        return None if rel.split("/")[0] == TRASH else rel

    def safe_wav(self, rel):
        rel = self.clean_rel(rel)
        if not rel:
            return None
        for base in (self.out, self.out / TRASH):
            if (base / rel).is_file():
                return base / rel
        return None

    # ---- routes
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        try:
            if path not in PUBLIC and not self.authenticated():
                if path.startswith("/api/") or path.startswith("/audio/") or path.startswith("/export/"):
                    return self.send_error_json(401, "connexion requise")
                return self.redirect("/login")
            if path in STATIC_FILES:
                name, ctype = STATIC_FILES[path]
                return self.send_file(STATIC / name, ctype, cache="no-cache")
            if path == "/api/session":
                return self.send_json({"connecte": self.authenticated(), "mot_de_passe_defini": self.S.auth.configured})
            if path == "/api/events":
                return self.send_json(read_events(self.out, self.S.cfg()["seuil"]))
            if path == "/api/status":
                return self.send_json(self.status())
            if path == "/api/config":
                return self.send_json(self.config_payload())
            if path == "/api/live":
                live = read_json(self.S.live_file)
                if not live:
                    return self.send_json({"absent": True})
                live["age_s"] = round(time.time() - float(live.get("ts", 0)), 1)
                return self.send_json(live)
            if path.startswith("/audio/"):
                p = self.safe_wav(path[len("/audio/"):])
                if not p:
                    return self.send_error_json(404, "fichier introuvable")
                dl = parse_qs(url.query).get("dl") == ["1"]
                return self.send_file(p, "audio/wav", p.name if dl else None)
            exports = {"/export/journal.csv": "journal_evenements.csv", "/export/historique.csv": "historique_ecoute.csv",
                       "/export/ignores.csv": "episodes_ignores.csv"}
            if path in exports:
                p = self.out / exports[path]
                if not p.exists():
                    return self.send_error_json(404, "pas encore de données")
                return self.send_file(p, "text/csv; charset=utf-8", exports[path], cache="no-store")
            return self.send_error_json(404, "page introuvable")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        path = urlparse(self.path).path
        routes = {"/api/login": self.login, "/api/logout": self.logout, "/api/annotate": self.file_action,
                  "/api/delete": self.file_action, "/api/restore": self.file_action, "/api/purge": self.file_action,
                  "/api/service": self.service_action, "/api/testmode": self.testmode_action,
                  "/api/config": self.save_config, "/api/password": self.change_password}
        if path not in routes:
            return self.send_error_json(404, "page introuvable")
        if not self.same_origin():
            self.log_security(f"POST {path} refusé (origine)")
            self.close_connection = True
            return self.send_error_json(403, "requête refusée (origine)")
        if path not in PUBLIC and not self.authenticated():
            self.close_connection = True
            return self.send_error_json(401, "connexion requise")
        try:
            data = self.read_body()
        except Exception:
            return self.send_error_json(400, "requête invalide")
        try:
            return routes[path](path, data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- connexion
    def login(self, path, data):
        ip, auth = self.client_ip(), self.S.auth
        if not auth.configured:
            return self.send_error_json(503, "aucun mot de passe défini : lancer « python3 auth.py --set » sur le boîtier")
        wait = auth.blocked_for(ip)
        if wait:
            self.log_security("connexion bloquée (trop de tentatives)")
            return self.send_error_json(429, f"trop de tentatives, réessayer dans {wait // 60 + 1} min")
        if not auth.check_password(data.get("mot_de_passe", "")):
            auth.record_failure(ip)
            self.log_security("mot de passe refusé")
            time.sleep(1)
            return self.send_error_json(401, "mot de passe incorrect")
        auth.reset(ip)
        append_history(self.out, "connexion a la page", f"page web ({ip})")
        self.send_json({"ok": True}, cookie=self.cookie(auth.make_token(), 30 * 86400))

    def logout(self, path, data):
        self.send_json({"ok": True}, cookie=self.cookie("", 0))

    def change_password(self, path, data):
        auth = self.S.auth
        if not auth.check_password(data.get("ancien", "")):
            time.sleep(1)
            return self.send_error_json(403, "mot de passe actuel incorrect")
        try:
            auth.set_password(str(data.get("nouveau", "")))
        except ValueError as e:
            return self.send_error_json(400, str(e))
        append_history(self.out, "mot de passe de la page modifie (sessions precedentes fermees)", f"page web ({self.client_ip()})")
        self.send_json({"ok": True}, cookie=self.cookie(auth.make_token(), 30 * 86400))

    # ---- réglages
    def config_payload(self):
        devs = read_json(self.S.devices_file) or {}
        cfg = self.S.cfg()
        return {"config": cfg, "id": cfgmod.config_id(cfg), "catalogue": catalog.public(),
                "micros": devs.get("micros", []), "parole_modes": list(cfgmod.PAROLE_MODES)}

    def save_config(self, path, data):
        with CFG_LOCK:
            old = self.S.cfg()
            try:
                new = cfgmod.save(self.S.config_path, data.get("config"))
            except cfgmod.ConfigError as e:
                return self.send_error_json(400, str(e))
            changes = cfgmod.diff(old, new)
            if changes:
                append_history(self.out, f"reglages modifies ({cfgmod.config_id(new)}) : {' / '.join(changes)}",
                               f"page web ({self.client_ip()})")
        payload = self.config_payload()
        payload["modifications"] = changes
        payload["redemarrage"] = old["audio"]["micro"] != new["audio"]["micro"]
        self.send_json(payload)

    # ---- fichiers
    def file_action(self, path, data):
        fichier = self.clean_rel(data.get("fichier", ""))
        if not fichier:
            return self.send_error_json(400, "fichier invalide")
        now = now_iso()
        main, trash = self.out / fichier, self.out / TRASH / fichier

        def move_side(src, dst):          # la chronologie .json suit son WAV
            s = src.with_suffix(".json")
            if s.is_file():
                os.replace(s, dst.with_suffix(".json"))

        with ANN_LOCK:
            ann = load_annotations(self.out)
            entry = ann.get(fichier, {})
            if path == "/api/annotate":
                if not (main.is_file() or trash.is_file()):
                    return self.send_error_json(404, "fichier introuvable")
                if "faux_positif" in data:
                    entry["faux_positif"] = bool(data["faux_positif"])
                if "note" in data:
                    entry["note"] = str(data["note"])[:500]
            elif path == "/api/delete":            # vers la corbeille (réversible)
                if not main.is_file():
                    return self.send_error_json(404, "fichier introuvable")
                trash.parent.mkdir(parents=True, exist_ok=True)
                os.replace(main, trash)
                move_side(main, trash)
                entry["supprime"] = now
            elif path == "/api/restore":
                if not trash.is_file():
                    return self.send_error_json(404, "fichier absent de la corbeille")
                if main.exists():
                    return self.send_error_json(409, "un fichier du même nom existe déjà")
                main.parent.mkdir(parents=True, exist_ok=True)
                os.replace(trash, main)
                move_side(trash, main)
                entry.pop("supprime", None)
                entry["restaure"] = now
            elif path == "/api/purge":             # définitif, seulement depuis la corbeille
                if not trash.is_file():
                    return self.send_error_json(404, "fichier absent de la corbeille")
                trash.unlink()
                trash.with_suffix(".json").unlink(missing_ok=True)
                entry["purge"] = now
            entry["modifie_le"] = now
            ann[fichier] = entry
            save_annotations(self.out, ann)
        if path != "/api/annotate":
            label = {"/api/delete": "mis a la corbeille", "/api/restore": "restaure",
                     "/api/purge": "supprime definitivement"}[path]
            append_history(self.out, f"enregistrement {label} : {fichier}", f"page web ({self.client_ip()})")
        self.send_json({"ok": True})

    # ---- mode test et service
    def testmode_action(self, path, data):
        """Active / renouvelle / coupe le mode test (pas d'enregistrement de fichiers)."""
        p, now = self.S.test_file, time.time()
        if not data.get("on"):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
            return self.send_json({"actif": False})
        cur = read_test(p)
        since = float(cur["since"]) if cur else now
        if now - since >= TEST_MAX_S:
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
            return self.send_json({"actif": False, "expire": True})
        until = min(now + TEST_LEASE_S, since + TEST_MAX_S)
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"since": since, "until": until}, f)
        os.replace(tmp, p)
        self.send_json({"actif": True, "reste_s": round(since + TEST_MAX_S - now)})

    def service_action(self, path, data):
        """Démarre / arrête l'écoute via sudo (règle limitée à ces commandes, posée par install.sh)."""
        act = data.get("action")
        if act not in ("start", "stop"):
            return self.send_error_json(400, "action invalide")
        if not self.S.can_control:
            return self.send_error_json(403, "pilotage non autorisé : relancer install.sh")
        append_history(self.out, "demarrage demande" if act == "start" else "arret demande", f"page web ({self.client_ip()})")
        try:
            r = subprocess.run(["sudo", "-n", SYSTEMCTL, act, self.S.service_name],
                               capture_output=True, text=True, timeout=60)
        except Exception as e:
            return self.send_error_json(500, f"échec : {e}")
        if r.returncode != 0:
            return self.send_error_json(500, (r.stderr or r.stdout or "échec").strip()[:300])
        self.send_json({"ok": True})

    def status(self):
        try:
            age = time.time() - (self.out / ".heartbeat").stat().st_mtime
        except FileNotFoundError:
            age = None
        try:   # état réel du service (active, inactive, failed, activating…)
            service = subprocess.run([SYSTEMCTL, "is-active", self.S.service_name],
                                     capture_output=True, text=True, timeout=5).stdout.strip() or None
        except Exception:
            service = None
        jv = []   # « version » du journal : change dès qu'un enregistrement ou une annotation est ajouté
        for name in ("journal_evenements.csv", "annotations.json"):
            try:
                st = (self.out / name).stat()
                jv.append(f"{st.st_mtime_ns}:{st.st_size}")
            except FileNotFoundError:
                jv.append("0")
        rec = {"en_cours": False}
        live = read_json(self.S.live_file)
        try:
            if live and time.time() - float(live.get("ts", 0)) < 5 and live.get("episode"):
                rec = {"en_cours": True, "duree_s": live.get("episode_s", 0), "tags": live.get("episode_tags", []),
                       "test": bool(live.get("episode_test"))}
        except (TypeError, ValueError):
            pass
        t = read_test(self.S.test_file)
        du = shutil.disk_usage(self.out)
        cfg = self.S.cfg()
        return {
            "maintenant": now_iso(), "service": service, "controle_service": self.S.can_control,
            "journal_version": "|".join(jv), "enregistrement": rec,
            "mode_test": {"actif": True, "reste_s": round(float(t["since"]) + TEST_MAX_S - time.time())} if t else {"actif": False},
            "ecoute_active": age is not None and age < 90 and service in ("active", None),
            "dernier_signe_de_vie_s": None if age is None else round(age),
            "horloge_synchronisee": clock_synced(),
            "disque_libre_go": round(du.free / 1e9, 1), "disque_total_go": round(du.total / 1e9, 1),
            "reglages": cfgmod.config_id(cfg), "reglages_ecoute": (live or {}).get("reglages"),
        }


# Messages d'erreur renvoyés à la page : français par défaut, anglais si la page le demande (en-tête X-Lang).
MSG_EN = {
    "connexion requise": "sign-in required",
    "fichier introuvable": "file not found",
    "pas encore de données": "no data yet",
    "page introuvable": "page not found",
    "requête refusée (origine)": "request refused (origin)",
    "requête invalide": "invalid request",
    "aucun mot de passe défini : lancer « python3 auth.py --set » sur le boîtier": "no password set: run “python3 auth.py --set” on the box",
    "mot de passe incorrect": "wrong password",
    "mot de passe actuel incorrect": "current password is wrong",
    "fichier invalide": "invalid file",
    "fichier absent de la corbeille": "file is not in the trash",
    "un fichier du même nom existe déjà": "a file with the same name already exists",
    "action invalide": "invalid action",
    "pilotage non autorisé : relancer install.sh": "control not allowed: run install.sh again",
    "format invalide": "invalid format",
    "profils : liste attendue": "profiles: list expected",
    "exclusions inconnues": "unknown exclusions",
    "seuils_profils : objet attendu": "per-profile thresholds: object expected",
    "parole : masquer, ignorer_episode ou desactive": "speech: masquer, ignorer_episode or desactive",
    "micro : nom ou index attendu": "microphone: name or index expected",
    "micro : nom invalide": "microphone: invalid name",
    "choisir au moins une nuisance (ou un seuil de niveau sonore)": "choose at least one nuisance (or a sound level threshold)",
}
MSG_EN_PATTERNS = [
    (re.compile(r"^trop de tentatives, réessayer dans (\d+) min$"), r"too many attempts, try again in \1 min"),
    (re.compile(r"^mot de passe trop court \((\d+) caractères minimum\)$"), r"password too short (\1 characters minimum)"),
    (re.compile(r"^(.+) : nombre attendu$"), r"\1: number expected"),
    (re.compile(r"^(.+) : doit être entre (.+) et (.+)$"), r"\1: must be between \2 and \3"),
    (re.compile(r"^profils inconnus : (.+)$"), r"unknown profiles: \1"),
    (re.compile(r"^JSON invalide : (.+)$"), r"invalid JSON: \1"),
    (re.compile(r"^échec : (.+)$"), r"failed: \1"),
]


def translate_message(message, lang):
    if lang != "en":
        return message
    if message in MSG_EN:
        return MSG_EN[message]
    for pat, repl in MSG_EN_PATTERNS:
        if pat.match(message):
            return pat.sub(repl, message)
    return message


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, TimeoutError)):
            return      # client parti : sans intérêt
        super().handle_error(request, client_address)

    def cfg(self):
        try:
            return cfgmod.load(self.config_path)
        except cfgmod.ConfigError:
            return cfgmod.validate({})


def can_control_service(name):
    """Vrai si la règle sudo autorise ce compte à démarrer/arrêter le service sans mot de passe."""
    try:
        return all(subprocess.run(["sudo", "-n", "-l", SYSTEMCTL, act, name],
                                  capture_output=True, timeout=10).returncode == 0 for act in ("start", "stop"))
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(HERE / "enregistrements"))
    p.add_argument("--config-dir", default=str(HERE / "config"))
    p.add_argument("--host", default="0.0.0.0", help="adresse d'écoute (127.0.0.1 si accès uniquement via tailscale serve)")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--service", default="barkdog", help="nom du service systemd de l'enregistreur")
    p.add_argument("--live-file", default="/dev/shm/barkdog-live.json")
    p.add_argument("--test-file", default="/dev/shm/barkdog-test.json")
    p.add_argument("--devices-file", default="/dev/shm/barkdog-devices.json")
    p.add_argument("--secure-cookies", action="store_true", help="cookie « Secure » (page servie en HTTPS)")
    p.add_argument("--no-service-control", action="store_true")
    a = p.parse_args()

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    conf = Path(a.config_dir).resolve()
    srv = Server((a.host, a.port), Handler)
    srv.out_dir = out
    srv.config_path = conf / "config.json"
    srv.auth = Auth(conf)
    srv.service_name = a.service
    srv.live_file, srv.test_file, srv.devices_file = a.live_file, a.test_file, a.devices_file
    srv.secure_cookies = a.secure_cookies
    srv.can_control = False if a.no_service_control else can_control_service(a.service)
    print(f"Interface web sur http://{a.host}:{a.port} | mot de passe "
          f"{'défini' if srv.auth.configured else 'ABSENT (python3 auth.py --set)'} | pilotage de l'écoute "
          f"{'oui' if srv.can_control else 'non'}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
