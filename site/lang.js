// Langue du site : le choix explicite du visiteur est mémorisé ; sans choix,
// un navigateur qui n'est pas en français est envoyé vers la version anglaise.
(() => {
  const KEY = 'barkdog.site.langue';
  const here = document.documentElement.lang === 'en' ? 'en' : 'fr';
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}

  if (here === 'fr' && !saved) {
    const bot = navigator.webdriver || /bot|crawl|spider|slurp|preview/i.test(navigator.userAgent);
    const langs = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''];
    const french = langs.some(l => /^fr\b/i.test(l));
    if (!bot && !french) {
      location.replace('en/' + location.hash);
      return;
    }
  }

  // Les liens FR / EN mémorisent le choix.
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[data-lang]');
    if (!a) return;
    try { localStorage.setItem(KEY, a.dataset.lang); } catch (err) {}
  });
})();
