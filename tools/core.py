# -*- coding: utf-8 -*-
"""Motore comune: modello del caso, compilazione indizi, contatore di soluzioni
(backtracking esatto) e risolutore 'umano' per propagazione (difficolta' + spiegazione)."""
import re
from layouts import OBJ

COLS = 'ABCDEFGHI'
def cname(n, x): return f"{COLS[x % n]}{x // n + 1}"
def popc(m): return bin(m).count('1')
def bits(m):
    while m:
        b = m & -m
        yield b.bit_length() - 1
        m ^= b

# ---------- grammatica ----------
def gclass(key):
    name, g, _, _ = OBJ[key]
    if g == 'm' and re.match(r'^(s[^aeiou]|z|gn|ps)', name): return 'mz'
    return g
ART = {  # ind, def, a, di, su, nessun
 'm':  ('un ', 'il ', 'al ', 'del ', 'sul ', 'nessun '),
 'mz': ('uno ', 'lo ', 'allo ', 'dello ', 'sullo ', 'nessuno '),
 'ma': ('un ', "l'", "all'", "dell'", "sull'", 'nessun '),
 'f':  ('una ', 'la ', 'alla ', 'della ', 'sulla ', 'nessuna '),
 'fa': ("un'", "l'", "all'", "dell'", "sull'", "nessun'"),
}
SEAT = {'sedia', 'poltrona', 'trono', 'sdraio', 'divano'}

class Case:
    def __init__(self, d):
        self.d = d
        self.n = n = len(d['grid'])
        self.room_of = []
        self.room_keys = list(d['rooms'].keys())
        for r in range(n):
            for c in range(n):
                self.room_of.append(self.room_keys.index(d['grid'][r][c]))
        self.obj = {}  # cell -> type
        for r in range(n):
            for c in range(n):
                ch = d['objs'][r][c]
                if ch != '.': self.obj[r * n + c] = d['omap'][ch]
        self.cells = n * n
        self.full = (1 << self.cells) - 1
        self.rowm = [sum(1 << (r * n + c) for c in range(n)) for r in range(n)]
        self.colm = [sum(1 << (r * n + c) for r in range(n)) for c in range(n)]
        self.roomm = [sum(1 << x for x in range(self.cells) if self.room_of[x] == k) for k in range(len(self.room_keys))]
        self.typem = {}
        for x, t in self.obj.items(): self.typem[t] = self.typem.get(t, 0) | (1 << x)
        self.block = sum(1 << x for x, t in self.obj.items() if OBJ[t][3])
        self.free = self.full & ~self.block
        self.people = [p[2] for p in d['people']] + [d['victim'][2]]
        self.pinfo = {p[2]: p for p in d['people'] + [d['victim']]}
        self.victim = d['victim'][2]
        self.np = len(self.people)
        assert self.np == n, (d['id'], self.np, n)
    def rc(self, x): return divmod(x, self.n)
    def nbrs(self, x):
        r, c = self.rc(x); n = self.n; out = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < n and 0 <= cc < n: out.append(rr * n + cc)
        return out
    # forme linguistiche per gli oggetti
    def unique(self, t): return popc(self.typem[t]) == 1
    def art(self, t, which):
        g = gclass(t); name = OBJ[t][0]
        i = {'ind': 0, 'def': 1, 'a': 2, 'di': 3, 'su': 4, 'nes': 5}[which]
        return ART[g][i] + name
    def o_a(self, t):   # "al forno" / "a un letto"
        return self.art(t, 'a') if self.unique(t) else 'a ' + self.art(t, 'ind')
    def o_di(self, t):  # "del forno" / "di un letto"
        return self.art(t, 'di') if self.unique(t) else 'di ' + self.art(t, 'ind')
    def o_su(self, t):
        return self.art(t, 'su') if self.unique(t) else 'su ' + self.art(t, 'ind')
    def o_bare(self, t):  # "il forno" / "un letto"
        return self.art(t, 'def') if self.unique(t) else self.art(t, 'ind')
    def on_phrase(self, t, g):
        if t in SEAT: return ('seduto ' if g == 'm' else 'seduta ') + self.o_su(t)
        return self.o_su(t)
    def room_in(self, k): return self.d['rooms'][self.room_keys[k]][1]
    def pname(self, p): return self.pinfo[p][0]

# ---------- indizi ----------
# Un indizio: dict(kind, who, text, unary={p: mask}, binary=[(p,q,fn)], glob=[name])

def compile_clues(case, clues):
    dom = {p: case.free for p in case.people}
    bins = []; globs = set()
    for cl in clues:
        for p, m in cl.get('unary', {}).items(): dom[p] &= m
        bins += cl.get('binary', [])
        globs |= set(cl.get('glob', []))
    # tabelle di compatibilita' per i vincoli binari
    btab = []
    for (p, q, fn) in bins:
        pq = [0] * case.cells; qp = [0] * case.cells
        for a in range(case.cells):
            for b in range(case.cells):
                if a != b and fn(a, b):
                    pq[b] |= 1 << a   # celle possibili di p dato q in b
                    qp[a] |= 1 << b
        btab.append((p, q, pq, qp))
    return dom, btab, globs

def count_solutions(case, clues, cap=2, collect=False, node_limit=None):
    dom0, btab, globs = compile_clues(case, clues)
    P = case.people; idx = {p: i for i, p in enumerate(P)}
    n = case.n; V = idx[case.victim]
    by = [[] for _ in P]
    for (p, q, pq, qp) in btab:
        by[idx[p]].append((idx[q], pq)); by[idx[q]].append((idx[p], qp))
    dom = [dom0[p] for p in P]
    pos = [-1] * len(P)
    sols = []; nodes = [0]
    rowofcell = [x // n for x in range(case.cells)]; colofcell = [x % n for x in range(case.cells)]
    roommasks = case.roomm; room_of = case.room_of
    noempty = 'noempty' in globs
    def avail(i, used):
        m = dom[i] & ~used
        for (j, tab) in by[i]:
            if pos[j] >= 0: m &= tab[pos[j]]
        return m
    def rec(used, nplaced):
        nodes[0] += 1
        if node_limit and nodes[0] > node_limit: raise TimeoutError()
        if len(sols) >= cap: return
        if nplaced == len(P):
            # vincolo vittima: esattamente 2 persone nella stanza della vittima
            vr = room_of[pos[V]]
            if sum(1 for x in pos if room_of[x] == vr) != 2: return
            if noempty:
                occ = {room_of[x] for x in pos}
                if len(occ) != len(roommasks): return
            sols.append(tuple(pos)); return
        excl = 0
        if pos[V] >= 0:
            vr = room_of[pos[V]]
            cnt = sum(1 for x in pos if x >= 0 and room_of[x] == vr)
            if cnt > 2: return
            if cnt == 2: excl = roommasks[vr]
        best = -1; bm = 0; bc = 999; union = 0
        for i in range(len(P)):
            if pos[i] >= 0: continue
            m = avail(i, used)
            if i != V: m &= ~excl
            c = popc(m)
            if c == 0: return
            union |= m
            if c < bc: bc, best, bm = c, i, m
        # ogni riga e colonna libera deve essere raggiungibile
        for r in range(n):
            if not (used & case.rowm[r]) and not (union & case.rowm[r]): return
        for c in range(n):
            if not (used & case.colm[c]) and not (union & case.colm[c]): return
        if noempty:
            for k, rm in enumerate(roommasks):
                if not any(pos[j] >= 0 and room_of[pos[j]] == k for j in range(len(P))) and not (union & rm): return
        for x in bits(bm):
            pos[best] = x
            rec(used | case.rowm[rowofcell[x]] | case.colm[colofcell[x]], nplaced + 1)
            pos[best] = -1
            if len(sols) >= cap: return
    rec(0, 0)
    return sols, nodes[0]

# ---------- risolutore per propagazione ----------
class Contradiction(Exception): pass

def human_solve(case, clues, want_log=True):
    """Ritorna (pos|False, stats, log). Regole 'umane': righe/colonne occupate, unica casella,
    unico candidato per riga/colonna, indizi relativi, regola della vittima, stanze non vuote.
    Se le regole non bastano: ipotesi (ragionamento per esclusione)."""
    dom0, btab, globs = compile_clues(case, clues)
    P = case.people; n = case.n; V = case.victim
    stats = {'hidden': 0, 'binary': 0, 'victim': 0, 'noempty': 0, 'hypotheses': 0, 'branch_nodes': 0}
    def g(p): return case.pinfo[p][1]
    def propagate(dom, log, ann):
        def note(q, why):
            if log is not None and q not in ann and popc(dom[q]) == 1:
                ann.add(q); log.append(f"{case.pname(q)} → {cname(n, next(bits(dom[q])))}: {why}.")
        def setd(q, nd, why, key=None):
            if nd == dom[q]: return False
            if nd == 0: raise Contradiction()
            dom[q] = nd
            if key: stats[key] += 1
            note(q, why); return True
        for q in P: note(q, "il suo indizio lascia una sola casella possibile")
        changed = True
        while changed:
            changed = False
            for p in P:
                if popc(dom[p]) != 1: continue
                x = next(bits(dom[p])); r, c = case.rc(x); kill = case.rowm[r] | case.colm[c]
                for q in P:
                    if q != p and dom[q] & kill:
                        changed |= setd(q, dom[q] & ~kill, "è l'unica casella compatibile con il suo indizio, escluse righe e colonne già occupate")
            if changed: continue
            for (p, q, pq, qp) in btab:
                for a, b, tab in ((p, q, pq), (q, p, qp)):
                    sup = 0
                    for y in bits(dom[b]):
                        rr, cc = case.rc(y)
                        sup |= tab[y] & ~(case.rowm[rr] | case.colm[cc])
                    changed |= setd(a, dom[a] & sup, f"è l'unica casella coerente con l'indizio che lo lega a {case.pname(b)}" if g(a)=='m' else f"è l'unica casella coerente con l'indizio che la lega a {case.pname(b)}", 'binary')
            if changed: continue
            vrooms = {case.room_of[x] for x in bits(dom[V])}
            if len(vrooms) == 1:
                vr = next(iter(vrooms)); rm = case.roomm[vr]
                inside = [q for q in P if q != V and popc(dom[q]) == 1 and dom[q] & rm]
                can = [q for q in P if q != V and dom[q] & rm]
                if len(inside) > 1 or not can: raise Contradiction()
                if inside:
                    for q in P:
                        if q != V and q not in inside and dom[q] & rm:
                            changed |= setd(q, dom[q] & ~rm, f"la vittima era sola con l'assassino, quindi nessun altro poteva essere {case.room_in(vr)}", 'victim')
                elif len(can) == 1:
                    changed |= setd(can[0], dom[can[0]] & rm, f"è l'unica persona che poteva trovarsi {case.room_in(vr)} con la vittima", 'victim')
            if changed: continue
            for lines, label in ((case.rowm, 'riga'), (case.colm, 'colonna')):
                for li, lm in enumerate(lines):
                    who = [q for q in P if dom[q] & lm]
                    if not who: raise Contradiction()
                    if len(who) == 1:
                        lab = str(li + 1) if label == 'riga' else COLS[li]
                        changed |= setd(who[0], dom[who[0]] & lm, f"nessun altro poteva occupare la {label} {lab}", 'hidden')
            if changed: continue
            if 'noempty' in globs:
                for k, rm in enumerate(case.roomm):
                    can = [q for q in P if dom[q] & rm]
                    if not can: raise Contradiction()
                    if len(can) == 1:
                        changed |= setd(can[0], dom[can[0]] & rm, f"non c'erano stanze vuote e solo {'lui' if g(can[0])=='m' else 'lei'} poteva essere {case.room_in(k)}", 'noempty')
        return dom
    def final_check(dom):
        pos = {p: next(bits(m)) for p, m in dom.items()}
        vr = case.room_of[pos[V]]
        if sum(1 for x in pos.values() if case.room_of[x] == vr) != 2: raise Contradiction()
        if 'noempty' in globs and len({case.room_of[x] for x in pos.values()}) != len(case.roomm): raise Contradiction()
    def solve(dom, log, ann):
        stats['branch_nodes'] += 1
        dom = propagate(dom, log, ann)
        if all(popc(m) == 1 for m in dom.values()):
            final_check(dom); return dom
        stats['hypotheses'] += 1 if log is not None else 0
        cand = min((p for p in P if popc(dom[p]) > 1), key=lambda p: (popc(dom[p]), P.index(p)))
        good = None; bad = []
        for x in bits(dom[cand]):
            d2 = dict(dom); d2[cand] = 1 << x
            try:
                solve(d2, None, set())
                if good is None: good = x
                else: raise RuntimeError('non unico')
            except Contradiction:
                bad.append(x)
        if good is None: raise Contradiction()
        d2 = dict(dom); d2[cand] = 1 << good
        if log is not None:
            log.append(f"{case.pname(cand)} → {cname(n, good)}: per esclusione. Provando " + ', '.join(cname(n, x) for x in bad) + " gli indizi portano a una contraddizione.")
            ann.add(cand)
        return solve(d2, log, ann)
    log = [] if want_log else None
    try:
        res = solve({p: dom0[p] for p in P}, log, set())
    except Contradiction:
        return False, stats, log
    return {p: next(bits(m)) for p, m in res.items()}, stats, log
