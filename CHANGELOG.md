# Changelog

All notable changes to BarkDog. Versions follow [semantic versioning](https://semver.org/).
🇫🇷 Version française plus bas.

## [1.1.0] — 2026-10-21

Shaped by the feedback on the 1.0 launch. Next steps are in [ROADMAP.md](ROADMAP.md).

### Detection
- New nuisances: **aircraft and helicopters**, **road traffic**.
- **Custom nuisances**: build your own from any of the 521 YAMNet sounds (up to 10, each with up to 10 sounds), with an optional threshold.
- A sound that is searched for is never also treated as a sound to ignore; contradictory choices (“Road traffic” + ignore “Traffic”) are refused with a clear message.

### Evidence and traceability
- **Chained log**: each line of `journal_evenements.csv` holds a SHA-256 linked to the previous line, so changing, inserting or removing a line afterwards breaks the chain.
- **Integrity check** from the page (“Check integrity”) or with `integrite.py`: the chain plus the fingerprint of every WAV file, written to the history.
- Upgrading from 1.0 never rewrites the old log: it is archived unchanged as `journal_evenements_v1.csv`, and the new chain starts from its fingerprint.
- Levels: new `niveau_detections_dBFS` column (average level during detections only); `niveau_moyen_dBFS` now excludes masked speech; levels are measured on the audio actually written.
- Speech masking: the 10 ms fade is now computed exactly, so audio outside masked passages stays bit-identical on every CPU.

### Web page
- Level shown on each episode card; levels added to the CSV export.
- **Detection reliability per category**, computed from the episodes flagged as false positives.
- Link to the archived 1.0 log when there is one.

### Project
- Python dependencies declared in `requirements.txt` and `requirements-engine.txt`, used by `install.sh` (lets dependency scanners such as Dependabot see them).
- CI: GitLab SAST (Semgrep) and secret detection jobs; the browser API helper only accepts a fixed list of local paths.
- Website and promo videos in English, with a FR / EN switch.
- FAQ in the README and on the website: microphones, voice masking and integrity, official reports, BirdNET, limits.

## [1.0.0] — 2026-10-19

First public release.

### Detection
- On-device AI classification with YAMNet (521 AudioSet classes), one analysis every 0.5 s; no audio leaves the box.
- 13 selectable nuisances (barking, howling, growling, rooster, cats, music, bass, construction work, fireworks, lawn mower and chainsaw, motorbikes, alarms, horns) with optional per-nuisance thresholds, plus an optional trigger on sound level alone.
- Sounds to ignore that cancel a detection when they dominate (ducks and geese, songbirds, wind and rain, traffic).
- Complete episodes: pre-roll, adjustable quiet time, maximum length, minimum number of detections to discard isolated sounds (discarded episodes are still logged).
- Software gain and high-pass filter against mains hum.

### Privacy
- Speech masking on by default: passages where the AI hears a human voice are silenced in the files and flagged on the timeline. An episode made mostly of speech can also be discarded.

### Evidence and traceability
- Every WAV file is timestamped, categorised and sealed with a SHA-256 fingerprint written to an append-only log.
- Identifier of the settings used for each episode; history of starts, stops, settings changes, deletions, test modes and sign-ins.
- Clock synchronisation status recorded and shown.

### Web page
- Phone-friendly page: listening status and start / stop button, recording banner, automatic refresh.
- Per-recording timeline with one lane per category and jump-to buttons.
- Days grouped and foldable, sticky day header, filters (period, category, night only), daily chart, CSV exports.
- Annotations (false positive, notes) stored separately from the original log; trash with restore and permanent delete.
- Live test mode showing AI scores against thresholds, without recording.
- Settings drawer with hot reload (no restart except for a microphone change).
- English and French interface.

### Security
- PBKDF2-SHA256 password hash, HMAC-signed sessions, anti-CSRF, strict CSP, rate-limited sign-in, path confinement.
- Sandboxed systemd services (`barkdog`, `barkdog-web`) and a single sudo rule limited to starting and stopping listening.

---

## [1.1.0] — 21/10/2026 (français)

Construite à partir des retours sur la sortie de la 1.0. La suite est dans [ROADMAP.md](ROADMAP.md).

- **Détection** : nouvelles nuisances **avions et hélicoptères** et **trafic routier** ; **nuisances personnalisées** à partir de n'importe lesquels des 521 sons de YAMNet (10 au maximum, 10 sons chacune), avec seuil facultatif ; un son cherché n'est jamais aussi un son à ignorer, et les choix contradictoires sont refusés avec un message clair.
- **Traçabilité** : **journal chaîné** (chaque ligne porte un SHA-256 lié à la précédente) ; **vérification d'intégrité** depuis la page ou avec `integrite.py` (chaîne et empreinte de chaque fichier, notée dans l'historique) ; à la mise à jour, le journal 1.0 est archivé tel quel (`journal_evenements_v1.csv`) et la nouvelle chaîne part de son empreinte ; nouvelle colonne `niveau_detections_dBFS`, et `niveau_moyen_dBFS` exclut désormais la parole masquée.
- **Masquage de la parole** : le fondu de 10 ms est calculé exactement ; hors passages masqués, le son reste identique au bit près sur tout processeur.
- **Page web** : niveau affiché sur chaque épisode et dans l'export CSV ; **fiabilité de la détection par catégorie**, calculée à partir des faux positifs marqués ; lien vers le journal 1.0 archivé.
- **Projet** : dépendances déclarées dans `requirements.txt` et `requirements-engine.txt` ; analyses Semgrep et recherche de secrets dans la CI GitLab ; site et vidéos en anglais ; FAQ dans le README et sur le site.

## [1.0.0] — 19/10/2026 (français)

Première version publique.

- **Détection** : IA locale YAMNet (521 classes), analyse toutes les 0,5 s, rien ne sort du boîtier. 13 nuisances au choix avec seuil par nuisance, déclenchement facultatif sur le niveau sonore, sons à ignorer (canards, oiseaux, météo, circulation). Épisodes complets avec pré-enregistrement, calme réglable et nombre minimum de détections. Gain et filtre coupe-bas.
- **Vie privée** : voix humaines rendues muettes par défaut et signalées sur la frise.
- **Traçabilité** : horodatage, catégories et empreinte SHA-256 de chaque fichier, identifiant des réglages, historique complet, état de synchronisation de l'heure.
- **Page web** : état et marche / arrêt, bandeau d'enregistrement, frise par fichier, journées repliables, filtres, graphique, exports CSV, annotations, corbeille, mode test en direct, réglages à chaud, interface en français et en anglais.
- **Sécurité** : mot de passe haché, sessions signées, anti-CSRF, CSP stricte, limitation des tentatives, services systemd cloisonnés, règle sudo minimale.
