#!/usr/bin/env python3
"""Генератор брони и гребня с плавниками (SVG): две линии улучшений червя из пяти ступеней.

Запуск из корня проекта:  python tools/gen_gear.py

Броня (линия «здоровье»): чешуя превращается в рога.
  1 Мелкая чешуя        2 Крупная чешуя        3 Чешуя с бугорками рогов
  4 Острые рога         5 Драконьи рога (золотые)
Гребень и плавники (линия «скорость»), вопрос Q11:
  1 Спинной гребешок (ряд шипов)   2 Высокий гребень и маленький хвостовой плавник   3 Спинной плавник с перепонкой
  4 Большой плавник, хвостовой веер, линии скорости   5 Золотой плавник, светится, искры следом

Для каждого из трёх персонажей (цвета берутся из design/worm/rig.json) пишет:
  design/upgrades/armor/<slug>/armor-<slug>-t<n>-plate.svg   пластина на спине (128×128), якорь = центр холста на верхней кромке тела
  design/upgrades/armor/<slug>/armor-<slug>-t<n>-head.svg    чешуя и ближний рог на голове (256×256), центр = центр головы
  design/upgrades/armor/<slug>/armor-<slug>-t<n>-horn.svg    дальний рог (с 3-й ступени), рисуется ПОД телом, как макушка
  design/upgrades/fins/<slug>/fin-<slug>-t<n>-seg.svg        звено спинного гребня (192×192), якорь на верхней кромке тела
  design/upgrades/fins/<slug>/fin-<slug>-t<n>-tail.svg       хвостовой плавник (с 2-й ступени, 320×320), центр = кончик хвоста, веер назад
и design/upgrades/gear.json (числа для игры: шаги, зоны, названия) и design/preview/gear-geometry.js.

Система координат у всех спрайтов: x вперёд (к голове), y вниз; «вверх» (спина) = −y; червь смотрит вправо.
Игра ставит спрайты вдоль тела (звенья) и на голове; при движении влево отражает по вертикали, поэтому свет всегда сверху.
Контур везде OUT (5,5 px у крупных форм, 3–4 px у мелких деталей), как у остального червя.

Правила контента (пп. 3.4.2, 3.4.5, 8.3.6, риск R14): рога округлые, цвета тёплой кости и золота, без красного и чёрного,
сочетание с тёмными крыльями проверяется в превью, чтобы не вышел образ «чёрта». Текста в рисунках нет.
SVG руками не правим: меняем параметры здесь и перегенерируем.
"""
import json
import math

from svgkit import ROOT, OUTLINE, OUT, mix, lighten, lgrad, write

WORM = ROOT / 'design' / 'worm'
UPG = ROOT / 'design' / 'upgrades'
PREVIEW = ROOT / 'design' / 'preview'
RIG = json.loads((WORM / 'rig.json').read_text(encoding='utf-8'))
R_HEAD = RIG['headRadius']

PLATE_CANVAS = 128
HEAD_CANVAS = 256
SEG_CANVAS = 192
TAIL_CANVAS = 320

BONE = ('#FFF7DC', '#E9CF94', '#BC9345')       # верх, низ, кольца (рога из тёплой кости)
GOLD = ('#FFF0A0', '#F5B820', '#B7780C')       # золото (драконьи рога, золотой плавник)
SPEED = ('#BFEFFF', '#38B6FF', '#1B6FB8')      # плавник 4-й ступени


# ---------- ступени: числа для игры и для генератора ----------
# Броня: пластины на спине. h — высота пластины над кромкой тела, w — ширина основания, sweep — наклон назад,
# horn — высота рога на пластине (0 — нет), pitch — шаг вдоль тела (px при масштабе 1:1).
ARMOR = {
    1: dict(name='Мелкая чешуя', w=18, h=11, sweep=6, horn=0, bump=0, pitch=13, cap=4, cap_h=9, cap_w=15, nub=0, horn_head=0),
    2: dict(name='Крупная чешуя', w=26, h=17, sweep=9, horn=0, bump=0, pitch=18, cap=5, cap_h=14, cap_w=21, nub=0, horn_head=0),
    3: dict(name='Чешуя с бугорками', w=27, h=19, sweep=10, horn=0, bump=8, pitch=19, cap=5, cap_h=15, cap_w=22, nub=14, horn_head=0),
    4: dict(name='Острые рога', w=27, h=17, sweep=9, horn=22, bump=0, pitch=23, cap=5, cap_h=15, cap_w=22, nub=0, horn_head=50),
    5: dict(name='Драконьи рога', w=29, h=19, sweep=11, horn=38, bump=0, pitch=27, cap=5, cap_h=16, cap_w=23, nub=0, horn_head=88),
}
# Гребень: шипы по спине. h — высота, bw — ширина основания шипа, sweep — наклон назад, membrane — перепонка между шипами.
FINS = {
    1: dict(name='Спинной гребешок', h=17, bw=13, sweep=7, pitch=17, membrane=False, tail=0, streaks=False, sparks=False),
    2: dict(name='Высокий гребень', h=27, bw=15, sweep=10, pitch=21, membrane=False, tail=56, streaks=False, sparks=False),
    3: dict(name='Спинной плавник', h=36, bw=16, sweep=12, pitch=25, membrane=True, tail=76, streaks=False, sparks=False),
    4: dict(name='Большой плавник', h=52, bw=18, sweep=15, pitch=29, membrane=True, tail=108, streaks=True, sparks=False),
    5: dict(name='Золотой плавник', h=68, bw=20, sweep=18, pitch=33, membrane=True, tail=140, streaks=True, sparks=True),
}
ARMOR_START = 54          # с какого расстояния от центра головы начинаются пластины на теле
ARMOR_END = 0.5           # до какой доли длины тела (передняя половина)
FIN_START = 0.5           # гребень от середины тела до хвоста (доли длины)


# ---------- геометрия ----------
def f(v):
    return f'{v:.1f}'


def pt(p):
    return f'{p[0]:.1f} {p[1]:.1f}'


def rot(p, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def curved_horn(base, tip, width, bend):
    """Рог: изогнутый конус от основания base (центр) к кончику tip; bend — изгиб вбок (доля длины, + в сторону нормали)."""
    ax, ay = tip[0] - base[0], tip[1] - base[1]
    ln = math.hypot(ax, ay) or 1.0
    ux, uy = ax / ln, ay / ln
    nx, ny = uy, -ux                                   # нормаль (против часовой)
    bl = (base[0] + nx * width / 2, base[1] + ny * width / 2)
    br = (base[0] - nx * width / 2, base[1] - ny * width / 2)
    k = bend * ln
    c1 = (bl[0] + ux * ln * 0.42 + nx * k * 0.55, bl[1] + uy * ln * 0.42 + ny * k * 0.55)
    c2 = (tip[0] - ux * ln * 0.22 + nx * k * 0.95, tip[1] - uy * ln * 0.22 + ny * k * 0.95)
    c3 = (tip[0] - ux * ln * 0.22 + nx * (k * 0.95 - width * 0.12), tip[1] - uy * ln * 0.22 + ny * (k * 0.95 - width * 0.12))
    c4 = (br[0] + ux * ln * 0.42 + nx * k * 0.55, br[1] + uy * ln * 0.42 + ny * k * 0.55)
    d = f'M {pt(bl)} C {pt(c1)} {pt(c2)} {pt(tip)} C {pt(c3)} {pt(c4)} {pt(br)} Z'
    return d, (bl, br, ux, uy, nx, ny, ln)


def horn_g(pid, base, tip, width, bend, pal, rings=2, sw=3.4):
    """Рог целиком: заливка градиентом, контур, кольца роста у основания и блик (кольца и блик обрезаны по контуру рога)."""
    d, (bl, br, ux, uy, nx, ny, ln) = curved_horn(base, tip, width, bend)
    cid = f'{pid}-clip'
    out = [f'<clipPath id="{cid}"><path d="{d}"/></clipPath>',
           f'<path d="{d}" fill="url(#{pid})" stroke="{OUTLINE}" stroke-width="{sw}"/>']
    inner = []
    for i in range(rings):
        t = 0.2 + 0.19 * i
        w = width * 1.2
        cx, cy = base[0] + ux * ln * t + nx * bend * ln * 0.3 * t, base[1] + uy * ln * t + ny * bend * ln * 0.3 * t
        a = (cx + nx * w * 0.5, cy + ny * w * 0.5)
        b = (cx - nx * w * 0.5, cy - ny * w * 0.5)
        m = (cx + ux * w * 0.3, cy + uy * w * 0.3)
        inner.append(f'<path d="M {pt(a)} Q {pt(m)} {pt(b)}" fill="none" stroke="{pal[2]}" stroke-width="2.4" stroke-opacity=".8"/>')
    hi_a = (base[0] + ux * ln * 0.16 + nx * width * 0.2, base[1] + uy * ln * 0.16 + ny * width * 0.2)
    hi_b = (base[0] + ux * ln * 0.66 + nx * (width * 0.1 + bend * ln * 0.5), base[1] + uy * ln * 0.66 + ny * (width * 0.1 + bend * ln * 0.5))
    inner.append(f'<path d="M {pt(hi_a)} L {pt(hi_b)}" fill="none" stroke="#FFFFFF" stroke-opacity=".7" stroke-width="3"/>')
    out.append(f'<g clip-path="url(#{cid})">{"".join(inner)}</g>')
    return ''.join(out)


def horn_grad(pid, pal):
    return lgrad(pid, [(0, pal[0]), (.55, mix(pal[0], pal[1], .6)), (1, pal[1])], 0, 0, 1, 1)


def leaf(w, h, sweep, inset=7):
    """Лист-пластина: основание шириной w на 7 px ниже якоря, вершина смещена назад на sweep и поднята на h."""
    bw = w / 2
    tip = (-sweep, -h)
    d = (f'M {f(bw)} {f(inset)} C {f(bw + 1.5)} {f(-h * 0.35)} {f(-sweep * 0.1 + 3)} {f(-h * 0.88)} {f(tip[0])} {f(tip[1])} '
         f'C {f(-sweep - w * 0.22)} {f(-h * 0.55)} {f(-bw - 2)} {f(-h * 0.05)} {f(-bw)} {f(inset)} Z')
    return d, tip


def scale_art(pid, w, h, sweep, pal_main, pal_light, pal_dark, bump=0, sw=3.2, ridge=True):
    """Пластина-чешуйка (в локальных координатах, якорь в нуле)."""
    d, tip = leaf(w, h, sweep)
    out = [f'<path d="{d}" fill="url(#{pid})" stroke="{OUTLINE}" stroke-width="{sw}"/>']
    # блик по передней кромке и дуга-«чешуйка» посередине
    bw = w / 2
    out.append(f'<path d="M {f(bw - 3)} {f(3)} C {f(bw - 2.5)} {f(-h * 0.32)} {f(-sweep * 0.05 + 3)} {f(-h * 0.8)} {f(tip[0] + 3.5)} {f(tip[1] + 4)}" '
               f'fill="none" stroke="#FFFFFF" stroke-opacity=".5" stroke-width="2.4" stroke-linecap="round"/>')
    if ridge:
        out.append(f'<path d="M {f(-bw * 0.62)} {f(1)} Q {f(-sweep * 0.3)} {f(-h * 0.52)} {f(bw * 0.52)} {f(1)}" fill="none" '
                   f'stroke="{pal_dark}" stroke-opacity=".6" stroke-width="2"/>')
    if bump:
        # бугорок будущего рога: костяной конус на вершине
        bx, by = tip[0] + sweep * 0.35, tip[1] + h * 0.22
        out.append(f'<path d="M {f(bx - 5)} {f(by + 2)} Q {f(bx - 4)} {f(by - bump * 0.65)} {f(bx - 7.5)} {f(by - bump)} '
                   f'Q {f(bx + 3)} {f(by - bump * 0.6)} {f(bx + 5.5)} {f(by + 2)} Z" fill="{BONE[0]}" stroke="{OUTLINE}" stroke-width="2.6"/>')
    return ''.join(out)


def palette(slug):
    v = next(s for s in RIG['skins'] if s['id'] == slug)
    body, dark = v['body'], v['dark']
    return dict(
        main=mix(dark, OUTLINE, 0.14),
        light=lighten(dark, 0.42),
        deep=mix(dark, OUTLINE, 0.55),
        body=body,
        pale=lighten(body, 0.42),
        fin_dark=mix(dark, OUTLINE, 0.3),
    )


def scale_grad(pid, pal):
    return lgrad(pid, [(0, pal['light']), (.45, pal['main']), (1, pal['deep'])], 0.2, 0, 0.8, 1)


# ---------- броня ----------
def plate_svg(slug, n):
    A = ARMOR[n]
    pal = palette(slug)
    c = PLATE_CANVAS // 2
    pid = f'armor-{slug}-t{n}-plate'
    defs = [scale_grad(f'{pid}-g', pal)]
    parts = []
    if A['horn']:
        defs.append(horn_grad(f'{pid}-h', GOLD if n == 5 else BONE))
        hp = GOLD if n == 5 else BONE
        base = (-A['sweep'] * 0.45, -A['h'] + 5)
        tip = (-A['sweep'] - 9 - A['horn'] * 0.28, -A['h'] - A['horn'])
        parts.append(horn_g(f'{pid}-h', base, tip, 15 if n == 4 else 19, 0.2 if n == 4 else 0.33, hp, 2))
    parts.append(scale_art(f'{pid}-g', A['w'], A['h'], A['sweep'], pal['main'], pal['light'], pal['deep'], bump=A['bump']))
    if n == 5:
        # золотая кайма вдоль передней кромки: «драконья» броня
        parts.append(f'<path d="M {f(A["w"] / 2 - 1)} 4 C {f(A["w"] / 2)} {f(-A["h"] * 0.3)} {f(-A["sweep"] * 0.1 + 3)} {f(-A["h"] * 0.85)} {f(-A["sweep"] + 2)} {f(-A["h"] + 3)}" '
                     f'fill="none" stroke="{GOLD[1]}" stroke-width="3"/>')
    body = f'<g transform="translate({c} {c})" stroke-linejoin="round" stroke-linecap="round">{"".join(parts)}</g>'
    return svg_(PLATE_CANVAS, defs, body)


def svg_(size, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">\n'
            f'<defs>{"".join(defs)}</defs>\n{body}\n</svg>\n')


# Чешуя и рога на голове живут на задней половине макушки (x от −40 до 4): передняя часть остаётся для глаз и бровей.
HEAD_X = [-39, -28, -17, -6, 5]


def head_point(x):
    return (x, -math.sqrt(max(1.0, R_HEAD ** 2 - x * x)) + 2)


def cap_scales(pid, A, pal):
    parts = []
    for i in range(A['cap']):
        x = HEAD_X[i]
        px, py = head_point(x)
        a = math.degrees(math.atan2(x, -py))               # наклон нормали головы
        art = scale_art(f'{pid}-g', A['cap_w'], A['cap_h'], A['cap_h'] * 0.35, pal['main'], pal['light'], pal['deep'], sw=3.0, ridge=False)
        parts.append(f'<g transform="translate({f(px)} {f(py)}) rotate({f(a)})">{art}</g>')
    return parts[::-1]                                       # от задних к передним: передние лежат сверху


def head_svg(slug, n):
    A = ARMOR[n]
    pal = palette(slug)
    pid = f'armor-{slug}-t{n}-head'
    defs = [scale_grad(f'{pid}-g', pal)]
    parts = cap_scales(pid, A, pal)
    hp = GOLD if n == 5 else BONE
    if A['nub']:
        defs.append(horn_grad(f'{pid}-n', BONE))
        for x, hh in ((-17, A['nub']), (-1, A['nub'] * 0.86)):
            bx, by = head_point(x)
            parts.append(horn_g(f'{pid}-n', (bx, by + 3), (bx - 6, by - hh), 11, 0.18, BONE, 1, 3.0))
    if A['horn_head']:
        defs.append(horn_grad(f'{pid}-h', hp))
        bx, by = head_point(-18)
        L = A['horn_head']
        tip = (bx - 0.46 * L, by - 0.9 * L) if n == 4 else (bx - 0.78 * L, by - 0.78 * L)
        parts.append(horn_g(f'{pid}-h', (bx, by + 4), tip, 25 if n == 4 else 32, 0.2 if n == 4 else 0.42, hp, 3))
    body = f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{"".join(parts)}</g>'
    return svg_(HEAD_CANVAS, defs, body)


def horn_back_svg(slug, n):
    """Дальний рог: чуть впереди ближнего и меньше; рисуется под телом, голова закрывает его основание."""
    A = ARMOR[n]
    pid = f'armor-{slug}-t{n}-horn'
    hp = GOLD if n == 5 else BONE
    defs = [horn_grad(f'{pid}-h', hp)]
    if n == 3:
        bx, by = head_point(4)
        art = horn_g(f'{pid}-h', (bx, by + 3), (bx - 5, by - A['nub'] * 0.8), 10, 0.18, hp, 1, 3.0)
    else:
        L = A['horn_head'] * 0.9
        bx, by = head_point(2)
        tip = (bx - 0.46 * L, by - 0.9 * L) if n == 4 else (bx - 0.78 * L, by - 0.78 * L)
        art = horn_g(f'{pid}-h', (bx, by + 4), tip, 22 if n == 4 else 28, 0.2 if n == 4 else 0.42, hp, 3)
    return svg_(HEAD_CANVAS, defs, f'<g transform="translate(128 128)" stroke-linejoin="round" stroke-linecap="round">{art}</g>')


# ---------- гребень и плавники ----------
def fin_colors(slug, n):
    pal = palette(slug)
    if n <= 2:
        return dict(top=pal['pale'], bot=pal['body'], ray=pal['fin_dark'], glow=None)
    if n == 3:
        return dict(top=lighten(pal['pale'], .4), bot=pal['pale'], ray=pal['fin_dark'], glow=None)
    if n == 4:
        return dict(top=SPEED[0], bot=SPEED[1], ray=SPEED[2], glow=None)
    return dict(top=GOLD[0], bot=GOLD[1], ray=GOLD[2], glow='#FFF3A6')


def seg_svg(slug, n):
    """Звено гребня: шип, наклонённый назад, и (с 3-й ступени) перепонка к следующему шипу."""
    F = FINS[n]
    col = fin_colors(slug, n)
    c = SEG_CANVAS // 2
    pid = f'fin-{slug}-t{n}-seg'
    h, bw, sw_, p = F['h'], F['bw'], F['sweep'], F['pitch']
    defs = [lgrad(f'{pid}-g', [(0, col['top']), (1, col['bot'])]),
            lgrad(f'{pid}-m', [(0, mix(col['top'], '#FFFFFF', .2)), (1, col['bot'])], 0, 0, 0, 1)]
    parts = []
    if col['glow']:
        defs.append(f'<radialGradient id="{pid}-gl"><stop offset="0" stop-color="{col["glow"]}" stop-opacity=".75"/>'
                    f'<stop offset="1" stop-color="{col["glow"]}" stop-opacity="0"/></radialGradient>')
        parts.append(f'<ellipse cx="{f(-p * 0.4)}" cy="{f(-h * 0.5)}" rx="{f(p * 0.9 + 14)}" ry="{f(h * 0.8)}" fill="url(#{pid}-gl)"/>')
    tip = (-sw_, -h)
    nxt_tip = (-p - sw_, -h * 0.94)
    spike = (f'M {f(bw / 2)} 8 C {f(bw / 2)} {f(-h * 0.4)} {f(-sw_ * 0.25)} {f(-h * 0.85)} {f(tip[0])} {f(tip[1])} '
             f'C {f(-sw_ - bw * 0.3)} {f(-h * 0.55)} {f(-bw / 2)} {f(-h * 0.1)} {f(-bw / 2)} 8 Z')
    if F['membrane']:
        # перепонка между этим шипом и следующим: вогнутая верхняя кромка
        mid = ((tip[0] + nxt_tip[0]) / 2, (tip[1] + nxt_tip[1]) / 2 + h * 0.34)
        memb = (f'M {f(-bw / 2)} 8 L {f(-bw / 2 - 1)} {f(-h * 0.12)} L {pt(tip)} Q {pt(mid)} {pt(nxt_tip)} '
                f'L {f(-p + bw / 2)} 8 Z')
        parts.append(f'<path d="{memb}" fill="url(#{pid}-m)" stroke="{OUTLINE}" stroke-width="3.2"/>')
        # прожилки перепонки
        for t in (0.3, 0.62):
            sx = -bw / 2 - (p - bw) * t
            ex = tip[0] + (nxt_tip[0] - tip[0]) * t
            ey = tip[1] + (nxt_tip[1] - tip[1]) * t + h * 0.34 * 4 * t * (1 - t) * 0.9
            parts.append(f'<path d="M {f(sx)} {f(4)} L {f(ex)} {f(ey + h * 0.18)}" fill="none" stroke="{col["ray"]}" stroke-opacity=".55" stroke-width="2"/>')
    parts.append(f'<path d="{spike}" fill="url(#{pid}-g)" stroke="{OUTLINE}" stroke-width="3.4"/>')
    parts.append(f'<path d="M {f(bw / 2 - 3)} {f(2)} C {f(bw / 2 - 3)} {f(-h * 0.38)} {f(-sw_ * 0.25 + 2)} {f(-h * 0.8)} {f(tip[0] + 2.5)} {f(tip[1] + 5)}" '
                 f'fill="none" stroke="#FFFFFF" stroke-opacity=".6" stroke-width="2.2"/>')
    parts.append(f'<path d="M {f(-bw / 2 + 3)} {f(2)} C {f(-bw / 2 + 2)} {f(-h * 0.3)} {f(-sw_ * 0.6)} {f(-h * 0.6)} {f(tip[0] - 1)} {f(tip[1] + 6)}" '
                 f'fill="none" stroke="{col["ray"]}" stroke-opacity=".55" stroke-width="2"/>')
    if n == 5:
        for k in (0.35, 0.7):
            sx, sy = -sw_ * k - bw * 0.25 * (1 - k), -h * k
            parts.append(f'<path d="M {f(sx)} {f(sy - 4)} L {f(sx + 2)} {f(sy)} L {f(sx)} {f(sy + 4)} L {f(sx - 2)} {f(sy)} Z" fill="#FFFFFF" fill-opacity=".85"/>')
    return svg_(SEG_CANVAS, defs, f'<g transform="translate({c} {c})" stroke-linejoin="round" stroke-linecap="round">{"".join(parts)}</g>')


def tail_svg(slug, n):
    """Хвостовой плавник: веер назад от кончика хвоста (центр холста), два лепестка и перепонка с лучами."""
    F = FINS[n]
    col = fin_colors(slug, n)
    pid = f'fin-{slug}-t{n}-tail'
    ln = F['tail']
    hs = ln * 0.52 + 6
    defs = [lgrad(f'{pid}-g', [(0, col['bot']), (1, col['top'])], 0, 0, 1, 0)]
    parts = []
    if col['glow']:
        defs.append(f'<radialGradient id="{pid}-gl"><stop offset="0" stop-color="{col["glow"]}" stop-opacity=".7"/>'
                    f'<stop offset="1" stop-color="{col["glow"]}" stop-opacity="0"/></radialGradient>')
        parts.append(f'<ellipse cx="{f(-ln * 0.55)}" cy="0" rx="{f(ln * 0.8)}" ry="{f(hs * 1.1)}" fill="url(#{pid}-gl)"/>')
    # два лепестка: верхний и нижний; между ними вогнутая задняя кромка
    up = (-ln, -hs)
    dn = (-ln, hs)
    notch = (-ln * 0.62, 0)
    fan = (f'M -6 -10 C {f(-ln * 0.3)} {f(-hs * 0.55)} {f(-ln * 0.75)} {f(-hs * 1.0)} {pt(up)} '
           f'Q {f(-ln * 0.8)} {f(-hs * 0.28)} {pt(notch)} Q {f(-ln * 0.8)} {f(hs * 0.28)} {pt(dn)} '
           f'C {f(-ln * 0.75)} {f(hs * 1.0)} {f(-ln * 0.3)} {f(hs * 0.55)} -6 10 Z')
    parts.append(f'<path d="{fan}" fill="url(#{pid}-g)" stroke="{OUTLINE}" stroke-width="{OUT - 1.2}"/>')
    rays = 3 if n <= 3 else 5
    for i in range(rays):
        u = -1 + 2 * i / (rays - 1)
        ex = -ln * (0.98 - 0.36 * (1 - abs(u)) ** 1.5 * (1 if abs(u) < 0.99 else 0))
        ey = u * hs * (0.92 - 0.1 * (1 - abs(u)))
        parts.append(f'<path d="M -8 {f(u * 4)} L {f(ex * 0.93)} {f(ey * 0.9)}" fill="none" stroke="{col["ray"]}" stroke-opacity=".7" stroke-width="2.4"/>')
    parts.append(f'<path d="M -10 -4 C {f(-ln * 0.3)} {f(-hs * 0.4)} {f(-ln * 0.6)} {f(-hs * 0.72)} {f(-ln * 0.86)} {f(-hs * 0.9)}" '
                 f'fill="none" stroke="#FFFFFF" stroke-opacity=".55" stroke-width="2.6"/>')
    if n == 5:
        for k, (sx, sy) in enumerate(((-0.5, -0.5), (-0.78, 0.3), (-0.4, 0.55))):
            x, y = ln * sx, hs * sy
            parts.append(f'<path d="M {f(x)} {f(y - 6)} L {f(x + 3)} {f(y)} L {f(x)} {f(y + 6)} L {f(x - 3)} {f(y)} Z" fill="#FFFFFF" fill-opacity=".9" '
                         f'stroke="{GOLD[2]}" stroke-width="1.2"/>')
    return svg_(TAIL_CANVAS, defs, f'<g transform="translate({TAIL_CANVAS // 2} {TAIL_CANVAS // 2})" stroke-linejoin="round" stroke-linecap="round">{"".join(parts)}</g>')


def main():
    files = 0
    for slug in (s['id'] for s in RIG['skins']):
        for n in ARMOR:
            d = UPG / 'armor' / slug
            write(d / f'armor-{slug}-t{n}-plate.svg', plate_svg(slug, n))
            write(d / f'armor-{slug}-t{n}-head.svg', head_svg(slug, n))
            files += 2
            if n >= 3:
                write(d / f'armor-{slug}-t{n}-horn.svg', horn_back_svg(slug, n))
                files += 1
        for n in FINS:
            d = UPG / 'fins' / slug
            write(d / f'fin-{slug}-t{n}-seg.svg', seg_svg(slug, n))
            files += 1
            if FINS[n]['tail']:
                write(d / f'fin-{slug}-t{n}-tail.svg', tail_svg(slug, n))
                files += 1
    info = {
        'plateCanvas': PLATE_CANVAS, 'headCanvas': HEAD_CANVAS, 'segCanvas': SEG_CANVAS, 'tailCanvas': TAIL_CANVAS,
        'armorStart': ARMOR_START, 'armorEnd': ARMOR_END, 'finStart': FIN_START,
        'armor': [dict(tier=n, **{k: v for k, v in A.items()}) for n, A in ARMOR.items()],
        'fins': [dict(tier=n, **{k: v for k, v in F.items()}) for n, F in FINS.items()],
    }
    write(UPG / 'gear.json', json.dumps(info, ensure_ascii=False, indent=1) + '\n')
    write(PREVIEW / 'gear-geometry.js', 'window.GEAR = ' + json.dumps(info, ensure_ascii=False) + ';\n')
    print(f'gear: written {files} svg files + gear.json + gear-geometry.js')


if __name__ == '__main__':
    main()
