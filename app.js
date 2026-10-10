/* Delitto in Griglia — PWA vanilla JS */
(() => {
'use strict';
const PUZ = window.PUZZLES;
const LEVELS = [
  {id: 'facile', name: 'Facile', icon: '🔍', meta: 'Griglie 5×5 e 6×6, indizi diretti'},
  {id: 'medio', name: 'Medio', icon: '🕵️', meta: 'Griglie 6×6 e 7×7, indizi incrociati'},
  {id: 'difficile', name: 'Difficile', icon: '🗝️', meta: 'Griglie 8×8 e 9×9, indizi negativi e relativi'},
];
const COLS = 'ABCDEFGHI';
const LS = {
  get(k, d) { try { const v = localStorage.getItem('dig.' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('dig.' + k, JSON.stringify(v)); } catch (e) {} },
  del(k) { try { localStorage.removeItem('dig.' + k); } catch (e) {} },
};
const $ = s => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const fmt = s => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
function toast(msg, ms = 2200) { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), ms); }
function avatar(p, extra = '') { return `<div class="person ${p.victim ? 'victim' : ''} ${extra}" style="background:${p.color}">${esc(p.id)}</div>`; }

/* ---------- HOME ---------- */
function progress() { return LS.get('progress', {}); }
function renderHome() {
  const prog = progress(); const box = $('#levels'); box.innerHTML = '';
  let tot = 0;
  for (const L of LEVELS) {
    const list = PUZ.filter(p => p.level === L.id);
    const solved = list.filter(p => prog[p.id] && prog[p.id].solved).length; tot += solved;
    const bests = list.map(p => prog[p.id] && prog[p.id].best).filter(Boolean);
    const b = el('button', 'level l-' + L.id);
    b.innerHTML = `<div class="badge">${L.icon}</div>
      <div><div class="lv-name">${L.name}</div><div class="lv-meta">${L.meta}</div>
      ${bests.length ? `<div class="lv-meta">Miglior tempo: ${fmt(Math.min(...bests))}</div>` : ''}</div>
      <div class="lv-prog"><b>${solved}/${list.length}</b>risolti<div class="dots">${list.map(p => `<i class="${prog[p.id] && prog[p.id].solved ? 'on' : ''}"></i>`).join('')}</div></div>`;
    b.onclick = () => openRandom(L.id);
    box.appendChild(b);
  }
  $('#totalSolved').textContent = `${tot}/${PUZ.length} casi risolti`;
}
function openRandom(level) {
  const list = PUZ.filter(p => p.level === level);
  const last = LS.get('last.' + level, null);
  let pool = list.filter(p => p.id !== last);
  if (!pool.length) pool = list;
  const pz = pool[Math.floor(Math.random() * pool.length)];
  LS.set('last.' + level, pz.id);
  openPuzzle(pz.id);
}
function show(id) { document.querySelectorAll('.screen').forEach(s => s.classList.toggle('active', s.id === id)); }

/* ---------- GIOCO ---------- */
let G = null; // stato corrente
function emptyCells(n) { return Array.from({length: n * n}, () => ({p: null, notes: [], x: false})); }
function openPuzzle(id) {
  const pz = PUZ.find(p => p.id === id); if (!pz) return;
  const saved = LS.get('state.' + id, null);
  G = {pz, n: pz.size, cells: saved ? saved.cells : emptyCells(pz.size), used: saved ? saved.used : {}, hints: saved ? saved.hints : [],
       elapsed: saved ? saved.elapsed : 0, start: performance.now(), sel: pz.people[0].id, mode: 'place', undo: [], redo: [], done: false};
  const lv = LEVELS.find(l => l.id === pz.level);
  $('#gKicker').textContent = `${lv.name.toUpperCase()} · ${pz.setting.toUpperCase()} · ${pz.size}×${pz.size}`;
  $('#gTitle').textContent = pz.title;
  $('#gIntro').textContent = pz.intro;
  $('#story').open = !saved;
  setMode('place');
  buildBoard(); renderAll(); show('game');
  $('#game .scroll').scrollTop = 0;
  startTimer();
  history.pushState({g: id}, '', '#' + id);
}
function save() { if (!G || G.done) return; LS.set('state.' + G.pz.id, {cells: G.cells, used: G.used, hints: G.hints, elapsed: elapsedNow()}); }
function elapsedNow() { return G.elapsed + (G.running ? (performance.now() - G.start) / 1000 : 0); }
let tick = null;
function startTimer() { G.running = true; G.start = performance.now(); clearInterval(tick); tick = setInterval(() => { $('#timer').textContent = fmt(elapsedNow()); }, 500); $('#timer').textContent = fmt(elapsedNow()); }
function pauseTimer() { if (G && G.running) { G.elapsed = elapsedNow(); G.running = false; } clearInterval(tick); }
document.addEventListener('visibilitychange', () => { if (!G || G.done || !$('#game').classList.contains('active')) return; if (document.hidden) { pauseTimer(); save(); } else startTimer(); });

function person(id) { return G.pz.people.find(p => p.id === id); }
function cellOf(pid) { return G.cells.findIndex(c => c.p === pid); }
function objAt(r, c) { return G.pz.objects.find(o => o.r === r && o.c === c); }
function isBlocking(i) { const o = objAt(Math.floor(i / G.n), i % G.n); return !!(o && G.pz.objectTypes[o.type].blocking); }

function buildBoard() {
  const n = G.n, pz = G.pz, board = $('#board');
  const avail = Math.min(window.innerWidth, 520) - 28 - 18;
  const cs = Math.floor(Math.min(56, avail / n));
  board.style.setProperty('--cs', cs + 'px');
  board.style.gridTemplateColumns = `18px repeat(${n}, ${cs}px)`;
  board.style.gridTemplateRows = `18px repeat(${n}, ${cs}px)`;
  board.innerHTML = '';
  board.appendChild(el('div', 'lab'));
  for (let c = 0; c < n; c++) board.appendChild(el('div', 'lab', COLS[c]));
  const room = (r, c) => (r < 0 || c < 0 || r >= n || c >= n) ? -1 : pz.grid[r][c];
  for (let r = 0; r < n; r++) {
    board.appendChild(el('div', 'lab', r + 1));
    for (let c = 0; c < n; c++) {
      const i = r * n + c, k = pz.grid[r][c];
      const d = el('div', 'cell');
      d.dataset.i = i;
      d.style.backgroundColor = pz.rooms[k].color;
      if (room(r - 1, c) !== k) d.classList.add('bt');
      if (room(r + 1, c) !== k) d.classList.add('bb');
      if (room(r, c - 1) !== k) d.classList.add('bl');
      if (room(r, c + 1) !== k) d.classList.add('br');
      const o = objAt(r, c);
      if (o) {
        const t = pz.objectTypes[o.type];
        d.classList.add(t.blocking ? 'blocking' : 'occ');
        if (o.type === 'tappeto') d.classList.add('carpet');
        d.title = t.name + (t.blocking ? '' : ' (ci si può stare)');
        d.appendChild(el('span', 'obj', t.emoji));
      }
      d.appendChild(el('div', 'content'));
      attachCell(d, i);
      board.appendChild(d);
    }
  }
  // legenda stanze e oggetti
  const leg = $('#roomLegend'); leg.innerHTML = '';
  pz.rooms.forEach(rm => leg.appendChild(el('span', '', `<i style="background:${rm.color}"></i>${esc(rm.name)}`)));
  const seen = {};
  pz.objects.forEach(o => { if (seen[o.type]) return; seen[o.type] = 1; const t = pz.objectTypes[o.type];
    leg.appendChild(el('span', '', `${o.type === 'tappeto' ? '<i style="background:repeating-linear-gradient(45deg,#c99 0 3px,#eed 3px 6px)"></i>' : t.emoji} ${esc(t.name)}${t.blocking ? '' : ' <em>(occupabile)</em>'}`)); });
}

function attachCell(d, i) {
  let lp = null, longDone = false;
  d.addEventListener('pointerdown', e => { longDone = false; clearTimeout(lp); lp = setTimeout(() => { longDone = true; clearCell(i, true); if (navigator.vibrate) navigator.vibrate(15); }, 480); });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev => d.addEventListener(ev, () => clearTimeout(lp)));
  d.addEventListener('contextmenu', e => e.preventDefault());
  d.addEventListener('click', () => { if (longDone) { longDone = false; return; } tapCell(i); });
}
function snapshot() { G.undo.push(JSON.stringify(G.cells)); if (G.undo.length > 200) G.undo.shift(); G.redo = []; }
function clearCell(i, viaLong) {
  const c = G.cells[i]; if (!c.p && !c.notes.length && !c.x) return;
  snapshot(); G.cells[i] = {p: null, notes: [], x: false}; afterChange(); if (viaLong) toast('Casella cancellata');
}
function tapCell(i) {
  if (G.done) return;
  const c = G.cells[i], mode = G.mode, sel = G.sel;
  if (mode === 'erase') return clearCell(i);
  if (isBlocking(i)) { flash(i); toast('Qui c\'è un oggetto: nessuno può starci'); return; }
  snapshot();
  if (mode === 'cross') { c.x = !c.x; if (c.x) c.p = null; }
  else if (mode === 'note') {
    if (c.p) { G.undo.pop(); toast('La casella è già occupata'); return; }
    const k = c.notes.indexOf(sel); if (k >= 0) c.notes.splice(k, 1); else { c.notes.push(sel); c.x = false; }
  } else { // posiziona
    if (c.p === sel) { c.p = null; }
    else {
      const prev = cellOf(sel); if (prev >= 0) G.cells[prev].p = null;
      c.p = sel; c.x = false; c.notes = [];
      G.hints = G.hints.filter(h => h !== sel);
      // passa automaticamente alla prossima persona non ancora posizionata
      const next = G.pz.people.find(p => cellOf(p.id) < 0);
      if (next) G.sel = next.id;
    }
  }
  afterChange();
}
function flash(i) { const d = document.querySelector(`.cell[data-i="${i}"]`); d.classList.remove('flash'); void d.offsetWidth; d.classList.add('flash'); }
function afterChange() { renderAll(); save(); }
function setMode(m) { G && (G.mode = m); document.querySelectorAll('.mode').forEach(b => b.classList.toggle('active', b.dataset.mode === m)); }

function renderAll() { renderCells(); renderPalette(); renderClues(); $('#btnUndo').disabled = !G.undo.length; $('#btnRedo').disabled = !G.redo.length;
  $('#hintLine').textContent = G.hints.length ? `Aiuti usati: ${G.hints.length}` : ''; }
function renderCells() {
  const n = G.n; const occRows = new Set(), occCols = new Set();
  G.cells.forEach((c, i) => { if (c.p) { occRows.add(Math.floor(i / n)); occCols.add(i % n); } });
  document.querySelectorAll('.cell').forEach(d => {
    const i = +d.dataset.i, c = G.cells[i], box = d.querySelector('.content');
    let h = '';
    if (c.p) h = avatar(person(c.p), G.hints.includes(c.p) ? 'hinted' : '');
    else {
      if (c.notes.length) h += `<div class="notes">${c.notes.map(id => `<span style="color:${person(id).color}">${esc(id)}</span>`).join('')}</div>`;
      if (c.x) h += '<div class="xmark">✕</div>';
    }
    box.innerHTML = h;
    d.classList.toggle('rowcol', !c.p && !isBlocking(i) && (occRows.has(Math.floor(i / n)) || occCols.has(i % n)));
  });
}
function renderPalette() {
  const pal = $('#palette'); pal.innerHTML = '';
  const np = G.pz.people.length, w = pal.clientWidth || (Math.min(window.innerWidth, 520) - 50);
  pal.style.gridTemplateColumns = `repeat(${np}, minmax(0, 1fr))`;
  pal.style.setProperty('--pcs', Math.max(30, Math.min(46, Math.floor(w / np) - 6)) + 'px');
  G.pz.people.forEach(p => {
    const b = el('button', 'pal' + (G.sel === p.id ? ' sel' : '') + (cellOf(p.id) >= 0 ? ' done' : ''));
    b.innerHTML = avatar(p) + `<small>${esc(p.name)}</small>`;
    b.setAttribute('aria-label', p.name);
    b.onclick = () => { G.sel = p.id; if (G.mode === 'cross' || G.mode === 'erase') setMode('place'); renderPalette(); };
    pal.appendChild(b);
  });
}
function renderClues() {
  const ul = $('#clues'); ul.innerHTML = '';
  G.pz.people.forEach(p => {
    const li = el('li', 'clue' + (p.victim ? ' victim' : '') + (G.used[p.id] ? ' used' : ''));
    li.innerHTML = avatar(p) + `<div class="ct"><b>${esc(p.name)}${p.victim ? ' · vittima' : ''}</b><span>${esc(p.clue)}</span></div>`;
    li.onclick = () => { G.used[p.id] = !G.used[p.id]; renderClues(); save(); };
    ul.appendChild(li);
  });
  const ex = $('#extra'); ex.innerHTML = '';
  G.pz.extraClues.forEach((t, k) => {
    const key = 'x' + k;
    const li = el('li', 'clue' + (G.used[key] ? ' used' : ''));
    li.innerHTML = `<div class="mag">🔎</div><div class="ct"><b>Indizio generale</b><span>${esc(t)}</span></div>`;
    li.onclick = () => { G.used[key] = !G.used[key]; renderClues(); save(); };
    ex.appendChild(li);
  });
}

/* ---------- azioni ---------- */
document.querySelectorAll('.mode').forEach(b => b.onclick = () => setMode(b.dataset.mode));
$('#btnUndo').onclick = () => { if (!G.undo.length) return; G.redo.push(JSON.stringify(G.cells)); G.cells = JSON.parse(G.undo.pop()); afterChange(); };
$('#btnRedo').onclick = () => { if (!G.redo.length) return; G.undo.push(JSON.stringify(G.cells)); G.cells = JSON.parse(G.redo.pop()); afterChange(); };
$('#btnReset').onclick = () => modal(`<h2>Ricominciare?</h2><p>Cancello tutte le persone, gli appunti e le esclusioni di questo caso. Il tempo riparte da zero.</p>
  <div class="row"><button class="sec-btn" data-act="close">Annulla</button><button class="primary" data-act="reset">Reset</button></div>`, {
    reset: () => { G.cells = emptyCells(G.n); G.used = {}; G.hints = []; G.undo = []; G.redo = []; G.elapsed = 0; startTimer(); closeModal(); afterChange(); } });
$('#btnHint').onclick = () => {
  const pz = G.pz, n = G.n;
  const wrong = pz.people.filter(p => { const [r, c] = pz.solution[p.id]; return cellOf(p.id) !== r * n + c; });
  if (!wrong.length) { toast('Sono già tutti al posto giusto!'); return; }
  const p = wrong[Math.floor(Math.random() * wrong.length)];
  const [r, c] = pz.solution[p.id], i = r * n + c;
  snapshot();
  const prev = cellOf(p.id); if (prev >= 0) G.cells[prev].p = null;
  // chi occupava quella casella torna in panchina
  G.cells[i] = {p: p.id, notes: [], x: false};
  if (!G.hints.includes(p.id)) G.hints.push(p.id);
  afterChange(); flash(i);
  toast(`${p.name} era in ${COLS[c]}${r + 1}`);
};
$('#btnCheck').onclick = () => {
  const pz = G.pz, n = G.n;
  const missing = pz.people.filter(p => cellOf(p.id) < 0);
  if (missing.length) { toast(`Mancano ancora ${missing.length === 1 ? '1 persona' : missing.length + ' persone'} sulla mappa`); return; }
  // regole di base
  const rows = new Set(), cols = new Set();
  pz.people.forEach(p => { const i = cellOf(p.id); rows.add(Math.floor(i / n)); cols.add(i % n); });
  if (rows.size < n || cols.size < n) { toast('Attenzione: deve esserci una sola persona per riga e per colonna'); return; }
  const wrong = pz.people.filter(p => { const [r, c] = pz.solution[p.id]; return cellOf(p.id) !== r * n + c; });
  if (wrong.length) {
    G.fails = (G.fails || 0) + 1;
    modal(`<h2>Qualcosa non torna</h2><p>${wrong.length === 1 ? 'Una persona non è' : wrong.length + ' persone non sono'} nel posto giusto. Rileggi gli indizi: sono tutti veri.</p>
      <div class="row"><button class="primary" data-act="close">Torna al caso</button></div>`); return;
  }
  const sus = pz.people.filter(p => !p.victim);
  modal(`<h2>Il colpevole è…</h2><p>La mappa è corretta. Chi era solo con ${esc(pz.people.find(p => p.victim).name)}?</p>
    <div class="accuse">${sus.map(p => `<button data-act="acc" data-id="${p.id}">${avatar(p)}${esc(p.name)}</button>`).join('')}</div>`, {
    acc: (b) => { if (b.dataset.id === pz.culprit) win(); else { toast(`${person(b.dataset.id).name} non era nella stanza della vittima`); } } });
};
function win() {
  const pz = G.pz; pauseTimer(); G.done = true;
  const t = G.elapsed; const prog = progress(); const prev = prog[pz.id] || {};
  const best = prev.best ? Math.min(prev.best, t) : t; const record = !prev.best || t < prev.best;
  prog[pz.id] = {solved: true, best, hints: Math.min(prev.hints == null ? 99 : prev.hints, G.hints.length), last: Date.now()};
  LS.set('progress', prog); LS.del('state.' + pz.id);
  const c = person(pz.culprit), v = pz.people.find(p => p.victim);
  modal(`<div class="win-head"><div class="stamp">CASO CHIUSO</div>
    <h2>${esc(c.name)} è ${c.gender === 'f' ? 'la colpevole' : 'il colpevole'}!</h2>
    <div class="mini">${avatar(c)}</div>
    <div class="stats"><div><b>${fmt(t)}</b>tempo</div><div><b>${fmt(best)}</b>${record ? 'nuovo record' : 'record'}</div><div><b>${G.hints.length}</b>aiuti</div></div></div>
    <h3 class="sec">La soluzione</h3>
    <ol class="expl">${pz.explanation.map(s => `<li>${esc(s)}</li>`).join('')}</ol>
    <div class="row"><button class="sec-btn" data-act="home">Livelli</button><button class="primary" data-act="again">Nuovo caso ${esc(LEVELS.find(l => l.id === pz.level).name.toLowerCase())}</button></div>`, {
      home: () => { closeModal(); goHome(); },
      again: () => { closeModal(); openRandom(pz.level); } });
}

/* ---------- modale ---------- */
function modal(html, acts = {}) {
  const m = $('#modal'); $('#modalBody').innerHTML = html; m.classList.remove('hidden');
  m.querySelectorAll('[data-act]').forEach(b => b.onclick = () => { const a = b.dataset.act; if (a === 'close') closeModal(); else acts[a] && acts[a](b); });
}
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal' && !(G && G.done)) closeModal(); });

function goHome() { if (G) { pauseTimer(); save(); } G = null; renderHome(); show('home'); if (location.hash) history.replaceState(null, '', location.pathname + location.search); }
$('#btnBack').onclick = () => goHome();
window.addEventListener('popstate', () => { if ($('#game').classList.contains('active')) { closeModal(); goHome(); } });
$('#btnRules').onclick = () => modal(`<h2>Come si gioca</h2><ul>
  <li>Sulla mappa ci sono le stanze (bordi spessi) e alcuni oggetti.</li>
  <li>Ogni riga e ogni colonna contiene <b>esattamente una persona</b>, vittima compresa.</li>
  <li>Sulle caselle con oggetti come tavoli, piante o TV non può stare nessuno. Su letti, sedie, poltrone, divani e tappeti invece sì.</li>
  <li>"Accanto" significa che le caselle condividono un lato. Righe numerate dall'alto (1, 2, 3…), colonne con lettere da sinistra (A, B, C…).</li>
  <li>Tutti gli indizi sono veri. La vittima era sola con l'assassino: il colpevole è l'unica altra persona nella stanza della vittima.</li>
  <li>Ogni caso ha una sola soluzione, verificata.</li></ul>
  <h3 class="sec">Prendere appunti</h3><ul>
  <li><b>👤 Posiziona</b>: scegli una persona in basso e tocca la casella.</li>
  <li><b>✏️ Appunti</b>: segna in piccolo i possibili candidati (anche più iniziali per casella).</li>
  <li><b>✕ Escludi</b>: barra le caselle dove non può esserci nessuno.</li>
  <li><b>🧽 Gomma</b> o <b>pressione prolungata</b>: svuota la casella. Annulla e Ripeti tornano indietro e avanti.</li></ul>
  <div class="row"><button class="primary" data-act="close">Ho capito</button></div>`);

window.addEventListener('resize', () => { if (G) { buildBoard(); renderAll(); } });

/* ---------- avvio ---------- */
renderHome();
const qs = new URLSearchParams(location.search);
const startId = qs.get('caso') || (location.hash ? location.hash.slice(1) : null);
if (startId && PUZ.find(p => p.id === startId)) openPuzzle(startId);
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});
window.__dig = {openPuzzle, tapCell, setMode: m => setMode(m), select: id => { G.sel = id; renderPalette(); }, state: () => G};
})();
