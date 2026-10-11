# -*- coding: utf-8 -*-
"""Verifica INDIPENDENTE dei 10 casi di puzzles.json.
Re-interpreta ogni indizio dalla sua specifica semantica (non usa il codice del generatore),
enumera TUTTE le disposizioni compatibili (una persona per riga e per colonna, niente caselle con
oggetti bloccanti, tutti gli indizi veri, vittima sola con l'assassino) e controlla che:
  1) la soluzione sia unica, 2) coincida con quella salvata, 3) il colpevole sia determinato."""
import json, time, sys, os
P = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'puzzles.json')))

def build(pz):
    n = pz['size']; rk = [r['id'] for r in pz['rooms']]
    room = lambda r, c: rk[pz['grid'][r][c]]
    obj = {(o['r'], o['c']): o['type'] for o in pz['objects']}
    blocking = {k for k, v in obj.items() if pz['objectTypes'][v]['blocking']}
    def cells_of(t): return [k for k, v in obj.items() if v == t]
    def adj(a, b): return abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1
    def U(spec, pos, me):  # predicato unario/relazionale: pos = dict persona->(r,c) (parziale)
        k = spec['k']; x = pos.get(me)
        if k == 'none': return True
        if k == 'and': return all(U(s, pos, me) for s in spec['parts'])
        if k in ('sameroom','diffroom','rowsbelow','below','above','leftof','rightof','diag'):
            y = pos.get(spec['q'])
            if x is None or y is None: return True
            return {'sameroom': room(*x) == room(*y), 'diffroom': room(*x) != room(*y),
                    'rowsbelow': x[0] - y[0] == spec.get('d', 0), 'below': x[0] > y[0], 'above': x[0] < y[0],
                    'leftof': x[1] < y[1], 'rightof': x[1] > y[1],
                    'diag': abs(x[0]-y[0]) == 1 and abs(x[1]-y[1]) == 1}[k]
        if x is None: return True
        r, c = x
        if k == 'room': return room(r, c) == spec['room']
        if k == 'notroom': return room(r, c) != spec['room']
        if k == 'row': return r == spec['r']
        if k == 'col': return c == spec['c']
        if k == 'on': return obj.get(x) == spec['t']
        if k == 'onlyon':
            if obj.get(x) != spec['t']: return False
            return all(obj.get(y) != spec['t'] for p, y in pos.items() if p != me)
        if k == 'adj': return any(adj(x, y) for y in cells_of(spec['t']))
        if k == 'notadj': return not any(adj(x, y) for y in cells_of(spec['t']))
        if k == 'dir': return obj.get((r + spec['dr'], c + spec['dc'])) == spec['t']
        if k == 'rowobj': return obj.get(x) != spec['t'] and any(y[0] == r for y in cells_of(spec['t']))
        if k == 'colobj': return obj.get(x) != spec['t'] and any(y[1] == c for y in cells_of(spec['t']))
        if k == 'edge': return r in (0, n-1) or c in (0, n-1)
        if k == 'notedge': return not (r in (0, n-1) or c in (0, n-1))
        raise ValueError(k)
    def G(spec, pos, full):
        k = spec['k']
        if k == 'noempty': return (not full) or len({room(*x) for x in pos.values()}) == len(rk)
        if k == 'emptyroom': return all(room(*x) != spec['room'] for x in pos.values())
        if k == 'nobodyon': return all(obj.get(x) != spec['t'] for x in pos.values())
        raise ValueError(k)
    return n, room, blocking, U, G

def solve_all(pz):
    n, room, blocking, U, G = build(pz)
    ppl = [p['id'] for p in pz['people']]; spec = {p['id']: p['spec'] for p in pz['people']}
    victims = [p['id'] for p in pz['people'] if p.get('victim')]
    V = victims[0] if victims else None
    sols = []; nodes = [0]; pos = {}
    def ok(full):
        for p in pos:
            if not U(spec[p], pos, p): return False
        # i vincoli relazionali vanno controllati anche se e' piazzato solo il riferimento
        for p in ppl:
            if p not in pos and spec[p]['k'] in ('sameroom','diffroom','rowsbelow','below','above','leftof','rightof','diag'): pass
        if not all(G(s, pos, full) for s in pz['extraSpecs']): return False
        if V and V in pos:
            cnt = sum(1 for x in pos.values() if room(*x) == room(*pos[V]))
            if cnt > 2 or (full and cnt != 2): return False
        return True
    def rec(r, usedc):
        nodes[0] += 1
        if r == n:
            if ok(True): sols.append(dict(pos))
            return
        for p in ppl:
            if p in pos: continue
            for c in range(n):
                if c in usedc or (r, c) in blocking: continue
                pos[p] = (r, c)
                if ok(False): rec(r + 1, usedc | {c})
                del pos[p]
            # una sola persona per riga: per la riga r proviamo ogni persona libera
    rec(0, frozenset())
    return sols, nodes[0], V, room

print("Verifica unicità dei casi\n" + "=" * 60)
allok = True
for pz in P:
    t0 = time.time()
    sols, nodes, V, room = solve_all(pz)
    saved = {k: tuple(v) for k, v in pz['solution'].items()}
    uniq = len(sols) == 1
    same = uniq and sols[0] == saved
    culprit = None
    if uniq:
        if pz.get('mode') == 'ana':
            ac = tuple(pz['answerCell'])
            culprit = [p for p, x in sols[0].items() if x == ac]
        else:
            vr = room(*sols[0][V]); culprit = [p for p, x in sols[0].items() if p != V and room(*x) == vr]
    good = uniq and same and culprit == [pz['culprit']]
    allok &= good
    st = pz['stats']
    print(f"{pz['id']} {pz['title']:<30} {pz['level']:<9} {pz['size']}x{pz['size']}  soluzioni={len(sols)}  "
          f"coincide={'sì' if same else 'NO'}  colpevole={culprit[0] if culprit else '?'}  "
          f"nodi_ricerca={nodes}  ipotesi_umane={st['hypotheses']}  nodi_ipotesi={st['branch_nodes']}  "
          f"passi_righe/colonne={st['hidden']}  passi_relativi={st['binary']}  t={time.time()-t0:.1f}s  {'OK' if good else 'ERRORE'}")
print("=" * 60)
print("TUTTI I CASI HANNO SOLUZIONE UNICA" if allok else "ATTENZIONE: ci sono errori")
sys.exit(0 if allok else 1)
