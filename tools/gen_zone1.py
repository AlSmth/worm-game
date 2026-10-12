#!/usr/bin/env python3
"""Генератор фона зоны 1 «Под землёй» (SVG): дальний, средний и ближний слои почвы, кромка с травой, облака.

Запуск из корня проекта:  python tools/gen_zone1.py

Слои бесшовные: дальний и ближний повторяются по обеим осям, кромка и облака только по горизонтали.
  bg-z1-far     1024×512    мягкие пласты и пятна, сплошной коричневый фон (без контуров)
  bg-z1-mid     1024×1024   камни и корни с контуром, прозрачный (параллакс 0,65)
  bg-z1-near    1024×1024   мелкие камешки, песчинки и ракушки, прозрачный (стоит на месте с миром)
  bg-z1-edge    1024×512    трава на линии земли, корешки под ней; линия земли на y = 190
  bg-z1-clouds  2048×512    облака для неба над землёй (параллакс 0,15)
Размеры мира: рисунок 1:1 = пиксели мира при масштабе червя 1. Игра не масштабирует фон вместе с червём:
по мере роста камера отъезжает, и почва становится мельче, как задумал автор («сначала масштаб земли»).
Без костей и других тревожных деталей (пп. 3.4.3, 8.3.6): только камни, корни и ракушки.
"""
import math
import random

from svgkit import ROOT, OUTLINE, mix, lighten, write

OUT_DIR = ROOT / 'design' / 'zone-1-underground' / 'background'
GROUND_Y = 190   # линия земли на полосе кромки


def svg_rect(w, h, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            f'<defs>{"".join(defs)}</defs>\n{body}\n</svg>\n')


class Tile:
    """Холст-плитка: фигуры у края дублируются с противоположной стороны, чтобы шов не был виден."""

    def __init__(self, w, h, wrap_y=True):
        self.w, self.h, self.wrap_y = w, h, wrap_y
        self.defs, self.parts, self.n = [], [], 0

    def uid(self, prefix='g'):
        self.n += 1
        return f'{prefix}{self.n}'

    def add(self, shape, cx, cy, rx, ry=None):
        ry = rx if ry is None else ry
        xs, ys = [0], [0]
        if cx - rx < 0:
            xs.append(self.w)
        if cx + rx > self.w:
            xs.append(-self.w)
        if self.wrap_y:
            if cy - ry < 0:
                ys.append(self.h)
            if cy + ry > self.h:
                ys.append(-self.h)
        for dx in xs:
            for dy in ys:
                self.parts.append(shape if dx == 0 and dy == 0 else f'<g transform="translate({dx} {dy})">{shape}</g>')

    def render(self, base=None):
        body = ''
        if base:
            body += f'<rect width="{self.w}" height="{self.h}" fill="{base}"/>'
        return svg_rect(self.w, self.h, self.defs, body + ''.join(self.parts))


def smooth_closed(pts):
    """Замкнутая гладкая кривая через точки (Catmull-Rom в кубические Безье)."""
    n = len(pts)
    d = f'M {pts[0][0]:.1f} {pts[0][1]:.1f}'
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f' C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}'
    return d + ' Z'


def blob(cx, cy, rx, ry, rnd, n=9, jitter=0.16, rot=0.0):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + rnd.uniform(-jitter, jitter)
        x, y = rx * k * math.cos(a), ry * k * math.sin(a)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    return smooth_closed(pts)


def wavy(x0, y0, x1, amp, periods, steps=48, phase=0.0):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((x0 + (x1 - x0) * t, y0 + amp * math.sin(2 * math.pi * periods * t + phase)))
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts)


# ---------- дальний слой ----------
def far():
    W, H = 1024, 512
    t = Tile(W, H)
    rnd = random.Random(11)
    t.defs.append('<radialGradient id="fl"><stop offset="0" stop-color="#8A5F40" stop-opacity=".62"/>'
                  '<stop offset="1" stop-color="#7B5438" stop-opacity="0"/></radialGradient>')
    t.defs.append('<radialGradient id="fd"><stop offset="0" stop-color="#2E1D16" stop-opacity=".62"/>'
                  '<stop offset="1" stop-color="#2E1D16" stop-opacity="0"/></radialGradient>')
    for i in range(20):
        cx, cy = rnd.uniform(0, W), rnd.uniform(0, H)
        rx, ry = rnd.uniform(90, 230), rnd.uniform(50, 120)
        g = 'fl' if i % 2 == 0 else 'fd'
        t.add(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" fill="url(#{g})"/>', cx, cy, rx, ry)
    # пласты: волнистые полосы, период укладывается в ширину плитки
    for y, amp, per, wid, col, op in ((70, 14, 2, 30, '#4A2F1F', .24), (190, 20, 1, 44, '#8A5F40', .24),
                                      (320, 12, 3, 26, '#4A2F1F', .22), (440, 18, 2, 38, '#8A5F40', .22)):
        t.add(f'<path d="{wavy(-4, y, W + 4, amp, per, phase=y)}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{wid}"/>',
              W / 2, y, W, amp + wid)
    return t.render(base='#6A4630')


# ---------- средний слой ----------
STONES = [('#B09A87', '#74604F'), ('#A38E7C', '#6A5646'), ('#BCA894', '#806B58'), ('#978272', '#5F4B3D')]


def mid():
    W, H = 1024, 1024
    t = Tile(W, H)
    rnd = random.Random(23)
    # корни: толстые извилистые ветви с обводкой, у каждой одна-две веточки
    for i in range(6):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ang = rnd.uniform(0, 2 * math.pi)
        pts = [(x, y)]
        for _ in range(4):
            ang += rnd.uniform(-0.7, 0.7)
            x += math.cos(ang) * rnd.uniform(60, 120)
            y += math.sin(ang) * rnd.uniform(60, 120)
            pts.append((x, y))
        d = 'M ' + ' '.join((f'{px:.0f} {py:.0f}' if j == 0 else f'L {px:.0f} {py:.0f}') for j, (px, py) in enumerate(pts))
        d = f'M {pts[0][0]:.0f} {pts[0][1]:.0f} ' + ' '.join(
            f'Q {pts[j][0]:.0f} {pts[j][1]:.0f} {(pts[j][0] + pts[j + 1][0]) / 2:.0f} {(pts[j][1] + pts[j + 1][1]) / 2:.0f}' for j in range(1, len(pts) - 1))
        wid = rnd.uniform(14, 24)
        shape = (f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="{wid + 6:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
                 f'<path d="{d}" fill="none" stroke="#9A6A44" stroke-width="{wid:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
                 f'<path d="{d}" fill="none" stroke="#C48E60" stroke-opacity=".6" stroke-width="{wid * 0.28:.1f}" stroke-linecap="round" transform="translate(-1.5 -2)"/>')
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        t.add(shape, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (max(xs) - min(xs)) / 2 + 12, (max(ys) - min(ys)) / 2 + 12)
    # камни
    for i in range(13):
        cx, cy = rnd.uniform(0, W), rnd.uniform(0, H)
        rx = rnd.uniform(24, 72)
        ry = rx * rnd.uniform(0.6, 0.9)
        rot = rnd.uniform(-0.6, 0.6)
        light, dark = STONES[i % len(STONES)]
        gid = t.uid('st')
        t.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{light}"/>'
                      f'<stop offset="1" stop-color="{dark}"/></linearGradient>')
        path = blob(cx, cy, rx, ry, rnd, n=9, jitter=0.14, rot=rot)
        hi = f'<ellipse cx="{cx - rx * 0.28:.0f}" cy="{cy - ry * 0.38:.0f}" rx="{rx * 0.34:.0f}" ry="{ry * 0.15:.0f}" fill="#FFFFFF" fill-opacity=".34" transform="rotate({math.degrees(rot):.0f} {cx:.0f} {cy:.0f})"/>'
        crack = ''
        if i % 3 == 0:
            crack = (f'<path d="M {cx + rx * 0.1:.0f} {cy - ry * 0.2:.0f} l {rx * 0.18:.0f} {ry * 0.3:.0f} l {-rx * 0.1:.0f} {ry * 0.24:.0f}" '
                     f'fill="none" stroke="{OUTLINE}" stroke-opacity=".55" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        t.add(f'<path d="{path}" fill="url(#{gid})" stroke="{OUTLINE}" stroke-width="4.4" stroke-linejoin="round"/>{hi}{crack}', cx, cy, rx + 6, rx + 6)
    return t.render()


# ---------- ближний слой ----------
PEBBLE_TONES = ['#8F6D4C', '#7D5D40', '#A0805C', '#6E513A']


def shell(cx, cy, r, rot):
    """Ракушка-аммонит: круг со спиралью и бороздами."""
    spiral = []
    for i in range(60):
        a = i / 59 * 3.2 * math.pi
        rr = r * (0.12 + 0.82 * i / 59)
        spiral.append((rr * math.cos(a), rr * math.sin(a)))
    sp = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in spiral)
    ridges = ''.join(
        f'<path d="M {r * 0.95 * math.cos(a):.1f} {r * 0.95 * math.sin(a):.1f} L {r * 0.5 * math.cos(a + 0.35):.1f} {r * 0.5 * math.sin(a + 0.35):.1f}" '
        f'stroke="#B08F5E" stroke-width="2.2" stroke-linecap="round" fill="none"/>' for a in [k * math.pi / 5 for k in range(10)])
    return (f'<g transform="translate({cx:.0f} {cy:.0f}) rotate({math.degrees(rot):.0f})" stroke-linejoin="round">'
            f'<circle r="{r:.1f}" fill="#EBD9B4" stroke="{OUTLINE}" stroke-width="3.6"/>{ridges}'
            f'<path d="{sp}" fill="none" stroke="#B08F5E" stroke-width="2.6" stroke-linecap="round"/>'
            f'<ellipse cx="{-r * 0.32:.1f}" cy="{-r * 0.45:.1f}" rx="{r * 0.28:.1f}" ry="{r * 0.1:.1f}" fill="#FFFFFF" fill-opacity=".5"/></g>')


def near():
    W, H = 1024, 1024
    t = Tile(W, H)
    rnd = random.Random(37)
    # песчинки без контура
    for i in range(260):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1.6, 4.6)
        col = '#4A2F1F' if i % 2 else '#B08D68'
        t.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{col}" fill-opacity=".55"/>', x, y, r + 1)
    # камешки с контуром
    for i in range(150):
        cx, cy = rnd.uniform(0, W), rnd.uniform(0, H)
        rx = rnd.uniform(6, 27)
        ry = rx * rnd.uniform(0.55, 0.9)
        rot = math.degrees(rnd.uniform(0, math.pi))
        col = PEBBLE_TONES[rnd.randrange(len(PEBBLE_TONES))]
        sw = max(2.0, min(3.6, rx * 0.2))
        hi = f'<ellipse cx="{cx - rx * 0.25:.0f}" cy="{cy - ry * 0.35:.0f}" rx="{rx * 0.32:.1f}" ry="{ry * 0.16:.1f}" fill="#FFFFFF" fill-opacity=".32" transform="rotate({rot:.0f} {cx:.0f} {cy:.0f})"/>' if rx > 9 else ''
        t.add(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.1f}" ry="{ry:.1f}" transform="rotate({rot:.0f} {cx:.0f} {cy:.0f})" '
              f'fill="{col}" stroke="{OUTLINE}" stroke-width="{sw:.1f}"/>{hi}', cx, cy, rx + 3)
    # ракушки
    for i in range(6):
        cx, cy = rnd.uniform(40, W - 40), rnd.uniform(40, H - 40)
        r = rnd.uniform(17, 27)
        t.add(shell(cx, cy, r, rnd.uniform(0, 6.28)), cx, cy, r + 4)
    # короткие корешки
    for i in range(7):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ang = rnd.uniform(0, 6.28)
        pts = [(x, y)]
        for _ in range(3):
            ang += rnd.uniform(-0.8, 0.8)
            x += math.cos(ang) * rnd.uniform(22, 40)
            y += math.sin(ang) * rnd.uniform(22, 40)
            pts.append((x, y))
        d = f'M {pts[0][0]:.0f} {pts[0][1]:.0f} ' + ' '.join(f'L {px:.0f} {py:.0f}' for px, py in pts[1:])
        t.add(f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
              f'<path d="{d}" fill="none" stroke="#A9794F" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>',
              pts[1][0], pts[1][1], 70)
    return t.render()


# ---------- кромка с травой ----------
def edge():
    W, H = 1024, 512
    t = Tile(W, H, wrap_y=False)
    rnd = random.Random(53)
    g = GROUND_Y
    t.defs.append(f'<linearGradient id="topsoil" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3E8E2F"/>'
                  f'<stop offset=".28" stop-color="#5E7A32"/><stop offset="1" stop-color="#6B4A32"/></linearGradient>')
    # корешки под землёй
    for i in range(10):
        x = rnd.uniform(0, W)
        ln = rnd.uniform(60, 190)
        dx = rnd.uniform(-40, 40)
        d = f'M {x:.0f} {g + 30} C {x + dx * 0.4:.0f} {g + 30 + ln * 0.35:.0f} {x - dx:.0f} {g + 30 + ln * 0.7:.0f} {x + dx * 0.6:.0f} {g + 30 + ln:.0f}'
        wid = rnd.uniform(5, 10)
        t.add(f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="{wid + 3.4:.1f}" stroke-linecap="round"/>'
              f'<path d="{d}" fill="none" stroke="#9A6A44" stroke-width="{wid:.1f}" stroke-linecap="round"/>', x, g + 100, 60, 150)
    # полоса дёрна с волнистым верхом (период укладывается в ширину)
    top = wavy(-4, g + 4, W + 4, 3.4, 16, steps=160)
    band = f'{top} L {W + 4} {g + 66} L -4 {g + 66} Z'
    t.parts.append(f'<path d="{band}" fill="url(#topsoil)" stroke="{OUTLINE}" stroke-width="4.4" stroke-linejoin="round"/>')
    # мелкие камешки в дёрне
    for i in range(22):
        x, y = rnd.uniform(0, W), g + rnd.uniform(24, 56)
        rx = rnd.uniform(4, 8)
        t.add(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rx:.1f}" ry="{rx * 0.7:.1f}" fill="#8F6D4C" stroke="{OUTLINE}" stroke-width="2.4"/>', x, y, rx + 3)
    # трава: два ряда лезвий, задний светлее и выше
    for row, (hmin, hmax, cols, sw) in enumerate(((18, 40, ('#6CC24A', '#5BB43D'), 2.6), (10, 27, ('#4FA83F', '#3E8E2F'), 3.0))):
        x = rnd.uniform(0, 8)
        while x < W + 10:
            h = rnd.uniform(hmin, hmax)
            lean = rnd.uniform(-9, 9)
            wd = rnd.uniform(5, 8.5)
            col = cols[rnd.randrange(2)]
            d = (f'M {x - wd:.1f} {g + 6} Q {x - wd * 0.3 + lean * 0.3:.1f} {g - h * 0.55:.1f} {x + lean:.1f} {g - h:.1f} '
                 f'Q {x + wd * 0.5 + lean * 0.3:.1f} {g - h * 0.5:.1f} {x + wd:.1f} {g + 6} Z')
            t.add(f'<path d="{d}" fill="{col}" stroke="{OUTLINE}" stroke-width="{sw}" stroke-linejoin="round"/>', x, g, wd + 12, h)
            x += rnd.uniform(7, 14) if row == 0 else rnd.uniform(9, 17)
    return t.render()


# ---------- облака ----------
def clouds():
    W, H = 2048, 512
    t = Tile(W, H, wrap_y=False)
    rnd = random.Random(71)
    spots = [(220, 150, 1.0), (640, 300, 0.7), (1010, 120, 1.15), (1420, 330, 0.8), (1740, 170, 0.95), (1950, 380, 0.6)]
    for cx, cy, s in spots:
        puffs = [(-70, 10, 42), (-28, -14, 54), (26, -22, 60), (74, 0, 46), (108, 14, 34)]
        shade, body = [], []
        for dx, dy, r in puffs:
            shade.append(f'<circle cx="{cx + dx * s:.0f}" cy="{cy + dy * s + 7:.0f}" r="{r * s:.0f}" fill="#CFE0F2"/>')
            body.append(f'<circle cx="{cx + dx * s:.0f}" cy="{cy + dy * s:.0f}" r="{r * s:.0f}" fill="#FFFFFF" stroke="#8FB5E0" stroke-width="3.2"/>')
        inner = [f'<circle cx="{cx + dx * s:.0f}" cy="{cy + dy * s:.0f}" r="{r * s - 1.6:.0f}" fill="#FFFFFF"/>' for dx, dy, r in puffs]
        base = f'<rect x="{cx - 108 * s:.0f}" y="{cy + 8 * s:.0f}" width="{236 * s:.0f}" height="{40 * s:.0f}" rx="{20 * s:.0f}" fill="#FFFFFF" stroke="#8FB5E0" stroke-width="3.2"/>'
        base_in = f'<rect x="{cx - 106 * s:.0f}" y="{cy + 10 * s:.0f}" width="{232 * s:.0f}" height="{36 * s:.0f}" rx="{18 * s:.0f}" fill="#FFFFFF"/>'
        t.add(''.join(shade) + base + ''.join(body) + base_in + ''.join(inner), cx, cy, 150 * s, 80 * s)
    return t.render()


def main():
    write(OUT_DIR / 'bg-z1-far.svg', far())
    write(OUT_DIR / 'bg-z1-mid.svg', mid())
    write(OUT_DIR / 'bg-z1-near.svg', near())
    write(OUT_DIR / 'bg-z1-edge.svg', edge())
    write(OUT_DIR / 'bg-z1-clouds.svg', clouds())
    print('zone1: written 5 background svg files')


if __name__ == '__main__':
    main()
