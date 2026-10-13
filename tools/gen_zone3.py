#!/usr/bin/env python3
"""Генератор арта зоны 3 «Небо» (SVG): лёгкие самолёты, вертолёты, истребитель, тяжёлый вертолёт, лайнеры, грузовой гигант.

Запуск из корня проекта:  python tools/gen_zone3.py

Пишет в design/zone-3-sky/:
  planes/  z3-plane-a|b-1|2     лёгкий самолёт с пропеллером (два кадра: лопасти и размытый диск), жёлтый и красный
           z3-heli-a|b-1|2      малый вертолёт (два кадра винта), синий и оранжевый
           z3-fighter           быстрый «скоростной самолёт охраны» (носом вправо, пламя из сопла)
           z3-heavy-1|2         тяжёлый грузовой вертолёт с двумя винтами (два кадра)
           z3-airliner-a|b      лайнер: белый корпус, окна, цветная полоса; синий и зелёный
           z3-cargo             грузовой гигант: высокий хвост, четыре двигателя

Все спрайты смотрят вправо, игра отражает их при полёте влево; центр рисунка = центр тела. Контур 4,2 px, свет сверху слева.
Правила: без текста, флагов, звёзд, эмблем, кокард и номеров, людей в кабинах не видно; техника вымышленная (пп. 3.4.4, R1).
Рисунки руками не правим: меняем параметры и перегенерируем.
"""
import math

from svgkit import ROOT, OUTLINE, mix, lighten
from z2kit import OUT, OUT_S, rr, circ, ell, path, poly, line, hi, glass, wheel, lg, fillg, sprite

Z3 = ROOT / 'design' / 'zone-3-sky'


def _w(path_, text):
    from svgkit import write as w
    w(path_, text)


def cockpit(defs, d):
    """Остекление кабины: голубое стекло по заданному контуру d (SVG path), блик."""
    g = lg(defs, '#D8F2FF', '#6FB8EE')
    return path(d, g, OUT_S)


# ---------------------------------------------------------------- лёгкий самолёт
PLANES = {
    'a': dict(body='#F7C93A', accent='#E9503F', wing='#F2F4F8'),   # жёлтый с красной полосой
    'b': dict(body='#E9503F', accent='#FFF2A8', wing='#F2F4F8'),   # красный с жёлтой полосой
}


def plane(kind, frame):
    P = PLANES[kind]
    W, H = 240, 140
    defs = []
    body = fillg(defs, P['body'], 0.3, 0.2)
    wing = fillg(defs, P['wing'], 0.1, 0.18)
    tailc = fillg(defs, P['accent'], 0.25, 0.2)
    parts = []
    # хвостовое оперение
    parts.append(poly([(26, 66), (12, 22), (44, 22), (58, 58)], tailc, OUT))
    parts.append(poly([(24, 70), (4, 78), (6, 88), (34, 80)], wing, OUT_S + 0.4))
    # колёса и стойки
    parts.append(line(176, 96, 182, 116, OUTLINE, 5))
    parts.append(line(116, 96, 112, 116, OUTLINE, 5))
    parts.append(wheel(184, 119, 10))
    parts.append(wheel(112, 119, 10))
    # фюзеляж
    parts.append(path('M 20 62 L 150 46 Q 196 42 212 62 Q 222 72 212 82 Q 196 100 150 98 L 20 78 Q 10 70 20 62 Z', body, OUT))
    parts.append(path('M 40 68 L 190 62 L 190 70 L 40 74 Z', P['accent'], 0, 'fill-opacity=".9"'))
    parts.append(hi(48, 54, 120, 5, op=0.4))
    # кабина
    parts.append(cockpit(defs, 'M 130 50 Q 152 34 180 50 L 176 66 L 132 66 Z'))
    parts.append(f'<path d="M 140 56 L 156 42 L 164 44 L 148 58 Z" fill="#FFFFFF" fill-opacity=".5"/>')
    # крыло: видно снизу, прямоугольное, с подкосом
    parts.append(poly([(100, 82), (182, 84), (170, 98), (88, 96)], wing, OUT))
    parts.append(line(138, 98, 146, 84, OUTLINE, 3.2))
    # нос, пропеллер
    parts.append(circ(214, 70, 9, '#4B4F61', OUT_S))
    if frame == 0:
        parts.append(ell(220, 70, 5, 38, '#3A3F4F', OUT_S))
    else:
        parts.append(f'<ellipse cx="220" cy="70" rx="9" ry="38" fill="#C8D2E6" fill-opacity=".55" stroke="{OUTLINE}" stroke-width="2.4" stroke-opacity=".6"/>')
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- малый вертолёт
HELIS = {
    'a': dict(body='#3FA9D9', stripe='#F2F4F8'),
    'b': dict(body='#F28A2E', stripe='#FFF2A8'),
}


def heli(kind, frame):
    P = HELIS[kind]
    W, H = 260, 150
    defs = []
    body = fillg(defs, P['body'], 0.3, 0.22)
    dark = fillg(defs, '#5E6C86', 0.1, 0.25)
    parts = []
    # хвостовая балка и хвостовой винт
    parts.append(path('M 96 74 L 22 62 L 14 74 L 98 90 Z', body, OUT))
    parts.append(poly([(26, 64), (14, 30), (34, 30), (46, 62)], dark, OUT_S + 0.4))
    parts.append(ell(24, 44, 7, 22, '#C8D2E6' if frame else '#3A3F4F', OUT_S))
    # полозья
    parts.append(line(78, 124, 190, 124, OUTLINE, 6))
    parts.append(line(96, 108, 92, 124, OUTLINE, 4.5))
    parts.append(line(168, 108, 172, 124, OUTLINE, 4.5))
    # кабина-пузырь и корпус
    parts.append(path('M 60 66 Q 70 40 122 38 Q 190 34 216 70 Q 220 98 190 108 L 82 108 Q 56 100 60 66 Z', body, OUT))
    parts.append(path('M 150 46 Q 196 46 212 72 Q 214 90 196 96 L 150 96 Z', lg(defs, '#D8F2FF', '#6FB8EE'), OUT_S + 0.4))
    parts.append(f'<path d="M 162 54 L 180 52 L 168 84 L 158 84 Z" fill="#FFFFFF" fill-opacity=".45"/>')
    parts.append(rr(66, 82, 84, 8, 4, P['stripe'], 0, 'fill-opacity=".9"'))
    parts.append(hi(80, 50, 54, 5, op=0.45))
    # главный винт
    parts.append(rr(116, 24, 14, 16, 4, '#4B4F61', OUT_S))
    if frame == 0:
        parts.append(rr(36, 14, 188, 9, 4.5, '#3A3F4F', OUT_S))
    else:
        parts.append(f'<ellipse cx="124" cy="20" rx="104" ry="9" fill="#C8D2E6" fill-opacity=".5" stroke="{OUTLINE}" stroke-width="2.4" stroke-opacity=".55"/>')
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- скоростной самолёт охраны
def fighter():
    W, H = 380, 130
    defs = []
    steel = fillg(defs, '#8FA3C4', 0.32, 0.2)
    dark = fillg(defs, '#4F5F82', 0.1, 0.25)
    flame = lg(defs, '#FFD23F', '#FF7A1A', 1, 0, 0, 0)
    parts = []
    # пламя из сопла
    parts.append(f'<path d="M 40 62 Q 14 52 2 66 Q 14 78 40 72 Z" fill="{flame}" stroke="#B8380C" stroke-width="2.6"/>')
    # хвостовые рули
    parts.append(poly([(60, 60), (30, 14), (84, 14), (112, 56)], dark, OUT))
    parts.append(poly([(60, 68), (22, 84), (30, 96), (80, 82)], dark, OUT_S + 0.4))
    # фюзеляж: длинный, к носу сужается
    parts.append(path('M 40 58 L 190 46 Q 280 44 372 66 Q 280 88 190 90 L 40 76 Q 30 67 40 58 Z', steel, OUT))
    parts.append(path('M 60 66 L 300 62 L 300 68 L 60 72 Z', '#F28A2E', 0, 'fill-opacity=".92"'))
    parts.append(hi(80, 52, 190, 4, op=0.45))
    # кабина
    parts.append(cockpit(defs, 'M 214 48 Q 250 28 300 52 L 286 62 L 220 62 Z'))
    parts.append(f'<path d="M 232 50 L 252 38 L 260 40 L 242 54 Z" fill="#FFFFFF" fill-opacity=".5"/>')
    # стреловидное крыло снизу
    parts.append(poly([(150, 76), (252, 80), (200, 118), (126, 112)], dark, OUT))
    parts.append(line(160, 84, 214, 82, '#FFFFFF', 3, 0.35))
    # воздухозаборник и сопло
    parts.append(rr(172, 62, 30, 14, 6, '#2F3548', OUT_S))
    parts.append(rr(34, 56, 14, 22, 5, '#3A3F4F', OUT_S))
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- тяжёлый вертолёт
def heavy(frame):
    W, H = 400, 180
    defs = []
    body = fillg(defs, '#8C9BB3', 0.3, 0.22)
    dark = fillg(defs, '#5E6C86', 0.1, 0.25)
    orange = fillg(defs, '#F28A2E', 0.25, 0.2)
    parts = []
    # задний пилон и винт
    parts.append(poly([(48, 92), (62, 38), (96, 38), (112, 92)], dark, OUT))
    parts.append(rr(70, 26, 14, 14, 4, '#4B4F61', OUT_S))
    # передний пилон
    parts.append(rr(278, 36, 16, 26, 4, '#4B4F61', OUT_S))
    # шасси
    parts.append(line(112, 132, 108, 156, OUTLINE, 5))
    parts.append(line(300, 132, 304, 156, OUTLINE, 5))
    parts.append(wheel(106, 160, 12))
    parts.append(wheel(306, 160, 12))
    # корпус: длинный бокс с кабиной впереди и аппарелью сзади
    parts.append(path('M 40 96 L 54 76 L 290 70 Q 360 74 378 108 Q 374 136 340 138 L 66 136 Q 36 130 40 96 Z', body, OUT))
    parts.append(path('M 300 78 Q 356 82 366 108 L 322 112 Q 316 90 300 78 Z', lg(defs, '#D8F2FF', '#6FB8EE'), OUT_S + 0.4))
    parts.append(rr(70, 112, 232, 10, 5, orange, 0, 'fill-opacity=".95"'))
    parts.append(poly([(40, 100), (48, 132), (66, 136), (62, 100)], dark, OUT_S + 0.4))
    parts.append(hi(80, 84, 190, 5, op=0.4))
    for x in (118, 168, 218):
        parts.append(rr(x, 90, 26, 16, 5, lg(defs, '#D8F2FF', '#6FB8EE'), OUT_S))
    # винты
    if frame == 0:
        parts.append(rr(0, 14, 170, 9, 4.5, '#3A3F4F', OUT_S))
        parts.append(rr(220, 24, 176, 9, 4.5, '#3A3F4F', OUT_S))
    else:
        parts.append(f'<ellipse cx="86" cy="22" rx="84" ry="9" fill="#C8D2E6" fill-opacity=".5" stroke="{OUTLINE}" stroke-width="2.4" stroke-opacity=".55"/>')
        parts.append(f'<ellipse cx="308" cy="30" rx="88" ry="9" fill="#C8D2E6" fill-opacity=".5" stroke="{OUTLINE}" stroke-width="2.4" stroke-opacity=".55"/>')
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- лайнер
AIRLINERS = {
    'a': dict(stripe='#2F78D6', tail='#2F78D6'),
    'b': dict(stripe='#2FA866', tail='#2FA866'),
}


def airliner(kind):
    P = AIRLINERS[kind]
    W, H = 520, 170
    defs = []
    white = fillg(defs, '#F7F9FC', 0.0, 0.14)
    dark = fillg(defs, '#C5CFE2', 0.1, 0.12)
    tailc = fillg(defs, P['tail'], 0.25, 0.2)
    parts = []
    # хвостовое оперение
    parts.append(poly([(70, 84), (30, 14), (96, 14), (146, 76)], tailc, OUT))
    parts.append(poly([(60, 94), (16, 108), (24, 120), (100, 100)], dark, OUT_S + 0.4))
    # дальнее крыло и двигатель
    parts.append(poly([(250, 100), (350, 104), (300, 140), (214, 134)], dark, OUT_S + 0.6))
    # фюзеляж: длинная сигара с носом справа
    parts.append(path('M 40 84 L 120 62 Q 330 52 470 70 Q 508 78 504 92 Q 496 108 460 112 Q 330 128 120 112 Z', white, OUT))
    parts.append(path('M 100 98 L 480 96 L 470 104 L 106 108 Z', P['stripe'], 0, 'fill-opacity=".95"'))
    parts.append(hi(150, 66, 280, 6, op=0.5))
    # окна и кабина
    for i in range(18):
        parts.append(rr(150 + i * 15.5, 76, 8, 11, 3.5, lg(defs, '#D8F2FF', '#6FB8EE'), 2.0))
    parts.append(path('M 448 70 Q 480 72 494 86 L 456 86 Z', lg(defs, '#BFE3FA', '#5FAEE6'), OUT_S))
    # ближнее крыло и двигатель
    parts.append(poly([(236, 106), (360, 108), (292, 156), (186, 148)], white, OUT))
    parts.append(line(250, 114, 346, 114, P['stripe'], 4, 0.9))
    parts.append(rr(270, 128, 70, 28, 13, lg(defs, '#E6EBF5', '#9DA9C0'), OUT_S + 0.4))
    parts.append(rr(334, 132, 12, 20, 5, '#3A3F4F', OUT_S))
    return sprite(W, H, defs, parts)


# ---------------------------------------------------------------- грузовой гигант
def cargo():
    W, H = 600, 230
    defs = []
    body = fillg(defs, '#C6CFDE', 0.25, 0.16)
    dark = fillg(defs, '#8693AD', 0.1, 0.22)
    yellow = fillg(defs, '#F7C93A', 0.25, 0.2)
    parts = []
    # высокий Т-образный хвост
    parts.append(poly([(88, 118), (56, 14), (136, 14), (170, 100)], yellow, OUT))
    parts.append(poly([(36, 20), (30, 40), (170, 40), (166, 20)], dark, OUT))
    # дальнее крыло
    parts.append(poly([(280, 140), (410, 146), (350, 188), (240, 176)], dark, OUT_S + 0.6))
    # фюзеляж: толстый, хвост задран, нос с «горбом» кабины
    parts.append(path('M 34 100 L 150 84 Q 330 70 520 84 Q 570 92 576 120 Q 570 154 520 160 Q 330 176 150 156 Q 44 140 34 100 Z', body, OUT))
    parts.append(path('M 500 82 Q 548 84 566 104 L 508 108 Z', lg(defs, '#BFE3FA', '#5FAEE6'), OUT_S))
    parts.append(rr(120, 118, 380, 12, 6, yellow, 0, 'fill-opacity=".95"'))
    parts.append(hi(170, 88, 310, 6, op=0.45))
    # грузовая аппарель сзади и двери
    parts.append(poly([(34, 100), (50, 150), (92, 156), (74, 100)], dark, OUT_S + 0.6))
    for x in (190, 270, 350, 430):
        parts.append(line(x, 98, x, 150, OUTLINE, 2.4, 0.5))
    # ближнее крыло и два двигателя
    parts.append(poly([(260, 142), (410, 146), (330, 206), (210, 192)], body, OUT))
    for (x, y) in ((250, 176), (338, 184)):
        parts.append(rr(x, y, 70, 34, 16, lg(defs, '#E6EBF5', '#9DA9C0'), OUT_S + 0.4))
        parts.append(rr(x + 62, y + 4, 12, 26, 6, '#3A3F4F', OUT_S))
    return sprite(W, H, defs, parts)


def main():
    n = 0
    out = Z3 / 'planes'
    for kind in ('a', 'b'):
        for f in (0, 1):
            _w(out / f'z3-plane-{kind}-{f + 1}.svg', plane(kind, f))
            _w(out / f'z3-heli-{kind}-{f + 1}.svg', heli(kind, f))
            n += 2
    _w(out / 'z3-fighter.svg', fighter())
    for f in (0, 1):
        _w(out / f'z3-heavy-{f + 1}.svg', heavy(f))
    for kind in ('a', 'b'):
        _w(out / f'z3-airliner-{kind}.svg', airliner(kind))
    _w(out / 'z3-cargo.svg', cargo())
    n += 1 + 2 + 2 + 1
    print(f'zone 3: written {n} svg files')


if __name__ == '__main__':
    main()
