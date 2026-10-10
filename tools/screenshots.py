import asyncio, json, sys
from playwright.async_api import async_playwright
URL = 'http://127.0.0.1:8765/'
OUT = '/workspace/murdoku-app/screenshot/'
P = {p['id']: p for p in json.load(open('/workspace/murdoku-app/puzzles.json'))}

async def place(page, pid, r, c, n):
    await page.evaluate(f"__dig.setMode('place'); __dig.select('{pid}')")
    await page.click(f'.cell[data-i="{r*n+c}"]')

async def note(page, pid, cells, n):
    await page.evaluate(f"__dig.setMode('note'); __dig.select('{pid}')")
    for (r, c) in cells: await page.click(f'.cell[data-i="{r*n+c}"]')

async def cross(page, cells, n):
    await page.evaluate("__dig.setMode('cross')")
    for (r, c) in cells: await page.click(f'.cell[data-i="{r*n+c}"]')

async def free_cells(page, pz, k, avoid=()):
    n = pz['size']; block = {(o['r'], o['c']) for o in pz['objects'] if pz['objectTypes'][o['type']]['blocking']}
    sol = {tuple(v) for v in pz['solution'].values()}
    out = []
    for r in range(n):
        for c in range(n):
            if (r, c) not in block and (r, c) not in sol and (r, c) not in avoid: out.append((r, c))
    return out[:k]

async def puzzle_with_notes(page, pid, fname, nplace=2):
    pz = P[pid]; n = pz['size']
    await page.goto(URL + '?caso=' + pid); await page.wait_for_selector('.cell')
    await page.evaluate("document.getElementById('story').open = false")
    people = pz['people']
    for p in people[:nplace]:
        r, c = pz['solution'][p['id']]; await place(page, p['id'], r, c, n)
    sol_cells = [tuple(pz['solution'][p['id']]) for p in people]
    # appunti: candidati per due persone, incluso il posto giusto
    a, b = people[nplace]['id'], people[nplace + 1]['id']
    fc = await free_cells(page, pz, 6)
    await note(page, a, [tuple(pz['solution'][a])] + fc[:2], n)
    await note(page, b, [tuple(pz['solution'][b]), fc[1], fc[3]], n)
    await cross(page, fc[4:6], n)
    await page.evaluate(f"__dig.setMode('note'); __dig.select('{b}')")
    await page.click('#clues .clue:nth-child(1)'); await page.click('#clues .clue:nth-child(2)')
    await page.evaluate("document.querySelector('#game .scroll').scrollTop = 0")
    await page.wait_for_timeout(300)
    await page.screenshot(path=OUT + fname)
    # seconda vista: indizi
    await page.evaluate("document.querySelector('#game .scroll').scrollTop = 99999")
    await page.wait_for_timeout(200)
    await page.screenshot(path=OUT + fname.replace('.png', '-indizi.png'))

async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        ctx = await br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='it-IT')
        page = await ctx.new_page()
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: m.type == 'error' and errs.append(m.text))
        await page.goto(URL); await page.wait_for_selector('.level')
        await page.screenshot(path=OUT + '01-livelli.png')
        await page.click('#btnRules'); await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '02-regole.png')
        await page.click('[data-act=close]')
        # apertura casuale dal livello (verifica del flusso)
        await page.click('.level.l-medio'); await page.wait_for_selector('.cell')
        first = await page.evaluate("__dig.state().pz.id")
        await page.click('#btnBack'); await page.click('.level.l-medio'); await page.wait_for_selector('.cell')
        second = await page.evaluate("__dig.state().pz.id")
        print('casuale medio:', first, '->', second, '(diversi)' if first != second else '(UGUALI!)')
        await puzzle_with_notes(page, 'f3', '03-facile-appunti.png')
        await puzzle_with_notes(page, 'm2', '04-medio-appunti.png')
        await puzzle_with_notes(page, 'd3', '05-difficile-appunti.png', nplace=3)
        # verifica con mappa incompleta / sbagliata
        pz = P['f1']; n = pz['size']
        await page.goto(URL + '?caso=f1'); await page.wait_for_selector('.cell')
        await page.click('#btnReset'); await page.click('[data-act=reset]')
        ids = [p['id'] for p in pz['people']]
        # caso sbagliato: scambia due persone
        sol = {k: tuple(v) for k, v in pz['solution'].items()}
        wrong = dict(sol); wrong[ids[0]], wrong[ids[1]] = sol[ids[1]], sol[ids[0]]
        for pid, (r, c) in wrong.items(): await place(page, pid, r, c, n)
        await page.click('#btnCheck'); await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '06-verifica-errore.png')
        await page.click('[data-act=close]')
        await page.click('#btnReset'); await page.click('[data-act=reset]')
        for pid, (r, c) in sol.items(): await place(page, pid, r, c, n)
        await page.evaluate("(() => { const g = __dig.state(); g.elapsed = 437; g.start = performance.now(); })()")
        await page.click('#btnCheck'); await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '07-accusa.png')
        await page.click(f'[data-act=acc][data-id="{pz["culprit"]}"]'); await page.wait_for_timeout(400)
        await page.screenshot(path=OUT + '08-vittoria.png')
        await page.evaluate("document.querySelector('.sheet').scrollTop = 9999"); await page.wait_for_timeout(200)
        await page.screenshot(path=OUT + '08-vittoria-soluzione.png')
        await page.click('[data-act=home]'); await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '09-livelli-progressi.png')
        # aiuto + long press
        await page.goto(URL + '?caso=d1'); await page.wait_for_selector('.cell')
        await page.click('#btnHint'); await page.wait_for_timeout(300)
        st = await page.evaluate("__dig.state().hints.length")
        print('aiuti usati d1:', st)
        # offline: service worker registrato?
        sw = await page.evaluate("navigator.serviceWorker.getRegistrations().then(r => r.length)")
        print('service worker registrati:', sw)
        print('errori JS:', errs or 'nessuno')
        await br.close()
asyncio.run(main())
