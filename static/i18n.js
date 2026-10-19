'use strict';
/* BarkDog : traduction de l'interface (français par défaut, anglais).
   Les clés sont les textes français ; un texte absent du dictionnaire reste en français.
   Langue : choix mémorisé dans ce navigateur, sinon langue du navigateur. */
(() => {
  const EN = {
    // ---- page principale (HTML)
    'Réglages': 'Settings',
    'Chargement…': 'Loading…',
    'Mode test': 'Test mode',
    "Scores de l'IA en direct, deux fois par seconde.": 'Live AI scores, twice per second.',
    'Démarrer': 'Start',
    'Arrêter': 'Stop',
    'Ne pas enregistrer pendant le test': 'Do not record during the test',
    "L'enregistrement reprend tout seul 5 min max après la fermeture de la page, et au bout de 30 min de test.": 'Recording resumes on its own at most 5 min after the page is closed, and after 30 min of testing.',
    'Période': 'Period',
    'Du': 'From',
    'Au': 'To',
    'Catégorie': 'Category',
    'Toutes': 'All',
    'Nuit seulement (22h–7h)': 'Night only (10 pm–7 am)',
    'Masquer les faux positifs': 'Hide false positives',
    'Voir la corbeille': 'Show trash',
    "Aujourd'hui": 'Today',
    '7 jours': '7 days',
    '30 jours': '30 days',
    'Tout': 'All',
    'Résumé': 'Summary',
    'Par jour': 'Per day',
    'Jour (7h–22h)': 'Day (7 am–10 pm)',
    'Nuit (22h–7h)': 'Night (10 pm–7 am)',
    'Toucher une barre pour voir ce jour': 'Tap a bar to see that day',
    'Exports': 'Exports',
    'Épisodes filtrés (CSV)': 'Filtered episodes (CSV)',
    'Synthèse par jour (CSV)': 'Daily summary (CSV)',
    "Journal brut d'origine": 'Original raw log',
    'Historique (marche, réglages…)': 'History (start/stop, settings…)',
    'Épisodes écartés': 'Discarded episodes',
    'Actualiser': 'Refresh',
    'Épisodes': 'Episodes',
    'Corbeille : ces enregistrements ne sont plus comptés. « Restaurer » les remet en place, « Supprimer définitivement » efface le fichier de la carte (la ligne reste dans le journal brut).': 'Trash: these recordings are no longer counted. “Restore” puts them back, “Delete permanently” erases the file from the SD card (the line stays in the raw log).',
    'Tout déplier': 'Expand all',
    'Tout replier': 'Collapse all',
    "Outil d'aide à la constitution d'un dossier : les niveaux sont relatifs (micro non calibré) et ne remplacent ni une mesure acoustique, ni un constat de commissaire de justice. Les annotations sont enregistrées à part : le journal d'origine n'est jamais modifié et un fichier audio n'est effacé que par une suppression définitive depuis la corbeille.": 'A tool to help build a case file: levels are relative (uncalibrated microphone) and replace neither an acoustic measurement nor an official report by a bailiff. Annotations are stored separately: the original log is never modified and an audio file is only erased by a permanent deletion from the trash.',
    'Fermer les réglages': 'Close settings',
    'Fermer': 'Close',
    'Nuisances à enregistrer': 'Nuisances to record',
    'Cochez ce qui vous gêne. Le seuil propre à une nuisance est facultatif (sinon, seuil général).': 'Tick what bothers you. A per-nuisance threshold is optional (otherwise the general threshold applies).',
    'Sons à ignorer': 'Sounds to ignore',
    "Quand l'un de ces sons domine, la détection est annulée (ex. canards confondus avec des aboiements).": 'When one of these sounds dominates, the detection is cancelled (e.g. ducks mistaken for barking).',
    'Vie privée': 'Privacy',
    "Enregistrer les paroles d'autrui sans consentement est interdit (art. 226-1 du Code pénal). Le masquage rend muets les passages où l'IA entend une voix.": "Recording other people's private conversations without consent is illegal in many countries (in France, art. 226-1 of the Penal Code). Masking silences the passages where the AI hears a voice.",
    'Masquer la parole dans les fichiers (recommandé)': 'Mask speech in the files (recommended)',
    'Ne pas enregistrer un épisode surtout composé de parole': 'Do not record an episode made mostly of speech',
    'Désactivé (à vos risques)': 'Disabled (at your own risk)',
    'Sensibilité de la détection de voix': 'Voice detection sensitivity',
    'Détection': 'Detection',
    'Seuil général (plus bas = plus sensible)': 'General threshold (lower = more sensitive)',
    'Détections minimum par épisode': 'Minimum detections per episode',
    '3 = un son isolé (1 s) est ignoré': '3 = an isolated sound (1 s) is ignored',
    'Déclencher aussi au-delà de (dBFS)': 'Also trigger above (dBFS)',
    'désactivé': 'disabled',
    'Niveau relatif, non calibré : vide = désactivé': 'Relative, uncalibrated level: empty = disabled',
    'Micro et audio': 'Microphone and audio',
    'Micro': 'Microphone',
    'Gain logiciel': 'Software gain',
    'Filtre coupe-bas': 'High-pass filter',
    'Aucun': 'None',
    '200 Hz (ronflement secteur)': '200 Hz (mains hum)',
    "Changer de micro redémarre l'écoute (environ 10 s). Les autres réglages s'appliquent sans interruption.": 'Changing the microphone restarts listening (about 10 s). Other settings apply without interruption.',
    'Pré-enregistrement (s)': 'Pre-roll (s)',
    'Calme pour clore (s)': 'Quiet time to close (s)',
    "Durée max d'un fichier (s)": 'Max file length (s)',
    'Enregistrer les réglages': 'Save settings',
    'Annuler les modifications': 'Discard changes',
    'Langue': 'Language',
    'Compte': 'Account',
    'Mot de passe actuel': 'Current password',
    'Nouveau (8 car. min.)': 'New (min. 8 characters)',
    'Confirmation': 'Confirm',
    'Changer le mot de passe': 'Change password',
    'Se déconnecter': 'Sign out',
    // ---- page de connexion
    'Connexion · BarkDog': 'Sign in · BarkDog',
    'Accès réservé. Ne pas exposer cette page directement sur Internet : utilisez un VPN (Tailscale, WireGuard).': 'Restricted access. Do not expose this page directly to the Internet: use a VPN (Tailscale, WireGuard).',
    'Mot de passe': 'Password',
    'Se connecter': 'Sign in',
    'Aucun mot de passe défini : sur le boîtier, lancer « python3 auth.py --set » (ou relancer install.sh).': 'No password set: on the box, run “python3 auth.py --set” (or run install.sh again).',
    'Connexion impossible': 'Sign-in failed',
    'Boîtier injoignable': 'Box unreachable',
    // ---- résumé, graphique, liste
    'épisodes': 'episodes',
    'durée cumulée': 'total duration',
    'épisodes la nuit': 'episodes at night',
    'jours avec nuisance': 'days with nuisance',
    '{day} : {n} épisode(s), {dur}': '{day}: {n} episode(s), {dur}',
    ' (dont {n} la nuit)': ' (incl. {n} at night)',
    'max {dur}/jour': 'max {dur}/day',
    'Corbeille vide sur cette période.': 'Trash is empty for this period.',
    'Aucun épisode sur cette période.': 'No episodes for this period.',
    '{n} épisode': '{n} episode',
    '{n} épisodes': '{n} episodes',
    '{n} la nuit': '{n} at night',
    'Afficher plus ({n} restants)': 'Show more ({n} left)',
    'nuit': 'night',
    'faux positif': 'false positive',
    'Passages avec une voix rendus muets': 'Passages with a voice silenced',
    'parole masquée {dur}': 'speech masked {dur}',
    ' · confiance IA {p} %': ' · AI confidence {p}%',
    'Fichier audio absent de la carte.': 'Audio file missing from the SD card.',
    'Télécharger': 'Download',
    'Restaurer': 'Restore',
    'Supprimer définitivement': 'Delete permanently',
    "Ce n'est pas un faux positif": 'Not a false positive',
    'Faux positif': 'False positive',
    'Modifier la note': 'Edit note',
    'Ajouter une note': 'Add a note',
    'Supprimer': 'Delete',
    'Empreinte SHA-256 du fichier': 'SHA-256 fingerprint of the file',
    ' · réglages {id}': ' · settings {id}',
    'Chronologie indisponible pour cet enregistrement (lancer reanalyse.py).': 'Timeline unavailable for this recording (run reanalyse.py).',
    'Parole masquée {a} – {b}': 'Speech masked {a} – {b}',
    'Écouter à partir de {t}': 'Play from {t}',
    '+{n} autres': '+{n} more',
    'Toucher pour écouter à cet endroit': 'Tap to play from here',
    // ---- actions
    "Impossible d'enregistrer : {e}": 'Could not save: {e}',
    'Action impossible : {e}': 'Action failed: {e}',
    'Note (ex. « chiens lâchés », « réveillés »)': 'Note (e.g. “dogs let out”, “woke us up”)',
    "Mettre l'enregistrement de {t} à la corbeille ?": 'Move the {t} recording to the trash?',
    'Supprimer définitivement ce fichier audio ? Cette action est irréversible.': 'Permanently delete this audio file? This cannot be undone.',
    // ---- état du boîtier
    'Écoute active': 'Listening',
    'Écoute arrêtée': 'Listening stopped',
    'Écoute en échec (micro débranché ?)': 'Listening failed (microphone unplugged?)',
    'Démarrage en cours…': 'Starting…',
    'Service lancé, aucun signe de vie depuis {dur}': 'Service running, no sign of life for {dur}',
    'Écoute jamais démarrée': 'Listening never started',
    'Écoute arrêtée depuis {dur}': 'Listening stopped {dur} ago',
    'Heure synchronisée': 'Clock synchronised',
    'Heure NON synchronisée': 'Clock NOT synchronised',
    'Heure : état inconnu': 'Clock: unknown state',
    'Mode test : enregistrement suspendu ({dur} max)': 'Test mode: recording paused ({dur} max)',
    "Nouveaux réglages en cours d'application…": 'Applying new settings…',
    '{n} Go libres': '{n} GB free',
    'Heure du boîtier : {t}': 'Box time: {t}',
    "Arrêter l'écoute": 'Stop listening',
    "Démarrer l'écoute": 'Start listening',
    'Son détecté · non enregistré (mode test)': 'Sound detected · not recorded (test mode)',
    'Enregistrement en cours': 'Recording',
    'Impossible de charger les épisodes ({e}).': 'Could not load episodes ({e}).',
    'Nouvel enregistrement : {t} · {cats}': 'New recording: {t} · {cats}',
    "Arrêter l'écoute ? Plus rien ne sera enregistré tant qu'elle n'est pas relancée (elle redémarre aussi au prochain démarrage du boîtier).": 'Stop listening? Nothing will be recorded until it is started again (it also restarts the next time the box boots).',
    'Arrêt…': 'Stopping…',
    'Démarrage…': 'Starting…',
    'Écoute démarrée': 'Listening started',
    'Impossible : {e}': 'Failed: {e}',
    'Fermer sans enregistrer les modifications ?': 'Close without saving changes?',
    // ---- mode test
    'Niveau': 'Level',
    'Voix (vie privée)': 'Voice (privacy)',
    "Pas de données{since} : l'écoute tourne-t-elle ?": 'No data{since}: is listening running?',
    ' depuis {dur}': ' for {dur}',
    'Son détecté · {dur} · non enregistré (test)': 'Sound detected · {dur} · not recorded (test)',
    'Enregistrement en cours · {dur}': 'Recording · {dur}',
    'En écoute · seuil {s}': 'Listening · threshold {s}',
    ' · enregistrement suspendu': ' · recording paused',
    "L'IA entend surtout : ": 'The AI mostly hears: ',
    '· son à ignorer {p} % : détection annulée': '· sound to ignore {p}%: detection cancelled',
    '· voix entendue : passage masqué': '· voice heard: passage masked',
    "▶ début d'épisode (avec les secondes précédentes)": '▶ episode start (including the previous seconds)',
    "■ fin d'épisode : écarté (trop court ou parole, voir les épisodes écartés)": '■ episode end: discarded (too short or speech, see discarded episodes)',
    "■ fin d'épisode (test : non enregistré)": '■ episode end (test: not recorded)',
    "■ fin d'épisode, fichier enregistré": '■ episode end, file saved',
    'Mode test limité à 30 min : enregistrement réactivé': 'Test mode limited to 30 min: recording re-enabled',
    "Impossible d'activer le mode test : {e}": 'Could not enable test mode: {e}',
    // ---- réglages
    'seuil': 'thr.',
    'Seuil propre (facultatif)': 'Own threshold (optional)',
    'Par défaut (système)': 'Default (system)',
    'default (ALSA, conversion automatique)': 'default (ALSA, automatic conversion)',
    '{name} ({n} canal, {hz} Hz)': '{name} ({n} channel, {hz} Hz)',
    '{name} ({n} canaux, {hz} Hz)': '{name} ({n} channels, {hz} Hz)',
    '{name} (actuel, non détecté)': '{name} (current, not detected)',
    "Identifiant des réglages (noté dans le journal et l'historique)": 'Settings identifier (written in the log and history)',
    'Modifications annulées.': 'Changes discarded.',
    'Désactiver la protection de la parole ? Les conversations captées seront enregistrées telles quelles, ce qui peut être illégal.': 'Disable speech protection? Captured conversations will be recorded as is, which may be illegal.',
    'Enregistrement…': 'Saving…',
    'Réglages enregistrés ({n} modification)': 'Settings saved ({n} change)',
    'Réglages enregistrés ({n} modifications)': 'Settings saved ({n} changes)',
    " : l'écoute redémarre, environ 10 s": ': listening restarts, about 10 s',
    'Aucun changement': 'No change',
    'Refusé : {e}': 'Rejected: {e}',
    'Les deux saisies diffèrent.': 'The two entries differ.',
    'Mot de passe changé (les autres appareils devront se reconnecter).': 'Password changed (other devices will have to sign in again).',
    // ---- groupes du catalogue
    'Animaux': 'Animals',
    'Activités humaines': 'Human activities',
    'Moteurs et alarmes': 'Engines and alarms',
    'Niveau sonore élevé': 'High sound level',
    // ---- exports (en-têtes et valeurs)
    'oui': 'yes',
    'non': 'no',
  };

  const STORE = 'barkdog.langue';
  let saved = null;
  try { saved = localStorage.getItem(STORE); } catch { /* stockage indisponible */ }
  const lang = saved === 'fr' || saved === 'en' ? saved : ((navigator.language || 'fr').toLowerCase().startsWith('fr') ? 'fr' : 'en');

  const t = (s, vars) => {
    let out = lang === 'en' && Object.prototype.hasOwnProperty.call(EN, s) ? EN[s] : s;
    if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
    return out;
  };

  // Traduit les textes et attributs statiques des pages HTML.
  function apply(root = document.documentElement) {
    document.documentElement.lang = lang;
    if (lang === 'fr') return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: n => (/^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    for (let n; (n = walker.nextNode());) {
      const key = n.nodeValue.replace(/\s+/g, ' ').trim();
      if (key && Object.prototype.hasOwnProperty.call(EN, key)) {
        const m = n.nodeValue.match(/^(\s*)[\s\S]*?(\s*)$/);
        n.nodeValue = m[1] + EN[key] + m[2];
      }
    }
    root.querySelectorAll('[title],[aria-label],[placeholder]').forEach(el => {
      for (const a of ['title', 'aria-label', 'placeholder']) {
        const v = el.getAttribute(a);
        if (v && Object.prototype.hasOwnProperty.call(EN, v)) el.setAttribute(a, EN[v]);
      }
    });
  }

  function setLang(l) {
    try { localStorage.setItem(STORE, l); } catch { /* stockage indisponible */ }
    location.reload();
  }

  window.I18N = {lang, t, apply, setLang, locale: lang === 'en' ? 'en-GB' : 'fr-FR'};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => apply());
  else apply();
})();
