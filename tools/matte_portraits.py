# -*- coding: utf-8 -*-
"""Scontorno dei ritratti (flood-fill dai bordi) e taglio dei fogli espressione.

I fogli sono 4 pose affiancate, in ordine: neutra, sorpresa, arrabbiata, preoccupata.
Lo sfondo bianco/grigio si toglie solo se è collegato al bordo, così camici e
luci interne restano. Uso: python3 matte_portraits.py /percorso/sorgenti /percorso/assets
"""
import os, sys
from PIL import Image

EXPRS = ('neutral', 'surprised', 'angry', 'worried')
CAST = ('livia', 'vasquez', 'brenner', 'okafor', 'nadia', 'halvorsen', 'mei')
# espressioni usate negli interludi; i volti in griglia escono dal ritratto intero
EXPR_CAST = ('livia', 'vasquez')


def flood_matte(im, tol=16):
    im = im.convert('RGB')
    w, h = im.size
    src = im.tobytes()
    # campiona il bordo per il colore di sfondo
    samp = []
    def px(x, y):
        i = (y * w + x) * 3
        return src[i], src[i + 1], src[i + 2]
    for x in range(0, w, 6):
        samp.append(px(x, 0)); samp.append(px(x, h - 1))
    for y in range(0, h, 6):
        samp.append(px(0, y)); samp.append(px(w - 1, y))
    bg = tuple(sorted(s[i] for s in samp)[len(samp) // 2] for i in range(3))

    def dist(x, y):
        r, g, b = px(x, y)
        return max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2]))

    seen = bytearray(w * h)
    stack = []
    def try_add(x, y):
        if x < 0 or y < 0 or x >= w or y >= h:
            return
        i = y * w + x
        if seen[i]:
            return
        if dist(x, y) <= tol:
            seen[i] = 1
            stack.append((x, y))
    for x in range(w):
        try_add(x, 0); try_add(x, h - 1)
    for y in range(h):
        try_add(0, y); try_add(w - 1, y)
    while stack:
        x, y = stack.pop()
        try_add(x + 1, y); try_add(x - 1, y); try_add(x, y + 1); try_add(x, y - 1)

    out = im.convert('RGBA')
    op = out.load()
    # alone: i pixel chiari attaccati allo sfondo diventano semitrasparenti, non i bianchi interni
    band = 28
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i]:
                op[x, y] = (0, 0, 0, 0)
                continue
            d = dist(x, y)
            if d >= tol + band:
                continue
            edge = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h and seen[yy * w + xx]:
                    edge = True
                    break
            if edge:
                a = int(255 * (d - tol) / band) if d > tol else 0
                r, g, b, _ = op[x, y]
                op[x, y] = (r, g, b, max(0, min(255, a)))
    return out


def crop_pad(im, pad=8, max_h=860):
    bb = im.getbbox()
    if not bb:
        return im
    x0, y0, x1, y1 = bb
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(im.width, x1 + pad); y1 = min(im.height, y1 + pad)
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


def main(src, dst):
    sizes = []
    for name in CAST:
        im = flood_matte(Image.open(os.path.join(src, 'cast-finale', name + '.jpg')))
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
            panel = crop_pad(flood_matte(panel), max_h=900)
            sizes.append((f'expr/{name}-{expr}', save_webp(panel, os.path.join(dst, 'expr', f'{name}-{expr}.webp'), 80), panel.size))
    bg = Image.open(os.path.join(src, 'backgrounds', 'hangar.jpg')).convert('RGB')
    sizes.append(('bg/hangar', save_webp(bg, os.path.join(dst, 'bg', 'hangar.webp'), 78), bg.size))
    for n, sz, dim in sizes:
        print(f'{n:28} {dim[0]:4}x{dim[1]:<4} {sz/1024:7.1f} KB')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
