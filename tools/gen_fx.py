#!/usr/bin/env python3
"""Генератор эффектов и частиц (SVG): звёздочка, точка, кольцо роста, всплеск «ам», облачко пыли, комочек земли,
блеск монеты, мягкое свечение, стрелка-подсказка, линия скорости.

Запуск из корня проекта:  python tools/gen_fx.py

Все частицы светлые: игра красит их умножением цвета (земля, звёзды, золото). В рисунках нет текста.
"""
import math

from svgkit import ROOT, OUTLINE, mix, lighten, lgrad, rgrad, svg, write

OUT_DIR = ROOT / 'design' / 'effects'


def star_path(cx, cy, r_out, r_in, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'


def fx_star():
    art = f'<path d="{star_path(20, 21, 17, 7.5)}" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="3" stroke-linejoin="round"/>'
    return svg(40, [], art)


def fx_dot():
    return svg(24, [], f'<circle cx="12" cy="12" r="9" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="3"/>')


def fx_ring():
    return svg(160, [], f'<circle cx="80" cy="80" r="66" fill="none" stroke="{OUTLINE}" stroke-width="16"/>'
                        f'<circle cx="80" cy="80" r="66" fill="none" stroke="#FFFFFF" stroke-width="9"/>')


def fx_glow():
    # мягкое свечение: прозрачность падает от центра к краю
    defs = ['<radialGradient id="fx-glow-g" cx=".5" cy=".5" r=".5">'
            '<stop offset="0" stop-color="#FFFFFF" stop-opacity=".95"/>'
            '<stop offset=".5" stop-color="#FFFFFF" stop-opacity=".45"/>'
            '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>']
    return svg(128, defs, '<circle cx="64" cy="64" r="64" fill="url(#fx-glow-g)"/>')


def fx_eat_pop():
    """Комикс-вспышка «ам»: зубчатая звезда без текста."""
    pts = []
    n = 12
    for i in range(n * 2):
        r = 58 if i % 2 == 0 else 33
        a = -math.pi / 2 + math.pi * i / n + (0.05 if i % 4 == 0 else 0)
        pts.append((64 + r * math.cos(a), 64 + r * math.sin(a)))
    d = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'
    defs = [rgrad('pop-g', [(0, '#FFFFFF'), (.45, '#FFF27A'), (1, '#FFB020')])]
    art = (f'<path d="{d}" fill="url(#pop-g)" stroke="{OUTLINE}" stroke-width="4.5" stroke-linejoin="round"/>'
           f'<circle cx="64" cy="64" r="15" fill="#FFFFFF" fill-opacity=".85"/>')
    return svg(128, defs, art)


def fx_dust_poof():
    """Облачко пыли: четыре перекрывающихся круга с контуром (мультяшный «пуф»)."""
    circles = [(34, 54, 22), (60, 40, 26), (66, 66, 24), (38, 70, 19)]
    g = []
    for cx, cy, r in circles:
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="3.2"/>')
    # внутренний слой без контура скрывает швы между кругами
    for cx, cy, r in circles:
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{r - 2}" fill="#FFFFFF"/>')
    g.append('<ellipse cx="54" cy="34" rx="11" ry="6" transform="rotate(-25 54 34)" fill="#DDE6F0" fill-opacity=".8"/>')
    return svg(96, [], f'<g stroke-linejoin="round">{"".join(g)}</g>')


def fx_dirt_chunk():
    pts = [(6, 18), (12, 7), (22, 5), (28, 14), (25, 25), (13, 27)]
    d = 'M ' + ' L '.join(f'{x} {y}' for x, y in pts) + ' Z'
    art = (f'<path d="{d}" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="2.6" stroke-linejoin="round"/>'
           f'<path d="M 12 11 L 20 9" stroke="#C9C9C9" stroke-width="2.4" stroke-linecap="round"/>')
    return svg(32, [], art)


def fx_coin_sparkle():
    r = 20
    d = (f'M 24 {24 - r} Q 24 24 {24 + r} 24 Q 24 24 24 {24 + r} Q 24 24 {24 - r} 24 Q 24 24 24 {24 - r} Z')
    return svg(48, [], f'<path d="{d}" fill="#FFFFFF" stroke="#E8A317" stroke-width="2" stroke-linejoin="round"/>'
                       f'<circle cx="24" cy="24" r="3.4" fill="#FFF6C0"/>')


def fx_arrow():
    """Стрелка-подсказка вниз: «конфетная», оранжевая, с обводкой."""
    defs = [lgrad('ar-g', [(0, '#FFE27A'), (1, '#FF9A00')])]
    d = 'M 22 6 L 42 6 L 42 30 L 54 30 L 32 58 L 10 30 L 22 30 Z'
    art = (f'<path d="{d}" fill="url(#ar-g)" stroke="{OUTLINE}" stroke-width="4.2" stroke-linejoin="round"/>'
           f'<path d="M 27 12 L 27 28" stroke="#FFFFFF" stroke-opacity=".7" stroke-width="3.6" stroke-linecap="round"/>')
    return svg(64, defs, art)


def fx_streak():
    """Линия скорости: тонкий штрих, к хвосту (слева) прозрачный. Игра красит его в голубой или золотой."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 24" width="128" height="24">\n'
            '<defs><linearGradient id="fx-streak-g" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/><stop offset=".55" stop-color="#FFFFFF" stop-opacity=".75"/>'
            '<stop offset="1" stop-color="#FFFFFF" stop-opacity="1"/></linearGradient></defs>\n'
            '<path d="M 0 12 Q 40 6 120 7 Q 128 7 128 12 Q 128 17 120 17 Q 40 18 0 12 Z" fill="url(#fx-streak-g)"/>\n</svg>\n')


def fx_boom(frame):
    """Мультяшный взрыв без текста, 4 кадра: вспышка, огненный шар, шар с дымом, рассеивание. Игра проигрывает их подряд."""
    n = 14
    cfg = [(36, 0.55, '#FFFFFF', '#FFF27A'), (56, 0.62, '#FFF27A', '#FF9A2E'), (62, 0.7, '#FFB347', '#E0541F'), (60, 0.78, '#B7A99C', '#6E6258')][frame]
    R, inner, c1, c2 = cfg
    pts = []
    for i in range(n * 2):
        r = R if i % 2 == 0 else R * inner
        a = -math.pi / 2 + math.pi * i / n + (0.07 if i % 4 == 0 else 0)
        pts.append((64 + r * math.cos(a), 64 + r * math.sin(a)))
    d = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'
    defs = [rgrad(f'boom{frame}-g', [(0, c1), (1, c2)])]
    art = f'<path d="{d}" fill="url(#boom{frame}-g)" stroke="{OUTLINE}" stroke-width="4.2" stroke-linejoin="round"/>'
    if frame < 3:
        art += f'<circle cx="64" cy="64" r="{R * 0.32:.1f}" fill="#FFFFFF" fill-opacity="{0.9 - 0.2 * frame:.2f}"/>'
    else:
        for (cx, cy, r) in ((40, 46, 14), (88, 52, 12), (60, 86, 16), (92, 88, 9), (34, 82, 9)):
            art += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#CFC6BC" fill-opacity=".85" stroke="{OUTLINE}" stroke-width="3"/>'
    return svg(128, defs, art)


def main():
    items = {
        'fx-star': fx_star(), 'fx-dot': fx_dot(), 'fx-tierup-ring': fx_ring(), 'fx-glow': fx_glow(),
        'fx-eat-pop': fx_eat_pop(), 'fx-dust-poof': fx_dust_poof(), 'fx-dirt-chunk': fx_dirt_chunk(),
        'fx-coin-sparkle': fx_coin_sparkle(), 'fx-arrow': fx_arrow(), 'fx-streak': fx_streak(),
        'fx-boom-1': fx_boom(0), 'fx-boom-2': fx_boom(1), 'fx-boom-3': fx_boom(2), 'fx-boom-4': fx_boom(3),
    }
    for name, text in items.items():
        write(OUT_DIR / f'{name}.svg', text)
    print(f'fx: written {len(items)} svg files')


if __name__ == '__main__':
    main()
