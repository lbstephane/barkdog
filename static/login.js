'use strict';
const form = document.getElementById('loginform'), msg = document.getElementById('msg'), go = document.getElementById('go');
fetch('/api/session').then(r => r.json()).then(s => {
  if (s.connecte) location.replace('/');
  else if (!s.mot_de_passe_defini) {
    msg.textContent = 'Aucun mot de passe défini : sur le boîtier, lancer « python3 auth.py --set » (ou relancer install.sh).';
    go.disabled = true;
  }
}).catch(() => {});
form.addEventListener('submit', async ev => {
  ev.preventDefault();
  go.disabled = true; msg.textContent = '';
  try {
    const r = await fetch('/api/login', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'barkdog'},
      body: JSON.stringify({mot_de_passe: document.getElementById('pw').value}),
    });
    if (r.ok) { location.replace('/'); return; }
    const d = await r.json().catch(() => ({}));
    msg.textContent = d.erreur || 'Connexion impossible';
  } catch { msg.textContent = 'Boîtier injoignable'; }
  go.disabled = false;
});
