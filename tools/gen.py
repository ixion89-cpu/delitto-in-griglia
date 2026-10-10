# -*- coding: utf-8 -*-
import random, json, sys, time
from layouts import CASES, OBJ, PALETTE, AVATAR
from core import Case, count_solutions, human_solve, cname, bits, popc
from clues import pool_for, global_pool

W = {
 'facile':   dict(compound=6, room=1, on=2, dir=2, onlyon=1, row=1, col=1),
 'medio':    dict(room=3, adj=2, dir=2, on=2, onlyon=2, rowobj=2, colobj=2, rel=1, relrow=1, notroom=1, compound=1, row=.5, col=.5),
 'difficile':dict(adj=2, rowobj=2, colobj=2, notroom=2, notadj=1, rel=2, relrow=1, relweak=1, reldiag=1, onlyon=1, on=1, edge=1, notedge=1, room=1, dir=1),
}
VW = {'facile': dict(compound=3, room=1, on=1, dir=1), 'medio': dict(none=2, room=1, adj=1, rowobj=1), 'difficile': dict(none=1)}

def wpick(rng, items, weights):
    cand = [(c, weights.get(c['cat'], 0)) for c in items]
    cand = [(c, w) for c, w in cand if w > 0]
    if not cand: return None
    tot = sum(w for _, w in cand); r = rng.random() * tot
    for c, w in cand:
        r -= w
        if r <= 0: return c
    return cand[-1][0]

def random_solution(case, rng):
    n = case.n
    for _ in range(10000):
        perm = list(range(n)); rng.shuffle(perm)
        cells = [r * n + perm[r] for r in range(n)]
        if any(case.block >> x & 1 for x in cells): continue
        ppl = case.people[:]; rng.shuffle(ppl)
        sol = dict(zip(ppl, cells))
        vr = case.room_of[sol[case.victim]]
        if sum(1 for x in cells if case.room_of[x] == vr) != 2: continue
        return sol
    raise RuntimeError('nessuna soluzione casuale')

def ok_level(level, st):
    if level == 'facile': return st['hypotheses'] == 0 and st['binary'] == 0 and st['hidden'] + st['victim'] >= 1
    if level == 'medio': return st['hypotheses'] == 0 and (st['hidden'] + st['victim'] + st['binary']) >= 3
    return 1 <= st['hypotheses'] <= 3 and st['branch_nodes'] <= 80

def cnt_of(case, clues, cap=40):
    try:
        s, _ = count_solutions(case, clues, cap=cap, node_limit=60000)
        return len(s)
    except TimeoutError:
        return cap

def generate(d, seed):
    case = Case(d); level = d['level']; rng = random.Random(seed)
    vic = case.victim
    for attempt in range(400):
        sol = random_solution(case, rng)
        pool = pool_for(case, sol)
        none = dict(cat='none', who=vic, text='', spec=dict(k='none'))
        pool[vic].append(none)
        gp = global_pool(case, sol)
        def pick(p):
            return wpick(rng, pool[p], VW[level] if p == vic else W[level])
        chosen = {p: pick(p) for p in case.people}
        if any(v is None for v in chosen.values()): continue
        extra = []
        if level == 'difficile' and gp: extra = [rng.choice(gp)]
        if level == 'difficile':
            chosen = {p: wpick(rng, pool[p], VW['medio'] if p == vic else W['medio']) for p in case.people}
        elif level == 'medio' and gp and rng.random() < .5: extra = [rng.choice(gp)]
        def allc(ch): return [c for c in ch.values()] + extra
        cnt = cnt_of(case, allc(chosen))
        for it in range(60):
            if cnt == 1: break
            if cnt == 0: break
            p = rng.choice(case.people)
            best = None; bc = cnt
            for _ in range(6):
                c = pick(p) if level != 'difficile' else wpick(rng, pool[p], VW['medio'] if p == vic else W['medio'])
                if c is None: continue
                ch2 = dict(chosen); ch2[p] = c
                k2 = cnt_of(case, allc(ch2))
                if 0 < k2 < bc or (k2 == bc and rng.random() < .3): best, bc = c, k2
            if best: chosen[p] = best; cnt = bc
        if cnt != 1: continue
        if len(count_solutions(case, allc(chosen), cap=2)[0]) != 1: continue
        if level == 'difficile':
            # indebolimento progressivo: sostituisce indizi con altri piu' deboli finche' resta unico
            for it in range(120):
                res, st, log = human_solve(case, allc(chosen))
                if ok_level(level, st): break
                if st['hypotheses'] > 3: break
                p = rng.choice(case.people)
                c = wpick(rng, pool[p], VW[level] if p == vic else W[level])
                if c is None or c is chosen[p]: continue
                ch2 = dict(chosen); ch2[p] = c
                try:
                    s2, _ = count_solutions(case, allc(ch2), cap=2, node_limit=150000)
                except TimeoutError:
                    continue
                if len(s2) == 1: chosen = ch2
        res, st, log = human_solve(case, allc(chosen))
        if not res: continue
        if level == 'difficile': print('   tentativo', attempt, st, flush=True)
        if not ok_level(level, st): continue
        if level == 'difficile':
            weak = sum(1 for c in chosen.values() if c and c['cat'] in ('notroom','notadj','rel','relrow','relweak','reldiag','notedge','onlyon','on','edge'))
            if weak < 4: continue
        return case, sol, chosen, extra, st, log, attempt
    raise RuntimeError('fallito ' + d['id'])

def export(case, sol, chosen, extra, st, log):
    d = case.d; n = case.n
    rooms = [dict(id=k, name=d['rooms'][k][0], color=PALETTE[i % len(PALETTE)]) for i, k in enumerate(case.room_keys)]
    grid = [[case.room_of[r * n + c] for c in range(n)] for r in range(n)]
    objs = [dict(r=x // n, c=x % n, type=t) for x, t in sorted(case.obj.items())]
    otypes = {t: dict(name=OBJ[t][0], emoji=OBJ[t][1 + 1], blocking=OBJ[t][3]) for t in set(case.obj.values())}
    people = []
    for i, p in enumerate(case.people):
        name, g, ini = case.pinfo[p]
        vic = p == case.victim
        txt = chosen[p]['text'] if chosen[p] else ''
        if vic: txt = ("La vittima. " + (txt + ' ' if txt else '') + "Era sola con l'assassino." if g == 'f' else "La vittima. " + (txt + ' ' if txt else '') + "Era solo con l'assassino.")
        people.append(dict(id=ini, name=name, gender=g, color=AVATAR[i % len(AVATAR)] if not vic else '#8E2F2F', victim=vic, clue=txt, spec=chosen[p]['spec']))
    vr = case.room_of[sol[case.victim]]
    culprit = [p for p in case.people if p != case.victim and case.room_of[sol[p]] == vr][0]
    expl = list(log) + [f"Nella stanza di {case.pname(case.victim)} ({d['rooms'][case.room_keys[vr]][0]}) c'era solo {case.pname(culprit)}: {'è lei' if case.pinfo[culprit][1]=='f' else 'è lui'} il colpevole."]
    return dict(id=d['id'], level=d['level'], title=d['title'], setting=d['setting'], intro=d['intro'], size=n,
                rooms=rooms, grid=grid, objects=objs, objectTypes=otypes, people=people,
                extraClues=[e['text'] for e in extra], extraSpecs=[e['spec'] for e in extra],
                solution={p: [sol[p] // n, sol[p] % n] for p in case.people}, culprit=culprit,
                explanation=expl, stats=st)

if __name__ == '__main__':
    only = sys.argv[1:] 
    out = []
    for i, d in enumerate(CASES):
        if only and d['id'] not in only: continue
        t0 = time.time()
        case, sol, chosen, extra, st, log, att = generate(d, seed=1000 + i)
        e = export(case, sol, chosen, extra, st, log)
        out.append(e)
        print(d['id'], d['level'], f"{case.n}x{case.n}", 'tentativi', att + 1, st, f"{time.time()-t0:.1f}s", flush=True)
        for pp in e['people']: print('   ', pp['id'], pp['name'], '|', pp['clue'])
        for x in e['extraClues']: print('    *', x)
    json.dump(out, open('generated.json', 'w'), ensure_ascii=False, indent=1)
