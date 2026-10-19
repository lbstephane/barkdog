# Changelog

All notable changes to BarkDog. Versions follow [semantic versioning](https://semver.org/).
🇫🇷 Version française plus bas.

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

## [1.0.0] — 19/10/2026 (français)

Première version publique.

- **Détection** : IA locale YAMNet (521 classes), analyse toutes les 0,5 s, rien ne sort du boîtier. 13 nuisances au choix avec seuil par nuisance, déclenchement facultatif sur le niveau sonore, sons à ignorer (canards, oiseaux, météo, circulation). Épisodes complets avec pré-enregistrement, calme réglable et nombre minimum de détections. Gain et filtre coupe-bas.
- **Vie privée** : voix humaines rendues muettes par défaut et signalées sur la frise.
- **Traçabilité** : horodatage, catégories et empreinte SHA-256 de chaque fichier, identifiant des réglages, historique complet, état de synchronisation de l'heure.
- **Page web** : état et marche / arrêt, bandeau d'enregistrement, frise par fichier, journées repliables, filtres, graphique, exports CSV, annotations, corbeille, mode test en direct, réglages à chaud, interface en français et en anglais.
- **Sécurité** : mot de passe haché, sessions signées, anti-CSRF, CSP stricte, limitation des tentatives, services systemd cloisonnés, règle sudo minimale.
