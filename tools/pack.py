#!/usr/bin/env python3
"""Упаковка собранной игры (папка dist) в ZIP для загрузки в Яндекс Игры, с проверкой правил архива.

Запуск: python tools/pack.py   (сначала npm run build; команда npm run pack делает оба шага)
Результат: build/worm-game-<версия>.zip. Если есть нарушение правил, ZIP не создаётся и код выхода 1.

Что проверяется (docs/YANDEX_REQUIREMENTS.md, пп. 1.7, 1.21, 1.22):
  - index.html лежит в корне архива и он ровно один;
  - в именах файлов и папок только латиница, цифры и . _ - (нет пробелов, русских букв, обратных слэшей);
  - в распакованном виде не больше 100 МБ (свой бюджет строже: 30 МБ всего, 5 МБ первая загрузка);
  - внутри нет sdk.js (его отдаёт платформа), а в index.html есть <script src="/sdk.js">;
  - ресурсы подключены относительными путями, нет абсолютных URL серверов Яндекса (S3) и чужих хостов;
  - нет мусора: карт кода, логов, служебных файлов, скрытых файлов.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
OUT_DIR = ROOT / 'build'

LIMIT_BYTES = 100 * 1024 * 1024      # п. 1.21: жёсткий предел платформы
BUDGET_TOTAL = 30 * 1024 * 1024      # свой бюджет: всё вместе
BUDGET_FIRST = 5 * 1024 * 1024       # свой бюджет: то, что нужно для старта

SAFE_NAME = re.compile(r'^[A-Za-z0-9._\-/]+$')
JUNK = re.compile(r'(\.map|\.log|\.tmp|\.bak)$|(^|/)(\.[^/]+|Thumbs\.db|desktop\.ini)$', re.I)
TEXT_EXT = {'.html', '.js', '.css', '.json', '.svg', '.txt', '.xml', '.webmanifest'}
S3_HINTS = ('s3.yandex', 'storage.yandexcloud', 'games.s3', 'yandexcloud.net', 'yastatic.net')
# адреса, которые встречаются в коде библиотек как идентификаторы пространств имён или значения по умолчанию, а не как
# загрузка ресурсов: phaser.io есть только в консольном баннере Phaser, а он выключен (banner: false в src/main.ts)
HARMLESS_HOSTS = ('www.w3.org', 'w3.org', 'www.khronos.org', 'khronos.org', 'localhost', '127.0.0.1', 'phaser.io')


def mb(n):
    return f'{n / 1024 / 1024:.2f} МБ'


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    problems = []
    warnings = []

    if not (DIST / 'index.html').is_file():
        print('Нет dist/index.html: сначала выполните npm run build.')
        return 1

    files = sorted(p for p in DIST.rglob('*') if p.is_file())
    rel = [p.relative_to(DIST).as_posix() for p in files]
    sizes = {r: p.stat().st_size for r, p in zip(rel, files)}
    total = sum(sizes.values())

    # --- имена и состав ---
    for r in rel:
        if not SAFE_NAME.match(r):
            problems.append(f'имя файла не из латиницы/цифр/._- : {r!r} (п. 1.22)')
        if JUNK.search(r):
            problems.append(f'лишний файл в сборке: {r} (карты кода, логи и скрытые файлы не нужны)')
        if r.lower().endswith('sdk.js') or Path(r).name.lower() == 'sdk.js':
            problems.append(f'в архиве не должно быть sdk.js: его подставляет платформа ({r})')
    indexes = [r for r in rel if Path(r).name.lower() == 'index.html']
    if indexes != ['index.html']:
        problems.append(f'index.html должен быть один и лежать в корне, найдено: {indexes} (п. 1.22)')

    # --- размер ---
    if total > LIMIT_BYTES:
        problems.append(f'распакованный размер {mb(total)} больше 100 МБ (п. 1.21)')
    if total > BUDGET_TOTAL:
        warnings.append(f'размер {mb(total)} больше нашего бюджета 30 МБ')

    # --- index.html ---
    html = (DIST / 'index.html').read_text(encoding='utf-8')
    if not re.search(r'<script[^>]+src=["\']/sdk\.js["\']', html):
        problems.append('в index.html нет <script src="/sdk.js"> (п. 1.1: без SDK нет рекламы, сохранений и языка)')
    for m in re.finditer(r'(?:src|href)=["\']([^"\']+)["\']', html):
        url = m.group(1)
        if url == '/sdk.js':
            continue
        if re.match(r'^(https?:)?//', url):
            problems.append(f'index.html: внешний адрес {url} (п. 1.7)')
        elif url.startswith('/'):
            problems.append(f'index.html: путь от корня сервера {url}, нужен относительный (п. 1.7)')
    if re.search(r'<(audio|video)\b', html, re.I):
        problems.append('index.html: есть <audio> или <video>, звук только через Web Audio (пп. 1.6.1.6, 1.6.2.5)')

    # --- текстовые файлы: адреса ---
    hosts = {}
    for r, p in zip(rel, files):
        if p.suffix.lower() not in TEXT_EXT:
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        low = text.lower()
        for hint in S3_HINTS:
            if hint in low:
                problems.append(f'{r}: встречается {hint!r}, а жёстких адресов серверов Яндекса быть не должно (п. 1.7)')
        for m in re.finditer(r'https?://([A-Za-z0-9.\-]+)', text):
            h = m.group(1).lower()
            if h not in HARMLESS_HOSTS:
                hosts.setdefault(h, set()).add(r)
        if p.suffix.lower() in ('.css', '.html'):
            for m in re.finditer(r'url\(\s*["\']?(https?:)?//', text):
                problems.append(f'{r}: ресурс по абсолютному адресу в url(...) (п. 1.7)')
    for h, where in sorted(hosts.items()):
        warnings.append(f'в коде есть адрес {h} ({", ".join(sorted(where))}): проверьте, что это не загрузка ресурса и не ссылка для игрока')

    # --- первая загрузка (верхняя оценка: страница, код и все атласы) ---
    first = sum(s for r, s in sizes.items() if r == 'index.html' or r.endswith(('.js', '.css')) or r.startswith('assets/') and r.endswith(('.png', '.json')))
    if first > BUDGET_FIRST:
        warnings.append(f'первая загрузка ≈{mb(first)}, больше нашего бюджета 5 МБ')

    # --- отчёт ---
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8')).get('version', '0.0.0')
    print(f'Сборка: {len(rel)} файлов, {mb(total)} в распакованном виде (первая загрузка ≈{mb(first)})')
    for r, s in sorted(sizes.items(), key=lambda kv: -kv[1])[:6]:
        print(f'  {s / 1024:9.1f} КБ  {r}')
    for w in warnings:
        print('ВНИМАНИЕ:', w)
    if problems:
        print('\nАрхив НЕ создан, нарушены правила:')
        for p in problems:
            print('  -', p)
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f'worm-game-{version}.zip'
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for r in sorted(rel, key=lambda x: (x != 'index.html', x)):  # index.html первым
            z.write(DIST / r, r)  # имя в архиве с прямыми слэшами

    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        names = z.namelist()
        unpacked = sum(i.file_size for i in z.infolist())
    assert bad is None, f'повреждённый файл в архиве: {bad}'
    assert 'index.html' in names and all(SAFE_NAME.match(n) and '\\' not in n for n in names)
    print(f'\nГотово: {out.relative_to(ROOT).as_posix()}  ({mb(out.stat().st_size)} в архиве, {mb(unpacked)} распакованно, '
          f'{len(names)} файлов, index.html в корне)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
