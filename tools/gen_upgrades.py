#!/usr/bin/env python3
"""Генератор визуальных улучшений червя (SVG).

Запуск из корня проекта:  python tools/gen_upgrades.py

Сейчас: крылья, 5 ступеней (драконьи: кожистая перепонка на костяных «пальцах», когти, шипы, жар).
Броня (здоровье) и чешуя (скорость) появятся на Э4.

Базовый червь без крыльев. Первое улучшение прыжка даёт крылья 1-й ступени,
каждое следующее делает их больше и круче.

Крыло: холст 768×768, центр холста = точка `anchor-wing` на теле (она же ось взмаха).
Рисуется сразу в экранных координатах: червь смотрит вправо, рука поднимается вверх,
пальцы веером уходят назад над спиной (нижние пальцы заканчиваются выше линии тела).
Два слоя: back (дальнее крыло, за телом, чуть выше и меньше) и front (ближнее, перед телом).
Подходит всем персонажам: у них одна геометрия тела (gen_worm.py).

Правила: никаких пентаграмм, рун, сигилов и религиозных знаков (п. 3.4.2, 3.4.5): только
драконья фантастика.
"""
import json
import math
import random

from svgkit import ROOT, OUTLINE, OUT, mix, lighten, lgrad, qb, svg, write

WINGS = ROOT / 'design' / 'upgrades' / 'wings'
CANVAS = 768
C = CANVAS // 2
FAR_DARK = '#12060F'
FAR_SCALE = 0.86
NEAR_ROT = -8         # всё крыло откинуто назад (против часовой) для динамики
FAR_ROT = 6           # дальнее крыло: откинуто меньше, то есть поднято выше ближнего

# Точки заданы долями длины L в экранной системе с началом в корне крыла: x вправо (к голове), y вниз.
WRIST = (-0.10, -0.60)        # запястье
ARM_CTRL = (0.05, -0.30)      # дуга руки выгибается вперёд
BODY = (-0.08, 0.04)          # где перепонка крепится к спине
TIERS = {
    1: dict(name='Крылышки дракончика', L=100, c=0.30,
            tips=[(-0.42, -0.96), (-0.78, -0.62), (-0.66, -0.12)],
            inner='#6B1B3A', outer='#B8405E', bone='#EAD9B0', claw='#F6EBD0', pad='#4A1830',
            spikes=0, plates=0, glow=None, rim=None, flames=False, pad_spikes=0),
    2: dict(name='Кожистые крылья', L=140, c=0.36,
            tips=[(-0.42, -0.98), (-0.74, -0.78), (-0.88, -0.44), (-0.66, -0.08)],
            inner='#701538', outer='#CC4660', bone='#EDDDB6', claw='#F8EDD2', pad='#4A1530',
            spikes=0, plates=0, glow=None, rim=None, flames=False, pad_spikes=0),
    3: dict(name='Шипастые крылья', L=185, c=0.40,
            tips=[(-0.42, -0.98), (-0.72, -0.80), (-0.88, -0.48), (-0.72, -0.10)],
            inner='#5A1238', outer='#D63B55', bone='#F0DFB4', claw='#FAEFD6', pad='#3E1030',
            spikes=3, plates=0, glow='#FF8A3D', rim=None, flames=False, pad_spikes=0),
    4: dict(name='Раскалённые крылья', L=235, c=0.44,
            tips=[(-0.42, -0.98), (-0.70, -0.82), (-0.86, -0.56), (-0.88, -0.28), (-0.62, -0.04)],
            inner='#3F0C30', outer='#E0304A', bone='#F4E2AE', claw='#FFF2CF', pad='#32092A',
            spikes=4, plates=2, glow='#FFB347', rim='#FF8A2E', flames=False, pad_spikes=2),
    5: dict(name='Пламенные крылья дракона', L=290, c=0.46,
            tips=[(-0.42, -0.98), (-0.70, -0.80), (-0.86, -0.50), (-0.84, -0.22), (-0.64, -0.06), (-0.42, -0.02)],
            inner='#260A2A', outer='#F0282A', bone='#FFE49C', claw='#FFF6D6', pad='#240826',
            spikes=5, plates=3, glow='#FFD66B', rim='#FF9A2E', flames=True, pad_spikes=3),
}
PLATE_GOLD = '#E0A93C'


# ---------- геометрия ----------
def pt(p):
    return f'{p[0]:.1f} {p[1]:.1f}'


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def unit(v):
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


def qtan(p0, p1, p2, t):
    return (2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]),
            2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1]))


def taper(p0, p1, p2, w0, w1, n=16):
    """Костяная «рука» или «палец» с сужением: многоугольник вдоль кривой."""
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        x, y = qb(p0, p1, p2, t)
        tx, ty = unit(qtan(p0, p1, p2, t))
        nx, ny = -ty, tx
        w = (w0 + (w1 - w0) * t) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    pts = left + right[::-1]
    return 'M ' + ' L '.join(pt(p) for p in pts) + ' Z'


def scallop(a, b, w, c):
    """Контрольная точка вогнутой кромки перепонки между кончиками пальцев a и b (тянется к запястью w)."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    return (mx + (w[0] - mx) * c, my + (w[1] - my) * c)


def tri(base, d, length, width, fill, sw=3.0):
    """Треугольник-коготь/шип: основание в base, вдоль d."""
    nx, ny = -d[1], d[0]
    a = (base[0] + nx * width / 2, base[1] + ny * width / 2)
    b = (base[0] - nx * width / 2, base[1] - ny * width / 2)
    tip = (base[0] + d[0] * length, base[1] + d[1] * length)
    return (f'<path d="M {pt(a)} L {pt(tip)} L {pt(b)} Z" fill="{fill}" stroke="{OUTLINE}" '
            f'stroke-width="{sw}"/>')


def flame(base, d, length, width):
    """Язык пламени: внешний оранжевый и внутренний жёлтый."""
    out = []
    for k, col in ((1.0, '#FF7A1A'), (0.58, '#FFE04D')):
        ln, w = length * k, width * (1.0 if k == 1.0 else 0.55)
        nx, ny = -d[1], d[0]
        bl = (base[0] + nx * w / 2, base[1] + ny * w / 2)
        br = (base[0] - nx * w / 2, base[1] - ny * w / 2)
        tip = (base[0] + d[0] * ln, base[1] + d[1] * ln)
        c1 = (base[0] + d[0] * ln * 0.55 + nx * w * 0.6, base[1] + d[1] * ln * 0.55 + ny * w * 0.6)
        c2 = (base[0] + d[0] * ln * 0.55 - nx * w * 0.2, base[1] + d[1] * ln * 0.55 - ny * w * 0.2)
        stroke = ' stroke="#B8380C" stroke-width="1.8"' if k == 1.0 else ''
        out.append(f'<path d="M {pt(bl)} Q {pt(c1)} {pt(tip)} Q {pt(c2)} {pt(br)} Z" fill="{col}"{stroke}/>')
    return ''.join(out)


# ---------- крыло ----------
def wing_svg(tier, layer):
    T = TIERS[tier]
    near = layer == 'front'
    L = T['L']
    p = f'wings-t{tier}-{layer}'
    shade = (lambda c: c) if near else (lambda c: mix(c, FAR_DARK, .38))
    inner, outer = shade(T['inner']), shade(T['outer'])
    bone, claw, pad = shade(T['bone']), shade(T['claw']), shade(T['pad'])
    glow = shade(T['glow']) if T['glow'] else None
    rim = shade(T['rim']) if T['rim'] else None

    def S(fx, fy):
        return (fx * L, fy * L)

    R = (0.0, 0.0)
    CE = S(*ARM_CTRL)
    W = S(*WRIST)
    tips = [S(*t) for t in T['tips']]
    B = S(*BODY)
    pts = tips + [B]
    ctrls = [scallop(a, b, W, T['c']) for a, b in zip(pts[:-1], pts[1:])]
    gaps = list(zip(pts[:-1], ctrls, pts[1:]))
    edge = 'M ' + pt(tips[0]) + ''.join(f' Q {pt(c)} {pt(b)}' for c, b in zip(ctrls, pts[1:]))

    g = []
    # жар по кромке (под перепонкой)
    if rim:
        g.append(f'<path d="{edge}" fill="none" stroke="{rim}" stroke-width="{0.07 * L:.1f}" stroke-opacity=".30"/>')
    # языки пламени (под перепонкой, торчат из-за кромки)
    if T['flames']:
        n = 0
        for a, c, b in gaps[:-1]:
            for t in (0.25, 0.5, 0.75):
                q = qb(a, c, b, t)
                g.append(flame(q, unit((q[0] - W[0], q[1] - W[1])), L * (0.10 if n % 2 == 0 else 0.07), L * 0.05))
                n += 1
        for tp in tips:
            g.append(flame(tp, unit((tp[0] - W[0], tp[1] - W[1])), L * 0.15, L * 0.06))

    # перепонка: тёмная у корня, ярче к кончикам
    defs = [lgrad(f'{p}-memb', [(0, inner), (.55, mix(inner, outer, .6)), (1, outer)], 1, 1, 0, 0)]
    mem = ('M 0 0 Q ' + pt(CE) + ' ' + pt(W) + ' L ' + pt(tips[0]) +
           ''.join(f' Q {pt(c)} {pt(b)}' for c, b in zip(ctrls, pts[1:])) + ' Z')
    g.append(f'<path d="{mem}" fill="url(#{p}-memb)" stroke="{OUTLINE}" stroke-width="{OUT - 1}"/>')
    # блик по кромке: та же линия, чуть внутрь
    g.append(f'<path d="{edge}" transform="translate({pt(W)}) scale(.965) translate({-W[0]:.1f} {-W[1]:.1f})" '
             f'fill="none" stroke="{lighten(outer, .55)}" stroke-opacity=".55" stroke-width="2.4"/>')

    # прожилки перепонки
    veins = []
    for i, (a, c, b) in enumerate(gaps):
        src = lerp(W, tips[i], 0.16)
        tgt = qb(a, c, b, 0.5)
        veins.append(f'M {pt(src)} Q {pt(lerp(src, tgt, 0.55))} {pt(tgt)}')
    vein_col = mix(inner, '#000000', .45)
    g.append('<g fill="none" stroke-linecap="round">' +
             ''.join(f'<path d="{v}" stroke="{vein_col}" stroke-opacity=".5" stroke-width="2.4"/>' for v in veins) +
             '</g>')
    if glow:
        g.append('<g fill="none" stroke-linecap="round">' +
                 ''.join(f'<path d="{v}" stroke="{glow}" stroke-opacity=".25" stroke-width="6.5"/>' for v in veins) +
                 ''.join(f'<path d="{v}" stroke="{glow}" stroke-opacity=".9" stroke-width="2.4"/>' for v in veins) +
                 '</g>')

    # пальцы слегка выгнуты вверх; когти на кончиках лежат под костью
    fingers = []
    for tp in tips:
        mid = lerp(W, tp, 0.5)
        nrm = unit((-(tp[1] - W[1]), tp[0] - W[0]))
        if nrm[1] > 0:
            nrm = (-nrm[0], -nrm[1])
        ctl = (mid[0] + nrm[0] * 0.035 * L, mid[1] + nrm[1] * 0.035 * L)
        fingers.append((ctl, tp))
        g.append(tri(tp, unit(qtan(W, ctl, tp, 1.0)), max(8.0, 0.08 * L), max(6.0, 0.05 * L), claw))

    # рука и пальцы
    aw0, aw1 = max(9.0, 0.095 * L), max(6.0, 0.055 * L)
    for i, (ctl, tp) in enumerate(fingers):
        fw0 = max(7.0, (0.06 if i == 0 else 0.048) * L)
        fw1 = max(3.6, 0.02 * L)
        g.append(f'<path d="{taper(W, ctl, tp, fw0, fw1)}" fill="{bone}" stroke="{OUTLINE}" stroke-width="3.2"/>')
    g.append(f'<path d="{taper(R, CE, W, aw0, aw1)}" fill="{bone}" stroke="{OUTLINE}" stroke-width="3.4"/>')

    # шипы по передней кромке руки (наружу, вперёд)
    if T['spikes']:
        n = T['spikes']
        for i in range(n):
            t = 0.22 + 0.68 * (i / max(1, n - 1))
            q = qb(R, CE, W, t)
            tx, ty = unit(qtan(R, CE, W, t))
            nout = (ty, -tx)
            if nout[0] < 0:
                nout = (-nout[0], -nout[1])
            wid = aw0 + (aw1 - aw0) * t
            base = (q[0] + nout[0] * (wid / 2 - 1), q[1] + nout[1] * (wid / 2 - 1))
            g.append(tri(base, nout, (0.07 + 0.004 * i) * L, max(6.0, 0.05 * L), claw, 2.8))

    # костяные пластины на руке
    for i in range(T['plates']):
        t = 0.18 + 0.22 * i
        q = qb(R, CE, W, t)
        tx, ty = qtan(R, CE, W, t)
        ang = math.degrees(math.atan2(ty, tx))
        wid = aw0 + (aw1 - aw0) * t
        pw, ph = 0.1 * L, wid + 5
        g.append(f'<rect x="{-pw / 2:.1f}" y="{-ph / 2:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="{ph * 0.3:.1f}" '
                 f'fill="{shade(PLATE_GOLD)}" stroke="{OUTLINE}" stroke-width="3" '
                 f'transform="translate({pt(q)}) rotate({ang:.1f})"/>')

    # суставы
    ep = qb(R, CE, W, 0.5)
    g.append(f'<circle cx="{ep[0]:.1f}" cy="{ep[1]:.1f}" r="{max(5.5, 0.05 * L):.1f}" fill="{bone}" '
             f'stroke="{OUTLINE}" stroke-width="3"/>')
    g.append(f'<circle cx="{W[0]:.1f}" cy="{W[1]:.1f}" r="{max(6.5, 0.062 * L):.1f}" fill="{bone}" '
             f'stroke="{OUTLINE}" stroke-width="3.2"/>')
    # коготь-«большой палец» на запястье: изогнутый крючок вперёд и вверх
    h = max(12.0, 0.15 * L)
    bw = max(5.0, 0.04 * L)
    bl, br = (W[0] - bw * 0.2, W[1] + bw), (W[0] + bw * 0.9, W[1] - bw * 0.6)
    c1 = (W[0] - bw * 0.1, W[1] - h * 0.55)
    tip = (W[0] + h * 0.62, W[1] - h * 0.95)
    c2 = (W[0] + h * 0.55, W[1] - h * 0.2)
    g.append(f'<path d="M {pt(bl)} Q {pt(c1)} {pt(tip)} Q {pt(c2)} {pt(br)} Z" fill="{claw}" '
             f'stroke="{OUTLINE}" stroke-width="3"/>')

    # «плечо»: закрывает стык с телом; у старших ступеней с шипами назад-вниз
    rx = max(11.0, 0.08 * L)
    ry = rx * 0.72
    for i in range(T['pad_spikes']):
        a = math.radians(120 + 28 * i)
        d = (math.cos(a), math.sin(a))
        base = (d[0] * rx * 0.8, d[1] * ry * 0.8)
        g.append(tri(base, d, 0.1 * L, 0.07 * L, claw, 2.8))
    g.append(f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="{pad}" stroke="{OUTLINE}" stroke-width="4"/>')
    g.append(f'<ellipse cx="{-rx * 0.25:.1f}" cy="{-ry * 0.3:.1f}" rx="{rx * 0.45:.1f}" ry="{ry * 0.22:.1f}" '
             f'fill="#FFFFFF" fill-opacity=".25"/>')

    # искры над пламенем
    if T['flames']:
        rnd = random.Random(tier * 31 + (1 if near else 2))
        for _ in range(8):
            a, c, b = gaps[rnd.randrange(len(gaps) - 1)]
            q = qb(a, c, b, rnd.uniform(0.2, 0.8))
            d = unit((q[0] - W[0], q[1] - W[1]))
            dist = L * rnd.uniform(0.12, 0.24)
            g.append(f'<circle cx="{q[0] + d[0] * dist:.1f}" cy="{q[1] + d[1] * dist:.1f}" '
                     f'r="{rnd.uniform(1.8, 3.2):.1f}" fill="#FFD66B" fill-opacity=".9"/>')

    far = f' rotate({NEAR_ROT})' if near else f' rotate({FAR_ROT}) scale({FAR_SCALE})'
    body = (f'<g transform="translate({C} {C}){far}" stroke-linejoin="round" stroke-linecap="round">'
            f'{"".join(g)}</g>')
    return svg(CANVAS, defs, body)


def main():
    n = 0
    for tier in TIERS:
        for layer in ('back', 'front'):
            write(WINGS / f'wings-t{tier}-{layer}.svg', wing_svg(tier, layer))
            n += 1
    # данные для страницы превью: названия и размеры ступеней
    info = [{'tier': t, 'name': T['name'], 'L': T['L']} for t, T in TIERS.items()]
    write(ROOT / 'design' / 'preview' / 'upgrades-geometry.js',
          'window.WING_TIERS = ' + json.dumps(info, ensure_ascii=False) + ';\n'
          'window.WING_CANVAS = ' + str(CANVAS) + ';\n')
    write(WINGS / 'wings.json', json.dumps({'canvas': CANVAS, 'tiers': info}, ensure_ascii=False, indent=1) + '\n')
    print(f'upgrades: written {n} wing files (5 tiers x 2 layers) + upgrades-geometry.js + wings.json')


if __name__ == '__main__':
    main()
