'use strict';
/* BarkDog : consultation, mode test, réglages. Aucun script inline (CSP). */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const pad = n => String(n).padStart(2, '0');
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const dayKey = iso => iso.slice(0, 10);
const parseDay = k => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
const frDay = k => parseDay(k).toLocaleDateString('fr-FR', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'});
const shortDay = k => parseDay(k).toLocaleDateString('fr-FR', {day: 'numeric', month: 'short'});
const fmtDur = s => { s = Math.round(s); if (s < 60) return s + ' s'; const m = Math.floor(s / 60); return m < 60 ? `${m} min ${pad(s % 60)}` : `${Math.floor(m / 60)} h ${pad(m % 60)}`; };
const fmtT = s => `${Math.floor(s / 60)}:${pad(Math.floor(s % 60))}`;
const audioUrl = f => '/audio/' + f.split('/').map(encodeURIComponent).join('/');

let EVENTS = [], LIMIT = 60, CONFIG = null, CATALOG = {profils: [], exclusions: []}, MICROS = [];
let JVER = null, REC = false, pendingRefresh = false, NEW_FILES = new Set(), statusTimer = null;

/* ---------- appels au boîtier (anti-CSRF : en-tête applicatif sur chaque POST) ---------- */
async function api(url, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'aboiements'},
    body: JSON.stringify(body),
  };
  const r = await fetch(url, opts);
  if (r.status === 401) { location.href = '/login'; throw new Error('connexion requise'); }
  let data = null;
  try { data = await r.json(); } catch { /* corps vide */ }
  if (!r.ok) throw new Error(data?.erreur || 'HTTP ' + r.status);
  return data;
}

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 5000);
}

/* ---------- catégories (catalogue fourni par le boîtier) ---------- */
const catInfo = id => CATALOG.profils.find(p => p.id === id) || {id, label: id, couleur: 2};
const catLabel = id => catInfo(id).label;
const catCol = id => 'col-' + (catInfo(id).couleur ?? 2);
const catOrder = id => { const i = CATALOG.profils.findIndex(p => p.id === id); return i < 0 ? 99 : i; };

/* ---------- filtres et période ---------- */
function setRange(days, keepLimit) {
  const t = new Date();
  if (days === 'all') {
    $('#from').value = EVENTS.length ? dayKey(EVENTS.reduce((a, e) => e.debut < a ? e.debut : a, EVENTS[0].debut)) : ymd(t);
  } else {
    const f = new Date(t); f.setDate(t.getDate() - (days - 1));
    $('#from').value = ymd(f);
  }
  $('#to').value = ymd(t);
  $$('[data-range]').forEach(b => b.classList.toggle('on', b.dataset.range == days));
  if (!keepLimit) LIMIT = 60;
  render();
}

function fillCategoryFilter() {
  const sel = $('#cat'), cur = sel.value;
  const ids = new Set([...(CONFIG?.profils || []), ...EVENTS.flatMap(e => e.tags)]);
  ids.delete('inconnu');
  const sorted = [...ids].sort((a, b) => catOrder(a) - catOrder(b));
  sel.innerHTML = '<option value="">Toutes</option>' + sorted.map(id => `<option value="${esc(id)}">${esc(catLabel(id))}</option>`).join('');
  if (sorted.includes(cur)) sel.value = cur;
}

function filtered() {
  const f = $('#from').value, t = $('#to').value, c = $('#cat').value;
  const n = $('#night').checked, h = $('#hidefp').checked, tr = $('#trash').checked;
  return EVENTS.filter(e => {
    if (e.supprime !== tr) return false;
    const k = dayKey(e.debut);
    if (f && k < f) return false;
    if (t && k > t) return false;
    if (c && !e.tags.includes(c)) return false;
    if (n && !e.nuit) return false;
    if (h && e.faux_positif) return false;
    return true;
  });
}

function perDay(list) {
  const f = $('#from').value || (list.length ? dayKey(list[list.length - 1].debut) : ymd(new Date()));
  const t = $('#to').value || ymd(new Date());
  const map = new Map();
  for (let d = parseDay(f); ymd(d) <= t && map.size < 400; d.setDate(d.getDate() + 1))
    map.set(ymd(d), {n: 0, s: 0, nn: 0, ns: 0, cats: {}});
  for (const e of list) {
    const r = map.get(dayKey(e.debut)); if (!r) continue;
    r.n++; r.s += e.duree_s;
    if (e.nuit) { r.nn++; r.ns += e.duree_s; }
    for (const c of e.tags) r.cats[c] = (r.cats[c] || 0) + 1;
  }
  return map;
}

/* ---------- affichage ---------- */
function render() {
  const inTrash = $('#trash').checked;
  document.body.classList.toggle('trash', inTrash);
  const nTrash = EVENTS.filter(e => e.supprime).length;
  $('#trashcount').textContent = nTrash ? `(${nTrash})` : '';
  const list = filtered().sort((a, b) => a.debut < b.debut ? 1 : -1);
  const days = perDay(list);

  const tot = list.reduce((a, e) => a + e.duree_s, 0);
  const nightN = list.filter(e => e.nuit).length;
  const active = [...days.values()].filter(d => d.n).length;
  $('#kpis').innerHTML = [[list.length, 'épisodes'], [fmtDur(tot), 'durée cumulée'], [nightN, 'épisodes la nuit'],
    [`${active}/${days.size}`, 'jours avec nuisance']]
    .map(([v, l]) => `<div class="card kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

  const vals = [...days.entries()];
  const max = Math.max(60, ...vals.map(([, d]) => d.s));
  $('#chart').innerHTML = vals.map(([k, d]) => {
    const hd = (d.s - d.ns) / max * 100, hn = d.ns / max * 100;
    const tip = `${shortDay(k)} : ${d.n} épisode(s), ${fmtDur(d.s)}${d.nn ? ` (dont ${d.nn} la nuit)` : ''}`;
    return `<div class="bar" data-day="${k}" title="${esc(tip)}" aria-label="${esc(tip)}"><div class="d" style="height:${hd}%"></div><div class="n" style="height:${hn}%"></div></div>`;
  }).join('');
  const ks = vals.map(([k]) => k);
  $('#axis').innerHTML = ks.length ? `<span>${shortDay(ks[0])}</span><span>max ${fmtDur(max)}/jour</span><span>${shortDay(ks[ks.length - 1])}</span>` : '';

  if (!list.length) { $('#daytools').hidden = true; $('#list').innerHTML = `<div class="empty">${inTrash ? 'Corbeille vide sur cette période.' : 'Aucun épisode sur cette période.'}</div>`; return; }

  // Regroupement par jour : chaque journée se replie, l'état est mémorisé dans ce navigateur.
  const groups = [];
  for (const e of list) {
    const k = dayKey(e.debut);
    if (!groups.length || groups[groups.length - 1].k !== k) groups.push({k, evs: []});
    groups[groups.length - 1].evs.push(e);
  }
  $('#daytools').hidden = groups.length < 2;
  let html = '', budget = LIMIT, hidden = 0;
  for (const g of groups) {
    if (budget <= 0) { hidden += g.evs.length; continue; }
    const open = isDayOpen(g.k, groups.length);
    const d = days.get(g.k) || {n: g.evs.length, s: g.evs.reduce((a, e) => a + e.duree_s, 0), nn: g.evs.filter(e => e.nuit).length};
    const isNew = g.evs.some(e => NEW_FILES.has(e.fichier));
    const id = 'd-' + g.k;
    html += `<section class="dgroup${open ? ' open' : ''}" data-day="${g.k}">
      <button type="button" class="day${isNew ? ' has-new' : ''}" aria-expanded="${open}" aria-controls="${id}">
        <svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="dname">${esc(frDay(g.k))}</span>
        <span class="dsum">${d.n} épisode${d.n > 1 ? 's' : ''} · ${fmtDur(d.s)}${d.nn ? ` · <b>${d.nn} la nuit</b>` : ''}</span>
      </button>
      <div class="dbody" id="${id}">`;
    if (open) {
      const shown = g.evs.slice(0, budget);
      html += shown.map(card).join('');
      budget -= shown.length; hidden += g.evs.length - shown.length;
    }
    html += '</div></section>';
  }
  if (hidden) html += `<button class="more" id="more">Afficher plus (${hidden} restants)</button>`;
  $('#list').innerHTML = html;
}

function card(e) {
  const cats = [...e.tags].sort((a, b) => catOrder(a) - catOrder(b));
  const score = Math.max(0, ...cats.map(c => e.scores?.[c] || 0));
  const masked = parseFloat(e.parole_masquee_s) || 0;
  return `<article class="ev ${catCol(cats[0])} ${e.faux_positif ? 'fp' : ''} ${NEW_FILES.has(e.fichier) ? 'new' : ''}" data-f="${esc(e.fichier)}">
      <div class="row1">
        <span class="time">${esc(e.debut.slice(11, 19))}</span>
        ${cats.map(c => `<span class="badge ${catCol(c)}">${esc(catLabel(c))}</span>`).join('')}
        ${e.nuit ? '<span class="badge b-nuit">nuit</span>' : ''}
        ${e.faux_positif ? '<span class="badge b-fp">faux positif</span>' : ''}
        ${masked ? `<span class="badge b-mask" title="Passages avec une voix rendus muets">parole masquée ${fmtDur(masked)}</span>` : ''}
        <span class="mute">${fmtDur(e.duree_s)}${score ? ` · confiance IA ${Math.round(score * 100)} %` : ''}</span>
      </div>
      ${e.present ? `<audio controls preload="none" src="${audioUrl(e.fichier)}"></audio>${timeline(e)}` : '<p class="mute err">Fichier audio absent de la carte.</p>'}
      <div class="actions">
        ${e.present ? `<a class="btn" href="${audioUrl(e.fichier)}?dl=1">Télécharger</a>` : ''}
        ${e.supprime ? `
        <button data-act="restore">Restaurer</button>
        <button data-act="purge" class="danger">Supprimer définitivement</button>` : `
        <button data-act="fp">${e.faux_positif ? 'Ce n\'est pas un faux positif' : 'Faux positif'}</button>
        <button data-act="note">${e.note ? 'Modifier la note' : 'Ajouter une note'}</button>
        <button data-act="del" class="danger">Supprimer</button>`}
        <span class="mute" title="Empreinte SHA-256 du fichier${e.reglages ? ' · réglages ' + esc(e.reglages) : ''}">#${esc((e.sha256 || '').slice(0, 10))}</span>
      </div>
      ${e.note ? `<p class="note">${esc(e.note)}</p>` : ''}
    </article>`;
}

/* ---------- journées repliables ---------- */
const DAYS_KEY = 'barkdog.jours';
let DAY_STATE = (() => { try { return JSON.parse(localStorage.getItem(DAYS_KEY)) || {}; } catch { return {}; } })();
function saveDays() {
  const limit = ymd(new Date(Date.now() - 120 * 864e5));            // on oublie les choix de plus de 4 mois
  for (const k of Object.keys(DAY_STATE)) if (k < limit) delete DAY_STATE[k];
  try { localStorage.setItem(DAYS_KEY, JSON.stringify(DAY_STATE)); } catch { /* stockage indisponible */ }
}
function isDayOpen(k, nGroups) {
  if (nGroups === 1 || $('#from').value && $('#from').value === $('#to').value) return true;   // un seul jour affiché
  if (k in DAY_STATE) return DAY_STATE[k];
  const t = new Date(), y = new Date(t); y.setDate(t.getDate() - 1);
  return k === ymd(t) || k === ymd(y);                             // aujourd'hui et hier ouverts par défaut
}
function setDays(open) {
  $$('#list .dgroup').forEach(g => DAY_STATE[g.dataset.day] = open);
  saveDays(); render();
}
$('#daytools').addEventListener('click', ev => {
  const b = ev.target.closest('button[data-days]'); if (b) setDays(b.dataset.days === 'open');
});

/* Le bandeau du jour reste collé sous la barre du haut (et sous le bandeau d'enregistrement s'il est affiché). */
function stickyTop() {
  const bar = $('.appbar'), rec = $('#recbanner');
  let top = bar ? bar.getBoundingClientRect().height : 0;
  if (rec && !rec.hidden && rec.offsetHeight) top = Math.max(top, parseFloat(getComputedStyle(rec).top) || 0) + rec.offsetHeight + 6;
  document.documentElement.style.setProperty('--sticky-top', Math.round(top) + 'px');
}
if ('ResizeObserver' in window) { const ro = new ResizeObserver(stickyTop); ['.appbar', '#recbanner'].forEach(s => $(s) && ro.observe($(s))); }
addEventListener('resize', stickyTop); stickyTop();

/* ---------- chronologie dans l'enregistrement ---------- */
function timeline(e) {
  if (e.segments === null || e.segments === undefined)
    return '<p class="notl">Chronologie indisponible pour cet enregistrement (lancer reanalyse.py).</p>';
  const masks = e.parole_masquee || [];
  if (!e.segments.length && !masks.length) return '';
  const D = Math.max(+e.duree_s || 0, 0.1);
  const lanes = [...new Set(e.segments.map(s => s.categorie))].sort((a, b) => catOrder(a) - catOrder(b));
  const nl = lanes.length + (masks.length ? 1 : 0);
  const pos = (a, b) => `left:${a / D * 100}%;width:${Math.max(0.8, (b - a) / D * 100)}%`;
  const bars = e.segments.map(s => {
    const tip = `${catLabel(s.categorie)} ${fmtT(s.debut_s)} – ${fmtT(s.fin_s)} (${Math.round(s.score_max * 100)} %)`;
    return `<span class="seg ${catCol(s.categorie)}" title="${esc(tip)}" style="top:${3 + lanes.indexOf(s.categorie) * 9}px;${pos(s.debut_s, s.fin_s)}"></span>`;
  }).join('') + masks.map(m =>
    `<span class="seg mask" title="Parole masquée ${fmtT(m.debut_s)} – ${fmtT(m.fin_s)}" style="top:${3 + lanes.length * 9}px;${pos(m.debut_s, m.fin_s)}"></span>`).join('');
  const shown = e.segments.slice(0, 12);
  const chips = shown.map(s =>
    `<button class="chip" data-seek="${Math.max(0, s.debut_s - 1)}" title="Écouter à partir de ${fmtT(Math.max(0, s.debut_s - 1))}"><i class="sw ${catCol(s.categorie)}"></i>${fmtT(s.debut_s)} ${esc(catLabel(s.categorie))}</button>`).join('');
  const more = e.segments.length > shown.length ? `<span class="mute">+${e.segments.length - shown.length} autres</span>` : '';
  return `<div class="tl" data-d="${D}" style="height:${nl * 9 + 5}px" title="Toucher pour écouter à cet endroit">${bars}<span class="ph"></span></div><div class="chips">${chips}${more}</div>`;
}
function seekAudio(art, t) {
  const a = art.querySelector('audio'); if (!a) return;
  if (a.readyState >= 1) { a.currentTime = t; a.play(); }
  else { a.addEventListener('loadedmetadata', () => { a.currentTime = t; }, {once: true}); a.play(); }
}
document.addEventListener('timeupdate', ev => {     // tête de lecture (timeupdate ne remonte pas : capture)
  const a = ev.target; if (a.tagName !== 'AUDIO') return;
  const tl = a.closest('.ev')?.querySelector('.tl'); if (!tl) return;
  const ph = tl.querySelector('.ph'), D = a.duration || +tl.dataset.d;
  ph.style.display = 'block'; ph.style.left = Math.min(100, a.currentTime / D * 100) + '%';
}, true);
document.addEventListener('play', ev => $$('audio').forEach(a => a !== ev.target && a.pause()), true);
const momentsText = e => (e.segments || []).map(s => `${catLabel(s.categorie)} ${fmtT(s.debut_s)}-${fmtT(s.fin_s)}`).join(' | ');

/* ---------- actions sur les épisodes ---------- */
async function annotate(f, patch) {
  const e = EVENTS.find(x => x.fichier === f); if (!e) return;
  const before = {faux_positif: e.faux_positif, note: e.note};
  Object.assign(e, patch); render();
  try { await api('/api/annotate', {fichier: f, ...patch}); }
  catch (err) { Object.assign(e, before); render(); alert('Impossible d\'enregistrer : ' + err.message); }
}
async function fileAction(f, act) {
  const e = EVENTS.find(x => x.fichier === f); if (!e) return;
  try { await api('/api/' + act, {fichier: f}); }
  catch (err) { alert('Action impossible : ' + err.message); return; }
  if (act === 'delete') e.supprime = true;
  if (act === 'restore') e.supprime = false;
  if (act === 'purge') EVENTS = EVENTS.filter(x => x !== e);
  render();
}
$('#list').addEventListener('click', ev => {
  if (ev.target.id === 'more') { LIMIT += 60; render(); return; }
  const dh = ev.target.closest('button.day');
  if (dh) {
    const k = dh.closest('.dgroup').dataset.day, open = dh.getAttribute('aria-expanded') !== 'true';
    DAY_STATE[k] = open; saveDays();
    const top = dh.getBoundingClientRect().top; render();
    const again = $(`#list .dgroup[data-day="${k}"] .day`);         // garder le bandeau sous le doigt
    if (again) scrollBy(0, again.getBoundingClientRect().top - top);
    return;
  }
  const chip = ev.target.closest('.chip[data-seek]');
  if (chip) { seekAudio(chip.closest('.ev'), +chip.dataset.seek); return; }
  const tl = ev.target.closest('.tl');
  if (tl) { const r = tl.getBoundingClientRect(); seekAudio(tl.closest('.ev'), Math.max(0, (ev.clientX - r.left) / r.width * +tl.dataset.d)); return; }
  const b = ev.target.closest('button[data-act]'); if (!b) return;
  const f = b.closest('.ev').dataset.f, e = EVENTS.find(x => x.fichier === f);
  if (b.dataset.act === 'fp') annotate(f, {faux_positif: !e.faux_positif});
  if (b.dataset.act === 'note') { const n = prompt('Note (ex. « chiens lâchés », « réveillés »)', e.note || ''); if (n !== null) annotate(f, {note: n.trim()}); }
  if (b.dataset.act === 'del' && confirm(`Mettre l'enregistrement de ${e.debut.slice(11, 19)} à la corbeille ?`)) fileAction(f, 'delete');
  if (b.dataset.act === 'restore') fileAction(f, 'restore');
  if (b.dataset.act === 'purge' && confirm('Supprimer définitivement ce fichier audio ? Cette action est irréversible.')) fileAction(f, 'purge');
});
$('#chart').addEventListener('click', ev => {
  const b = ev.target.closest('.bar'); if (!b) return;
  $('#from').value = $('#to').value = b.dataset.day;
  $$('[data-range]').forEach(x => x.classList.remove('on'));
  LIMIT = 60; render(); $('#list').scrollIntoView({behavior: 'smooth'});
});
$$('[data-range]').forEach(b => b.onclick = () => setRange(b.dataset.range === 'all' ? 'all' : +b.dataset.range));
['#from', '#to', '#cat', '#night', '#hidefp', '#trash'].forEach(s => $(s).addEventListener('change', () => {
  if (s === '#from' || s === '#to') $$('[data-range]').forEach(x => x.classList.remove('on'));
  LIMIT = 60; render();
}));

/* ---------- exports CSV (calculés dans la page) ---------- */
function download(name, rows) {
  const csv = rows.map(r => r.map(v => { v = String(v ?? ''); return /[;"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; }).join(';')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], {type: 'text/csv;charset=utf-8'}));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const suffix = () => `${$('#from').value || 'debut'}_${$('#to').value || 'fin'}`;
$('#exp-events').onclick = () => {
  const list = filtered().sort((a, b) => a.debut < b.debut ? -1 : 1);
  download(`episodes_${suffix()}.csv`, [
    ['debut', 'fin', 'duree_s', 'categories', 'moments_dans_le_fichier', 'nuit_22h_7h', 'faux_positif', 'note', 'scores_max',
      'parole_masquee_s', 'niveau_crete_dBFS', 'horloge_synchronisee', 'reglages', 'fichier', 'sha256'],
    ...list.map(e => [e.debut, e.fin, e.duree_s, e.tags.map(catLabel).join(' + '), momentsText(e), e.nuit ? 'oui' : 'non',
      e.faux_positif ? 'oui' : 'non', e.note, Object.entries(e.scores || {}).map(([k, v]) => `${k}:${v}`).join('|'),
      e.parole_masquee_s, e.niveau_crete_dBFS, e.horloge_synchronisee, e.reglages, e.fichier, e.sha256]),
  ]);
};
$('#exp-days').onclick = () => {
  const list = filtered(), days = perDay(list);
  const cats = [...new Set(list.flatMap(e => e.tags))].sort((a, b) => catOrder(a) - catOrder(b));
  const n = v => (v / 60).toFixed(1).replace('.', ',');
  download(`synthese_${suffix()}.csv`, [
    ['jour', 'episodes', 'duree_totale_min', 'episodes_22h_7h', 'duree_22h_7h_min', ...cats.map(catLabel)],
    ...[...days.entries()].map(([k, d]) => [k, d.n, n(d.s), d.nn, n(d.ns), ...cats.map(c => d.cats[c] || 0)]),
  ]);
};

/* ---------- état du boîtier ---------- */
async function loadStatus() {
  try {
    const s = await api('/api/status');
    const pills = [], age = s.dernier_signe_de_vie_s;
    if (s.ecoute_active) pills.push(['ok', 'Écoute active']);
    else if (s.service === 'inactive') pills.push(['bad', 'Écoute arrêtée']);
    else if (s.service === 'failed' || s.service === 'activating') pills.push(['bad', 'Écoute en échec (micro débranché ?)']);
    else if (s.service === 'active') pills.push(['warn', age == null ? 'Démarrage en cours…' : `Service lancé, aucun signe de vie depuis ${fmtDur(age)}`]);
    else pills.push(['bad', age == null ? 'Écoute jamais démarrée' : `Écoute arrêtée depuis ${fmtDur(age)}`]);
    pills.push(s.horloge_synchronisee === true ? ['ok', 'Heure synchronisée']
      : s.horloge_synchronisee === false ? ['bad', 'Heure NON synchronisée'] : ['warn', 'Heure : état inconnu']);
    if (s.mode_test?.actif) pills.push(['warn', `Mode test : enregistrement suspendu (${fmtDur(Math.max(0, s.mode_test.reste_s))} max)`]);
    if (s.ecoute_active && s.reglages_ecoute && s.reglages_ecoute !== s.reglages) pills.push(['warn', 'Nouveaux réglages en cours d\'application…']);
    const pct = s.disque_libre_go / s.disque_total_go;
    pills.push([pct < .1 ? 'bad' : pct < .25 ? 'warn' : 'ok', `${s.disque_libre_go} Go libres`]);
    $('#status').innerHTML = pills.map(([c, t]) => `<span class="pill"><span class="dot ${c}"></span>${esc(t)}</span>`).join('');
    $('#now').textContent = 'Heure du boîtier : ' + new Date(s.maintenant).toLocaleString('fr-FR');

    const btn = $('#svcbtn');
    if (s.controle_service && s.service && !btn.disabled) {
      const running = s.service === 'active' || s.service === 'activating';
      btn.hidden = false; btn.dataset.act = running ? 'stop' : 'start';
      btn.textContent = running ? 'Arrêter l\'écoute' : 'Démarrer l\'écoute';
      btn.classList.toggle('danger', running);
    } else if (!s.controle_service) btn.hidden = true;

    const rec = s.enregistrement || {}, testing = !!rec.test;   // épisode commencé pendant le test
    REC = !!rec.en_cours;
    const ban = $('#recbanner');
    ban.hidden = !REC; ban.classList.toggle('test', testing);
    if (REC) ban.innerHTML = `${testing ? 'Son détecté · non enregistré (mode test)' : 'Enregistrement en cours'} · ${fmtDur(rec.duree_s || 0)}${rec.tags?.length ? ` <small>${rec.tags.map(c => esc(catLabel(c))).join(', ')}</small>` : ''}`;
    document.title = (REC && !testing ? '● ' : '') + 'BarkDog';

    if (JVER !== null && s.journal_version !== JVER) refreshEvents();
    JVER = s.journal_version;
  } catch (err) {
    if (err.message !== 'connexion requise')
      $('#status').innerHTML = '<span class="pill"><span class="dot bad"></span>Boîtier injoignable</span>';
  }
}
async function loadEvents(first) {
  try {
    EVENTS = await api('/api/events');
    fillCategoryFilter();
    if (first) setRange(30); else render();
  } catch (err) {
    $('#list').innerHTML = `<div class="empty err">Impossible de charger les épisodes (${esc(err.message)}).</div>`;
  }
}
const anyPlaying = () => $$('audio').some(a => !a.paused && !a.ended);
async function refreshEvents() {
  if (anyPlaying()) { pendingRefresh = true; return; }   // ne pas couper une écoute en cours
  pendingRefresh = false;
  const before = new Set(EVENTS.map(e => e.fichier)), y = window.scrollY;
  try { EVENTS = await api('/api/events'); } catch { return; }
  const fresh = EVENTS.filter(e => !before.has(e.fichier));
  fresh.forEach(e => NEW_FILES.add(e.fichier));
  fillCategoryFilter();
  const quick = document.querySelector('[data-range].on');
  if (quick) setRange(quick.dataset.range === 'all' ? 'all' : +quick.dataset.range, true); else render();
  window.scrollTo(0, y);
  if (fresh.length) {
    const e = fresh.sort((a, b) => a.debut < b.debut ? 1 : -1)[0];
    toast(`Nouvel enregistrement : ${e.debut.slice(11, 16)} · ${e.tags.map(catLabel).join(', ')}`);
    setTimeout(() => fresh.forEach(x => NEW_FILES.delete(x.fichier)), 6000);
  }
}
['pause', 'ended'].forEach(t => document.addEventListener(t, () => {
  if (pendingRefresh && !anyPlaying()) setTimeout(refreshEvents, 300);
}, true));
function scheduleStatus() {
  clearTimeout(statusTimer);
  statusTimer = setTimeout(async () => { if (!document.hidden) await loadStatus(); scheduleStatus(); }, REC ? 2000 : 5000);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) { loadStatus(); scheduleStatus(); } });

$('#svcbtn').onclick = async () => {
  const b = $('#svcbtn'), act = b.dataset.act;
  if (act === 'stop' && !confirm('Arrêter l\'écoute ? Plus rien ne sera enregistré tant qu\'elle n\'est pas relancée (elle redémarre aussi au prochain démarrage du boîtier).')) return;
  b.disabled = true; b.textContent = act === 'stop' ? 'Arrêt…' : 'Démarrage…';
  try { await api('/api/service', {action: act}); toast(act === 'stop' ? 'Écoute arrêtée' : 'Écoute démarrée'); }
  catch (err) { alert('Impossible : ' + err.message); }
  b.disabled = false;
  await loadStatus(); setTimeout(loadStatus, 2500);
};
$('#refresh').onclick = () => { loadStatus(); refreshEvents(); };

/* ---------- panneau des réglages ---------- */
let DIRTY = false;
const drawerOpen = () => $('#drawer').classList.contains('open');
function openDrawer() {
  fillSettings();                                  // toujours repartir de la config en vigueur
  $('#cfgmsg').textContent = '';
  const d = $('#drawer');
  d.inert = false; d.classList.add('open');
  $('#backdrop').hidden = false;
  document.body.classList.add('noscroll');
  $('#gear').setAttribute('aria-expanded', 'true');
  d.querySelector('.drawer-body').scrollTop = 0;
  setTimeout(() => $('#drawer-close').focus(), 50);
}
function closeDrawer(force) {
  if (!drawerOpen()) return;
  if (!force && DIRTY && !confirm('Fermer sans enregistrer les modifications ?')) return;
  const d = $('#drawer');
  d.classList.remove('open'); d.inert = true;
  $('#backdrop').hidden = true;
  document.body.classList.remove('noscroll');
  $('#gear').setAttribute('aria-expanded', 'false');
  DIRTY = false;
  $('#gear').focus();
}
$('#gear').onclick = () => drawerOpen() ? closeDrawer() : openDrawer();
$('#drawer-close').onclick = () => closeDrawer();
$('#backdrop').onclick = () => closeDrawer();
document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && drawerOpen()) closeDrawer(); });
$('#cfgform').addEventListener('input', () => { DIRTY = true; });

$('#logout').onclick = async () => { try { await api('/api/logout', {}); } catch { /* déjà déconnecté */ } location.href = '/login'; };

/* ---------- mode test : scores en direct ---------- */
let LIVE = false, liveTimer = null, lastLogTs = 0, lastEpisode = false, liveCats = '';
function liveLog(text) {
  const box = $('#livelog'), line = document.createElement('div');
  line.textContent = new Date().toLocaleTimeString('fr-FR') + '  ' + text;
  box.prepend(line);
  while (box.children.length > 40) box.lastChild.remove();
}
const meterRow = (id, label, cls) => `<div class="lrow ${cls}" id="lr-${esc(id)}"><span>${esc(label)}</span><div class="meter"><div class="fill" id="lv-${esc(id)}" style="width:0"></div><div class="thr" id="lt-${esc(id)}"></div></div><span class="v" id="lvv-${esc(id)}">–</span></div>`;
function buildLiveRows(d) {
  const key = JSON.stringify([d.categories, d.parole_mode]);
  if (key === liveCats) return;
  liveCats = key;
  $('#liverows').innerHTML = meterRow('_niveau', 'Niveau', 'level')
    + d.categories.filter(c => c !== 'niveau').map(c => meterRow(c, catLabel(c), catCol(c))).join('')
    + (d.parole_mode !== 'desactive' ? meterRow('_parole', 'Voix (vie privée)', 'voice') : '');
  $('#lt-_niveau')?.remove();
}
const setMeter = (id, v, thr) => {
  const fill = document.getElementById('lv-' + id); if (!fill) return;
  fill.style.width = (Math.max(0, Math.min(1, v)) * 100) + '%';
  const t = document.getElementById('lt-' + id); if (t && thr != null) t.style.left = `calc(${thr * 100}% - 1px)`;
  document.getElementById('lr-' + id).classList.toggle('hit', thr != null && v >= thr);
};
async function livePoll() {
  if (!LIVE) return;
  try {
    const d = await api('/api/live');
    if (d.absent || d.age_s > 3) {
      $('#livestate').innerHTML = `<span class="dot bad"></span> Pas de données ${d.absent ? '' : `depuis ${fmtDur(d.age_s)}`} : l'écoute tourne-t-elle ?`;
    } else {
      buildLiveRows(d);
      setMeter('_niveau', (d.niveau_dBFS + 90) / 90, null);
      $('#lvv-_niveau').textContent = Math.round(d.niveau_dBFS);
      for (const c of d.categories.filter(c => c !== 'niveau')) {
        const v = d.scores?.[c] ?? 0;
        setMeter(c, v, d.seuils?.[c] ?? d.seuil);
        $('#lvv-' + c).textContent = v.toFixed(2);
      }
      if (d.parole_mode !== 'desactive' && $('#lr-_parole')) {
        setMeter('_parole', d.parole || 0, d.seuil_parole);
        $('#lvv-_parole').textContent = (d.parole || 0).toFixed(2);
      }
      $('#livestate').innerHTML = d.episode
        ? (d.episode_test ? `<span class="rec test">Son détecté · ${fmtDur(d.episode_s)} · non enregistré (test)</span>`
          : `<span class="rec">Enregistrement en cours · ${fmtDur(d.episode_s)}</span>`)
        : `<span class="dot ${d.test ? 'warn' : 'ok'}"></span> En écoute · seuil ${d.seuil}${d.test ? ' · enregistrement suspendu' : ''}`;
      $('#hears').innerHTML = (d.top?.length ? 'L\'IA entend surtout : ' + d.top.map(([l, v]) => `<b>${esc(l)}</b> ${Math.round(v * 100)} %`).join(' · ') : '')
        + (d.ignore >= 0.2 ? ` <span class="masked">· son à ignorer ${Math.round(d.ignore * 100)} % : détection annulée</span>` : '')
        + (d.parole_active && d.parole_mode === 'masquer' ? ' <span class="masked">· voix entendue : passage masqué</span>' : '');
      if (d.ts !== lastLogTs) {
        if (d.episode && !lastEpisode) liveLog('▶ début d\'épisode (avec les secondes précédentes)');
        if (d.detection?.length) liveLog(d.detection.map(c => `${catLabel(c)} ${(d.scores[c] ?? 1).toFixed(2)}`).join(' + '));
        if (!d.episode && lastEpisode) {
          if (d.dernier === 'ignore') liveLog('■ fin d\'épisode : écarté (trop court ou parole, voir les épisodes écartés)');
          else if (d.dernier === 'test' || d.test) liveLog('■ fin d\'épisode (test : non enregistré)');
          else { liveLog('■ fin d\'épisode, fichier enregistré'); setTimeout(refreshEvents, 1500); }
        }
        lastEpisode = d.episode; lastLogTs = d.ts;
      }
    }
  } catch (err) {
    $('#livestate').innerHTML = '<span class="dot bad"></span> Boîtier injoignable';
  }
  liveTimer = setTimeout(livePoll, 500);
}
// mode test sans enregistrement : bail de 5 min renouvelé toutes les 30 s tant que la page est ouverte
let testTimer = null;
const testExpired = () => { clearInterval(testTimer); testTimer = null; $('#nosave').checked = false; toast('Mode test limité à 30 min : enregistrement réactivé'); loadStatus(); };
async function setTestMode(on) {
  clearInterval(testTimer); testTimer = null;
  try {
    const r = await api('/api/testmode', {on});
    if (on && r.expire) return testExpired();
    if (on) testTimer = setInterval(async () => {
      const r2 = await api('/api/testmode', {on: true}).catch(() => ({}));
      if (r2.expire) testExpired();
    }, 30000);
  } catch (err) { if (on) toast('Impossible d\'activer le mode test : ' + err.message); }
  loadStatus();
}
function setLive(on) {
  LIVE = on; clearTimeout(liveTimer);
  $('#livepanel').classList.toggle('open', on);
  $('#livebtn').textContent = on ? 'Arrêter' : 'Démarrer';
  $('#livebtn').classList.toggle('on', on);
  setTestMode(on && $('#nosave').checked);
  if (on) livePoll(); else $('#livestate').textContent = 'Scores de l\'IA en direct, deux fois par seconde.';
}
$('#livebtn').onclick = () => setLive(!LIVE);
$('#nosave').onchange = () => { if (LIVE) setTestMode($('#nosave').checked); };
window.addEventListener('pagehide', () => {   // fermeture : on rend la main tout de suite (sinon le bail expire seul)
  if (testTimer) fetch('/api/testmode', {method: 'POST', keepalive: true, body: JSON.stringify({on: false}),
    headers: {'Content-Type': 'application/json', 'X-Requested-With': 'aboiements'}});
});
document.addEventListener('visibilitychange', () => { if (document.hidden && LIVE) clearTimeout(liveTimer); else if (LIVE) livePoll(); });

/* ---------- réglages ---------- */
const num = id => $('#cfg-' + id);
function syncRange(id) { const i = num(id); i.nextElementSibling.textContent = (+i.value).toFixed(2); }
function fillSettings() {
  const c = CONFIG;
  const groups = {};
  CATALOG.profils.filter(p => p.id !== 'niveau').forEach(p => (groups[p.groupe] ||= []).push(p));
  $('#cfg-profils').innerHTML = Object.entries(groups).map(([g, ps]) => `<div class="profgroup"><h4>${esc(g)}</h4>${ps.map(p => `
    <div class="profrow ${catCol(p.id)}">
      <label class="chk"><input type="checkbox" name="profil" value="${esc(p.id)}" ${c.profils.includes(p.id) ? 'checked' : ''}><i class="sw"></i>${esc(p.label)}</label>
      <input type="number" name="seuil_profil" data-id="${esc(p.id)}" min="0.05" max="0.95" step="0.05" placeholder="seuil" title="Seuil propre (facultatif)" value="${c.seuils_profils[p.id] ?? ''}">
    </div>`).join('')}</div>`).join('');
  $('#cfg-excl').innerHTML = CATALOG.exclusions.map(e =>
    `<label class="chk"><input type="checkbox" name="exclusion" value="${esc(e.id)}" ${c.exclusions.includes(e.id) ? 'checked' : ''}> ${esc(e.label)}</label>`).join('');
  $$('input[name=parole]').forEach(r => r.checked = r.value === c.parole);
  num('seuil_parole').value = c.seuil_parole; syncRange('seuil_parole');
  num('seuil').value = c.seuil; syncRange('seuil');
  num('min_detections').value = c.episodes.min_detections;
  num('seuil_niveau_dbfs').value = c.audio.seuil_niveau_dbfs ?? '';
  const mic = c.audio.micro, opts = [['', 'Par défaut (système)']];
  if (!MICROS.some(m => m.nom === 'default')) opts.push(['default', 'default (ALSA, conversion automatique)']);
  MICROS.forEach(m => opts.push([m.nom, `${m.nom} (${m.canaux} ${m.canaux > 1 ? 'canaux' : 'canal'}, ${m.frequence} Hz)`]));
  if (mic != null && !opts.some(([v]) => v === String(mic))) opts.push([String(mic), `${mic} (actuel, non détecté)`]);
  num('micro').innerHTML = opts.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
  num('micro').value = mic == null ? '' : String(mic);
  num('gain').value = c.audio.gain;
  num('coupe_bas_hz').value = String(c.audio.coupe_bas_hz);
  if (num('coupe_bas_hz').value !== String(c.audio.coupe_bas_hz)) {
    num('coupe_bas_hz').insertAdjacentHTML('beforeend', `<option value="${c.audio.coupe_bas_hz}">${c.audio.coupe_bas_hz} Hz</option>`);
    num('coupe_bas_hz').value = String(c.audio.coupe_bas_hz);
  }
  num('pre_s').value = c.episodes.pre_s; num('calme_s').value = c.episodes.calme_s; num('max_s').value = c.episodes.max_s;
  DIRTY = false;
}
function readSettings() {
  const seuils = {};
  $$('input[name=seuil_profil]').forEach(i => { if (i.value !== '') seuils[i.dataset.id] = +i.value; });
  const niveau = num('seuil_niveau_dbfs').value;
  return {
    profils: $$('input[name=profil]:checked').map(i => i.value),
    exclusions: $$('input[name=exclusion]:checked').map(i => i.value),
    seuil: +num('seuil').value, seuils_profils: seuils,
    parole: $('input[name=parole]:checked')?.value || 'masquer', seuil_parole: +num('seuil_parole').value,
    audio: {micro: num('micro').value === '' ? null : num('micro').value, gain: +num('gain').value,
      coupe_bas_hz: +num('coupe_bas_hz').value, seuil_niveau_dbfs: niveau === '' ? null : +niveau},
    episodes: {pre_s: +num('pre_s').value, calme_s: +num('calme_s').value, max_s: +num('max_s').value,
      min_detections: +num('min_detections').value},
  };
}
async function loadConfig() {
  const r = await api('/api/config');
  CONFIG = r.config; CATALOG = r.catalogue; MICROS = r.micros || [];
  $('#cfgid').textContent = `· ${r.id}`; $('#cfgid').title = 'Identifiant des réglages (noté dans le journal et l\'historique)';
  fillSettings();
}
['seuil', 'seuil_parole'].forEach(id => num(id).addEventListener('input', () => syncRange(id)));
$('#cfgreset').onclick = () => { fillSettings(); $('#cfgmsg').textContent = 'Modifications annulées.'; };
$('#cfgform').addEventListener('submit', async ev => {
  ev.preventDefault();
  const next = readSettings();
  if (next.parole === 'desactive' && CONFIG.parole !== 'desactive'
    && !confirm('Désactiver la protection de la parole ? Les conversations captées seront enregistrées telles quelles, ce qui peut être illégal.')) return;
  $('#cfgsave').disabled = true; $('#cfgmsg').textContent = 'Enregistrement…';
  try {
    const r = await api('/api/config', {config: next});
    CONFIG = r.config; CATALOG = r.catalogue; MICROS = r.micros || [];
    $('#cfgid').textContent = `· ${r.id}`; $('#cfgid').title = 'Identifiant des réglages (noté dans le journal et l\'historique)';
    fillSettings(); fillCategoryFilter(); liveCats = '';
    toast(r.modifications.length
      ? `Réglages enregistrés (${r.modifications.length} modification${r.modifications.length > 1 ? 's' : ''})${r.redemarrage ? ' : l\'écoute redémarre, environ 10 s' : ''}`
      : 'Aucun changement');
    render();
    closeDrawer(true);
  } catch (err) { $('#cfgmsg').textContent = 'Refusé : ' + err.message; }   // erreur : le panneau reste ouvert
  $('#cfgsave').disabled = false;
});
$('#pwform').addEventListener('submit', async ev => {
  ev.preventDefault();
  const msg = $('#pwmsg');
  if ($('#pw-new').value !== $('#pw-new2').value) { msg.textContent = 'Les deux saisies diffèrent.'; return; }
  try {
    await api('/api/password', {ancien: $('#pw-old').value, nouveau: $('#pw-new').value});
    ev.target.reset(); msg.textContent = 'Mot de passe changé (les autres appareils devront se reconnecter).';
  } catch (err) { msg.textContent = 'Refusé : ' + err.message; }
});

/* ---------- démarrage ---------- */
(async () => {
  try { await loadConfig(); } catch (err) { if (err.message === 'connexion requise') return; }
  loadStatus().then(scheduleStatus);
  loadEvents(true);
})();
