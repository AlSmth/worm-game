#!/usr/bin/env python3
"""Генератор персонажей-червей (SVG), модель 2: гладкая трубка и две челюсти.

Запуск из корня проекта:  python tools/gen_worm.py

Тело червя: одна гладкая трубка без соединений. Игра (и страница превью) рисует её кругами-«штампами»
вдоль пути головы в пять проходов: контур, тень, основной тон, свет, блик. Поэтому тело изгибается плавно и растёт без швов.
На переднем конце две большие челюсти: размер челюсти определяет, какого размера добычу червь может съесть.

Для каждого персонажа пишет design/worm/<slug>/worm-<slug>-*.svg:
  stamp-out|shade|main|light|gloss     круги тела (128×128): контур, тень, основной тон, свет, блик (плоские цвета)
  jaw-top, jaw-bottom                  челюсти (256×256), центр холста = петля (шарнир) челюсти
  maw                                  зев между челюстями (256×256), центр холста = центр головы
  face-idle|open|chomp|hurt|happy      глаза, брови, румянец (256×256), центр холста = центр головы
  crown                                макушка (256×256), рисуется ПОД телом; есть не у всех
и design/preview/worm-geometry.js, design/worm/rig.json (единый источник чисел для игры и превью).

Контур у всех частей одинаковый (OUT px при масштабе 1:1). Правим параметры здесь и перегенерируем;
SVG червей руками не правим.
"""
import json
import math

from svgkit import ROOT, OUTLINE, OUT, mix, lighten, rgrad, lgrad, svg, write

WORM = ROOT / 'design' / 'worm'
PREVIEW = ROOT / 'design' / 'preview'

STAMP = 128       # холст круга тела
CANVAS = 256      # холст головных деталей
R_BODY = 44.0     # радиус тела (заливка), контур снаружи
R_HEAD = 50.0     # радиус головы (заливка)
R_TAIL = 27.0     # радиус на самом кончике хвоста
HEAD_BULGE = 70   # на каком расстоянии от головы радиус сходит к телу
TAPER_FROM = 0.70 # с какой доли длины начинается сужение хвоста
SPACING = 11.0    # расстояние между кругами вдоль тела, px при масштабе 1:1 (≈ 0,25 радиуса): край света без зубчиков
STEP = 72         # длина одного «звена» роста: сегменты тира задают длину тела (концепт, раздел 5)
WING_DIST = 216   # крылья сидят в 3 звеньях от головы

JAW = {
    'hinge': [30, -4],      # шарнир верхней челюсти от центра головы (нижней: зеркально по y)
    'length': 84,           # длина челюсти от шарнира до кончика
    'rest': -10,            # угол в покое, градусы (минус: раскрыта вверх у верхней челюсти)
    'open': -34,
    'closed': 17,
}

GEOM = {
    'stampCanvas': STAMP,
    'canvas': CANVAS,
    'bodyRadius': R_BODY,
    'headRadius': R_HEAD,
    'tailRadius': R_TAIL,
    'outline': OUT,
    'headBulge': HEAD_BULGE,
    'taperFrom': TAPER_FROM,
    'spacing': SPACING,
    'step': STEP,
    'wingDist': WING_DIST,
    'jaw': JAW,
    'passes': ['out', 'shade', 'main', 'light', 'gloss'],
    # точки привязки: смещение от центра головы (или тела), px при масштабе 1:1
    'anchors': {'mouth': [78, 4], 'wing': [0, -(R_BODY - 6)], 'crown': [0, -R_HEAD], 'helmet': [0, -R_HEAD]},
}

EXPRS = ('idle', 'open', 'chomp', 'hurt', 'happy')

VARIANTS = {
    'peach': dict(tag='A', name='Персик', body='#FF9AA2', dark='#E56B7A', belly='#FFD9C9',
                  crown=None, brows=False, teeth='blunt', pupil=9.5, iris=None, blush=True,
                  note='Милаха: круглые глаза, румянец, тупые зубки. Самый добрый.'),
    'salad': dict(tag='B', name='Салат', body='#9BE15D', dark='#5BB82F', belly='#F4F2A0',
                  crown='sprout', brows=True, teeth='grin', pupil=7.2, iris=None, blush=False,
                  note='Хулиган: частые зубки, хитрые брови, росток на макушке.'),
    'plum': dict(tag='C', name='Слива', body='#B58CFF', dark='#7E57E0', belly='#F1E3FF',
                 crown='crest', brows=True, teeth='fangs', pupil=8.0, iris='#FFD23F', blush=False,
                 note='Монстрик: два клычка, гребень на макушке, жёлтые глаза. Мультяшный и дружелюбный.'),
}

MOUTH_DARK = '#7A1730'
MOUTH_LIGHT = '#B3263E'
TONGUE = '#FF6F8A'


def jaw_plate(v):
    """Цвет пластины челюсти: чуть темнее и насыщеннее тела, чтобы челюсти читались на фоне головы."""
    return mix(v['body'], v['dark'], .5)


# ---------- тело: круги-штампы ----------
# Тело рисуется несколькими проходами одинаковых кругов вдоль пути головы: контур, тень, основной тон, свет, блик.
# Каждый проход закрашен плоским цветом, поэтому объединение кругов без швов; объём даёт смещение кругов вверх.
PASSES = ('out', 'shade', 'main', 'light', 'gloss')


def stamp_svg(slug, kind):
    v = VARIANTS[slug]
    c = STAMP // 2
    R = R_BODY
    if kind == 'out':
        art = f'<circle cx="{c}" cy="{c}" r="{R + OUT:.1f}" fill="{OUTLINE}"/>'
    elif kind == 'shade':
        art = f'<circle cx="{c}" cy="{c}" r="{R:.1f}" fill="{mix(v["body"], v["dark"], .95)}"/>'
    elif kind == 'main':
        art = f'<circle cx="{c}" cy="{c - 0.09 * R:.1f}" r="{0.90 * R:.1f}" fill="{v["body"]}"/>'
    elif kind == 'light':
        art = f'<circle cx="{c}" cy="{c - 0.27 * R:.1f}" r="{0.62 * R:.1f}" fill="{lighten(v["body"], .38)}"/>'
    else:  # gloss
        art = (f'<ellipse cx="{c - 3}" cy="{c - 0.64 * R:.1f}" rx="{0.5 * R:.1f}" ry="6" '
               f'transform="rotate(-5 {c - 3} {c - 0.64 * R:.1f})" fill="{lighten(v["body"], .8)}"/>')
    return svg(STAMP, [], art)


# ---------- челюсти ----------
def bez(b, c, t_, u):
    w = 1 - u
    return (w * w * b[0] + 2 * w * u * c[0] + u * u * t_[0], w * w * b[1] + 2 * w * u * c[1] + u * u * t_[1])


def bez_tan(b, c, t_, u):
    w = 1 - u
    return (2 * w * (c[0] - b[0]) + 2 * u * (t_[0] - c[0]), 2 * w * (c[1] - b[1]) + 2 * u * (t_[1] - c[1]))


def jaw_path(L):
    """Контуры челюсти (верхней): центральная кривая, внешняя и внутренняя кромки, нормали. Система: x вперёд, y вниз, шарнир в (0, 0)."""
    B, C, T = (0.0, 0.0), (0.56 * L, -0.66 * L), (L, -0.02 * L)
    n = 28
    mid, outer, inner, norms = [], [], [], []
    for i in range(n + 1):
        u = i / n
        x, y = bez(B, C, T, u)
        tx, ty = bez_tan(B, C, T, u)
        ln = math.hypot(tx, ty) or 1
        nx, ny = ty / ln, -tx / ln          # наружу (вверх для верхней челюсти)
        w = 34 * (1 - u) ** 0.85 + 9 * u
        mid.append((x, y))
        outer.append((x + nx * w / 2, y + ny * w / 2))
        inner.append((x - nx * w / 2, y - ny * w / 2))
        norms.append((nx, ny, w))
    return mid, outer, inner, norms


def tooth(base, d, h, w, style):
    """Зуб: основание на кромке в точке base, направление d (единичный вектор), высота h, ширина w."""
    nx, ny = -d[1], d[0]
    a = (base[0] + nx * w / 2 - d[0] * 3, base[1] + ny * w / 2 - d[1] * 3)
    b = (base[0] - nx * w / 2 - d[0] * 3, base[1] - ny * w / 2 - d[1] * 3)
    tip = (base[0] + d[0] * h, base[1] + d[1] * h)
    if style == 'round':
        # тупой зуб: прямоугольник со скруглением
        c1 = (a[0] + d[0] * h * 0.95, a[1] + d[1] * h * 0.95)
        c2 = (b[0] + d[0] * h * 0.95, b[1] + d[1] * h * 0.95)
        dd = (f'M {a[0]:.1f} {a[1]:.1f} L {c1[0]:.1f} {c1[1]:.1f} Q {tip[0] + d[0] * h * 0.1:.1f} {tip[1] + d[1] * h * 0.1:.1f} '
              f'{c2[0]:.1f} {c2[1]:.1f} L {b[0]:.1f} {b[1]:.1f} Z')
    else:
        dd = f'M {a[0]:.1f} {a[1]:.1f} L {tip[0]:.1f} {tip[1]:.1f} L {b[0]:.1f} {b[1]:.1f} Z'
    return f'<path d="{dd}" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="3.2"/>'


def teeth_spec(v, lower):
    """(u, высота, ширина, стиль) вдоль внутренней кромки; нижняя челюсть смещена на полшага, зубы входят между верхними."""
    t = v['teeth']
    if t == 'blunt':
        s = [(.30, 17, 17, 'round'), (.52, 17, 17, 'round'), (.74, 14, 15, 'round')]
        lo = [(.41, 15, 16, 'round'), (.63, 13, 15, 'round')]
    elif t == 'grin':
        s = [(.20, 11, 11, 'tri'), (.36, 12, 11, 'tri'), (.52, 12, 11, 'tri'), (.68, 11, 10, 'tri'), (.84, 9, 9, 'tri')]
        lo = [(.28, 10, 10, 'tri'), (.44, 11, 10, 'tri'), (.60, 11, 10, 'tri'), (.76, 9, 9, 'tri')]
    else:  # fangs: два клычка и мелкие зубки
        s = [(.34, 20, 14, 'tri'), (.58, 9, 9, 'tri'), (.72, 9, 9, 'tri'), (.86, 17, 11, 'tri')]
        lo = [(.46, 15, 12, 'tri'), (.78, 8, 8, 'tri')]
    return lo if lower else s


def jaw_svg(slug, lower):
    v = JAW
    var = VARIANTS[slug]
    L = JAW['length']
    mid, outer, inner, norms = jaw_path(L)
    sy = -1 if lower else 1

    def P(p):
        return (p[0], p[1] * sy)

    plate = jaw_plate(var)
    p = f'worm-{slug}-jaw-{"bottom" if lower else "top"}'
    defs = [f'<linearGradient id="{p}-g" gradientUnits="userSpaceOnUse" x1="0" y1="-62" x2="0" y2="62">'
            f'<stop offset="0" stop-color="{lighten(plate, .5)}"/><stop offset=".5" stop-color="{plate}"/>'
            f'<stop offset="1" stop-color="{mix(plate, var["dark"], .9)}"/></linearGradient>']
    pts = [P(q) for q in outer] + [P(q) for q in inner[::-1]]
    d_plate = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'
    g = []
    # зубы: от внутренней кромки к оси рта; рисуются под пластиной
    for (u, h, w, style) in teeth_spec(var, lower):
        i = min(len(mid) - 1, max(0, round(u * (len(mid) - 1))))
        nx, ny, _ = norms[i]
        base = P(inner[i])
        d = (-nx, -ny * sy)    # от кромки внутрь (к оси рта)
        g.append(tooth(base, d, h, w, style))
    g.append(f'<path d="{d_plate}" fill="url(#{p}-g)" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    # блик по внешней кромке и «шарнир»
    hi = [P(outer[i]) for i in range(2, 17)]
    sh = [(q[0] - 0.0, q[1] + (4.5 if not lower else -4.5)) for q in hi]
    g.append('<path d="M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in sh) +
             f'" fill="none" stroke="#FFFFFF" stroke-opacity="{0.55 if not lower else 0.28}" stroke-width="3.6"/>')
    return svg(CANVAS, defs, f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{"".join(g)}</g>')


# ---------- зев ----------
def maw_svg(slug):
    p = f'worm-{slug}-maw'
    defs = [lgrad(f'{p}-cav', [(0, MOUTH_DARK), (1, MOUTH_LIGHT)], 0, 0, 1, 0)]
    art = (f'<g transform="translate(128 128)" stroke-linejoin="round">'
           f'<ellipse cx="46" cy="2" rx="24" ry="30" fill="url(#{p}-cav)" stroke="{OUTLINE}" stroke-width="{OUT - 1}"/>'
           f'<ellipse cx="56" cy="14" rx="13" ry="9" fill="{TONGUE}"/>'
           f'</g>')
    return svg(CANVAS, defs, art)


# ---------- лицо ----------
ER = (15, 18)
EYES = [(-6, -22), (20, -27)]


def eye_normal(c, v, k=1.0):
    cx, cy = c
    rx, ry = ER[0] * k, ER[1] * k
    pr = v['pupil'] * (0.92 if k > 1 else 1)
    px, py = cx + 3.5, cy + 2
    s = [f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#FFFFFF" '
         f'stroke="{OUTLINE}" stroke-width="{OUT - 1}"/>']
    if v['iris']:
        s.append(f'<circle cx="{px}" cy="{py}" r="{pr + 2:.1f}" fill="{v["iris"]}"/>')
    s.append(f'<circle cx="{px}" cy="{py}" r="{pr:.1f}" fill="{OUTLINE}"/>')
    s.append(f'<circle cx="{px + pr * 0.32:.1f}" cy="{py - pr * 0.38:.1f}" r="{pr * 0.36:.1f}" fill="#FFFFFF"/>')
    s.append(f'<circle cx="{px - pr * 0.3:.1f}" cy="{py + pr * 0.42:.1f}" r="{pr * 0.18:.1f}" '
             f'fill="#FFFFFF" fill-opacity="0.9"/>')
    return ''.join(s)


def eye_squeeze(c, side):
    """Зажмуренный глаз (жуёт): «>» у заднего, «<» у переднего."""
    cx, cy = c
    if side == 0:
        d = f'M {cx - 10} {cy - 11} L {cx + 8} {cy} L {cx - 10} {cy + 11}'
    else:
        d = f'M {cx + 10} {cy - 11} L {cx - 8} {cy} L {cx + 10} {cy + 11}'
    return f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="6"/>'


def eye_happy(c):
    cx, cy = c
    return (f'<path d="M {cx - 13} {cy + 6} Q {cx} {cy - 19} {cx + 13} {cy + 6}" fill="none" '
            f'stroke="{OUTLINE}" stroke-width="6"/>')


def spiral(cx, cy, r_max, turns=2.4, n=56):
    pts = []
    for i in range(n + 1):
        t = i / n
        a = t * turns * 2 * math.pi
        pts.append((cx + r_max * t * math.cos(a), cy + r_max * t * math.sin(a)))
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts)


def eye_swirl(c):
    cx, cy = c
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{ER[0]}" ry="{ER[1]}" fill="#FFFFFF" '
            f'stroke="{OUTLINE}" stroke-width="{OUT - 1}"/>'
            f'<path d="{spiral(cx, cy, 11)}" fill="none" stroke="{OUTLINE}" stroke-width="3"/>')


def brows(style):
    (x1, y1), (x2, y2) = EYES
    if style == 'cheeky':      # хитрые: внутренние концы вниз
        L, R = ((x1 - 16, y1 - 28), (x1 + 11, y1 - 21)), ((x2 - 11, y2 - 24), (x2 + 15, y2 - 30))
    elif style == 'worried':
        L, R = ((x1 - 16, y1 - 21), (x1 + 11, y1 - 28)), ((x2 - 11, y2 - 30), (x2 + 15, y2 - 22))
    else:                      # подняты
        return (f'<path d="M {x1 - 15} {y1 - 24} Q {x1} {y1 - 36} {x1 + 13} {y1 - 26}" fill="none" stroke="{OUTLINE}" stroke-width="6"/>'
                f'<path d="M {x2 - 12} {y2 - 28} Q {x2 + 2} {y2 - 40} {x2 + 15} {y2 - 30}" fill="none" stroke="{OUTLINE}" stroke-width="6"/>')
    return ''.join(f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" fill="none" stroke="{OUTLINE}" stroke-width="6"/>'
                   for a, b in (L, R))


def face_svg(slug, expr):
    v = VARIANTS[slug]
    layers = []
    if v['blush'] or expr == 'happy':
        k = 1.25 if expr == 'happy' else 1.0
        layers.append(f'<ellipse cx="2" cy="8" rx="{11 * k:.1f}" ry="{7 * k:.1f}" fill="#FF5C7A" fill-opacity=".5"/>')
        layers.append(f'<ellipse cx="34" cy="2" rx="{8 * k:.1f}" ry="{5.5 * k:.1f}" fill="#FF5C7A" fill-opacity=".5"/>')
    if expr == 'open':
        eyes = ''.join(eye_normal(c, v, 1.1) for c in EYES)
    elif expr == 'chomp':
        eyes = ''.join(eye_squeeze(c, i) for i, c in enumerate(EYES))
    elif expr == 'hurt':
        eyes = ''.join(eye_swirl(c) for c in EYES)
    elif expr == 'happy':
        eyes = ''.join(eye_happy(c) for c in EYES)
    else:
        eyes = ''.join(eye_normal(c, v) for c in EYES)
    layers.append(eyes)
    if expr == 'hurt':
        layers.append(brows('worried'))
    elif expr != 'happy' and v['brows']:
        layers.append(brows('raised' if expr == 'open' else 'cheeky'))
    return svg(CANVAS, [], f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{"".join(layers)}</g>')


# ---------- макушка ----------
def sprout(p):
    top = -R_HEAD
    return (f'<path d="M -4 {top + 10} Q -6 {top - 12} 0 {top - 28}" fill="none" stroke="{OUTLINE}" stroke-width="12"/>'
            f'<path d="M -4 {top + 10} Q -6 {top - 12} 0 {top - 28}" fill="none" stroke="#4FA83F" stroke-width="5.5"/>'
            f'<path d="M 0 {top - 22} C -22 {top - 36} -40 {top - 24} -38 {top - 10} C -22 {top - 6} -6 {top - 10} 0 {top - 22} Z" '
            f'fill="url(#{p}-leaf)" stroke="{OUTLINE}" stroke-width="4.5"/>'
            f'<path d="M 1 {top - 28} C 20 {top - 48} 44 {top - 40} 44 {top - 24} C 32 {top - 16} 12 {top - 16} 1 {top - 28} Z" '
            f'fill="url(#{p}-leaf)" stroke="{OUTLINE}" stroke-width="4.5"/>')


def crest(p):
    out = []
    for xb, hgt in ((-30, 26), (-4, 34), (22, 26)):
        yb = -math.sqrt(max(1.0, R_HEAD ** 2 - xb ** 2))
        d = (f'M {xb - 12:.1f} {yb + 12:.1f} Q {xb - 10:.1f} {yb - hgt * 0.4:.1f} {xb + 3:.1f} {yb - hgt:.1f} '
             f'Q {xb + 14:.1f} {yb - hgt * 0.4:.1f} {xb + 12:.1f} {yb + 12:.1f} Z')
        out.append(f'<path d="{d}" fill="url(#{p}-crest)" stroke="{OUTLINE}" stroke-width="4.5"/>')
    return ''.join(out)


def crown_svg(slug):
    """Макушка отдельным слоем: рисуется ПОД телом, чтобы шлем и рога могли её закрыть."""
    v = VARIANTS[slug]
    if not v['crown']:
        return None
    p = f'worm-{slug}-crown'
    if v['crown'] == 'sprout':
        defs = [lgrad(f'{p}-leaf', [(0, '#B9F27A'), (1, '#4FB04A')], 0, 0, 1, 1)]
        art = sprout(p)
    else:
        defs = [lgrad(f'{p}-crest', [(0, '#B6FAE6'), (1, '#4FD6B3')])]
        art = crest(p)
    return svg(CANVAS, defs, f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{art}</g>')


def main():
    count = 0
    for slug in VARIANTS:
        d = WORM / slug
        # убираем файлы прежней модели (бусины и головы целиком), чтобы они не попали в атлас
        for old in list(d.glob('*.svg')):
            old.unlink()
        for kind in PASSES:
            write(d / f'worm-{slug}-stamp-{kind}.svg', stamp_svg(slug, kind))
            count += 1
        write(d / f'worm-{slug}-jaw-top.svg', jaw_svg(slug, False))
        write(d / f'worm-{slug}-jaw-bottom.svg', jaw_svg(slug, True))
        write(d / f'worm-{slug}-maw.svg', maw_svg(slug))
        count += 3
        for expr in EXPRS:
            write(d / f'worm-{slug}-face-{expr}.svg', face_svg(slug, expr))
            count += 1
        crown = crown_svg(slug)
        if crown:
            write(d / f'worm-{slug}-crown.svg', crown)
            count += 1
    chars = [{'id': k, 'tag': v['tag'], 'name': v['name'], 'note': v['note'], 'crown': bool(v['crown']),
              'body': v['body'], 'dark': v['dark']} for k, v in VARIANTS.items()]
    js = ('window.WORM_GEOM = ' + json.dumps(GEOM) + ';\n'
          'window.WORM_VARIANTS = ' + json.dumps(chars, ensure_ascii=False) + ';\n')
    write(PREVIEW / 'worm-geometry.js', js)
    rig = dict(GEOM)
    rig['skins'] = chars
    write(WORM / 'rig.json', json.dumps(rig, ensure_ascii=False, indent=1) + '\n')
    print(f'worm: written {count} svg files + worm-geometry.js + rig.json')


if __name__ == '__main__':
    main()
