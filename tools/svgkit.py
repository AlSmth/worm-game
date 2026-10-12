"""Общие помощники для генераторов SVG: цвет, градиенты, запись файлов."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTLINE = '#2B1B17'
OUT = 5.5   # толщина контура червя и его накладок, px при масштабе 1:1


def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lighten(c, t):
    return mix(c, '#FFFFFF', t)


def rgrad(id_, stops, cx=0.45, cy=0.30, r=0.85):
    s = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}">{s}</radialGradient>'


def lgrad(id_, stops, x1=0, y1=0, x2=0, y2=1):
    s = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{s}</linearGradient>'


def qb(p0, p1, p2, t):
    """Точка квадратичной кривой Безье."""
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def svg(size, defs, body):
    """Квадратный холст size×size."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'width="{size}" height="{size}">\n<defs>{"".join(defs)}</defs>\n{body}\n</svg>\n')


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')
