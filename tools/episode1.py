# -*- coding: utf-8 -*-
"""Episodio 1 — Attracco al buio (accesso non autorizzato).

Cerca un insieme di indizi con soluzione unica, difficoltà fra Facile e Medio
(come la misurano gen.py / human_solve / count_solutions):

  Facile:  ipotesi=0, passi relativi=0, nodi di ricerca <= 15
  Medio:   ipotesi=0, nodi di ricerca >= 187 (griglie 6×6 e 7×7)
  Questo:  griglia 6×6, ipotesi=0, niente regola della vittima,
           almeno un passo relativo, nodi di ricerca strettamente fra i due.

La risposta non è un colpevole di omicidio: è chi occupa la manovella.
Quell'indizio non viene dato in chiaro («era sulla manovella»).
"""
import json, os, random, sys, time
from core import Case, count_solutions, human_solve, cname, popc
from clues import pool_for

# Fra il massimo dei nodi Facile (15) e il minimo dei nodi Medio (187).
NODE_LO, NODE_HI = 16, 186
W = dict(compound=4, room=2, dir=3, on=2, adj=2, row=1.5, col=1.5,
         rowobj=1, colobj=1, rel=3, relrow=2.5)
SKIP = {'notroom', 'notadj', 'relweak', 'reldiag', 'edge', 'notedge', 'onlyon'}

CASE = dict(
    id='n1', mode='ana', level='nadir',
    title='Attracco al buio', setting='Hangar di attracco',
    intro=("Blackout sulla Stazione Nadir. I sensori di presenza tengono una sola firma "
           "per riga e per colonna, e ogni frammento di log rimasto è vero: qui si cancella, "
           "non si falsifica. Ricostruisci dov'era l'equipaggio. Chi si trova sulla manovella "
           "ha aperto il portellone a mano."),
    rooms={
        'H': ('Hangar', "nell'hangar"),
        'A': ('Camera stagna', 'nella camera stagna'),
        'C': ('Corridoio', 'nel corridoio'),
        'K': ('Plancia', 'in plancia'),
        'G': ('Stiva', 'in stiva'),
    },
    grid=["HHHAAA", "HHHAAA", "HHCCKK", "CCCCKK", "CCGGGG", "CCGGGG"],
    objs=["G....P", "....M.", ".....C", ".E....", "S..X..", "..R..."],
    omap={'G': 'generatore', 'P': 'paratia', 'M': 'manovella', 'C': 'console',
          'E': 'estintore', 'S': 'panca', 'X': 'container', 'R': 'rack'},
    people=[('Teo', 'm', 'V'), ('Brenner', 'm', 'B'), ('Okafor', 'f', 'O'),
            ('Nadia', 'f', 'N'), ('Halvorsen', 'm', 'H'), ('Mei', 'f', 'M')],
)
FULL = {'V': 'Teo Vasquez', 'B': 'Ilario Brenner', 'O': 'Yara Okafor',
        'N': 'Nadia Ferrante', 'H': 'Sven Halvorsen', 'M': 'Mei Takeda'}
ROLE = {'V': 'ingegnere capo', 'B': 'comandante', 'O': 'medico di bordo',
        'N': 'comunicazioni', 'H': 'capo della sicurezza', 'M': 'ricerca ambientale'}
FACE = {'V': 'vasquez', 'B': 'brenner', 'O': 'okafor', 'N': 'nadia', 'H': 'halvorsen', 'M': 'mei'}
COLOR = {'V': '#C65A1E', 'B': '#2E4A5C', 'O': '#1F7A6B', 'N': '#3E6E9A', 'H': '#6B5344', 'M': '#2F6B4F'}
ROOM_COLOR = {'H': '#D5E3EE', 'A': '#F6DCC8', 'C': '#E4DCEC', 'K': '#D3E8DA', 'G': '#EFE2C9'}

INTRO = [
    {"who": "vasquez", "expr": "worried",
     "text": "Benvenuta sulla Nadir, ispettrice. Scusi il buio: il generatore principale è giù da sei ore."},
    {"who": "livia", "expr": "neutral",
     "text": "Sei ore. E il portellone dell'hangar risulta aperto. Non è così che si attracca, ingegnere."},
    {"who": "vasquez", "expr": "worried",
     "text": "Il comando automatico è morto col generatore. Qualcuno ha girato la manovella a mano, pochi minuti prima che la sua navetta entrasse nel raggio."},
    {"who": "livia", "expr": "neutral",
     "text": "Pochi minuti prima. Allora non l'hanno aperto per me. Chi c'era di turno?"},
    {"who": "vasquez", "expr": "worried",
     "text": "L'equipaggio non lo ricorda. I log rimasti sono veri: qui si cancella, non si falsifica. Ma mancano interi minuti."},
    {"who": "livia", "expr": "neutral",
     "text": "Allora li ricostruisco. I sensori tengono una firma per binario: una persona per riga e per colonna. Se la griglia chiude, sappiamo chi era sulla manovella."},
]
OUTRO = [
    {"who": "livia", "expr": "neutral",
     "text": "La ricostruzione è unica. Sulla manovella c'era Lei, Vasquez. Il portellone l'ha aperto a mano, prima ancora che la mia navetta fosse nel raggio."},
    {"who": "vasquez", "expr": "surprised",
     "text": "Con il generatore a terra il portellone non obbedisce. O lo giravo io, o Lei restava fuori dalla stazione."},
    {"who": "livia", "expr": "neutral",
     "text": "L'orario non coincide con un benvenuto. Il log è incompleto, non falso: Lei l'ha aperto senza autorizzazione."},
    {"who": "vasquez", "expr": "worried",
     "text": "Non sono stato l'unico a muovermi al buio. Nel laboratorio ambientale il sensore dell'ossigeno ha lo stesso buco, negli stessi minuti."},
    {"who": "livia", "expr": "worried",
     "text": "Ivo Rendina era di turno ai sensori. Non risponde. La prossima ricostruzione inizia da lì."},
]


def reveals_crank(c):
    """Vero se l'indizio dice esplicitamente che qualcuno è sulla manovella."""
    def walk(s):
        if not isinstance(s, dict):
            return False
        if s.get('k') in ('on', 'onlyon') and s.get('t') == 'manovella':
            return True
        return any(walk(x) for x in s.get('parts', []))
    return walk(c.get('spec'))


def clue_ok(p, c):
    if c['cat'] in SKIP or reveals_crank(c):
        return False
    if c['spec'].get('k') == 'diffroom':
        return False
    # la posizione di Vasquez non deve essere una casella sola nel suo indizio
    if p == 'V' and 'unary' in c and popc(next(iter(c['unary'].values()))) == 1:
        return False
    return True


def wpick(rng, items):
    cand = [(c, W.get(c['cat'], 0)) for c in items if clue_ok(c.get('who', ''), c)]
    if not cand:
        return None
    tot = sum(w for _, w in cand)
    r = rng.random() * tot
    for c, w in cand:
        r -= w
        if r <= 0:
            return c
    return cand[-1][0]


def random_solution(case, rng, fixed):
    n = case.n
    used_r = {x // n for x in fixed.values()}
    used_c = {x % n for x in fixed.values()}
    rows = [r for r in range(n) if r not in used_r]
    cols_all = [c for c in range(n) if c not in used_c]
    people = [p for p in case.people if p not in fixed]
    for _ in range(4000):
        cols = cols_all[:]
        rng.shuffle(cols)
        ppl = people[:]
        rng.shuffle(ppl)
        sol = dict(fixed)
        bad = False
        for p, r, c in zip(ppl, rows, cols):
            x = r * n + c
            if case.block >> x & 1:
                bad = True
                break
            sol[p] = x
        if not bad and len(sol) == n:
            return sol
    return None


def ok_band(st, nodes):
    return (st['hypotheses'] == 0 and st['victim'] == 0 and st['noempty'] == 0
            and 1 <= st['binary'] <= 3 and st['hidden'] >= 1
            and NODE_LO <= nodes <= NODE_HI)


def search():
    case = Case(CASE)
    answer = next(x for x, t in case.obj.items() if t == 'manovella')
    assert case.obj[answer] == 'manovella' and not (case.block >> answer & 1)
    best_near = None
    t0 = time.time()
    for seed in range(400):
        rng = random.Random(20000 + seed)
        for _attempt in range(30):
            sol = random_solution(case, rng, {'V': answer})
            if not sol:
                continue
            pool = {}
            raw = pool_for(case, sol)
            for p in case.people:
                pool[p] = [c for c in raw[p] if clue_ok(p, c)]
            def pick(p, rng=rng):
                return wpick(rng, pool[p])
            chosen = {p: pick(p) for p in case.people}
            if any(v is None for v in chosen.values()):
                continue
            if not any(c['cat'] in ('rel', 'relrow') for c in chosen.values()):
                p = rng.choice(case.people)
                rels = [c for c in pool[p] if c['cat'] in ('rel', 'relrow')]
                if not rels:
                    continue
                chosen[p] = rng.choice(rels)

            def allc(ch):
                return list(ch.values())

            try:
                sols, _ = count_solutions(case, allc(chosen), cap=2, node_limit=80000)
            except TimeoutError:
                continue
            cnt = len(sols)
            for _it in range(50):
                if cnt == 1:
                    break
                if cnt == 0:
                    break
                p = rng.choice(case.people)
                best = None
                bc = cnt
                for _k in range(8):
                    c = pick(p)
                    if c is None:
                        continue
                    ch2 = dict(chosen)
                    ch2[p] = c
                    if not any(x['cat'] in ('rel', 'relrow') for x in ch2.values()):
                        continue
                    try:
                        s2, _ = count_solutions(case, allc(ch2), cap=2, node_limit=80000)
                    except TimeoutError:
                        continue
                    k2 = len(s2)
                    if 0 < k2 < bc or (k2 == bc and rng.random() < .3):
                        best, bc = c, k2
                if best:
                    chosen[p] = best
                    cnt = bc
            if cnt != 1:
                continue
            try:
                sols, nodes = count_solutions(case, allc(chosen), cap=2, node_limit=200000)
            except TimeoutError:
                continue
            if len(sols) != 1:
                continue
            try:
                res, st, log = human_solve(case, allc(chosen))
            except RuntimeError:
                continue
            if not res:
                continue
            if tuple(res[p] for p in case.people) != sols[0]:
                continue
            # la persona sulla manovella deve essere Vasquez, e il risolutore umano non deve ipotizzare
            if res['V'] != answer:
                continue
            near = (nodes, st, seed)
            if best_near is None or abs(nodes - 80) < abs(best_near[0] - 80):
                best_near = near
            if not ok_band(st, nodes):
                continue
            # varietà: non tutti indizi composti
            cats = {c['cat'] for c in chosen.values()}
            if len(cats) < 3:
                continue
            print(f"TROVATO seed={seed} nodi={nodes} stats={st} t={time.time()-t0:.1f}s", flush=True)
            return case, sol, chosen, st, log, nodes, answer
        if seed % 20 == 19:
            print(f"... seed {seed} t={time.time()-t0:.1f}s vicino={best_near[0] if best_near else None} {best_near[1] if best_near else ''}", flush=True)
    raise RuntimeError('nessun episodio nella fascia ' + str(best_near))


def export(case, sol, chosen, st, log, nodes, answer):
    d = CASE
    n = case.n
    rooms = [dict(id=k, name=d['rooms'][k][0], color=ROOM_COLOR[k]) for k in case.room_keys]
    grid = [[case.room_of[r * n + c] for c in range(n)] for r in range(n)]
    objs = [dict(r=x // n, c=x % n, type=t) for x, t in sorted(case.obj.items())]
    from layouts import OBJ
    otypes = {t: dict(name=OBJ[t][0], emoji=OBJ[t][2], blocking=OBJ[t][3]) for t in set(case.obj.values())}
    people = []
    for p in case.people:
        name, g, ini = case.pinfo[p]
        people.append(dict(
            id=ini, name=name, full=FULL[ini], role=ROLE[ini], gender=g, color=COLOR[ini],
            victim=False, face=f"assets/faces/{FACE[ini]}.webp",
            clue=chosen[p]['text'], spec=chosen[p]['spec'],
        ))
    cell = cname(n, answer)
    expl = list(log) + [f"Sulla manovella ({cell}) c'era {FULL['V']}: ha aperto il portellone a mano."]
    return dict(
        id='n1', level='nadir', mode='ana', episode=1,
        title=d['title'], setting=d['setting'], intro=d['intro'], size=n,
        rooms=rooms, grid=grid, objects=objs, objectTypes=otypes, people=people,
        extraClues=[], extraSpecs=[],
        solution={p: [sol[p] // n, sol[p] % n] for p in case.people},
        answerCell=[answer // n, answer % n], answerObject='manovella', culprit='V',
        question=dict(
            title='Chi ha aperto il portellone?',
            prompt='La mappa è corretta. Chi era sulla manovella?',
            wrong='Non era sulla manovella.',
        ),
        explanation=expl, stats=st,
        scenes=dict(
            intro=dict(kicker='RECON // LOG 01', clock='NADIR · T+06:12:40',
                       bg='assets/bg/hangar.webp', lines=INTRO),
            outro=dict(kicker='RECON // LOG 01 · ESITO', clock='NADIR · T+07:02:18',
                       bg='assets/bg/hangar.webp', lines=OUTRO),
        ),
    )


def write_puzzles(ep):
    root = os.path.join(os.path.dirname(__file__), '..')
    jp = os.path.join(root, 'puzzles.json')
    with open(jp, encoding='utf-8') as f:
        data = json.load(f)
    data = [p for p in data if p.get('id') != 'n1'] + [ep]
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    js = 'window.PUZZLES = ' + json.dumps(data, ensure_ascii=False, separators=(', ', ': ')) + ';\n'
    with open(os.path.join(root, 'puzzles.js'), 'w', encoding='utf-8') as f:
        f.write(js)


if __name__ == '__main__':
    case, sol, chosen, st, log, nodes, answer = search()
    ep = export(case, sol, chosen, st, log, nodes, answer)
    print('nodi_ricerca', nodes)
    print('stats', st)
    for p in ep['people']:
        print(f"  {p['id']} {p['full']:<18} {ep['solution'][p['id']]} | {p['clue']}")
    for s in ep['explanation']:
        print('   ', s)
    if '--write' in sys.argv:
        write_puzzles(ep)
        print('scritto in puzzles.json e puzzles.js')
