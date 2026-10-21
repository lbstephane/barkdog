"""Tests du serveur web : authentification, anti-CSRF, en-têtes, confinement des chemins, réglages, corbeille."""
import csv
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import fakes  # noqa: F401  (chemin d'import)
import auth as authmod
import config as cfgmod
import web

PW = "un-mot-de-passe-solide"
HDR = {"X-Requested-With": "barkdog", "Content-Type": "application/json"}


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        authmod.ITERATIONS = 1000            # tests rapides
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.out, cls.conf = root / "enregistrements", root / "config"
        cls.out.mkdir()
        (cls.out / "2026-10-18").mkdir()
        (cls.out / "2026-10-18" / "a.wav").write_bytes(b"RIFF" + b"\0" * 100)
        (cls.out / "2026-10-18" / "a.json").write_text(json.dumps({"segments": [{"categorie": "aboiement", "debut_s": 1, "fin_s": 3, "score_max": 0.7}],
                                                                   "parole_masquee": [{"debut_s": 5, "fin_s": 6}]}))
        (root / "secret.txt").write_text("ne doit jamais sortir")
        fields = ["debut", "fin", "duree_s", "categorie", "nb_detections", "scores_max", "niveau_crete_dBFS",
                  "niveau_moyen_dBFS", "horloge_synchronisee", "parole_masquee_s", "reglages", "fichier", "sha256"]
        with open(cls.out / "journal_evenements.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fields, delimiter=";")
            w.writeheader()
            w.writerow({k: "" for k in fields} | {"debut": "2026-10-18T05:12:00+02:00", "duree_s": "25", "categorie": "aboiement",
                                                   "scores_max": "aboiement:0.71|hurlement:0.40", "fichier": "2026-10-18/a.wav",
                                                   "sha256": "abc", "parole_masquee_s": "1.0", "reglages": "x"})
        a = authmod.Auth(cls.conf)
        a.set_password(PW)
        srv = web.Server(("127.0.0.1", 0), web.Handler)
        srv.out_dir, srv.config_path, srv.auth = cls.out.resolve(), cls.conf / "config.json", a
        srv.service_name, srv.can_control, srv.secure_cookies = "barkdog", False, False
        srv.live_file = str(root / "live.json")
        srv.test_file = str(root / "test.json")
        srv.devices_file = str(root / "devices.json")
        cls.srv = srv
        cls.port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        cls.cookie = cls.login()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    @classmethod
    def req(cls, method, path, body=None, headers=None, cookie=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        h = dict(headers or {})
        h.setdefault("Host", f"127.0.0.1:{cls.port}")
        if cookie:
            h["Cookie"] = f"session={cookie}"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    @classmethod
    def login(cls, pw=PW):
        r, _ = cls.req("POST", "/api/login", {"mot_de_passe": pw}, HDR)
        sc = r.getheader("Set-Cookie") or ""
        return sc.split(";")[0].split("=", 1)[1] if r.status == 200 else None

    # ---- langue des messages
    def test_error_messages_translated(self):
        self.assertEqual(web.translate_message("mot de passe incorrect", "en"), "wrong password")
        self.assertEqual(web.translate_message("trop de tentatives, réessayer dans 3 min", "en"), "too many attempts, try again in 3 min")
        self.assertEqual(web.translate_message("seuil : doit être entre 0.05 et 0.95", "en"), "seuil: must be between 0.05 and 0.95")
        self.assertEqual(web.translate_message("mot de passe incorrect", "fr"), "mot de passe incorrect")
        bad = {"config": {"profils": [], "audio": {"seuil_niveau_dbfs": None}}}
        r, d = self.req("POST", "/api/config", bad, HDR | {"X-Lang": "en"}, cookie=self.cookie)
        self.assertEqual((r.status, json.loads(d)["erreur"]), (400, "choose at least one nuisance (or a sound level threshold)"))
        r, d = self.req("POST", "/api/config", bad, HDR, cookie=self.cookie)
        self.assertIn("choisir au moins une nuisance", json.loads(d)["erreur"])
        self.assertEqual(self.req("GET", "/static/i18n.js")[0].status, 200)     # public : la page de connexion en a besoin

    # ---- accès
    def test_unauthenticated(self):
        r, _ = self.req("GET", "/")
        self.assertEqual((r.status, r.getheader("Location")), (302, "/login"))
        for p in ("/api/events", "/api/config", "/audio/2026-10-18/a.wav", "/export/journal.csv"):
            self.assertEqual(self.req("GET", p)[0].status, 401, p)
        self.assertEqual(self.req("GET", "/login")[0].status, 200)
        self.assertEqual(self.req("GET", "/static/app.js")[0].status, 302)   # le script de l'appli n'est pas public

    def test_cookie_flags_and_headers(self):
        r, _ = self.req("POST", "/api/login", {"mot_de_passe": PW}, HDR)
        sc = r.getheader("Set-Cookie")
        for flag in ("HttpOnly", "SameSite=Strict", "Path=/"):
            self.assertIn(flag, sc)
        self.assertNotIn("Secure", sc)
        r, _ = self.req("POST", "/api/login", {"mot_de_passe": PW}, HDR | {"X-Forwarded-Proto": "https"})
        self.assertIn("Secure", r.getheader("Set-Cookie"))      # HTTPS signalé par le proxy local (tailscale serve)
        r, _ = self.req("GET", "/", cookie=self.cookie)
        csp = r.getheader("Content-Security-Policy")
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline' 'self'; script", csp)
        self.assertEqual(r.getheader("X-Frame-Options"), "DENY")
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.getheader("Server"), "BarkDog")

    def test_bad_password_and_rate_limit(self):
        ip_hdr = HDR | {"X-Forwarded-For": "203.0.113.9"}     # client distant derrière le proxy local
        for _ in range(authmod.MAX_FAILURES):
            r, d = self.req("POST", "/api/login", {"mot_de_passe": "faux"}, ip_hdr)
            self.assertEqual(r.status, 401)
        r, d = self.req("POST", "/api/login", {"mot_de_passe": PW}, ip_hdr)
        self.assertEqual(r.status, 429)                       # même le bon mot de passe est bloqué
        r, _ = self.req("POST", "/api/login", {"mot_de_passe": PW}, HDR)   # autre adresse : pas bloquée
        self.assertEqual(r.status, 200)

    def test_forged_and_expired_tokens(self):
        for tok in ("x", "1.2.3", "9999999999.abc.0000", self.cookie[:-1] + ("0" if self.cookie[-1] != "0" else "1")):
            self.assertEqual(self.req("GET", "/api/events", cookie=tok)[0].status, 401, tok)

    # ---- anti-CSRF
    def test_csrf(self):
        body = {"config": {}}
        r, _ = self.req("POST", "/api/config", body, {"Content-Type": "application/json"}, cookie=self.cookie)
        self.assertEqual(r.status, 403)                                   # pas d'en-tête applicatif
        r, _ = self.req("POST", "/api/config", body, HDR | {"Origin": "https://evil.example"}, cookie=self.cookie)
        self.assertEqual(r.status, 403)                                   # autre origine
        r, _ = self.req("POST", "/api/login", {"mot_de_passe": PW}, {"Content-Type": "application/json"})
        self.assertEqual(r.status, 403)                                   # connexion forcée (login CSRF)
        r, _ = self.req("POST", "/api/config", {"config": {"seuil": 0.3}},
                        HDR | {"Origin": f"http://127.0.0.1:{self.port}"}, cookie=self.cookie)
        self.assertEqual(r.status, 200)

    # ---- chemins
    def test_path_confinement(self):
        for p in ("/audio/../secret.txt", "/audio/..%2f..%2fsecret.txt", "/audio/%2e%2e/secret.txt",
                  "/audio/2026-10-18/a.json", "/audio/corbeille/x.wav", "/static/../web.py", "/audio/a.wav%00.wav"):
            self.assertIn(self.req("GET", p, cookie=self.cookie)[0].status, (400, 404), p)
        r, d = self.req("GET", "/audio/2026-10-18/a.wav", cookie=self.cookie, headers={"Range": "bytes=0-3"})
        self.assertEqual((r.status, d), (206, b"RIFF"))
        r, _ = self.req("POST", "/api/delete", {"fichier": "../secret.txt"}, HDR, cookie=self.cookie)
        self.assertEqual(r.status, 400)

    # ---- données
    def test_events_and_config(self):
        r, d = self.req("GET", "/api/events", cookie=self.cookie)
        ev = json.loads(d)[0]
        self.assertEqual(ev["tags"], ["aboiement", "hurlement"])          # hurlement repris du score max
        self.assertEqual(ev["parole_masquee"], [{"debut_s": 5, "fin_s": 6}])
        r, d = self.req("GET", "/api/config", cookie=self.cookie)
        payload = json.loads(d)
        self.assertIn("profils", payload["catalogue"])
        self.assertEqual(payload["config"]["seuil"], 0.3)

    def test_config_save_validation_and_history(self):
        r, d = self.req("POST", "/api/config", {"config": {"seuil": 5}}, HDR, cookie=self.cookie)
        self.assertEqual(r.status, 400)
        self.assertIn("seuil", json.loads(d)["erreur"])
        r, d = self.req("POST", "/api/config", {"config": {"profils": ["aboiement", "coq"], "seuil": 0.35}}, HDR, cookie=self.cookie)
        res = json.loads(d)
        self.assertEqual(r.status, 200)
        self.assertIn("seuil : 0.3 -> 0.35", res["modifications"])
        self.assertEqual(cfgmod.load(self.conf / "config.json")["profils"], ["aboiement", "coq"])
        self.assertIn("reglages modifies", (self.out / "historique_ecoute.csv").read_text())
        self.req("POST", "/api/config", {"config": {}}, HDR, cookie=self.cookie)   # retour aux valeurs par défaut

    def test_custom_nuisance_and_conflict(self):
        perso = [{"id": "frigo", "label": "Frigo", "classes": ["Hum"]}]
        r, d = self.req("POST", "/api/config", {"config": {"perso": perso, "profils": ["aboiement", "frigo"]}}, HDR, cookie=self.cookie)
        self.assertEqual(r.status, 200, d)
        res = json.loads(d)
        self.assertIn("frigo", [p["id"] for p in res["catalogue"]["profils"]])
        self.assertIn("Hum", res["classes_yamnet"])
        self.assertTrue(any(m.startswith("perso : aucune -> Frigo (Hum)") for m in res["modifications"]))
        bad = {"config": {"profils": ["trafic"], "exclusions": ["circulation"]}}
        r, d = self.req("POST", "/api/config", bad, HDR | {"X-Lang": "en"}, cookie=self.cookie)
        self.assertEqual(json.loads(d)["erreur"], "“Road traffic” and the sound to ignore “Traffic (cars, trucks)” "
                                                  "exclude each other: untick one of them")
        self.req("POST", "/api/config", {"config": {}}, HDR, cookie=self.cookie)

    def test_verify_and_archived_journal(self):
        r, d = self.req("GET", "/api/verify", cookie=self.cookie)
        res = json.loads(d)
        self.assertEqual(res["chaine"], "absente")                     # journal de test au format 1.0
        self.assertFalse(res["ok"])                                    # sha256 « abc » ne correspond pas au fichier
        self.assertIn("verification d'integrite", (self.out / "historique_ecoute.csv").read_text())
        self.assertEqual(self.req("GET", "/api/verify")[0].status, 401)
        v1 = self.out / "journal_evenements_v1.csv"
        v1.write_text((self.out / "journal_evenements.csv").read_text(encoding="utf-8").replace("05:12:00", "04:00:00"),
                      encoding="utf-8")
        try:
            r, d = self.req("GET", "/api/events", cookie=self.cookie)
            self.assertEqual(len(json.loads(d)), 2)                    # archive 1.0 + journal courant
            self.assertTrue(json.loads(self.req("GET", "/api/status", cookie=self.cookie)[1])["journal_v1"])
            self.assertEqual(self.req("GET", "/export/journal_v1.csv", cookie=self.cookie)[0].status, 200)
        finally:
            v1.unlink()

    def test_trash_flow(self):
        f = "2026-10-18/a.wav"
        self.assertEqual(self.req("POST", "/api/purge", {"fichier": f}, HDR, cookie=self.cookie)[0].status, 404)
        self.assertEqual(self.req("POST", "/api/delete", {"fichier": f}, HDR, cookie=self.cookie)[0].status, 200)
        self.assertTrue((self.out / "corbeille" / "2026-10-18" / "a.json").exists())
        self.assertEqual(self.req("GET", "/audio/" + f, cookie=self.cookie)[0].status, 200)   # écoute depuis la corbeille
        self.assertEqual(self.req("POST", "/api/restore", {"fichier": f}, HDR, cookie=self.cookie)[0].status, 200)
        self.assertTrue((self.out / f).exists())
        hist = (self.out / "historique_ecoute.csv").read_text()
        self.assertIn("mis a la corbeille : 2026-10-18/a.wav", hist)
        self.assertIn("restaure", hist)

    def test_password_change_invalidates_sessions(self):
        tok = self.login()
        r, _ = self.req("POST", "/api/password", {"ancien": "faux", "nouveau": "abcdefghij"}, HDR, cookie=tok)
        self.assertEqual(r.status, 403)
        r, _ = self.req("POST", "/api/password", {"ancien": PW, "nouveau": "court"}, HDR, cookie=tok)
        self.assertEqual(r.status, 400)
        r, _ = self.req("POST", "/api/password", {"ancien": PW, "nouveau": "nouveau-mot-de-passe"}, HDR, cookie=tok)
        self.assertEqual(r.status, 200)
        new_tok = r.getheader("Set-Cookie").split(";")[0].split("=", 1)[1]
        self.assertEqual(self.req("GET", "/api/events", cookie=self.cookie)[0].status, 401)   # ancienne session fermée
        self.assertEqual(self.req("GET", "/api/events", cookie=new_tok)[0].status, 200)
        self.req("POST", "/api/password", {"ancien": "nouveau-mot-de-passe", "nouveau": PW}, HDR, cookie=new_tok)
        type(self).cookie = self.login()

    def test_testmode_lease(self):
        r, d = self.req("POST", "/api/testmode", {"on": True}, HDR, cookie=self.cookie)
        self.assertTrue(json.loads(d)["actif"])
        r, d = self.req("GET", "/api/status", cookie=self.cookie)
        self.assertTrue(json.loads(d)["mode_test"]["actif"])
        self.req("POST", "/api/testmode", {"on": False}, HDR, cookie=self.cookie)
        r, d = self.req("GET", "/api/status", cookie=self.cookie)
        self.assertFalse(json.loads(d)["mode_test"]["actif"])
        self.assertEqual(json.loads(d)["version"], (Path(web.__file__).parent / "VERSION").read_text().strip())

    def test_body_limits(self):
        r, _ = self.req("POST", "/api/annotate", ["liste"], HDR, cookie=self.cookie)
        self.assertEqual(r.status, 400)
        big = {"note": "x" * 70_000, "fichier": "2026-10-18/a.wav"}
        self.assertEqual(self.req("POST", "/api/annotate", big, HDR, cookie=self.cookie)[0].status, 400)


class AuthUnitTest(unittest.TestCase):
    def test_hash_is_salted_and_file_private(self):
        authmod.ITERATIONS = 1000
        with tempfile.TemporaryDirectory() as d:
            a = authmod.Auth(d)
            a.set_password("abcdefgh")
            h1 = a.data["hash"]
            a.set_password("abcdefgh")
            self.assertNotEqual(h1, a.data["hash"])
            self.assertTrue(a.check_password("abcdefgh"))
            self.assertFalse(a.check_password("abcdefgi"))
            self.assertEqual((Path(d) / "auth.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((Path(d) / "session.key").stat().st_mode & 0o777, 0o600)
            self.assertNotIn("abcdefgh", (Path(d) / "auth.json").read_text())
            with self.assertRaises(ValueError):
                a.set_password("court")


if __name__ == "__main__":
    unittest.main()
