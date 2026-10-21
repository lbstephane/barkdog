# Roadmap

🇫🇷 Version française plus bas.

Ideas come from user feedback. Have a need that isn't listed? Open an [issue on GitLab](https://gitlab.com/lbstephane/barkdog/-/issues).

## Planned for 1.2

- **Approximate dB(A) level, with calibration.** During a steady noise, measure the level with any sound level meter (or a phone app), enter it in BarkDog, and it derives an offset and applies A-weighting. Always shown as “indicative, not certified”.
- **Optional trusted timestamping (RFC 3161).** Once a day, only the fingerprint of the day's log is sent to a public timestamping authority (for example FreeTSA). No sound ever leaves the box. The token can be checked with `openssl ts -verify`. The recorder keeps having no network access: the web service would handle it.
- **Chain the other logs too**: listening history and discarded episodes, like the episode log since 1.1.
- **Home Assistant integration via MQTT**, with automatic discovery: listening status, recording in progress, last episode and episodes of the day appear as sensors. The web service would publish them; the recorder keeps having no network access.
- **Read-only REST API** (status, episodes, statistics) with a token, for integrations and a possible native mobile app.
- **Power consumption measured** on Pi Zero 2 W, 3 and 4, listening and recording, and added to the documentation.
- **Tested microphones**: a short list of models that work well, with their quirks.

## Considered, not planned

- **Dog breed or bird species recognition**: YAMNet recognises families of sounds, not breeds or species. For birds, see [BirdNET-Pi](https://github.com/Nachtzuster/BirdNET-Pi).
- **Infrasound**: out of reach with 16 kHz audio, YAMNet and a USB microphone.
- **Answering back** (predator sounds, ultrasound…) or **neighbourhood surveillance**: BarkDog documents, it does not retaliate or watch people.

---

# Feuille de route

Les idées viennent des retours des utilisateurs. Un besoin qui n'apparaît pas ici ? Ouvrez un [ticket sur GitLab](https://gitlab.com/lbstephane/barkdog/-/issues).

## Prévu pour la 1.2

- **Niveau approximatif en dB(A), avec étalonnage.** Pendant un bruit stable, on mesure le niveau avec n'importe quel sonomètre (ou une appli de téléphone), on le saisit dans BarkDog, qui en déduit un décalage et applique la pondération A. Toujours affiché comme « indicatif, non certifié ».
- **Horodatage par un tiers de confiance (RFC 3161), en option.** Une fois par jour, seule l'empreinte du journal de la journée part vers une autorité d'horodatage publique (par exemple FreeTSA). Aucun son ne sort du boîtier. Le jeton se vérifie avec `openssl ts -verify`. L'enregistreur reste sans accès réseau : c'est le service web qui s'en chargerait.
- **Chaîner aussi les autres journaux** : historique de l'écoute et épisodes écartés, comme le journal des épisodes depuis la 1.1.
- **Intégration Home Assistant via MQTT**, avec découverte automatique : état de l'écoute, enregistrement en cours, dernier épisode et épisodes du jour apparaissent comme capteurs. C'est le service web qui publierait ; l'enregistreur reste sans accès réseau.
- **API REST en lecture seule** (état, épisodes, statistiques) avec un jeton, pour les intégrations et une éventuelle appli mobile native.
- **Consommation électrique mesurée** sur Pi Zero 2 W, 3 et 4, en écoute et pendant un enregistrement, et ajoutée à la documentation.
- **Micros testés** : une courte liste de modèles qui fonctionnent bien, avec leurs particularités.

## Étudié, non prévu

- **Reconnaître la race d'un chien ou l'espèce d'un oiseau** : YAMNet reconnaît des familles de sons, pas des races ni des espèces. Pour les oiseaux, voir [BirdNET-Pi](https://github.com/Nachtzuster/BirdNET-Pi).
- **Infrabasses** : hors de portée avec un audio à 16 kHz, YAMNet et un micro USB.
- **Riposte** (sons de prédateur, ultrasons…) ou **surveillance du voisinage** : BarkDog documente, il ne riposte pas et ne surveille personne.
