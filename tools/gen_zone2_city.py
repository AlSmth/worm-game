"""Дома, многоэтажки, башни и фон зоны 2 (часть gen_zone2.py).

Здания без религиозных форм: нет куполов, шпилей-колоколен, крестообразных рам и антенн с перекладинами; окна простые
(без крестовин), антенны одиночные мачты. Стены светлые, чтобы читались на фоне неба и травы. Контур как у остальной графики.
"""
import math
import random

from svgkit import OUTLINE, mix, lighten, svgwh
import z2kit as k
from z2kit import PAD, OUT, OUT_S, rr, circ, ell, path, poly, line, hi, glass, lg, fillg, sprite

WALLS = {'cream': '#FBE7B5', 'blue': '#BFE0F7', 'salmon': '#F2B6A0', 'sage': '#B7D6A5', 'beige': '#EAD9B8', 'pink': '#F2C2C9'}
ROOFS = {'red': '#D9493B', 'brown': '#8C5A3C'}


def house_a(wall, roof):
    W, H = 320, 256
    gy = H - PAD
    defs = []
    wl = fillg(defs, WALLS[wall], 0.3, 0.12)
    rf = fillg(defs, ROOFS[roof], 0.25, 0.25)
    brick = fillg(defs, '#B5614A')
    door = fillg(defs, '#8C5A3C')
    parts = [rr(220, 44, 28, 62, 3, brick, OUT), rr(215, 36, 38, 12, 4, '#8E4A38', OUT_S)]          # труба
    parts.append(rr(36, 124, 248, gy - 124, 6, wl, OUT))                                              # стена
    parts.append(poly([(12, 134), (160, 28), (308, 134)], rf, OUT))                                    # крыша
    parts.append(f'<path d="M 40 122 L 150 44 L 160 50 L 56 128 Z" fill="#FFFFFF" fill-opacity=".22"/>')
    for i in range(3):                                                                                 # черепица
        y = 70 + i * 20
        parts.append(line(160 - (y - 28) * 1.35 + 10, y, 160 + (y - 28) * 1.35 - 10, y, OUTLINE, 2.4, 0.3))
    parts.append(circ(160, 84, 13, '#CFEFFF', OUT_S))                                                  # круглое окно
    parts.append(hi(154, 76, 6, 10, op=0.6))
    for x in (64, 204):
        parts.append(glass(defs, x, 150, 54, 46))
        parts.append(rr(x - 6, 196, 66, 9, 3, '#8C5A3C', 2.6))
        for j, c in enumerate(('#FF7A8A', '#FFD23F', '#FF7A8A', '#FFD23F')):                          # цветы на подоконнике
            parts.append(circ(x + 6 + j * 14, 192, 4.5, c, 1.8))
    parts.append(rr(138, 176, 44, gy - 176, 8, door, OUT))
    parts.append(circ(173, 214, 3.4, '#FFE27A', 1.8))
    parts.append(hi(144, 184, 8, 46, op=0.3))
    parts.append(rr(126, gy - 8, 68, 8, 3, '#B7C2D6', OUT_S))
    return sprite(W, H, defs, parts)


def house_b(wall):
    W, H = 288, 320
    gy = H - PAD
    defs = []
    wl = fillg(defs, WALLS[wall], 0.3, 0.12)
    roof = fillg(defs, '#7E8AA3', 0.2, 0.25)
    door = fillg(defs, '#8C5A3C')
    awn = fillg(defs, '#E9503F')
    parts = [rr(190, 40, 28, 30, 3, '#B5614A', OUT_S)]
    parts.append(rr(30, 90, 228, gy - 90, 6, wl, OUT))
    parts.append(rr(20, 66, 248, 30, 6, roof, OUT))                                                    # плоская крыша с бортиком
    parts.append(hi(28, 70, 232, 7, op=0.35))
    parts.append(line(30, 198, 258, 198, OUTLINE, 2.6, 0.4))                                           # межэтажный пояс
    for x in (50, 126, 202):
        parts.append(glass(defs, x, 112, 36, 52))
        parts.append(rr(x - 4, 164, 44, 7, 3, '#8C5A3C', 2.4))
    for x in (50, 202):
        parts.append(glass(defs, x, 218, 36, 56))
    parts.append(rr(116, 226, 56, gy - 226, 8, door, OUT))
    parts.append(circ(162, 272, 3.2, '#FFE27A', 1.8))
    parts.append(poly([(104, 226), (184, 226), (192, 208), (96, 208)], awn, OUT))                      # навес
    parts.append(rr(100, gy - 8, 88, 8, 3, '#B7C2D6', OUT_S))
    return sprite(W, H, defs, parts)


def apartment(wall, seed):
    W, H = 256, 448
    gy = H - PAD
    rnd = random.Random(seed)
    defs = []
    wl = fillg(defs, WALLS[wall], 0.3, 0.14)
    parts = [rr(60, 22, 60, 28, 4, '#9AA3B8', OUT_S), rr(152, 12, 42, 40, 6, '#B7C2D6', OUT_S)]        # крышные надстройки
    parts.append(rr(24, 44, 208, gy - 44, 8, wl, OUT))
    parts.append(rr(24, 44, 208, 12, 4, '#8E97AD', OUT_S))
    rows = 8
    for j in range(rows):
        for i in range(4):
            parts.append(glass(defs, 44 + i * 48, 70 + j * 42, 30, 28, lit=rnd.random() < 0.3, r=3))
    parts.append(hi(28, 60, 8, gy - 90, op=0.3))
    parts.append(rr(94, gy - 44, 68, 44, 6, '#5B6178', OUT))
    parts.append(poly([(86, gy - 44), (170, gy - 44), (176, gy - 58), (80, gy - 58)], '#E9503F', OUT_S))
    return sprite(W, H, defs, parts)


def tower():
    """Офисная башня с зеркальным фасадом: горизонтальные ленты окон."""
    W, H = 224, 640
    gy = H - PAD
    defs = []
    body = lg(defs, '#7FD3E6', '#2F8FB0')
    parts = [line(112, 6, 112, 46, OUTLINE, 5)]
    parts.append(circ(112, 8, 6, '#FFE27A', OUT_S))
    parts.append(rr(62, 40, 100, 52, 6, body, OUT))
    parts.append(rr(22, 84, 180, gy - 84, 6, body, OUT))
    for j in range(18):
        y = 100 + j * 30
        parts.append(rr(34, y, 156, 18, 3, '#CFF2FF', 2.4))
        for x in (66, 98, 130, 162):
            parts.append(line(x, y + 2, x, y + 16, OUTLINE, 1.6, 0.25))
    parts.append(f'<path d="M 30 90 L 90 90 L 30 300 Z" fill="#FFFFFF" fill-opacity=".18"/>')
    parts.append(rr(84, gy - 46, 56, 46, 6, '#3A4A66', OUT))
    return sprite(W, H, defs, parts)


def skyscraper():
    W, H = 192, 768
    gy = H - PAD
    defs = []
    body = lg(defs, '#B7C6F2', '#5E78C8')
    parts = [line(96, 4, 96, 46, OUTLINE, 5), circ(96, 6, 5, '#FFE27A', OUT_S)]
    parts.append(rr(70, 38, 52, 52, 6, body, OUT))
    parts.append(rr(48, 84, 96, 64, 6, body, OUT))
    parts.append(rr(26, 142, 140, gy - 142, 8, body, OUT))
    for j in range(22):
        y = 158 + j * 27
        parts.append(rr(36, y, 120, 15, 3, '#E3ECFF', 2.2))
        for x in (66, 96, 126):
            parts.append(line(x, y + 2, x, y + 13, OUTLINE, 1.5, 0.22))
    parts.append(f'<path d="M 34 150 L 84 150 L 34 420 Z" fill="#FFFFFF" fill-opacity=".2"/>')
    parts.append(rr(72, gy - 50, 48, 50, 6, '#3A4A66', OUT))
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- фон
def skyline(seed=11):
    """Дальние дома: силуэты в дымке, бесшовная полоса 1024×512; нижний край = линия земли."""
    W, H = 1024, 512
    rnd = random.Random(seed)
    defs = []
    out = []
    x = 0
    while x < W:
        w = min(W - x, rnd.randint(46, 120))
        if W - x - w < 46:
            w = W - x
        h = rnd.choice([90, 120, 150, 190, 230, 280, 340, 420])
        h = int(h * rnd.uniform(0.8, 1.15))
        base = mix('#9FC4E8', '#C9E1F5', rnd.random() * 0.6)
        g = lg(defs, lighten(base, 0.25), base)
        out.append(f'<rect x="{x}" y="{H - h}" width="{w}" height="{h}" fill="{g}"/>')
        out.append(f'<rect x="{x}" y="{H - h}" width="{w}" height="6" fill="#FFFFFF" fill-opacity=".25"/>')
        cols = max(1, (w - 12) // 16)
        rows = max(1, (h - 30) // 24)
        for j in range(rows):
            for i in range(cols):
                if rnd.random() < 0.55:
                    out.append(f'<rect x="{x + 8 + i * 16}" y="{H - h + 14 + j * 24}" width="8" height="12" fill="#FFFFFF" fill-opacity=".4"/>')
        if rnd.random() < 0.3 and w > 50:
            out.append(f'<rect x="{x + w / 2 - 1.5}" y="{H - h - 26}" width="3" height="26" fill="#A9CBEA"/>')
        x += w
    return svgwh(W, H, defs, ''.join(out))


def hills(seed=5):
    """Холмы с деревьями: периодические кривые, поэтому полоса 1024×256 повторяется без шва."""
    W, H = 1024, 256
    rnd = random.Random(seed)
    defs = []

    def curve(base, a1, a2, p1, p2):
        pts = []
        for i in range(0, W + 1, 8):
            t = i / W * math.pi * 2
            pts.append((i, base + a1 * math.sin(t * 2 + p1) + a2 * math.sin(t * 5 + p2)))
        return 'M ' + ' L '.join(f'{x} {y:.1f}' for x, y in pts) + f' L {W} {H} L 0 {H} Z', pts

    out = []
    layers = [(120, 34, 12, 0.4, 1.7, '#8FD07A', '#6DB85E'), (172, 26, 10, 2.2, 0.3, '#6DBE5A', '#4FA14A')]
    for base, a1, a2, p1, p2, c1, c2 in layers:
        d, pts = curve(base, a1, a2, p1, p2)
        g = lg(defs, c1, c2)
        out.append(f'<path d="{d}" fill="{g}"/>')
        for _ in range(9):
            tx = rnd.randint(20, W - 20)
            ty = base + a1 * math.sin(tx / W * math.pi * 2 * 2 + p1) + a2 * math.sin(tx / W * math.pi * 2 * 5 + p2)
            r = rnd.randint(9, 15)
            out.append(f'<rect x="{tx - 2}" y="{ty - 4:.1f}" width="4" height="{r * 0.9:.1f}" fill="#8C5A3C"/>')
            out.append(f'<circle cx="{tx}" cy="{ty - r * 0.6:.1f}" r="{r}" fill="{c2}"/>')
            out.append(f'<circle cx="{tx - r * 0.3:.1f}" cy="{ty - r * 0.9:.1f}" r="{r * 0.4:.1f}" fill="#FFFFFF" fill-opacity=".2"/>')
    return svgwh(W, H, defs, ''.join(out))


def main(write, Z2):
    n = 0
    for wall, roof in (('cream', 'red'), ('blue', 'brown')):
        write(Z2 / 'houses' / f'z2-house-a-{wall}.svg', house_a(wall, roof))
        n += 1
    for wall in ('salmon', 'sage'):
        write(Z2 / 'houses' / f'z2-house-b-{wall}.svg', house_b(wall))
        n += 1
    for i, wall in enumerate(('beige', 'pink')):
        write(Z2 / 'houses' / f'z2-apartment-{wall}.svg', apartment(wall, 40 + i))
        n += 1
    write(Z2 / 'houses' / 'z2-tower.svg', tower())
    write(Z2 / 'houses' / 'z2-skyscraper.svg', skyscraper())
    write(Z2 / 'background' / 'bg-z2-skyline.svg', skyline())
    write(Z2 / 'background' / 'bg-z2-hills.svg', hills())
    return n + 4
