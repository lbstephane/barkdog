#!/usr/bin/env python3
"""
Authentification de la page web.

- Mot de passe haché en PBKDF2-SHA256 (sel aléatoire, 200 000 itérations), dans config/auth.json (0600).
- Session : jeton signé HMAC-SHA256 (clé aléatoire config/session.key), valable 30 jours, lié à
  l'empreinte du mot de passe : changer le mot de passe déconnecte toutes les sessions.
- Limitation des tentatives : 5 échecs en 15 min bloquent l'adresse jusqu'à la fin de la fenêtre.

Ligne de commande (utilisée par install.sh) :
  python3 auth.py --set                    # définir / changer le mot de passe (saisie masquée)
  python3 auth.py --from-file FICHIER      # reprendre un ancien web_password.txt puis le supprimer
"""
import argparse
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITERATIONS = 200_000
SESSION_S = 30 * 86400
MIN_LENGTH = 8
FAIL_WINDOW_S = 15 * 60
MAX_FAILURES = 5


def _write_private(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".auth")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


class Auth:
    def __init__(self, conf_dir):
        self.dir = Path(conf_dir)
        self.path = self.dir / "auth.json"
        self.key_path = self.dir / "session.key"
        self.lock = threading.Lock()
        self.failures = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.data = None
        if self.key_path.exists():
            self.key = self.key_path.read_bytes()
        else:
            self.key = secrets.token_bytes(32)
            _write_private(self.key_path, self.key)

    @property
    def configured(self):
        return bool(self.data and self.data.get("hash"))

    # ---- mot de passe
    @staticmethod
    def _hash(password, salt, iterations):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()

    def set_password(self, password):
        if len(password) < MIN_LENGTH:
            raise ValueError(f"mot de passe trop court ({MIN_LENGTH} caractères minimum)")
        salt = secrets.token_bytes(16)
        data = {"algo": "pbkdf2_sha256", "iterations": ITERATIONS, "salt": salt.hex(),
                "hash": self._hash(password, salt, ITERATIONS)}
        _write_private(self.path, json.dumps(data).encode())
        self.data = data

    def check_password(self, password):
        if not self.configured or not isinstance(password, str) or len(password) > 256:
            return False
        d = self.data
        given = self._hash(password, bytes.fromhex(d["salt"]), int(d["iterations"]))
        return hmac.compare_digest(given, d["hash"])

    # ---- sessions
    def _sign(self, msg):
        fp = self.data["hash"][:16] if self.configured else ""
        return hmac.new(self.key, f"{msg}.{fp}".encode(), hashlib.sha256).hexdigest()

    def make_token(self):
        msg = f"{int(time.time()) + SESSION_S}.{secrets.token_urlsafe(12)}"
        return f"{msg}.{self._sign(msg)}"

    def verify_token(self, token):
        if not self.configured or not token or len(token) > 200:
            return False
        try:
            exp, nonce, sig = token.split(".")
            if int(exp) < time.time():
                return False
        except ValueError:
            return False
        return hmac.compare_digest(sig, self._sign(f"{exp}.{nonce}"))

    # ---- limitation des tentatives
    def blocked_for(self, ip):
        now = time.time()
        with self.lock:
            fails = [t for t in self.failures.get(ip, []) if now - t < FAIL_WINDOW_S]
            self.failures[ip] = fails
            return int(FAIL_WINDOW_S - (now - fails[0])) + 1 if len(fails) >= MAX_FAILURES else 0

    def record_failure(self, ip):
        with self.lock:
            self.failures.setdefault(ip, []).append(time.time())
            if len(self.failures) > 1000:            # pas de croissance illimitée
                self.failures = dict(list(self.failures.items())[-500:])

    def reset(self, ip):
        with self.lock:
            self.failures.pop(ip, None)


def main():
    ap = argparse.ArgumentParser(description="Mot de passe de la page web")
    ap.add_argument("--config-dir", default=str(HERE / "config"))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", action="store_true", help="définir le mot de passe (saisie masquée)")
    g.add_argument("--from-file", help="reprendre un ancien mot de passe en clair puis supprimer le fichier")
    g.add_argument("--status", action="store_true", help="indique si un mot de passe est défini")
    a = ap.parse_args()
    auth = Auth(a.config_dir)
    if a.status:
        print("défini" if auth.configured else "absent")
        sys.exit(0 if auth.configured else 1)
    if a.from_file:
        p = Path(a.from_file)
        pw = p.read_text(encoding="utf-8").strip()
        if len(pw) < MIN_LENGTH:
            print(f"Ancien mot de passe trop court (< {MIN_LENGTH}) : non repris, définissez-en un nouveau.")
            sys.exit(2)
        auth.set_password(pw)
        p.unlink()
        print("Ancien mot de passe repris (désormais haché) ; le fichier en clair a été supprimé.")
        return
    while True:
        pw = getpass.getpass(f"Mot de passe de la page web ({MIN_LENGTH} caractères minimum) : ")
        if pw != getpass.getpass("Confirmation : "):
            print("Les deux saisies diffèrent.")
            continue
        try:
            auth.set_password(pw)
            print("Mot de passe enregistré.")
            return
        except ValueError as e:
            print(e)


if __name__ == "__main__":
    main()
