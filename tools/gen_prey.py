#!/usr/bin/env python3
"""Генератор добычи зоны 1 (SVG): жук и червячок, вид сверху.

Запуск из корня проекта:  python tools/gen_prey.py

По наброску автора: насекомые видны сверху, ползают по земле и оставляют за собой небольшой след
(след рисует игра частицами). У каждого вида два кадра («шаг 1» и «шаг 2»): игра переключает их, и добыча «семенит».
Холст 128×128, добыча смотрит вправо (влево её отражает игра). Основной цвет светлый: игра красит его оттенками
по размеру и виду, поэтому в рисунке нет тёмных заливок, кроме контура.
"""
import math

from svgkit import ROOT, OUTLINE, mix, lighten, lgrad, svg, write

FOOD = ROOT / 'design' / 'zone-1-underground' / 'food'
SIZE = 128
C = SIZE // 2
OUT = 4.5


def beetle_svg(pose):
    """Жук сверху: надкрылья, шов, голова с глазками и усиками, шесть лапок. pose 0/1: чередование лапок (шаг)."""
    shell, shell_dark = '#F5B84A', '#C9801E'
    defs = [lgrad('bt-shell', [(0, lighten(shell, .45)), (.5, shell), (1, shell_dark)], 0, 0, 0, 1),
            lgrad('bt-thorax', [(0, mix(shell, shell_dark, .5)), (1, mix(shell, shell_dark, .95))], 0, 0, 0, 1)]
    g = []
    # лапки: тройками (две передние и задняя с одной стороны шагают вместе с средней с другой)
    for k, x in enumerate((20, 2, -16)):
        for side in (-1, 1):
            fwd = 1 if ((k + (0 if side < 0 else 1) + pose) % 2) else -1
            hip = (x, side * 20)
            knee = (x + fwd * 7, side * 34)
            foot = (x + fwd * 15, side * 45)
            d = f'M {C + hip[0]} {C + hip[1]} L {C + knee[0]} {C + knee[1]} L {C + foot[0]} {C + foot[1]}'
            g.append(f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="7.5"/>')
            g.append(f'<path d="{d}" fill="none" stroke="{mix(shell, shell_dark, .7)}" stroke-width="3.2"/>')
    # усики
    for side in (-1, 1):
        d = f'M {C + 50} {C + side * 5} Q {C + 58} {C + side * 14} {C + 62} {C + side * 9}'
        g.append(f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="4.5"/>')
    # надкрылья
    g.append(f'<ellipse cx="{C - 8}" cy="{C}" rx="34" ry="27" fill="url(#bt-shell)" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    g.append(f'<path d="M {C - 41} {C} L {C + 24} {C}" fill="none" stroke="{OUTLINE}" stroke-width="3" stroke-opacity=".75"/>')
    for side in (-1, 1):
        g.append(f'<path d="M {C - 28} {C + side * 14} Q {C - 8} {C + side * 20} {C + 12} {C + side * 15}" fill="none" '
                 f'stroke="#FFFFFF" stroke-opacity=".5" stroke-width="3.4"/>')
    # грудь и голова
    g.append(f'<ellipse cx="{C + 24}" cy="{C}" rx="13" ry="19" fill="url(#bt-thorax)" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    g.append(f'<circle cx="{C + 42}" cy="{C}" r="10.5" fill="{mix(shell, shell_dark, .8)}" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    for side in (-1, 1):
        g.append(f'<circle cx="{C + 46}" cy="{C + side * 5}" r="3.6" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="1.6"/>')
        g.append(f'<circle cx="{C + 47}" cy="{C + side * 5}" r="1.6" fill="{OUTLINE}"/>')
    return svg(SIZE, defs, f'<g stroke-linejoin="round" stroke-linecap="round">{"".join(g)}</g>')


def worm_svg(pose):
    """Червячок сверху: розовое тело в виде буквы S с кольцами и светлым пояском. pose 0/1: зеркальный изгиб."""
    sgn = 1 if pose == 0 else -1
    pts = [(-56, 14 * sgn), (-30, -14 * sgn), (-6, 40 * sgn), (22, 8 * sgn), (34, -8 * sgn), (44, -12 * sgn), (52, -6 * sgn)]

    def bez(p0, p1, p2, p3, t):
        u = 1 - t
        return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])

    def pos(t):
        if t < 0.5:
            return bez(pts[0], pts[1], pts[2], pts[3], t * 2)
        return bez(pts[3], pts[4], pts[5], pts[6], (t - 0.5) * 2)

    path = ' '.join(('M' if i == 0 else 'L') + f' {C + pos(i / 60)[0]:.1f} {C + pos(i / 60)[1]:.1f}' for i in range(61))
    base, dark = '#F2A3A0', '#C96A66'
    g = [f'<path d="{path}" fill="none" stroke="{OUTLINE}" stroke-width="24"/>',
         f'<path d="{path}" fill="none" stroke="{base}" stroke-width="15.5"/>',
         f'<path d="{path}" fill="none" stroke="{lighten(base, .45)}" stroke-width="4.5" transform="translate(0 -3)" stroke-opacity=".7"/>']
    # кольца
    for i in range(4, 58, 3):
        t = i / 60
        x, y = pos(t)
        x2, y2 = pos(min(1, t + 0.01))
        ang = math.atan2(y2 - y, x2 - x) + math.pi / 2
        dx, dy = math.cos(ang) * 6.6, math.sin(ang) * 6.6
        g.append(f'<path d="M {C + x - dx:.1f} {C + y - dy:.1f} L {C + x + dx:.1f} {C + y + dy:.1f}" stroke="{dark}" '
                 f'stroke-width="2.2" stroke-opacity=".8"/>')
    # поясок
    a, b = int(0.60 * 60), int(0.72 * 60)
    belt = ' '.join(('M' if i == a else 'L') + f' {C + pos(i / 60)[0]:.1f} {C + pos(i / 60)[1]:.1f}' for i in range(a, b + 1))
    g.append(f'<path d="{belt}" fill="none" stroke="{lighten(base, .55)}" stroke-width="15.5" stroke-linecap="butt"/>')
    # глазки на переднем конце
    hx, hy = pos(0.97)
    for off in (-5.5, 5.5):
        g.append(f'<circle cx="{C + hx + 2:.1f}" cy="{C + hy + off:.1f}" r="3.6" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="1.6"/>')
        g.append(f'<circle cx="{C + hx + 3:.1f}" cy="{C + hy + off:.1f}" r="1.6" fill="{OUTLINE}"/>')
    return svg(SIZE, [], f'<g stroke-linejoin="round" stroke-linecap="round">{"".join(g)}</g>')


def main():
    for old in FOOD.glob('*.svg'):
        old.unlink()
    write(FOOD / 'z1-beetle-a.svg', beetle_svg(0))
    write(FOOD / 'z1-beetle-b.svg', beetle_svg(1))
    write(FOOD / 'z1-worm-a.svg', worm_svg(0))
    write(FOOD / 'z1-worm-b.svg', worm_svg(1))
    print('prey: written 4 svg files (beetle and worm, 2 steps each)')


if __name__ == '__main__':
    main()
