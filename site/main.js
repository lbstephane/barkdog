// Vidéo verticale sur téléphone en portrait, horizontale ailleurs.
(() => {
  const v = document.getElementById('film');
  if (v) {
    const portrait = matchMedia('(max-width: 700px) and (orientation: portrait)');
    const pick = () => {
      const vert = portrait.matches;
      const src = vert ? v.dataset.v : v.dataset.h;
      if (v.currentSrc === new URL(src, location.href).href) return;
      v.poster = vert ? v.dataset.vp : v.dataset.hp;
      v.src = src;
      v.closest('.film').classList.toggle('v', vert);
    };
    pick();
    portrait.addEventListener('change', pick);
  }

  // Bouton « Copier » des commandes d'installation.
  const en = document.documentElement.lang === 'en';
  const L = en ? { copy: 'Copy', done: 'Copied', sel: 'Selected' } : { copy: 'Copier', done: 'Copié', sel: 'Sélectionné' };
  document.querySelectorAll('.copy').forEach(btn => {
    btn.addEventListener('click', async () => {
      const text = document.getElementById(btn.dataset.target).innerText.trim();
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = L.done;
      } catch {
        const r = document.createRange();
        r.selectNodeContents(document.getElementById(btn.dataset.target));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        btn.textContent = L.sel;
      }
      setTimeout(() => (btn.textContent = L.copy), 1800);
    });
  });
})();
