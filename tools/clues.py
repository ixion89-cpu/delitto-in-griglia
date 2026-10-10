# -*- coding: utf-8 -*-
"""Generazione del pool di indizi veri per una soluzione data."""
from core import COLS, popc, bits, OBJ

def pool_for(case, sol):
    """sol: dict persona->cella. Ritorna dict persona -> lista di indizi (dict con 'cat')."""
    n = case.n; P = case.people; out = {p: [] for p in P}
    occ_cells = set(sol.values())
    def add(p, cat, text, unary=None, binary=None, glob=None, spec=None):
        assert spec is not None, text
        cl = dict(cat=cat, who=p, text=text, spec=spec)
        if unary: cl['unary'] = unary
        if binary: cl['binary'] = binary
        if glob: cl['glob'] = glob
        out[p].append(cl)
    types = list(case.typem.keys())
    adjm = {t: sum(1 << x for x in range(case.cells) if any((1 << y) & case.typem[t] for y in case.nbrs(x))) for t in types}
    def dirm(t, dr, dc):  # celle la cui vicina (dr,dc) e' di tipo t
        m = 0
        for x in range(case.cells):
            r, c = case.rc(x); rr, cc = r + dr, c + dc
            if 0 <= rr < n and 0 <= cc < n and case.typem[t] >> (rr * n + cc) & 1: m |= 1 << x
        return m
    rowT = {t: sum(case.rowm[r] for r in range(n) if case.typem[t] & case.rowm[r]) for t in types}
    colT = {t: sum(case.colm[c] for c in range(n) if case.typem[t] & case.colm[c]) for t in types}
    edge = case.rowm[0] | case.rowm[n - 1] | case.colm[0] | case.colm[n - 1]
    for p in P:
        x = sol[p]; r, c = case.rc(x); k = case.room_of[x]; g = case.pinfo[p][1]
        B = 1 << x
        unary_basic = []  # (testo-frammento, mask) per composti
        rm = case.roomm[k]
        add(p, 'room', f"Era {case.room_in(k)}.", {p: rm}, spec=dict(k='room', room=case.room_keys[k])); unary_basic.append((case.room_in(k), rm, 'room', None))
        add(p, 'row', f"Era nella riga {r+1}.", {p: case.rowm[r]}, spec=dict(k='row', r=r))
        add(p, 'col', f"Era nella colonna {COLS[c]}.", {p: case.colm[c]}, spec=dict(k='col', c=c))
        unary_basic.append((f"nella riga {r+1}", case.rowm[r], 'row', dict(k='row', r=r))); unary_basic.append((f"nella colonna {COLS[c]}", case.colm[c], 'col', dict(k='col', c=c)))
        if x in case.obj:
            t = case.obj[x]
            add(p, 'on', f"Era {case.on_phrase(t, g)}.", {p: case.typem[t]}, spec=dict(k='on', t=t))
            others = [q for q in P if q != p and sol[q] in case.obj and case.obj[sol[q]] == t]
            if not others:
                un = {q: case.full & ~case.typem[t] for q in P if q != p}; un[p] = case.typem[t]
                add(p, 'onlyon', f"Era l'unica persona {case.on_phrase(t, 'f')}.", un, spec=dict(k='onlyon', t=t))
            unary_basic.append((case.on_phrase(t, g), case.typem[t], 'on', dict(k='on', t=t)))
        for t in types:
            if adjm[t] & B:
                add(p, 'adj', f"Era accanto {case.o_a(t)}.", {p: adjm[t]}, spec=dict(k='adj', t=t)); unary_basic.append((f"accanto {case.o_a(t)}", adjm[t], 'adj', dict(k='adj', t=t)))
            else:
                add(p, 'notadj', f"Non era accanto a {case.art(t,'nes')}.", {p: case.full & ~adjm[t]}, spec=dict(k='notadj', t=t))
            for (dr, dc, ph) in ((1, 0, 'nella casella subito sopra {}'), (-1, 0, 'nella casella subito sotto {}'),
                                 (0, 1, 'subito a sinistra {}'), (0, -1, 'subito a destra {}')):
                m = dirm(t, dr, dc)
                if m & B:
                    obj = case.o_bare(t) if 'casella' in ph else case.o_di(t)
                    txt = ph.format(obj)
                    add(p, 'dir', f"Era {txt}.", {p: m}, spec=dict(k='dir', t=t, dr=dr, dc=dc)); unary_basic.append((txt, m, 'dir', dict(k='dir', t=t, dr=dr, dc=dc)))
            if rowT[t] & B and not (case.typem[t] & B):
                add(p, 'rowobj', f"Era nella stessa riga {case.o_di(t)}.", {p: rowT[t]}, spec=dict(k='rowobj', t=t)); unary_basic.append((f"nella stessa riga {case.o_di(t)}", rowT[t], 'rowobj', dict(k='rowobj', t=t)))
            if colT[t] & B and not (case.typem[t] & B):
                add(p, 'colobj', f"Era nella stessa colonna {case.o_di(t)}.", {p: colT[t]}, spec=dict(k='colobj', t=t)); unary_basic.append((f"nella stessa colonna {case.o_di(t)}", colT[t], 'colobj', dict(k='colobj', t=t)))
        for k2 in range(len(case.roomm)):
            if k2 != k: add(p, 'notroom', f"Non era {case.room_in(k2)}.", {p: case.full & ~case.roomm[k2]}, spec=dict(k='notroom', room=case.room_keys[k2]))
        if edge & B: add(p, 'edge', "Era sul bordo della mappa.", {p: edge}, spec=dict(k='edge'))
        else: add(p, 'notedge', "Non era sul bordo della mappa.", {p: case.full & ~edge}, spec=dict(k='notedge'))
        # composti: stanza + altro
        for (ph, m, cat, sp) in unary_basic:
            if cat == 'room': continue
            add(p, 'compound', f"Era {case.room_in(k)}, {ph}.", {p: rm & m}, spec=dict(k='and', parts=[dict(k='room', room=case.room_keys[k]), sp]))
        # relativi ad altre persone
        for q in P:
            if q == p: continue
            y = sol[q]; r2, c2 = case.rc(y); qn = case.pname(q)
            same = case.room_of[y] == k
            ro = case.room_of
            if same:
                add(p, 'rel', f"Era nella stessa stanza di {qn}.", binary=[(p, q, lambda a, b: ro[a] == ro[b])], spec=dict(k='sameroom', q=q))
            else:
                add(p, 'rel', f"Non era nella stessa stanza di {qn}.", binary=[(p, q, lambda a, b: ro[a] != ro[b])], spec=dict(k='diffroom', q=q))
            dr = r - r2
            if dr > 0:
                txt = f"Era nella riga subito sotto {qn}." if dr == 1 else f"Era esattamente {dr} righe sotto {qn}."
                add(p, 'relrow', txt, binary=[(p, q, (lambda d: lambda a, b: a // n - b // n == d)(dr))], spec=dict(k='rowsbelow', q=q, d=dr))
                add(p, 'relweak', f"Era più in basso di {qn}.", binary=[(p, q, lambda a, b: a // n > b // n)], spec=dict(k='below', q=q))
            else:
                add(p, 'relweak', f"Era più in alto di {qn}.", binary=[(p, q, lambda a, b: a // n < b // n)], spec=dict(k='above', q=q))
            if c < c2: add(p, 'relweak', f"Era più a sinistra di {qn}.", binary=[(p, q, lambda a, b: a % n < b % n)], spec=dict(k='leftof', q=q))
            else: add(p, 'relweak', f"Era più a destra di {qn}.", binary=[(p, q, lambda a, b: a % n > b % n)], spec=dict(k='rightof', q=q))
            if abs(dr) == 1 and abs(c - c2) == 1:
                add(p, 'reldiag', f"Era in una casella in diagonale accanto a {qn}.", binary=[(p, q, lambda a, b: abs(a // n - b // n) == 1 and abs(a % n - b % n) == 1)], spec=dict(k='diag', q=q))
    return out

def global_pool(case, sol):
    out = []
    occ = [case.room_of[x] for x in sol.values()]
    if len(set(occ)) == len(case.roomm): out.append(dict(cat='noempty', who=None, text="Non c'erano stanze vuote.", glob=['noempty'], spec=dict(k='noempty')))
    for k in range(len(case.roomm)):
        if k not in occ:
            out.append(dict(cat='emptyroom', who=None, text=f"Nessuno era {case.room_in(k)}.", unary={p: case.full & ~case.roomm[k] for p in case.people}, spec=dict(k='emptyroom', room=case.room_keys[k])))
    for t, m in case.typem.items():
        if not OBJ[t][3] and not any(m >> x & 1 for x in sol.values()):
            out.append(dict(cat='nobodyon', who=None, text=f"Nessuno era {case.on_phrase(t, 'm').replace('seduto ', 'seduto ')}.".replace('Nessuno era su ', 'Nessuno era su '), unary={p: case.full & ~m for p in case.people}, spec=dict(k='nobodyon', t=t)))
    return out
