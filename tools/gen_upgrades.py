#!/usr/bin/env python3
"""Генератор визуальных улучшений червя (SVG).

Запуск из корня проекта:  python tools/gen_upgrades.py

Сейчас: крылья, 5 ступеней (ряд автора: жук, птица, светлые, тёмные, золотой дракон):
  1  Крылья жука: два овальных надкрылья с прожилками и тонкие плёнчатые крылья
  2  Птичьи крылья: синие перья, зубчатый край
  3  Светлые крылья: большие белые перья в несколько рядов, золотая кромка
  4  Тёмные крылья: кожистая перепонка на костяных «пальцах», шипы, жар по кромке
  5  Крылья золотого дракона: огромные, золотая перепонка, искры
Броня (чешуя, затем рога) и гребень за скорость появятся на Э4.

Названия нейтральные: слова «ангел», «демон», «ад», нимбы, кресты, пентаграммы, руны и прочие религиозные и оккультные
знаки в игре нельзя (пп. 3.4.2, 3.4.5, 8.3.6, риск R14 в docs/YANDEX_REQUIREMENTS.md).

Базовый червь без крыльев. Первое улучшение прыжка даёт крылья 1-й ступени, каждое следующее делает их больше и круче.

Крыло: холст 768×768, центр холста = точка `anchor-wing` на теле (она же ось взмаха).
Рисуется сразу в экранных координатах: червь смотрит вправо, рука поднимается вверх,
перья или пальцы веером уходят назад над спиной (нижние заканчиваются выше линии тела).
Два слоя: back (дальнее крыло, за телом, чуть выше и меньше) и front (ближнее, перед телом).
Подходит всем персонажам: у них одна геометрия тела (gen_worm.py).
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
    1: dict(kind='elytra', name='Крылья жука', L=100,
            shell='#F2A33A', shell_dark='#B8650F', shell_hi='#FFE2A6', vein='#6E3508',
            film='#EAF6FF', film_edge='#8FB0D0', pad='#6E3508'),
    2: dict(kind='feather', name='Птичьи крылья', L=140, flight=7, mid=0, cov_b=6, cov_c=7,
            dark='#2A62C4', base='#4D9BFF', tip='#EAF4FF', quill='#1D468F', arm='#2A62C4', trim=None, glow=None,
            pad='#244F9E', lean=-4),
    3: dict(kind='feather', name='Светлые крылья', L=190, flight=9, mid=8, cov_b=8, cov_c=9,
            dark='#BFD0EC', base='#F2F7FF', tip='#FFFFFF', quill='#9FB3D6', arm='#F2C54B', trim='#F2C54B', glow='#FFF3B8',
            pad='#D9A92E', lean=-4),
    4: dict(kind='leather', name='Тёмные крылья', L=240, c=0.44,
            tips=[(-0.42, -0.98), (-0.70, -0.82), (-0.86, -0.56), (-0.88, -0.28), (-0.62, -0.04)],
            inner='#22082C', outer='#8C1B4F', bone='#D8C8A8', claw='#F3EAD6', pad='#1A0820',
            spikes=4, plates=0, glow='#FF6A3D', rim='#FF5A2E', flames=False, pad_spikes=2, sparkles=False, plate_col='#E0A93C'),
    5: dict(kind='leather', name='Крылья золотого дракона', L=300, c=0.46,
            tips=[(-0.42, -0.98), (-0.70, -0.80), (-0.86, -0.50), (-0.84, -0.22), (-0.64, -0.06), (-0.42, -0.02)],
            inner='#8F4F0E', outer='#FFC933', bone='#FFF1B8', claw='#FFFBE6', pad='#7A4410',
            spikes=5, plates=3, glow='#FFF3A6', rim='#FFE27A', flames=False, pad_spikes=3, sparkles=True, plate_col='#E8A317'),
}


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


def shade_for(near):
    """Дальнее крыло темнее ближнего."""
    return (lambda c: c) if near else (lambda c: mix(c, FAR_DARK, .38))


def wrap(g, defs, near, lean=0):
    """Ближнее крыло откинуто назад, дальнее поднято выше и меньше. lean: добавочный наклон назад, градусы."""
    far = f' rotate({NEAR_ROT + lean})' if near else f' rotate({FAR_ROT + lean * 0.8}) scale({FAR_SCALE})'
    body = (f'<g transform="translate({C} {C}){far}" stroke-linejoin="round" stroke-linecap="round">'
            f'{"".join(g)}</g>')
    return svg(CANVAS, defs, body)


def dirv(phi_deg):
    """Направление: 0° вверх, 90° назад (влево), больше 90° назад и вниз (экранная система, y вниз)."""
    a = math.radians(phi_deg)
    return (-math.sin(a), -math.cos(a))


def spark(x, y, r, edge='#E8A317'):
    """Четырёхконечная звёздочка."""
    d = (f'M {x:.1f} {y - r:.1f} Q {x:.1f} {y:.1f} {x + r:.1f} {y:.1f} Q {x:.1f} {y:.1f} {x:.1f} {y + r:.1f} '
         f'Q {x:.1f} {y:.1f} {x - r:.1f} {y:.1f} Q {x:.1f} {y:.1f} {x:.1f} {y - r:.1f} Z')
    return f'<path d="{d}" fill="#FFFFFF" stroke="{edge}" stroke-width="1.6"/>'


def root_pad(L, fill, rx_k=0.12):
    """Круглое «плечо» в корне крыла: закрывает стык с телом."""
    rx = max(11.0, rx_k * L)
    ry = rx * 0.74
    return (f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="{OUTLINE}" stroke-width="4"/>'
            f'<ellipse cx="{-rx * 0.25:.1f}" cy="{-ry * 0.3:.1f}" rx="{rx * 0.45:.1f}" ry="{ry * 0.22:.1f}" '
            f'fill="#FFFFFF" fill-opacity=".28"/>')


# ---------- ступень 1: крылья жука ----------
def elytra_svg(tier, layer):
    """Два овальных надкрылья (твёрдые крышки) и тонкие плёнчатые крылья под ними."""
    T = TIERS[tier]
    near = layer == 'front'
    L = T['L']
    p = f'wings-t{tier}-{layer}'
    sh = shade_for(near)
    shell, shell_dark, vein = sh(T['shell']), sh(T['shell_dark']), sh(T['vein'])
    film, film_edge = sh(T['film']), sh(T['film_edge'])
    defs = [lgrad(f'{p}-sh', [(0, lighten(shell, .35)), (.45, shell), (1, shell_dark)])]
    g = []

    def oval(phi, length, width, fill, stroke, sw, extra='', opacity=1.0):
        d = dirv(phi)
        cx, cy = d[0] * length / 2, d[1] * length / 2
        ang = math.degrees(math.atan2(d[1], d[0]))
        return (f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({ang:.1f})">'
                f'<ellipse rx="{length / 2:.1f}" ry="{width / 2:.1f}" fill="{fill}" fill-opacity="{opacity}" '
                f'stroke="{stroke}" stroke-width="{sw}"/>{extra}</g>')

    # плёнчатое крыло: длинное, тонкое, полупрозрачное, с прожилками
    lf, wf = 1.30 * L, 0.34 * L
    veins = ''.join(f'<path d="M {-lf * 0.45:.1f} {y:.1f} Q {lf * 0.05:.1f} {y * 1.5:.1f} {lf * 0.42:.1f} {y * 0.6:.1f}" '
                    f'fill="none" stroke="{film_edge}" stroke-width="1.8" stroke-opacity=".8"/>' for y in (-wf * 0.14, 0, wf * 0.14))
    g.append(oval(52, lf, wf, film, film_edge, 2.6, veins, 0.72))
    # надкрылье: глянцевый овал, шов по оси, три чёрточки-прожилки, блик по верхней кромке
    le, we = 1.0 * L, 0.58 * L
    detail = (f'<path d="M {-le * 0.46:.1f} 0 L {le * 0.40:.1f} 0" fill="none" stroke="{vein}" stroke-width="3" stroke-opacity=".85"/>'
              f'<path d="M {-le * 0.12:.1f} {-we * 0.22:.1f} L {le * 0.06:.1f} {-we * 0.30:.1f}" fill="none" stroke="{vein}" stroke-width="3"/>'
              f'<path d="M {le * 0.14:.1f} {-we * 0.12:.1f} L {le * 0.30:.1f} {-we * 0.20:.1f}" fill="none" stroke="{vein}" stroke-width="3"/>'
              f'<path d="M {-le * 0.12:.1f} {we * 0.20:.1f} L {le * 0.06:.1f} {we * 0.28:.1f}" fill="none" stroke="{vein}" stroke-width="3"/>'
              f'<path d="M {-le * 0.34:.1f} {-we * 0.34:.1f} Q {le * 0.02:.1f} {-we * 0.52:.1f} {le * 0.30:.1f} {-we * 0.34:.1f}" '
              f'fill="none" stroke="#FFFFFF" stroke-opacity=".6" stroke-width="4.2"/>')
    g.append(oval(30, le, we, f'url(#{p}-sh)', OUTLINE, OUT - 1, detail))
    g.append(root_pad(L, sh(T['pad']), 0.15))
    return wrap(g, defs, near)


# ---------- ступени 2 и 3: перья ----------
def feather_profile(n=24):
    """Полуширина пера по длине (0..1): заострённое основание, округлый кончик."""
    pts = [(i / n, math.sqrt(i / n) * math.sqrt(max(0.0, 1 - (i / n) ** 3))) for i in range(n + 1)]
    m = max(h for _, h in pts)
    return [(t, h / m) for t, h in pts]


FEATHER = feather_profile()


def poly(points):
    return ' L '.join(f'{x:.1f} {y:.1f}' for x, y in points)


def feather_g(base, phi, ell, wid, gid, quill, trim=None):
    """Перо: основание в base, направление phi (см. dirv), длина ell, ширина wid."""
    d = dirv(phi)
    ang = math.degrees(math.atan2(d[1], d[0]))
    top = [(t * ell, -h * wid / 2) for t, h in FEATHER]
    bot = [(t * ell, h * wid / 2) for t, h in FEATHER][::-1]
    parts = [f'<path d="M {poly(top + bot)} Z" fill="url(#{gid})" stroke="{OUTLINE}" stroke-width="3.2"/>']
    if trim:
        edge = [(t * ell * 0.985, -h * wid / 2 * 0.86) for t, h in FEATHER if t >= 0.78]
        edge2 = [(x, -y) for x, y in edge]
        parts.append(f'<path d="M {poly(edge)}" fill="none" stroke="{trim}" stroke-width="2.4"/>')
        parts.append(f'<path d="M {poly(edge2)}" fill="none" stroke="{trim}" stroke-width="2.4"/>')
    parts.append(f'<path d="M {ell * 0.05:.1f} 0 L {ell * 0.9:.1f} 0" fill="none" stroke="{quill}" stroke-width="2.4"/>')
    for t in (0.34, 0.52, 0.70):
        x = ell * t
        for sgn in (-1, 1):
            parts.append(f'<path d="M {x:.1f} 0 L {x + ell * 0.12:.1f} {sgn * wid * 0.28:.1f}" fill="none" stroke="{quill}" '
                         f'stroke-width="1.6" stroke-opacity=".45"/>')
    return f'<g transform="translate({base[0]:.1f} {base[1]:.1f}) rotate({ang:.1f})">{"".join(parts)}</g>'


def feather_svg(tier, layer):
    """Перьевое крыло: перья крепятся рядами вдоль изогнутой руки (маховые, средние, мелкие кроющие),
    концы маховых образуют дугу, как у настоящего крыла."""
    T = TIERS[tier]
    near = layer == 'front'
    L = T['L']
    p = f'wings-t{tier}-{layer}'
    sh = shade_for(near)
    dark, base, tip, quill, arm = sh(T['dark']), sh(T['base']), sh(T['tip']), sh(T['quill']), sh(T['arm'])
    trim = sh(T['trim']) if T['trim'] else None
    gid = f'{p}-fe'
    defs = [lgrad(gid, [(0, dark), (.5, base), (1, tip)], 0, 0, 1, 0)]
    if T['glow']:
        gl = sh(T['glow'])
        defs.append(f'<radialGradient id="{p}-gl"><stop offset="0" stop-color="{gl}" stop-opacity=".85"/>'
                    f'<stop offset="1" stop-color="{gl}" stop-opacity="0"/></radialGradient>')
    K = 0.84                       # масштаб схемы: размах перьевого крыла ≈ размаху кожистого той же длины L
    R = (0.0, 0.0)
    CEa = (0.08 * L * K, -0.40 * L * K)
    H = (-0.42 * L * K, -0.80 * L * K)    # кончик кисти
    g = []
    if T['glow']:
        g.append(f'<ellipse cx="{-0.34 * L:.1f}" cy="{-0.50 * L:.1f}" rx="{0.86 * L:.1f}" ry="{0.76 * L:.1f}" fill="url(#{p}-gl)"/>')
    # рука (передняя кромка) лежит под перьями
    g.append(f'<path d="{taper(R, CEa, H, max(9.0, 0.09 * L), max(5.0, 0.05 * L))}" fill="{arm}" stroke="{OUTLINE}" stroke-width="3.4"/>')

    def trailing_phi(u):
        """Направление «назад и вниз» перпендикулярно руке в точке u (формат dirv)."""
        tx, ty = qtan(R, CEa, H, u)
        n = unit((ty, -tx))
        return math.degrees(math.atan2(-n[0], -n[1]))

    def row(count, u0, u1, lens, wid, phi_fn):
        out = []
        for i in range(count):
            u = u0 + (u1 - u0) * i / max(1, count - 1)
            ell = lens[min(len(lens) - 1, round(i * (len(lens) - 1) / max(1, count - 1)))] * L * K
            out.append(feather_g(qb(R, CEa, H, u), phi_fn(u), ell, wid * L * K, gid, quill, trim))
        return out

    # маховые: у кисти вытягиваются вдоль руки (заострённый кончик), самые длинные на конце
    g += row(T['flight'], 0.14, 1.0, [0.62, 0.70, 0.78, 0.86, 0.94, 1.02, 1.08], 0.25, lambda u: trailing_phi(u) - 56 * u ** 1.4)
    if T['mid']:
        g += row(T['mid'], 0.12, 0.98, [0.50, 0.60, 0.70, 0.76, 0.80, 0.72], 0.25, lambda u: trailing_phi(u) - 40 * u ** 1.4 - 6)
    g += row(T['cov_b'], 0.10, 0.96, [0.38, 0.44, 0.50, 0.52, 0.44], 0.24, lambda u: trailing_phi(u) - 22 * u - 12)
    g += row(T['cov_c'], 0.06, 0.94, [0.24, 0.28, 0.31, 0.26], 0.19, lambda u: trailing_phi(u) - 12 * u - 22)
    g.append(f'<circle cx="{H[0]:.1f}" cy="{H[1]:.1f}" r="{max(5.0, 0.04 * L):.1f}" fill="{arm}" stroke="{OUTLINE}" stroke-width="3"/>')
    g.append(root_pad(L, sh(T['pad'])))
    return wrap(g, defs, near, lean=T['lean'])


# ---------- ступени 4 и 5: кожистые крылья ----------
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


def leather_svg(tier, layer):
    """Кожистое крыло: перепонка на костяных «пальцах», когти, шипы, жар по кромке."""
    T = TIERS[tier]
    near = layer == 'front'
    L = T['L']
    p = f'wings-t{tier}-{layer}'
    shade = shade_for(near)
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
                 f'fill="{shade(T["plate_col"])}" stroke="{OUTLINE}" stroke-width="3" '
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

    # искры: у пламенных крыльев кружки, у золотых четырёхконечные звёздочки
    if T['flames'] or T['sparkles']:
        rnd = random.Random(tier * 31 + (1 if near else 2))
        for _ in range(9 if T['sparkles'] else 8):
            a, c, b = gaps[rnd.randrange(len(gaps) - 1)]
            q = qb(a, c, b, rnd.uniform(0.15, 0.85))
            d = unit((q[0] - W[0], q[1] - W[1]))
            dist = L * (rnd.uniform(0.04, 0.2) if T['sparkles'] else rnd.uniform(0.12, 0.24))
            x, y = q[0] + d[0] * dist, q[1] + d[1] * dist
            if T['sparkles']:
                g.append(spark(x, y, rnd.uniform(0.022, 0.04) * L + 3, shade('#E8A317')))
            else:
                g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rnd.uniform(1.8, 3.2):.1f}" fill="#FFD66B" fill-opacity=".9"/>')

    return wrap(g, defs, near)


def wing_svg(tier, layer):
    return {'elytra': elytra_svg, 'feather': feather_svg, 'leather': leather_svg}[TIERS[tier]['kind']](tier, layer)


def main():
    n = 0
    for tier in TIERS:
        for layer in ('back', 'front'):
            write(WINGS / f'wings-t{tier}-{layer}.svg', wing_svg(tier, layer))
            n += 1
    # данные для страницы превью и игры: названия и размеры ступеней
    info = [{'tier': t, 'name': T['name'], 'L': T['L']} for t, T in TIERS.items()]
    write(ROOT / 'design' / 'preview' / 'upgrades-geometry.js',
          'window.WING_TIERS = ' + json.dumps(info, ensure_ascii=False) + ';\n'
          'window.WING_CANVAS = ' + str(CANVAS) + ';\n')
    write(WINGS / 'wings.json', json.dumps({'canvas': CANVAS, 'tiers': info}, ensure_ascii=False, indent=1) + '\n')
    print(f'upgrades: written {n} wing files (5 tiers x 2 layers) + upgrades-geometry.js + wings.json')


if __name__ == '__main__':
    main()
