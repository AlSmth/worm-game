#!/usr/bin/env python3
"""Генератор арта зоны 2 «Поверхность» (SVG): люди, машины, техника охраны, снаряды, декор, дома и фон.

Запуск из корня проекта:  python tools/gen_zone2.py

Пишет в design/zone-2-surface/:
  people/     z2-person-<вид>-run1|run2   взрослые мультяшные люди, два кадра бега (96×96, ноги на нижнем краю)
  vehicles/   z2-car-a|b-<цвет>, z2-bus-<цвет>, z2-truck-<цвет>   гражданские машины (колёса на нижнем краю)
  military/   z2-patrol, z2-patrol-barrel, z2-heavy, z2-heavy-barrel, z2-bullet, z2-shell   вымышленная техника охраны
              (папка названа по ТЗ; в игре и текстах слова «армия», «война», «бой» не используются: пп. 3.4.4, R1)
  decor/      z2-tree-a|b, z2-bush, z2-lamp
  houses/     z2-house-a|b-<цвет>, z2-apartment-<цвет>, z2-tower, z2-skyscraper   (код gen_zone2_city.py)
  background/ bg-z2-skyline (1024×512), bg-z2-hills (1024×256)   бесшовные полосы по горизонтали

Правила: контур 4,2 px, свет сверху слева, у каждого спрайта нижний край фигуры = земля. Без текста, флагов, звёзд, гербов,
номеров, камуфляжа, крестов и куполов; люди только взрослые, без крови. Рисунки руками не правим: меняем параметры и перегенерируем.
"""
import random

from svgkit import ROOT, OUTLINE, mix, lighten
import z2kit as k
from z2kit import PAD, OUT, OUT_S, rr, circ, ell, path, poly, line, hi, glass, wheel, lg, fillg, sprite
import gen_zone2_city as city

Z2 = ROOT / 'design' / 'zone-2-surface'
write = None


def _w(path_, text):
    from svgkit import write as w
    w(path_, text)


# ---------------------------------------------------------------- люди
PEOPLE = {
    # вид: цвета и одежда; всё взрослые: пропорции головы и тела не детские
    'a': dict(skin='#F6C79B', hair='#5A3A22', top='#E9503F', legs='#3B4F8C', style='suit'),     # мужчина в красной куртке
    'b': dict(skin='#E0A877', hair='#2F2A2A', top='#3FA9D9', legs='#2F2F3D', style='dress'),    # женщина в платье
    'c': dict(skin='#8F5C3E', hair='#1F1B1B', top='#F2C23B', legs='#5B7A4A', style='cap'),      # мужчина в жёлтой жилетке и кепке
}


def person(kind, frame):
    """Человек бежит вправо в испуге: широко раскрытые глаза и рот, руки и ноги в беге. frame 0/1: фазы шага."""
    P = PEOPLE[kind]
    W, H = 96, 104
    gy = H - PAD
    cx = 46
    defs = []
    parts = []
    s = 1 if frame == 0 else -1
    hip = (cx - 1, gy - 34)
    # задняя нога и рука рисуются первыми
    def leg(sign, front):
        knee = (hip[0] + sign * 12, hip[1] + 12)
        foot = (hip[0] + sign * 20 * (1 if front else 0.8), gy - (2 if front else 6 + 2 * s))
        d = f'M {hip[0]} {hip[1]} L {knee[0]} {knee[1]} L {foot[0]} {foot[1]}'
        return (f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="11"/>'
                f'<path d="{d}" fill="none" stroke="{P["legs"]}" stroke-width="6"/>'
                f'<ellipse cx="{foot[0] + 3}" cy="{foot[1]}" rx="7" ry="4" fill="#3A2A22" stroke="{OUTLINE}" stroke-width="2.4"/>')
    sh = (cx + 1, gy - 62)                      # плечо
    def arm(sign):
        elbow = (sh[0] + sign * 10, sh[1] + 9)
        hand = (sh[0] + sign * 16, sh[1] - (8 if sign * s > 0 else -4))
        d = f'M {sh[0]} {sh[1]} L {elbow[0]} {elbow[1]} L {hand[0]} {hand[1]}'
        sleeve = P['top']
        return (f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="9"/>'
                f'<path d="{d}" fill="none" stroke="{sleeve}" stroke-width="4.6"/>'
                f'<circle cx="{hand[0]}" cy="{hand[1]}" r="4.2" fill="{P["skin"]}" stroke="{OUTLINE}" stroke-width="2.2"/>')
    parts.append(leg(-1 * s, False))
    parts.append(arm(-1 * s))
    # туловище
    top_g = fillg(defs, P['top'])
    if P['style'] == 'dress':
        parts.append(path(f'M {cx - 9} {gy - 64} L {cx + 11} {gy - 64} L {cx + 17} {gy - 28} L {cx - 15} {gy - 28} Z', top_g, OUT_S + 0.6))
    else:
        parts.append(path(f'M {cx - 10} {gy - 65} Q {cx + 1} {gy - 69} {cx + 12} {gy - 65} L {cx + 10} {gy - 34} L {cx - 9} {gy - 34} Z', top_g, OUT_S + 0.6))
        if P['style'] == 'suit':
            parts.append(path(f'M {cx - 1} {gy - 65} L {cx + 4} {gy - 65} L {cx + 2} {gy - 48} Z', '#FFFFFF', 2))
        if P['style'] == 'cap':
            parts.append(line(cx - 8, gy - 42, cx + 9, gy - 42, '#FFFFFF', 2.4, 0.8))
    parts.append(leg(1 * s, True))
    parts.append(arm(1 * s))
    # голова: взрослые пропорции (голова около четверти роста), сжимаем вокруг центра
    hy = gy - 78
    body_parts = parts
    parts = []
    hair_back = P['hair']
    if P['style'] == 'dress':
        parts.append(path(f'M {cx - 12} {hy - 4} Q {cx - 20} {hy + 14} {cx - 10} {hy + 20} L {cx - 3} {hy + 8} Z', hair_back, 2.6))
    parts.append(circ(cx + 1, hy, 13.5, P['skin'], OUT_S + 0.6))
    # волосы / кепка
    if P['style'] == 'cap':
        parts.append(path(f'M {cx - 12} {hy - 3} Q {cx + 1} {hy - 20} {cx + 14} {hy - 3} Z', '#3FA9D9', 2.8))
        parts.append(path(f'M {cx + 8} {hy - 5} L {cx + 21} {hy - 2} L {cx + 9} {hy + 1} Z', '#2B80AA', 2.4))
    else:
        parts.append(path(f'M {cx - 13} {hy - 1} Q {cx - 12} {hy - 17} {cx + 3} {hy - 15} Q {cx + 14} {hy - 14} {cx + 14} {hy - 3} '
                          f'Q {cx + 5} {hy - 9} {cx - 4} {hy - 7} Q {cx - 9} {hy - 3} {cx - 13} {hy - 1} Z', P['hair'], 2.6))
    # испуганное лицо: большие глаза и круглый рот
    parts.append(f'<ellipse cx="{cx + 7}" cy="{hy + 1}" rx="3.6" ry="4.4" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="1.6"/>')
    parts.append(f'<circle cx="{cx + 8.4}" cy="{hy + 1.6}" r="1.7" fill="{OUTLINE}"/>')
    parts.append(f'<ellipse cx="{cx - 1}" cy="{hy + 1.6}" rx="3.2" ry="4" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="1.6"/>')
    parts.append(f'<circle cx="{cx}" cy="{hy + 2.1}" r="1.5" fill="{OUTLINE}"/>')
    parts.append(f'<ellipse cx="{cx + 5}" cy="{hy + 9}" rx="2.4" ry="3" fill="#8A2A2A" stroke="{OUTLINE}" stroke-width="1.4"/>')
    head = f'<g transform="translate({cx + 1} {hy + 4}) scale(0.84) translate({-(cx + 1)} {-(hy + 4)})">{"".join(parts)}</g>'
    return sprite(W, H, defs, body_parts + [head])


# ---------------------------------------------------------------- гражданские машины
CAR_COLORS = {'red': '#E9503F', 'blue': '#3F8CE9', 'yellow': '#F5C434', 'green': '#4FB85C', 'orange': '#F28A2E', 'white': '#EEF1F6'}


def car(model, color):
    """Легковая машина, смотрит вправо. model: a — хэтчбек, b — седан."""
    W, H = 224, 96
    gy = H - PAD
    c = CAR_COLORS[color]
    defs = []
    body = fillg(defs, c)
    dark = fillg(defs, mix(c, '#000000', 0.25), 0.1, 0.2)
    parts = []
    if model == 'a':
        cab = [(54, 46), (70, 20), (140, 20), (170, 46)]
        parts.append(poly([(x, y) for x, y in cab], body, OUT))
        parts.append(rr(12, 44, 200, 34, 12, body, OUT))
        parts.append(glass(defs, 76, 26, 32, 18, r=3))
        parts.append(glass(defs, 112, 26, 36, 18, r=3))
    else:
        cab = [(62, 46), (84, 18), (150, 18), (176, 46)]
        parts.append(poly([(x, y) for x, y in cab], body, OUT))
        parts.append(rr(8, 44, 208, 32, 12, body, OUT))
        parts.append(glass(defs, 90, 24, 30, 20, r=3))
        parts.append(glass(defs, 124, 24, 32, 20, r=3))
    # полоска, фары, бампер
    parts.append(rr(14, 60, 196, 8, 4, dark, 2.4))
    parts.append(rr(198, 50, 12, 10, 4, '#FFF2A8', 2.6))
    parts.append(rr(10, 50, 8, 10, 3, '#FF8A7A', 2.6))
    parts.append(hi(20, 47, 150, 6, op=0.4))
    parts.append(wheel(56, gy - 14, 14))
    parts.append(wheel(164, gy - 14, 14))
    return sprite(W, H, defs, parts)


def bus(color):
    W, H = 384, 160
    gy = H - PAD
    c = {'yellow': '#F5C434', 'blue': '#3F8CE9'}[color]
    defs = []
    body = fillg(defs, c)
    dark = fillg(defs, mix(c, '#000000', 0.3), 0.05, 0.2)
    parts = [rr(8, 30, 368, 104, 20, body, OUT)]
    for i in range(7):
        parts.append(glass(defs, 26 + i * 40, 46, 32, 34, r=4))
    parts.append(glass(defs, 306, 44, 56, 46, r=6))
    parts.append(rr(14, 98, 350, 10, 5, dark, 2.6))
    parts.append(rr(26, 108, 40, 22, 4, '#B7C2D6', 2.6))      # двери
    parts.append(rr(346, 106, 22, 12, 4, '#FFF2A8', 2.6))
    parts.append(rr(12, 40, 6, 24, 3, '#FF8A7A', 2))
    parts.append(hi(22, 33, 330, 7, op=0.4))
    parts.append(wheel(92, gy - 22, 22))
    parts.append(wheel(292, gy - 22, 22))
    return sprite(W, H, defs, parts)


def truck(color):
    W, H = 320, 160
    gy = H - PAD
    cab_c = {'white': '#EEF1F6', 'orange': '#F28A2E'}[color]
    cargo_c = {'white': '#8FB6E8', 'orange': '#F5D58A'}[color]
    defs = []
    cargo = fillg(defs, cargo_c)
    cab = fillg(defs, cab_c)
    parts = [rr(6, 20, 214, 102, 8, cargo, OUT)]
    for i in range(4):
        parts.append(line(60 + i * 46, 26, 60 + i * 46, 116, OUTLINE, 2.4, 0.35))
    parts.append(rr(218, 52, 88, 72, 14, cab, OUT))
    parts.append(poly([(226, 54), (246, 30), (292, 30), (300, 54)], cab, OUT))
    parts.append(glass(defs, 252, 36, 38, 22, r=4))
    parts.append(rr(10, 112, 296, 14, 5, '#4B4F61', 2.6))
    parts.append(rr(292, 96, 12, 12, 4, '#FFF2A8', 2.6))
    parts.append(hi(14, 24, 196, 7, op=0.4))
    parts.append(wheel(54, gy - 20, 20))
    parts.append(wheel(136, gy - 20, 20))
    parts.append(wheel(256, gy - 20, 20))
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- техника охраны (вымышленная, без символики)
def patrol():
    """Лёгкая машина охраны: бирюзовый вездеход с купольной башенкой; ствол отдельным спрайтом. Ствол крепится в (112, 44)."""
    W, H = 224, 128
    gy = H - PAD
    defs = []
    body = fillg(defs, '#3FB7B0')
    dark = fillg(defs, '#2A8C86', 0.1, 0.2)
    parts = [rr(16, 62, 192, 38, 12, body, OUT)]
    parts.append(poly([(48, 62), (68, 38), (150, 38), (176, 62)], dark, OUT))
    parts.append(glass(defs, 78, 44, 30, 16, r=3))
    parts.append(glass(defs, 112, 44, 34, 16, r=3))
    parts.append(rr(20, 82, 184, 8, 4, '#FFFFFF', 2.4))
    parts.append(rr(196, 70, 12, 10, 4, '#FFF2A8', 2.6))
    parts.append(hi(24, 65, 150, 6, op=0.4))
    # башенка
    parts.append(ell(112, 40, 20, 12, dark, OUT))
    parts.append(hi(98, 33, 18, 6, op=0.45))
    parts.append(wheel(56, gy - 18, 18))
    parts.append(wheel(168, gy - 18, 18))
    return sprite(W, H, defs, parts)


def barrel(length, thick, pivot, W, H, body_c, tip_c):
    """Ствол: труба с дульным утолщением, ось вращения (pivot) слева. Рисуется вправо."""
    defs = []
    g = fillg(defs, body_c, 0.35, 0.3)
    cy = H / 2
    px = pivot
    parts = [rr(px, cy - thick / 2, length, thick, thick * 0.25, g, OUT),
             rr(px + length - thick * 0.9, cy - thick * 0.72, thick * 0.9, thick * 1.44, thick * 0.2, tip_c, OUT),
             hi(px + 6, cy - thick / 2 + 2, length - thick, thick * 0.22, op=0.5),
             circ(px, cy, thick * 0.78, tip_c, OUT)]
    return sprite(W, H, defs, parts)


def heavy():
    """Тяжёлая машина охраны: гусеничная, стальная с оранжевыми полосами; ствол отдельным спрайтом. Ствол крепится в (150, 74)."""
    W, H = 384, 192
    gy = H - PAD
    defs = []
    steel = fillg(defs, '#8C9BB3')
    dark = fillg(defs, '#5E6C86', 0.1, 0.25)
    orange = fillg(defs, '#F28A2E')
    parts = [rr(18, 128, 348, 56, 26, '#3A3F4F', OUT)]                       # гусеница
    for i in range(6):
        parts.append(circ(52 + i * 56, 156, 17, '#C9CED8', OUT_S))
        parts.append(circ(52 + i * 56, 156, 6, '#5E6C86', 2))
    parts.append(rr(36, 84, 312, 52, 14, steel, OUT))                        # корпус
    parts.append(rr(36, 112, 312, 12, 4, orange, 2.6))
    for i in range(7):
        parts.append(line(60 + i * 40, 114, 72 + i * 40, 122, OUTLINE, 2.2, 0.55))
    parts.append(rr(120, 40, 160, 50, 18, dark, OUT))                        # башня
    parts.append(rr(132, 46, 70, 12, 6, '#FFFFFF', 0, 'fill-opacity=".35"'))
    parts.append(circ(150, 74, 11, '#3A3F4F', OUT_S))                        # узел ствола
    parts.append(glass(defs, 226, 52, 38, 24, r=5))
    parts.append(rr(324, 96, 18, 14, 5, '#FFF2A8', 2.6))
    return sprite(W, H, defs, parts)


def bullet():
    d = []
    g = lg(d, '#FFE27A', '#FF9A2E')
    return sprite(32, 32, d, [circ(16, 16, 10, g, OUT_S + 0.4), hi(11, 10, 7, 5, op=0.7)])


def shell():
    d = []
    g = lg(d, '#7C8497', '#3A3F4F')
    return sprite(48, 48, d, [circ(24, 24, 15, g, OUT), path('M 12 24 Q 24 16 36 24', 'none', 4.5, 'stroke-opacity="0"'),
                              f'<path d="M 11 27 Q 24 36 37 27" fill="none" stroke="#F28A2E" stroke-width="5"/>', hi(15, 13, 10, 6, op=0.5)])


# ---------------------------------------------------------------- декор
def tree(kind):
    W, H = (192, 256) if kind == 'a' else (176, 224)
    gy = H - PAD
    defs = []
    trunk = fillg(defs, '#9A6A3F', 0.2, 0.25)
    leaf = fillg(defs, '#5DB85A' if kind == 'a' else '#78C850', 0.25, 0.2)
    leaf2 = fillg(defs, '#4AA24A' if kind == 'a' else '#63B140', 0.25, 0.2)
    cx = W // 2
    parts = [path(f'M {cx - 14} {gy} L {cx - 9} {gy - 80} L {cx + 9} {gy - 80} L {cx + 14} {gy} Z', trunk, OUT)]
    if kind == 'a':
        for (x, y, r, c) in ((cx - 36, gy - 112, 40, leaf2), (cx + 34, gy - 118, 38, leaf2), (cx, gy - 150, 50, leaf), (cx - 8, gy - 100, 44, leaf)):
            parts.append(circ(x, y, r, c, OUT))
        parts.append(hi(cx - 28, gy - 176, 40, 10, op=0.4))
    else:
        for (x, y, r, c) in ((cx - 30, gy - 104, 36, leaf2), (cx + 30, gy - 104, 36, leaf2), (cx, gy - 128, 44, leaf)):
            parts.append(circ(x, y, r, c, OUT))
        for (x, y) in ((cx - 24, gy - 110), (cx + 20, gy - 96), (cx + 4, gy - 136), (cx - 40, gy - 90), (cx + 40, gy - 122)):
            parts.append(circ(x, y, 6, '#E9503F', 2.6))
    return sprite(W, H, defs, parts)


def bush():
    W, H = 128, 80
    gy = H - PAD
    defs = []
    g1 = fillg(defs, '#4AA24A')
    g2 = fillg(defs, '#63B140')
    parts = [circ(34, gy - 22, 22, g1, OUT), circ(90, gy - 22, 22, g1, OUT), circ(62, gy - 30, 28, g2, OUT), hi(48, gy - 52, 24, 8, op=0.4)]
    return sprite(W, H, defs, parts)


def lamp():
    W, H = 64, 192
    gy = H - PAD
    defs = []
    glow = f'<radialGradient id="lampglow"><stop offset="0" stop-color="#FFF3A6" stop-opacity=".8"/><stop offset="1" stop-color="#FFF3A6" stop-opacity="0"/></radialGradient>'
    defs.append(glow)
    parts = [f'<circle cx="38" cy="30" r="26" fill="url(#lampglow)"/>',
             rr(28, gy - 140, 8, 140, 3, '#6E7585', OUT_S),
             rr(26, gy - 8, 12, 8, 3, '#4B4F61', OUT_S),
             path(f'M 32 {gy - 140} Q 32 {gy - 160} 46 {gy - 160}', 'none', 5, 'stroke-linecap="round"'),
             rr(36, gy - 166, 20, 12, 5, '#FFE27A', OUT_S)]
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- запись
def main():
    n = 0
    for kind in PEOPLE:
        for f in (0, 1):
            _w(Z2 / 'people' / f'z2-person-{kind}-run{f + 1}.svg', person(kind, f))
            n += 1
    for model, colors in (('a', ('red', 'blue', 'yellow')), ('b', ('green', 'orange', 'white'))):
        for c in colors:
            _w(Z2 / 'vehicles' / f'z2-car-{model}-{c}.svg', car(model, c))
            n += 1
    for c in ('yellow', 'blue'):
        _w(Z2 / 'vehicles' / f'z2-bus-{c}.svg', bus(c))
        n += 1
    for c in ('white', 'orange'):
        _w(Z2 / 'vehicles' / f'z2-truck-{c}.svg', truck(c))
        n += 1
    _w(Z2 / 'military' / 'z2-patrol.svg', patrol())
    _w(Z2 / 'military' / 'z2-patrol-barrel.svg', barrel(70, 14, 16, 96, 32, '#8CE0DA', '#2A8C86'))
    _w(Z2 / 'military' / 'z2-heavy.svg', heavy())
    _w(Z2 / 'military' / 'z2-heavy-barrel.svg', barrel(138, 22, 24, 176, 48, '#B7C2D6', '#5E6C86'))
    _w(Z2 / 'military' / 'z2-bullet.svg', bullet())
    _w(Z2 / 'military' / 'z2-shell.svg', shell())
    n += 6
    for kind in ('a', 'b'):
        _w(Z2 / 'decor' / f'z2-tree-{kind}.svg', tree(kind))
        n += 1
    _w(Z2 / 'decor' / 'z2-bush.svg', bush())
    _w(Z2 / 'decor' / 'z2-lamp.svg', lamp())
    n += 2
    n += city.main(_w, Z2)
    print(f'zone 2: written {n} svg files')


if __name__ == '__main__':
    main()
