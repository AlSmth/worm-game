#!/usr/bin/env python3
"""Генератор сокровищ (SVG): монета, самоцвет, малый и большой сундуки.

Запуск из корня проекта:  python tools/gen_treasure.py

За съеденные сокровища игрок получает монеты (концепт, раздел 8). Монета вращается в коде (сжатие по ширине),
самоцвет светлый и почти белый: игра красит его в рубин, изумруд, сапфир или аметист умножением цвета.
В рисунках нет текста.
"""
import math

from svgkit import ROOT, OUTLINE, mix, lighten, lgrad, rgrad, svg, write

OUT_DIR = ROOT / 'design' / 'treasure'
OUT = 4.0


def star_path(cx, cy, r_out, r_in, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'


def sparkle(cx, cy, r, fill='#FFFFFF', stroke='none', sw=0):
    d = (f'M {cx:.1f} {cy - r:.1f} Q {cx:.1f} {cy:.1f} {cx + r:.1f} {cy:.1f} Q {cx:.1f} {cy:.1f} {cx:.1f} {cy + r:.1f} '
         f'Q {cx:.1f} {cy:.1f} {cx - r:.1f} {cy:.1f} Q {cx:.1f} {cy:.1f} {cx:.1f} {cy - r:.1f} Z')
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def coin_svg():
    gold, deep = '#F7B731', '#C47A0C'
    defs = [lgrad('coin-g', [(0, '#FFEFA0'), (.5, gold), (1, '#D8870F')], 0, 0, 1, 1)]
    art = (f'<g transform="translate(32 32)" stroke-linejoin="round" stroke-linecap="round">'
           f'<circle r="27" fill="url(#coin-g)" stroke="{OUTLINE}" stroke-width="{OUT}"/>'
           f'<circle r="19.5" fill="none" stroke="{deep}" stroke-width="2.6"/>'
           f'<path d="{star_path(0, 1, 11.5, 5)}" fill="#F0A21C" stroke="{deep}" stroke-width="1.8"/>'
           f'<path d="M -20 -8 A 21.5 21.5 0 0 1 3 -21" fill="none" stroke="#FFFFFF" stroke-opacity=".8" stroke-width="3.4"/>'
           f'</g>')
    return svg(64, defs, art)


def gem_svg():
    """Светлый самоцвет: грани разных оттенков серого, цвет игра подставляет умножением."""
    out = [(12, 24), (21, 11), (43, 11), (52, 24), (32, 54)]
    facets = [
        ([(21, 11), (43, 11), (38, 24), (26, 24)], '#FFFFFF'),
        ([(21, 11), (26, 24), (12, 24)], '#DCE8F4'),
        ([(43, 11), (52, 24), (38, 24)], '#C6D7E8'),
        ([(12, 24), (26, 24), (32, 54)], '#B0C5DA'),
        ([(26, 24), (38, 24), (32, 54)], '#D9E6F2'),
        ([(38, 24), (52, 24), (32, 54)], '#9DB5CC'),
    ]
    g = []
    for pts, fill in facets:
        g.append(f'<path d="M {" L ".join(f"{x} {y}" for x, y in pts)} Z" fill="{fill}" stroke="#6F8AA6" stroke-width="1.6"/>')
    g.append(f'<path d="M {" L ".join(f"{x} {y}" for x, y in out)} Z" fill="none" stroke="{OUTLINE}" stroke-width="{OUT - 0.6}"/>')
    g.append(sparkle(22, 17, 7.5))
    return svg(64, [], f'<g stroke-linejoin="round" stroke-linecap="round">{"".join(g)}</g>')


def chest_svg(big):
    """Сундук: деревянный корпус, выпуклая крышка, золотые полосы и замок. Большой богаче: камень на крышке, лишние полосы."""
    S = 256 if big else 128
    k = S / 128
    wood, wood_dark, wood_light = '#B9753A', '#8A5226', '#D69A55'
    gold, gold_dark = '#F7B731', '#C47A0C'
    defs = [lgrad('ch-body', [(0, wood_light), (1, wood_dark)]),
            lgrad('ch-lid', [(0, lighten(wood_light, .2)), (1, wood)]),
            lgrad('ch-gold', [(0, '#FFEFA0'), (.5, gold), (1, gold_dark)], 0, 0, 1, 1),
            rgrad('ch-gem', [(0, '#FFC4CF'), (.5, '#FF4D6D'), (1, '#A8132F')])]
    sw = 4.2
    g = []
    # корпус
    g.append(f'<rect x="16" y="58" width="96" height="52" rx="6" fill="url(#ch-body)" stroke="{OUTLINE}" stroke-width="{sw}"/>')
    for x in (40, 64, 88):
        g.append(f'<path d="M {x} 62 L {x} 106" stroke="{wood_dark}" stroke-width="2" stroke-opacity=".7"/>')
    # крышка
    g.append(f'<path d="M 12 62 Q 12 24 64 24 Q 116 24 116 62 Z" fill="url(#ch-lid)" stroke="{OUTLINE}" stroke-width="{sw}"/>')
    g.append(f'<path d="M 24 50 Q 30 36 56 32" fill="none" stroke="#FFFFFF" stroke-opacity=".45" stroke-width="4"/>')
    # золотые полосы
    for x in ((30, 98) if not big else (28, 64, 100)):
        g.append(f'<path d="M {x} 34 L {x} 108" stroke="{OUTLINE}" stroke-width="{16 if not big else 14}"/>')
        g.append(f'<path d="M {x} 34 L {x} 108" stroke="url(#ch-gold)" stroke-width="{9 if not big else 8}"/>')
    g.append(f'<rect x="10" y="56" width="108" height="11" rx="3" fill="url(#ch-gold)" stroke="{OUTLINE}" stroke-width="{sw - 0.6}"/>')
    # замок
    g.append(f'<rect x="52" y="60" width="24" height="26" rx="5" fill="url(#ch-gold)" stroke="{OUTLINE}" stroke-width="{sw - 0.6}"/>')
    g.append(f'<circle cx="64" cy="70" r="4.2" fill="{OUTLINE}"/><path d="M 64 72 L 64 80" stroke="{OUTLINE}" stroke-width="3.4"/>')
    # заклёпки
    for x, y in ((20, 70), (108, 70), (20, 100), (108, 100)):
        g.append(f'<circle cx="{x}" cy="{y}" r="3.2" fill="{gold}" stroke="{OUTLINE}" stroke-width="1.8"/>')
    if big:
        # камень на крышке и блеск
        g.append(f'<path d="M 64 28 L 74 38 L 64 50 L 54 38 Z" fill="url(#ch-gem)" stroke="{OUTLINE}" stroke-width="3.2"/>')
        g.append(f'<path d="M 58 36 L 62 33" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round"/>')
        g.append(sparkle(100, 36, 9, '#FFFFFF', gold_dark, 1.4))
    else:
        g.append(sparkle(98, 36, 8, '#FFFFFF', gold_dark, 1.4))
    body = f'<g transform="scale({k})" stroke-linejoin="round" stroke-linecap="round">{"".join(g)}</g>'
    return svg(S, defs, body)


def main():
    write(OUT_DIR / 'treasure-coin.svg', coin_svg())
    write(OUT_DIR / 'treasure-gem.svg', gem_svg())
    write(OUT_DIR / 'treasure-chest-small.svg', chest_svg(False))
    write(OUT_DIR / 'treasure-chest-big.svg', chest_svg(True))
    print('treasure: written 4 svg files')


if __name__ == '__main__':
    main()
