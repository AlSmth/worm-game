#!/usr/bin/env python3
"""Генератор персонажей-червей (SVG).

Запуск из корня проекта:  python tools/gen_worm.py

Для каждого персонажа пишет design/worm/<slug>/worm-<slug>-*.svg:
  head-idle|open|chomp|hurt|happy   голова (256×256), без макушки
  crown                             макушка (256×256), рисуется ПОД головой; есть не у всех
  body-a, body-b                    сегменты тела (128×128)
  tail                              хвост (128×128)
и design/preview/worm-geometry.js (геометрия и список персонажей для страницы превью).

Контур у всех частей одинаковый (OUT px при масштабе 1:1), поэтому швов по толщине нет.
Правим параметры здесь и перегенерируем; SVG червей руками не правим.
"""
import json
import math

from svgkit import ROOT, OUTLINE, OUT, mix, lighten, rgrad, lgrad, qb, svg, write

WORM = ROOT / 'design' / 'worm'
PREVIEW = ROOT / 'design' / 'preview'

HEAD_CANVAS = 256
SEG_CANVAS = 128
HEAD_RX, HEAD_RY = 82, 76      # полуоси головы
BEAD_R = 51                    # радиус сегмента тела
WING_ANCHOR_Y = -(BEAD_R - 6)  # крыло растёт на 6 px внутри спины, стык закрывает «плечо»

GEOM = {
    'headCanvas': HEAD_CANVAS,
    'segCanvas': SEG_CANVAS,
    'headToBead': 76,          # центр головы -> центр первого сегмента
    'beadStep': 72,            # между центрами сегментов (перекрытие ≈ 30%)
    'beadToTail': 68,          # центр последнего сегмента -> центр хвоста
    'beadRadius': BEAD_R,
    'wingBead': 3,             # крылья сидят на 3-м сегменте от головы
    # точки привязки: смещение от центра холста своей части, px при масштабе 1:1
    'anchors': {'mouth': [80, 34], 'wing': [0, WING_ANCHOR_Y], 'helmet': [0, -HEAD_RY]},
}

EXPRS = ('idle', 'open', 'chomp', 'hurt', 'happy')

VARIANTS = {
    'peach': dict(tag='A', name='Персик', body='#FF9AA2', dark='#E56B7A', belly='#FFD9C9',
                  crown=None, brows=False, teeth='buck', pupil=11.5, iris=None, blush=True,
                  note='Милаха: круглые глаза, два передних зуба, румянец. Самый добрый.'),
    'salad': dict(tag='B', name='Салат', body='#9BE15D', dark='#5BB82F', belly='#F4F2A0',
                  crown='sprout', brows=True, teeth='grin', pupil=8.5, iris=None, blush=False,
                  note='Хулиган: широкая зубастая улыбка, хитрые брови, росток на макушке.'),
    'plum': dict(tag='C', name='Слива', body='#B58CFF', dark='#7E57E0', belly='#F1E3FF',
                 crown='crest', brows=True, teeth='fangs', pupil=9.5, iris='#FFD23F', blush=False,
                 note='Монстрик: клычки, гребень на макушке, жёлтые глаза. Мультяшный и дружелюбный.'),
}

MOUTH_DARK = '#7A1730'
MOUTH_LIGHT = '#B3263E'
TONGUE = '#FF6F8A'


# ---------- примитивы ----------
def tooth_rect(x, y, w, h, sw=3.5, rx=3.5):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="{sw}"/>')


def fang(x, y, w, h, sw=3.5):
    d = f'M {x - w / 2:.1f} {y:.1f} L {x + w / 2:.1f} {y:.1f} L {x:.1f} {y + h:.1f} Z'
    return f'<path d="{d}" fill="#FFFFFF" stroke="{OUTLINE}" stroke-width="{sw}"/>'


def spiral(cx, cy, r_max, turns=2.4, n=56):
    pts = []
    for i in range(n + 1):
        t = i / n
        a = t * turns * 2 * math.pi
        pts.append((cx + r_max * t * math.cos(a), cy + r_max * t * math.sin(a)))
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts)


# ---------- глаза ----------
ER = (18, 21)
EYES = [(-12, -22), (26, -24)]


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
    """Зажмуренный глаз (жуёт): «>» у левого, «<» у правого."""
    cx, cy = c
    if side == 0:
        d = f'M {cx - 12} {cy - 13} L {cx + 9} {cy} L {cx - 12} {cy + 13}'
    else:
        d = f'M {cx + 12} {cy - 13} L {cx - 9} {cy} L {cx + 12} {cy + 13}'
    return f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="6.5"/>'


def eye_happy(c):
    cx, cy = c
    return (f'<path d="M {cx - 16} {cy + 7} Q {cx} {cy - 22} {cx + 16} {cy + 7}" fill="none" '
            f'stroke="{OUTLINE}" stroke-width="6.5"/>')


def eye_swirl(c):
    cx, cy = c
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{ER[0]}" ry="{ER[1]}" fill="#FFFFFF" '
            f'stroke="{OUTLINE}" stroke-width="{OUT - 1}"/>'
            f'<path d="{spiral(cx, cy, 13)}" fill="none" stroke="{OUTLINE}" stroke-width="3.2"/>')


def brows(style):
    if style == 'cheeky':
        L, R = ((-34, -58), (-2, -50)), ((10, -50), (40, -58))
    elif style == 'worried':
        L, R = ((-34, -50), (-2, -58)), ((10, -58), (40, -50))
    else:  # raised
        return (f'<path d="M -32 -50 Q -14 -62 2 -52" fill="none" stroke="{OUTLINE}" stroke-width="6.5"/>'
                f'<path d="M 14 -52 Q 28 -64 42 -54" fill="none" stroke="{OUTLINE}" stroke-width="6.5"/>')
    return ''.join(f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" fill="none" stroke="{OUTLINE}" stroke-width="6.5"/>'
                   for a, b in (L, R))


# ---------- рот ----------
SMILE = ((-22, 20), (22, 52), (64, 16))

MOUTH_OPEN = 'M -28 18 Q 24 6 80 22 Q 92 58 36 78 Q -22 76 -28 18 Z'
MOUTH_CLENCH = 'M -26 24 Q 24 16 76 26 Q 86 48 30 56 Q -24 54 -26 24 Z'
MOUTH_HAPPY = 'M -26 14 Q 26 28 78 12 Q 86 66 30 72 Q -24 70 -26 14 Z'


def teeth_top(v, y, h):
    t = v['teeth']
    if t == 'buck':
        return [tooth_rect(4, y, 20, h), tooth_rect(24, y, 20, h)]
    if t == 'grin':
        return [tooth_rect(x, y, 15, h * 0.72, rx=3) for x in (-16, -1, 14, 29, 44)]
    out = [tooth_rect(x, y, 10, h * 0.5, rx=2.5) for x in (6, 16, 26, 36)]
    out += [fang(-8, y, 15, h), fang(58, y, 15, h)]
    return out


def closed_mouth(v):
    t = v['teeth']
    s = []
    if t == 'buck':
        s += [tooth_rect(8.5, 31, 13, 22), tooth_rect(21.5, 31, 13, 22)]
    elif t == 'grin':
        for tt in (0.25, 0.375, 0.5, 0.625, 0.75):
            x, y = qb(*SMILE, tt)
            s.append(tooth_rect(x - 5.4, y - 3, 10.8, 14, sw=2.8, rx=2.5))
    else:
        for tt in (0.2, 0.8):
            x, y = qb(*SMILE, tt)
            s.append(fang(x, y - 2, 13, 15, sw=3))
    p0, p1, p2 = SMILE
    s.append(f'<path d="M {p0[0]} {p0[1]} Q {p1[0]} {p1[1]} {p2[0]} {p2[1]}" fill="none" '
             f'stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    return ''.join(s)


def open_mouth(p, v, path, tongue, teeth_y, teeth_h):
    s = [f'<path d="{path}" fill="url(#{p}-cav)"/>']
    s.append(f'<g clip-path="url(#{p}-mclip)">')
    s.append(f'<ellipse cx="{tongue[0]}" cy="{tongue[1]}" rx="{tongue[2]}" ry="{tongue[3]}" fill="{TONGUE}" '
             f'stroke="{OUTLINE}" stroke-width="3.5"/>')
    s += teeth_top(v, teeth_y, teeth_h)
    s.append('</g>')
    s.append(f'<path d="{path}" fill="none" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    return ''.join(s), path


def chomp_mouth(p):
    """Стиснутые зубы: два ряда, смещённые на ползуба, как в мультяшном «ам»."""
    s = [f'<path d="{MOUTH_CLENCH}" fill="#FFFFFF"/>',
         f'<g clip-path="url(#{p}-mclip)" fill="none" stroke="{OUTLINE}" stroke-width="2.8">']
    s += [f'<path d="M {x} 16 L {x} 39"/>' for x in (-12, 4, 20, 36, 52, 68)]
    s += [f'<path d="M {x} 39 L {x} 60"/>' for x in (-4, 12, 28, 44, 60)]
    s.append('<path d="M -30 38 Q 24 43 84 35" stroke-width="3.6"/>')
    s.append('</g>')
    s.append(f'<path d="{MOUTH_CLENCH}" fill="none" stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    return ''.join(s), MOUTH_CLENCH


# ---------- макушка ----------
def sprout(p):
    return (f'<path d="M 4 -66 Q 2 -88 8 -104" fill="none" stroke="{OUTLINE}" stroke-width="12"/>'
            f'<path d="M 4 -66 Q 2 -88 8 -104" fill="none" stroke="#4FA83F" stroke-width="5.5"/>'
            f'<path d="M 8 -98 C -14 -112 -32 -100 -30 -86 C -14 -82 2 -86 8 -98 Z" '
            f'fill="url(#{p}-leaf)" stroke="{OUTLINE}" stroke-width="4.5"/>'
            f'<path d="M 9 -104 C 28 -124 52 -116 52 -100 C 40 -92 20 -92 9 -104 Z" '
            f'fill="url(#{p}-leaf)" stroke="{OUTLINE}" stroke-width="4.5"/>')


def crest(p):
    out = []
    for xb, hgt in ((-36, 30), (0, 38), (36, 30)):
        yb = -HEAD_RY * math.sqrt(1 - (xb / HEAD_RX) ** 2)
        d = (f'M {xb - 13:.1f} {yb + 12:.1f} Q {xb - 11:.1f} {yb - hgt * 0.4:.1f} {xb + 4:.1f} {yb - hgt:.1f} '
             f'Q {xb + 15:.1f} {yb - hgt * 0.4:.1f} {xb + 13:.1f} {yb + 12:.1f} Z')
        out.append(f'<path d="{d}" fill="url(#{p}-crest)" stroke="{OUTLINE}" stroke-width="4.5"/>')
    return ''.join(out)


def crown_svg(slug):
    """Макушка отдельным слоем: рисуется ПОД головой, чтобы шлем и броня могли её закрыть."""
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
    return svg(HEAD_CANVAS, defs,
               f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{art}</g>')


# ---------- голова ----------
def head_svg(slug, expr):
    v = VARIANTS[slug]
    p = f'worm-{slug}-head-{expr}'
    body, dark, belly = v['body'], v['dark'], v['belly']
    defs = [
        rgrad(f'{p}-hg', [(0, lighten(body, .5)), (.55, body), (1, mix(body, dark, .85))], cx=.42, cy=.28, r=.9),
        rgrad(f'{p}-mz', [(0, lighten(belly, .55)), (1, belly)], cx=.5, cy=.3, r=.9),
        lgrad(f'{p}-cav', [(0, MOUTH_DARK), (1, MOUTH_LIGHT)]),
        f'<clipPath id="{p}-clip"><ellipse rx="{HEAD_RX}" ry="{HEAD_RY}"/></clipPath>',
    ]

    layers = [f'<ellipse rx="{HEAD_RX}" ry="{HEAD_RY}" fill="url(#{p}-hg)"/>']

    inner = [f'<ellipse cx="24" cy="30" rx="52" ry="36" fill="url(#{p}-mz)"/>']
    if v['blush'] or expr == 'happy':
        k = 1.25 if expr == 'happy' else 1.0
        inner.append(f'<ellipse cx="-18" cy="28" rx="{12 * k:.1f}" ry="{7.5 * k:.1f}" fill="#FF5C7A" fill-opacity=".5"/>')
        inner.append(f'<ellipse cx="62" cy="24" rx="{9 * k:.1f}" ry="{6 * k:.1f}" fill="#FF5C7A" fill-opacity=".5"/>')
    if expr == 'hurt':
        inner.append(f'<circle cx="-52" cy="-44" r="12" fill="{lighten(body, .35)}" stroke="{OUTLINE}" stroke-width="4"/>'
                     f'<ellipse cx="-55" cy="-48" rx="4.5" ry="2.8" fill="#FFFFFF" fill-opacity=".7"/>')
    inner.append('<ellipse cx="-40" cy="-50" rx="22" ry="8" transform="rotate(-35 -40 -50)" '
                 'fill="#FFFFFF" fill-opacity=".55"/>')
    layers.append(f'<g clip-path="url(#{p}-clip)">{"".join(inner)}</g>')
    layers.append(f'<ellipse rx="{HEAD_RX}" ry="{HEAD_RY}" fill="none" stroke="{OUTLINE}" stroke-width="{OUT}"/>')

    # глаза
    if expr == 'open':
        eyes = ''.join(eye_normal(c, v, 1.08) for c in EYES)
    elif expr == 'chomp':
        eyes = ''.join(eye_squeeze(c, i) for i, c in enumerate(EYES))
    elif expr == 'hurt':
        eyes = ''.join(eye_swirl(c) for c in EYES)
    elif expr == 'happy':
        eyes = ''.join(eye_happy(c) for c in EYES)
    else:
        eyes = ''.join(eye_normal(c, v) for c in EYES)
    layers.append(eyes)

    # брови
    if expr == 'hurt':
        layers.append(brows('worried'))
    elif expr != 'happy' and v['brows']:
        layers.append(brows('raised' if expr == 'open' else 'cheeky'))

    # рот
    if expr == 'idle':
        layers.append(closed_mouth(v))
    elif expr == 'hurt':
        layers.append(f'<path d="M -18 36 q 9 -13 18 0 t 18 0 t 18 0 t 18 0" fill="none" '
                      f'stroke="{OUTLINE}" stroke-width="{OUT}"/>')
    else:
        if expr == 'open':
            m, path = open_mouth(p, v, MOUTH_OPEN, (24, 62, 36, 15), 10, 24)
        elif expr == 'chomp':
            m, path = chomp_mouth(p)
        else:
            m, path = open_mouth(p, v, MOUTH_HAPPY, (22, 56, 32, 13), 8, 20)
        defs.append(f'<clipPath id="{p}-mclip"><path d="{path}"/></clipPath>')
        layers.append(m)

    layers.append('<circle id="anchor-mouth" cx="80" cy="34" r="2" fill="none"/>')
    layers.append(f'<circle id="anchor-helmet" cx="0" cy="{-HEAD_RY}" r="2" fill="none"/>')
    body_svg = (f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">'
                f'{"".join(layers)}</g>')
    return svg(HEAD_CANVAS, defs, body_svg)


# ---------- сегмент тела ----------
def bead_svg(slug, kind):
    v = VARIANTS[slug]
    p = f'worm-{slug}-body-{kind}'
    base = v['body'] if kind == 'a' else mix(v['body'], v['dark'], .62)
    defs = [rgrad(f'{p}-g', [(0, lighten(base, .5)), (.5, base), (1, mix(base, v['dark'], .85))],
                  cx=.42, cy=.28, r=.9)]
    body_svg = (f'<g transform="translate(64 64)" stroke-linejoin="round" stroke-linecap="round">'
                f'<circle r="{BEAD_R}" fill="url(#{p}-g)" stroke="{OUTLINE}" stroke-width="{OUT}"/>'
                f'<ellipse cx="-10" cy="-30" rx="21" ry="8" transform="rotate(-14 -10 -30)" '
                f'fill="#FFFFFF" fill-opacity=".5"/>'
                f'<circle id="anchor-wing" cx="0" cy="{WING_ANCHOR_Y}" r="2" fill="none"/>'
                f'<circle id="anchor-armor" cx="0" cy="0" r="2" fill="none"/>'
                f'</g>')
    return svg(SEG_CANVAS, defs, body_svg)


# ---------- хвост ----------
def tail_svg(slug):
    v = VARIANTS[slug]
    p = f'worm-{slug}-tail'
    base = v['body']
    defs = [rgrad(f'{p}-g', [(0, lighten(base, .5)), (.5, base), (1, mix(base, v['dark'], .85))],
                  cx=.55, cy=.28, r=.9)]
    d = 'M 14 58 C 30 42 50 20 78 18 A 46 46 0 0 1 78 110 C 50 108 30 86 14 70 A 6.5 6.5 0 0 1 14 58 Z'
    body_svg = (f'<g stroke-linejoin="round" stroke-linecap="round">'
                f'<path d="{d}" fill="url(#{p}-g)" stroke="{OUTLINE}" stroke-width="{OUT}"/>'
                f'<ellipse cx="48" cy="40" rx="17" ry="6" transform="rotate(-24 48 40)" '
                f'fill="#FFFFFF" fill-opacity=".5"/>'
                f'</g>')
    return svg(SEG_CANVAS, defs, body_svg)


def main():
    count = 0
    for slug in VARIANTS:
        d = WORM / slug
        for expr in EXPRS:
            write(d / f'worm-{slug}-head-{expr}.svg', head_svg(slug, expr))
            count += 1
        crown = crown_svg(slug)
        if crown:
            write(d / f'worm-{slug}-crown.svg', crown)
            count += 1
        write(d / f'worm-{slug}-body-a.svg', bead_svg(slug, 'a'))
        write(d / f'worm-{slug}-body-b.svg', bead_svg(slug, 'b'))
        write(d / f'worm-{slug}-tail.svg', tail_svg(slug))
        count += 3
    chars = [{'id': k, 'tag': v['tag'], 'name': v['name'], 'note': v['note'], 'crown': bool(v['crown'])}
             for k, v in VARIANTS.items()]
    js = ('window.WORM_GEOM = ' + json.dumps(GEOM) + ';\n'
          'window.WORM_VARIANTS = ' + json.dumps(chars, ensure_ascii=False) + ';\n')
    write(PREVIEW / 'worm-geometry.js', js)
    # то же для игры: единый источник чисел (design/worm/rig.json)
    rig = dict(GEOM)
    rig['skins'] = chars
    write(WORM / 'rig.json', json.dumps(rig, ensure_ascii=False, indent=1) + '\n')
    print(f'worm: written {count} svg files + worm-geometry.js + rig.json')


if __name__ == '__main__':
    main()
