"""Общие кисти для спрайтов зоны 2 (поверхность): скруглённые прямоугольники, окна, колёса, градиенты.

Стиль тот же, что у червя: тёмный контур одной толщины, яркие плоские цвета с мягким градиентом сверху вниз и белым бликом.
Все спрайты стоят на земле: нижний край фигуры лежит на y = H - PAD (PAD px запаса под контур), игра ставит точку
опоры в этот y. Правила контента: без текста, флагов, звёзд, эмблем, крестов, куполов; техника вымышленная.
"""
from svgkit import OUTLINE, mix, lighten, svgwh

PAD = 4          # запас под контур у нижнего края: точка опоры y = H - PAD
OUT = 4.2        # толщина контура крупных форм
OUT_S = 3.0      # тонкие детали

_uid = [0]


def uid(prefix='g'):
    _uid[0] += 1
    return f'{prefix}{_uid[0]}'


def lg(defs, top, bot, x1=0, y1=0, x2=0, y2=1):
    """Линейный градиент сверху вниз, возвращает ссылку fill."""
    i = uid('lg')
    defs.append(f'<linearGradient id="{i}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"><stop offset="0" stop-color="{top}"/>'
                f'<stop offset="1" stop-color="{bot}"/></linearGradient>')
    return f'url(#{i})'


def shade(c, up=0.28, down=0.22):
    """Пара (светлее, темнее) для градиента."""
    return lighten(c, up), mix(c, '#000000', down)


def fillg(defs, c, up=0.28, down=0.22):
    a, b = shade(c, up, down)
    return lg(defs, a, b)


def rr(x, y, w, h, r, fill, sw=OUT, extra=''):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r:.1f}" fill="{fill}" '
            f'stroke="{OUTLINE}" stroke-width="{sw}" {extra}/>')


def circ(cx, cy, r, fill, sw=OUT):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{OUTLINE}" stroke-width="{sw}"/>'


def ell(cx, cy, rx, ry, fill, sw=OUT):
    return f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="{OUTLINE}" stroke-width="{sw}"/>'


def path(d, fill, sw=OUT, extra=''):
    return f'<path d="{d}" fill="{fill}" stroke="{OUTLINE}" stroke-width="{sw}" {extra}/>'


def poly(pts, fill, sw=OUT):
    return path('M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z', fill, sw)


def line(x1, y1, x2, y2, col=OUTLINE, sw=OUT_S, op=1.0):
    return (f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" fill="none" stroke="{col}" stroke-width="{sw}" '
            f'stroke-opacity="{op}" stroke-linecap="round"/>')


def hi(x, y, w, h, r=None, op=0.35):
    """Белый блик (скруглённый прямоугольник)."""
    r = min(w, h) / 2 if r is None else r
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r:.1f}" fill="#FFFFFF" fill-opacity="{op}"/>'


def glass(defs, x, y, w, h, lit=False, r=3, sw=OUT_S):
    """Окно: голубое стекло, диагональный блик; lit — тёплое жёлтое свечение."""
    top, bot = ('#FFF3B0', '#FFC94D') if lit else ('#D8F2FF', '#7CC4F2')
    g = lg(defs, top, bot)
    out = [rr(x, y, w, h, r, g, sw)]
    if w > 14 and h > 14:
        out.append(f'<path d="M {x + w * 0.2:.1f} {y + h * 0.82:.1f} L {x + w * 0.5:.1f} {y + h * 0.16:.1f} '
                   f'L {x + w * 0.64:.1f} {y + h * 0.16:.1f} L {x + w * 0.34:.1f} {y + h * 0.82:.1f} Z" fill="#FFFFFF" fill-opacity=".45"/>')
    return ''.join(out)


def wheel(cx, cy, r):
    """Колесо: чёрная шина, светлый диск, блик."""
    return (circ(cx, cy, r, '#3A3A46', OUT) + circ(cx, cy, r * 0.5, '#C9CED8', OUT_S) +
            f'<circle cx="{cx - r * 0.12:.1f}" cy="{cy - r * 0.14:.1f}" r="{r * 0.16:.1f}" fill="#FFFFFF" fill-opacity=".6"/>')


def group(parts, extra=''):
    return f'<g stroke-linejoin="round" stroke-linecap="round" {extra}>{"".join(parts)}</g>'


def sprite(w, h, defs, parts):
    return svgwh(w, h, defs, group(parts))
