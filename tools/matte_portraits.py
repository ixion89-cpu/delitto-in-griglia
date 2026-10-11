# -*- coding: utf-8 -*-
"""Scontorno dei ritratti e taglio dei fogli espressione.

I fogli sono 4 pose affiancate: neutra, sorpresa, arrabbiata, preoccupata.
Lo sfondo si toglie dal bordo e anche dalle zone chiuse (il buco fra braccio
e testa), ma solo se il colore è quello del fondale. Un camice bianco resta:
è più variegato e i raggi dal bordo non incontrano subito il personaggio.
Uso: python3 matte_portraits.py /percorso/sorgenti /percorso/assets
"""
import math
import os
import sys
from PIL import Image, ImageDraw

EXPRS = ('neutral', 'surprised', 'angry', 'worried')
CAST = ('livia', 'vasquez', 'brenner', 'okafor', 'nadia', 'halvorsen', 'mei')
EXPR_CAST = ('livia', 'vasquez')


def border_bg(src, w, h):
    samp = []
    step = max(1, w // 180)
    for x in range(0, w, step):
        samp.append(src[x, 0])
        samp.append(src[x, h - 1])
    for y in range(0, h, step):
        samp.append(src[0, y])
        samp.append(src[w - 1, y])
    return tuple(sorted(s[i] for s in samp)[len(samp) // 2] for i in range(3))


def flood_matte(im):
    im = im.convert('RGB')
    w, h = im.size
    src = im.load()
    bg = border_bg(src, w, h)

    def dist(rgb):
        return max(abs(rgb[0] - bg[0]), abs(rgb[1] - bg[1]), abs(rgb[2] - bg[2]))

    def lum(rgb):
        return (rgb[0] + rgb[1] + rgb[2]) / 3

    def chroma(rgb):
        return max(rgb) - min(rgb)

    edge_tol = 20
    seen = bytearray(w * h)
    stack = []

    def try_add(x, y):
        if x < 0 or y < 0 or x >= w or y >= h:
            return
        i = y * w + x
        if seen[i]:
            return
        if dist(src[x, y]) <= edge_tol:
            seen[i] = 1
            stack.append((x, y))

    for x in range(w):
        try_add(x, 0)
        try_add(x, h - 1)
    for y in range(h):
        try_add(0, y)
        try_add(w - 1, y)
    while stack:
        x, y = stack.pop()
        try_add(x + 1, y)
        try_add(x - 1, y)
        try_add(x, y + 1)
        try_add(x, y - 1)

    # Fondale chiuso: quasi identico al bordo, poca tinta. Il camice non lo è.
    pure_tol = 8
    pure = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i]:
                continue
            rgb = src[x, y]
            if dist(rgb) <= pure_tol and chroma(rgb) <= 10 and lum(rgb) >= 200:
                pure[i] = 1

    vis = bytearray(w * h)
    kill = bytearray(w * h)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if vis[i] or not pure[i]:
                continue
            q = [(x, y)]
            vis[i] = 1
            pts = []
            while q:
                cx, cy = q.pop()
                pts.append((cx, cy))
                for dx, dy in dirs:
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < w and 0 <= ny < h):
                        continue
                    j = ny * w + nx
                    if vis[j] or not pure[j]:
                        continue
                    vis[j] = 1
                    q.append((nx, ny))
            if len(pts) < 48:
                continue
            pset = set(pts)
            hi = lo = 0
            for cx, cy in pts:
                for dx, dy in dirs:
                    if (cx + dx, cy + dy) in pset:
                        continue
                    kind = None
                    for step in range(1, 26):
                        xx, yy = cx + dx * step, cy + dy * step
                        if not (0 <= xx < w and 0 <= yy < h) or seen[yy * w + xx]:
                            kind = 'bg'
                            break
                        j = yy * w + xx
                        if pure[j]:
                            continue
                        rgb = src[xx, yy]
                        if chroma(rgb) > 16 or lum(rgb) < 176 or dist(rgb) > 22:
                            kind = 'fg'
                            break
                    if kind is None:
                        lo += 1
                    else:
                        hi += 1
            if hi + lo and hi / (hi + lo) >= 0.55:
                for px, py in pts:
                    kill[py * w + px] = 1

    alpha = bytearray(w * h)
    for i in range(w * h):
        alpha[i] = 0 if seen[i] or kill[i] else 255

    # Alone chiaro attaccato al trasparente: prima il fondale, poi il grigio di bordo.
    # Due passate soltanto sul grigio, così il bordo di un camice non si assottiglia.
    for step in range(7):
        loose = step >= 5
        peel = []
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if alpha[i] == 0:
                    continue
                rgb = src[x, y]
                if loose:
                    if chroma(rgb) > 14 or lum(rgb) < 208:
                        continue
                elif chroma(rgb) > 16 or dist(rgb) > 22 or lum(rgb) < 186:
                    continue
                if any(
                    not (0 <= x + dx < w and 0 <= y + dy < h) or alpha[(y + dy) * w + (x + dx)] == 0
                    for dx, dy in dirs
                ):
                    peel.append(i)
        if not peel:
            continue
        for i in peel:
            alpha[i] = 0

    out = im.convert('RGBA')
    op = out.load()
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if alpha[i] == 0:
                op[x, y] = (0, 0, 0, 0)
                continue
            rgb = src[x, y]
            # un filo chiaro e slavato sul bordo resta un alone: via del tutto
            if chroma(rgb) <= 16 and lum(rgb) >= 200:
                if any(
                    not (0 <= x + dx < w and 0 <= y + dy < h) or alpha[(y + dy) * w + (x + dx)] == 0
                    for dx, dy in dirs
                ):
                    op[x, y] = (0, 0, 0, 0)
    return out


def strict_navy(rgb):
    r, g, b = rgb
    L = (r + g + b) / 3
    return 28 < L < 105 and b > r + 12 and b > g + 4 and r < 85 and g < 100


def repaint_livia_patch(im):
    """Sostituisce la mostrina con stella e ali con un anello d'orbita e una stazione."""
    im = im.convert('RGB')
    w, h = im.size
    src = im.load()
    bg = border_bg(src, w, h)

    def dist(rgb):
        return max(abs(rgb[0] - bg[0]), abs(rgb[1] - bg[1]), abs(rgb[2] - bg[2]))

    vis = bytearray(w * h)
    comps = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if vis[i] or not strict_navy(src[x, y]):
                continue
            q = [(x, y)]
            vis[i] = 1
            pts = []
            while q:
                cx, cy = q.pop()
                pts.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if not (0 <= nx < w and 0 <= ny < h):
                            continue
                        j = ny * w + nx
                        if vis[j] or not strict_navy(src[nx, ny]):
                            continue
                        vis[j] = 1
                        q.append((nx, ny))
            if len(pts) >= 40:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                comps.append((pts, (min(xs), min(ys), max(xs), max(ys))))
    if not comps:
        return im

    # La stella spezza il disco in due macchie vicine: si riuniscono.
    comps.sort(key=lambda c: len(c[0]), reverse=True)
    group = [comps[0]]
    rest = comps[1:]
    changed = True
    while changed:
        changed = False
        still = []
        x0, y0, x1, y1 = group[0][1]
        for _, box in group[1:]:
            x0, y0 = min(x0, box[0]), min(y0, box[1])
            x1, y1 = max(x1, box[2]), max(y1, box[3])
        for comp in rest:
            box = comp[1]
            if box[0] <= x1 + 10 and box[2] >= x0 - 10 and box[1] <= y1 + 10 and box[3] >= y0 - 10:
                group.append(comp)
                changed = True
            else:
                still.append(comp)
        rest = still
    pts = [p for comp, _ in group for p in comp]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    rads = sorted(math.hypot(x - cx, y - cy) for x, y in pts)
    rad = rads[int(len(rads) * 0.92)] + 1.5
    rad = max(8.0, min(rad, 28.0))
    cols = [src[x, y] for x, y in pts if math.hypot(x - cx, y - cy) <= rad]
    if not cols:
        cols = [src[x, y] for x, y in pts]
    navy = tuple(sorted(c[i] for c in cols)[len(cols) // 2] for i in range(3))
    navy = (
        max(18, min(55, navy[0])),
        max(28, min(72, navy[1])),
        max(56, min(102, navy[2] + 6)),
    )
    navy_pts = set(pts)

    def near_navy(x, y, reach=5):
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                if (x + dx, y + dy) in navy_pts:
                    return True
        return False

    # Ali e stella: pixel chiari attaccati al disco, non il fondale.
    wing_w, wing_h = rad * 1.85, rad * 0.62
    for y in range(int(cy - wing_h) - 1, int(cy + wing_h) + 2):
        for x in range(int(cx - wing_w) - 1, int(cx + wing_w) + 2):
            if not (0 <= x < w and 0 <= y < h):
                continue
            dx, dy = x - cx, y - cy
            if (dx * dx) / (wing_w * wing_w) + (dy * dy) / (wing_h * wing_h) > 1:
                continue
            rgb = src[x, y]
            L = (rgb[0] + rgb[1] + rgb[2]) / 3
            if dist(rgb) <= 14 and L > 200:
                continue
            if L > 150 and max(rgb) - min(rgb) < 48 and near_navy(x, y):
                src[x, y] = navy

    draw = ImageDraw.Draw(im)
    draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=navy)
    ink = (214, 226, 234)
    station = (240, 244, 247)
    ang = math.radians(-28)
    a, b = rad * 0.70, rad * 0.32
    ca, sa = math.cos(ang), math.sin(ang)

    def rot(px, py):
        return (cx + px * ca - py * sa, cy + px * sa + py * ca)

    ring = [rot(a * math.cos(t), b * math.sin(t)) for t in (2 * math.pi * i / 72 for i in range(72))]
    draw.line(ring + [ring[0]], fill=ink, width=max(1, int(round(rad / 9))))
    hw, hh = rad * 0.16, max(0.7, rad * 0.065)
    pw, ph = rad * 0.26, max(0.6, rad * 0.038)
    draw.rectangle([cx - hw, cy - hh, cx + hw, cy + hh], fill=station)
    draw.rectangle([cx - hw - pw, cy - ph, cx - hw, cy + ph], fill=ink)
    draw.rectangle([cx + hw, cy - ph, cx + hw + pw, cy + ph], fill=ink)
    nx, ny = rot(a * 0.95, 0)
    rr = max(1.0, rad * 0.07)
    draw.ellipse([nx - rr, ny - rr, nx + rr, ny + rr], fill=ink)
    return im


def crop_pad(im, pad=8, max_h=860):
    bb = im.getbbox()
    if not bb:
        return im
    x0, y0, x1, y1 = bb
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(im.width, x1 + pad)
    y1 = min(im.height, y1 + pad)
    im = im.crop((x0, y0, x1, y1))
    if im.height > max_h:
        nh = max_h
        nw = max(1, int(im.width * nh / im.height))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    return im


def save_webp(im, path, q=80):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, 'WEBP', quality=q, method=6)
    return os.path.getsize(path)


def face_from(im):
    bb = im.getbbox()
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    bw, bh = x1 - x0, y1 - y0
    side = int(bh * 0.40)
    cx = (x0 + x1) // 2
    top = y0 + int(bh * 0.01)
    left = cx - side // 2
    left = max(0, min(left, im.width - side))
    top = max(0, min(top, im.height - side))
    face = im.crop((left, top, left + side, top + side))
    return face.resize((192, 192), Image.Resampling.LANCZOS)


def prepare(im, name):
    if name == 'livia':
        im = repaint_livia_patch(im)
    return flood_matte(im)


def main(src, dst):
    sizes = []
    for name in CAST:
        im = prepare(Image.open(os.path.join(src, 'cast-finale', name + '.jpg')), name)
        im = crop_pad(im)
        sizes.append(('cast/' + name, save_webp(im, os.path.join(dst, 'cast', name + '.webp'), 82), im.size))
        if name != 'livia':
            face = face_from(im)
            sizes.append(('faces/' + name, save_webp(face, os.path.join(dst, 'faces', name + '.webp'), 80), face.size))
    for name in EXPR_CAST:
        sheet = Image.open(os.path.join(src, 'espressioni', name + '.jpg')).convert('RGB')
        w, h = sheet.size
        fw = w // 4
        for i, expr in enumerate(EXPRS):
            panel = sheet.crop((i * fw, 0, (i + 1) * fw if i < 3 else w, h))
            panel = crop_pad(prepare(panel, name), max_h=900)
            sizes.append((
                'expr/%s-%s' % (name, expr),
                save_webp(panel, os.path.join(dst, 'expr', '%s-%s.webp' % (name, expr)), 80),
                panel.size,
            ))
    bg = Image.open(os.path.join(src, 'backgrounds', 'hangar.jpg')).convert('RGB')
    sizes.append(('bg/hangar', save_webp(bg, os.path.join(dst, 'bg', 'hangar.webp'), 78), bg.size))
    for n, sz, dim in sizes:
        print('%s %4dx%-4d %7.1f KB' % (n.ljust(28), dim[0], dim[1], sz / 1024))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
