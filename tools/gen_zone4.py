#!/usr/bin/env python3
"""Генератор арта зоны 4 «Космос» и финала (SVG): спутники, станция, астероиды, Луна, Земля, звёздный фон.

Запуск из корня проекта:  python tools/gen_zone4.py

Пишет в design/zone-4-space/:
  objects/    z4-sat-a|b      спутники (панели и антенна; шар с антеннами)
              z4-station      космическая станция (ферма, модули, панели)
              z4-rock-a|b|c   астероиды (три формы с кратерами)
              z4-moon         Луна (512×512, кратеры)
              z4-earth        Земля (512×512, океан, материки, облака, свечение атмосферы)
  background/ bg-z4-stars-a   бесшовная плитка звёзд 512×512 (мелкие и яркие)
              bg-z4-stars-b   бесшовная плитка звёзд 256×256 (дальний слой)

Контур 4,2 px, свет сверху слева. Без текста, флагов, эмблем и людей; Земля нарисована условными материками (без контуров реальных стран).
Рисунки руками не правим: меняем параметры и перегенерируем.
"""
import math
import random

from svgkit import ROOT, OUTLINE, mix, lighten, rgrad, svg
from z2kit import OUT, OUT_S, rr, circ, ell, path, poly, line, hi, lg, fillg, sprite

Z4 = ROOT / 'design' / 'zone-4-space'


def _w(path_, text):
    from svgkit import write as w
    w(path_, text)


def panel(defs, x, y, w, h, cols, rows):
    """Солнечная панель: синее стекло с сеткой."""
    g = lg(defs, '#4AA3F0', '#1E56B8')
    out = [rr(x, y, w, h, 3, g, OUT_S)]
    for i in range(1, cols):
        out.append(line(x + w * i / cols, y, x + w * i / cols, y + h, '#BFE3FA', 1.6, 0.8))
    for j in range(1, rows):
        out.append(line(x, y + h * j / rows, x + w, y + h * j / rows, '#BFE3FA', 1.6, 0.8))
    out.append(f'<path d="M {x + 4:.1f} {y + h - 4:.1f} L {x + w * 0.35:.1f} {y + 4:.1f} L {x + w * 0.5:.1f} {y + 4:.1f} L {x + 18:.1f} {y + h - 4:.1f} Z" fill="#FFFFFF" fill-opacity=".22"/>')
    return ''.join(out)


# ---------------------------------------------------------------- спутники
def sat_a():
    W, H = 260, 166
    defs = []
    gold = fillg(defs, '#F7C93A', 0.35, 0.22)
    steel = fillg(defs, '#C5CFE2', 0.2, 0.2)
    parts = []
    parts.append(line(88, 76, 38, 76, OUTLINE, 9))
    parts.append(line(172, 76, 222, 76, OUTLINE, 9))
    parts.append(line(88, 76, 38, 76, '#8693AD', 4))
    parts.append(line(172, 76, 222, 76, '#8693AD', 4))
    parts.append(panel(defs, 6, 46, 82, 60, 4, 3))
    parts.append(panel(defs, 172, 46, 82, 60, 4, 3))
    # корпус
    parts.append(rr(88, 44, 84, 64, 10, gold, OUT))
    parts.append(rr(96, 54, 68, 10, 4, '#FFFFFF', 0, 'fill-opacity=".38"'))
    parts.append(rr(100, 82, 20, 14, 4, '#3A3F4F', OUT_S))
    parts.append(rr(130, 82, 24, 14, 4, steel, OUT_S))
    # антенна-тарелка
    parts.append(line(130, 44, 130, 24, OUTLINE, 6))
    parts.append(line(130, 44, 130, 24, '#8693AD', 2.4))
    parts.append(path('M 104 22 Q 130 -2 156 22 Q 130 34 104 22 Z', steel, OUT_S + 0.4))
    parts.append(circ(130, 10, 4.5, '#E9503F', 2.4))
    parts.append(line(172, 56, 196, 24, OUTLINE, 4))
    parts.append(circ(198, 21, 5, '#FFF2A8', 2.4))
    return sprite(W, H, defs, ['<g transform="translate(0 16)">' + ''.join(parts) + '</g>'])


def sat_b():
    W, H = 220, 220
    defs = []
    sphere = rgrad('sat-sph', [(0, '#F4F7FC'), (1, '#8E9BB5')])
    defs.append(sphere)
    parts = []
    for ang in (30, 150, 210, 330):
        a = math.radians(ang)
        x2, y2 = 110 + math.cos(a) * 100, 110 + math.sin(a) * 100
        parts.append(line(110 + math.cos(a) * 40, 110 + math.sin(a) * 40, x2, y2, OUTLINE, 6))
        parts.append(line(110 + math.cos(a) * 40, 110 + math.sin(a) * 40, x2, y2, '#8693AD', 2.4))
        parts.append(circ(x2, y2, 8, '#FFD23F', OUT_S))
    parts.append(f'<circle cx="110" cy="110" r="52" fill="url(#sat-sph)" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    parts.append(f'<path d="M 60 96 Q 110 116 160 96" fill="none" stroke="#3FA9D9" stroke-width="9"/>')
    parts.append(f'<path d="M 62 124 Q 110 142 158 124" fill="none" stroke="#3FA9D9" stroke-width="9"/>')
    parts.append(f'<ellipse cx="92" cy="86" rx="16" ry="9" fill="#FFFFFF" fill-opacity=".55" transform="rotate(-28 92 86)"/>')
    parts.append(circ(110, 110, 11, '#2F3548', OUT_S))
    parts.append(circ(106, 106, 4, '#BFE3FA', 0))
    return sprite(W, H, defs, parts)


def station():
    W, H = 480, 220
    defs = []
    white = fillg(defs, '#F2F4F8', 0.0, 0.16)
    steel = fillg(defs, '#B7C2D6', 0.2, 0.22)
    orange = fillg(defs, '#F28A2E', 0.25, 0.2)
    parts = []
    # ферма
    parts.append(rr(24, 104, 432, 14, 5, steel, OUT))
    for x in range(40, 450, 36):
        parts.append(line(x, 104, x + 18, 118, OUTLINE, 2.2, 0.7))
        parts.append(line(x + 18, 104, x, 118, OUTLINE, 2.2, 0.7))
    # панели: две пары слева и справа
    for x in (24, 104, 304, 384):
        parts.append(line(x + 36, 104, x + 36, 80, OUTLINE, 6))
        parts.append(panel(defs, x, 10, 72, 70, 3, 3))
        parts.append(line(x + 36, 118, x + 36, 142, OUTLINE, 6))
        parts.append(panel(defs, x, 142, 72, 70, 3, 3))
    # модули
    parts.append(rr(150, 90, 180, 42, 18, white, OUT))
    parts.append(rr(168, 90, 14, 42, 0, orange, 0, 'fill-opacity=".95"'))
    parts.append(rr(300, 90, 14, 42, 0, orange, 0, 'fill-opacity=".95"'))
    parts.append(rr(206, 70, 70, 22, 10, steel, OUT))
    parts.append(rr(206, 130, 70, 22, 10, steel, OUT))
    parts.append(rr(124, 98, 34, 26, 8, steel, OUT_S + 0.6))
    parts.append(rr(322, 98, 34, 26, 8, steel, OUT_S + 0.6))
    parts.append(hi(174, 96, 130, 5, op=0.5))
    for x in (194, 224, 254, 284):
        parts.append(circ(x, 112, 6, lg(defs, '#D8F2FF', '#6FB8EE'), 2.4))
    # купол-обзорник
    parts.append(path('M 226 70 Q 240 52 256 70 Z', lg(defs, '#BFE3FA', '#5FAEE6'), OUT_S))
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- астероиды
def rock(seed, fillc, darkc, lumps=11):
    rnd = random.Random(seed)
    W = H = 280
    cx = cy = 140
    defs = []
    g = rgrad(f'rock{seed}', [(0, lighten(fillc, 0.25)), (1, darkc)], 0.38, 0.32, 0.9)
    defs.append(g)
    pts = []
    for i in range(lumps):
        a = 2 * math.pi * i / lumps + rnd.uniform(-0.12, 0.12)
        r = rnd.uniform(96, 126)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    # сглаженный контур через середины отрезков
    mids = [((pts[i][0] + pts[(i + 1) % lumps][0]) / 2, (pts[i][1] + pts[(i + 1) % lumps][1]) / 2) for i in range(lumps)]
    d = f'M {mids[-1][0]:.1f} {mids[-1][1]:.1f} ' + ' '.join(f'Q {pts[i][0]:.1f} {pts[i][1]:.1f} {mids[i][0]:.1f} {mids[i][1]:.1f}' for i in range(lumps)) + ' Z'
    parts = [f'<path d="{d}" fill="url(#rock{seed})" stroke="{OUTLINE}" stroke-width="{OUT + 0.6}" stroke-linejoin="round"/>']
    for _ in range(5):
        a = rnd.uniform(0, 2 * math.pi)
        rr_ = rnd.uniform(18, 66)
        x, y = cx + math.cos(a) * rr_, cy + math.sin(a) * rr_
        s = rnd.uniform(12, 24)
        parts.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{s:.1f}" ry="{s * 0.78:.1f}" fill="{darkc}" fill-opacity=".75" stroke="{OUTLINE}" stroke-width="2.6"/>')
        parts.append(f'<path d="M {x - s * 0.8:.1f} {y + s * 0.1:.1f} Q {x - s * 0.6:.1f} {y - s * 0.7:.1f} {x + s * 0.4:.1f} {y - s * 0.7:.1f}" fill="none" stroke="#FFFFFF" stroke-opacity=".38" stroke-width="3" stroke-linecap="round"/>')
    parts.append(f'<ellipse cx="108" cy="86" rx="30" ry="13" fill="#FFFFFF" fill-opacity=".3" transform="rotate(-30 108 86)"/>')
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- Луна и Земля
def moon():
    S = 512
    c = 256
    R = 236
    defs = [rgrad('moon-g', [(0, '#F5F2EA'), (0.6, '#D4CFC3'), (1, '#9C9488')], 0.36, 0.3, 0.95)]
    parts = [f'<circle cx="{c}" cy="{c}" r="{R}" fill="url(#moon-g)" stroke="{OUTLINE}" stroke-width="9"/>']
    craters = [(170, 160, 46), (330, 130, 30), (320, 300, 62), (170, 330, 36), (250, 240, 22), (390, 230, 24), (220, 410, 28), (110, 250, 20), (380, 380, 26)]
    for (x, y, r) in craters:
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#A8A092" fill-opacity=".85" stroke="{OUTLINE}" stroke-width="4.2"/>')
        parts.append(f'<path d="M {x - r * 0.75:.1f} {y + r * 0.1:.1f} Q {x - r * 0.55:.1f} {y - r * 0.8:.1f} {x + r * 0.45:.1f} {y - r * 0.75:.1f}" fill="none" stroke="#FFFFFF" stroke-opacity=".5" stroke-width="5" stroke-linecap="round"/>')
    parts.append(f'<ellipse cx="170" cy="96" rx="76" ry="30" fill="#FFFFFF" fill-opacity=".28" transform="rotate(-28 170 96)"/>')
    # тень справа внизу
    parts.append(f'<path d="M 440 150 A 236 236 0 0 1 150 470 A 258 258 0 0 0 440 150 Z" fill="#000000" fill-opacity=".1"/>')
    return svg(S, defs, ''.join(parts))


def earth():
    S = 512
    c = 256
    R = 226
    defs = [rgrad('earth-g', [(0, '#7FD0FF'), (0.55, '#3C97E8'), (1, '#1F5FBF')], 0.36, 0.3, 0.98),
            f'<clipPath id="earth-clip"><circle cx="{c}" cy="{c}" r="{R}"/></clipPath>']
    parts = []
    # свечение атмосферы: два мягких кольца за шаром
    parts.append(f'<circle cx="{c}" cy="{c}" r="{R + 22}" fill="#9BD8FF" fill-opacity=".28"/>')
    parts.append(f'<circle cx="{c}" cy="{c}" r="{R + 11}" fill="#BFE9FF" fill-opacity=".4"/>')
    parts.append(f'<circle cx="{c}" cy="{c}" r="{R}" fill="url(#earth-g)" stroke="{OUTLINE}" stroke-width="9"/>')
    land = '#6FCB6A'
    land_dark = '#4FA84E'
    sand = '#E7C77B'
    cont = [
        # условные материки, не повторяют реальных очертаний
        'M 120 150 Q 150 100 220 112 Q 262 120 240 170 Q 214 210 186 232 Q 150 250 126 214 Q 104 184 120 150 Z',
        'M 300 190 Q 360 150 410 190 Q 440 232 404 276 Q 372 316 334 296 Q 290 270 292 232 Q 288 204 300 190 Z',
        'M 170 330 Q 210 300 252 330 Q 276 372 246 420 Q 210 446 176 408 Q 150 366 170 330 Z',
        'M 360 360 Q 394 340 416 366 Q 410 400 380 410 Q 352 396 360 360 Z',
    ]
    parts.append('<g clip-path="url(#earth-clip)">')
    for d in cont:
        parts.append(f'<path d="{d}" fill="{land}" stroke="{OUTLINE}" stroke-width="5" stroke-linejoin="round"/>')
        parts.append(f'<path d="{d}" fill="{land_dark}" fill-opacity=".35" transform="translate(6 8) scale(.97)"/>')
    parts.append(f'<ellipse cx="226" cy="190" rx="22" ry="12" fill="{sand}" fill-opacity=".9"/>')
    parts.append(f'<ellipse cx="364" cy="236" rx="26" ry="14" fill="{sand}" fill-opacity=".9"/>')
    # облака
    for (x, y, w) in ((150, 120, 80), (330, 110, 70), (250, 270, 90), (140, 300, 60), (370, 330, 74), (260, 400, 80)):
        parts.append(f'<path d="M {x} {y} q {w * 0.1} -{w * 0.22} {w * 0.3} -{w * 0.14} q {w * 0.18} -{w * 0.22} {w * 0.38} -{w * 0.02} q {w * 0.3} {w * 0.0} {w * 0.3} {w * 0.18} q -{w * 0.1} {w * 0.12} -{w * 0.3} {w * 0.1} z" fill="#FFFFFF" fill-opacity=".92" stroke="{OUTLINE}" stroke-width="3.2" stroke-linejoin="round"/>')
    # блик и тень
    parts.append(f'<ellipse cx="170" cy="100" rx="86" ry="34" fill="#FFFFFF" fill-opacity=".3" transform="rotate(-30 170 100)"/>')
    parts.append(f'<path d="M 450 150 A 226 226 0 0 1 150 470 A 250 250 0 0 0 450 150 Z" fill="#0B2A66" fill-opacity=".22"/>')
    parts.append('</g>')
    return svg(S, defs, ''.join(parts))


# ---------------------------------------------------------------- звёздные плитки
def stars(size, seed, count, bright):
    rnd = random.Random(seed)
    cols = ['#FFFFFF', '#FFF2A8', '#BFE3FA', '#FFD9F0']
    parts = []
    for _ in range(count):
        x, y = rnd.uniform(0, size), rnd.uniform(0, size)
        r = rnd.choice((1.0, 1.2, 1.6, 2.0)) * (1.3 if bright else 1.0)
        col = rnd.choice(cols)
        op = rnd.uniform(0.55, 1.0)
        for dx in (-size, 0, size):
            for dy in (-size, 0, size):
                xx, yy = x + dx, y + dy
                if -6 < xx < size + 6 and -6 < yy < size + 6:
                    parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="{op:.2f}"/>')
    if bright:
        for _ in range(6):
            x, y = rnd.uniform(10, size - 10), rnd.uniform(10, size - 10)
            s = rnd.uniform(7, 11)
            for dx in (-size, 0, size):
                for dy in (-size, 0, size):
                    xx, yy = x + dx, y + dy
                    if -14 < xx < size + 14 and -14 < yy < size + 14:
                        parts.append(f'<path d="M {xx:.1f} {yy - s:.1f} Q {xx:.1f} {yy:.1f} {xx + s:.1f} {yy:.1f} Q {xx:.1f} {yy:.1f} {xx:.1f} {yy + s:.1f} '
                                     f'Q {xx:.1f} {yy:.1f} {xx - s:.1f} {yy:.1f} Q {xx:.1f} {yy:.1f} {xx:.1f} {yy - s:.1f} Z" fill="#FFFFFF" fill-opacity=".9"/>')
    return svg(size, [], ''.join(parts))


def main():
    out = Z4 / 'objects'
    _w(out / 'z4-sat-a.svg', sat_a())
    _w(out / 'z4-sat-b.svg', sat_b())
    _w(out / 'z4-station.svg', station())
    _w(out / 'z4-rock-a.svg', rock(3, '#B79B7A', '#6E5A44', 11))
    _w(out / 'z4-rock-b.svg', rock(8, '#A9A7AC', '#5F5D66', 12))
    _w(out / 'z4-rock-c.svg', rock(21, '#C48B63', '#7A4B34', 10))
    _w(out / 'z4-moon.svg', moon())
    _w(out / 'z4-earth.svg', earth())
    _w(Z4 / 'background' / 'bg-z4-stars-a.svg', stars(512, 5, 70, True))
    _w(Z4 / 'background' / 'bg-z4-stars-b.svg', stars(256, 9, 46, False))
    print('zone 4: written 10 svg files')


if __name__ == '__main__':
    main()
