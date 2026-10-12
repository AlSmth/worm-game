#!/usr/bin/env python3
"""Проверка собранного ZIP в условиях, близких к боевым (Яндекс Игры): без dev-сервера и без отладочных средств.

Запуск: python tools/test_dist.py [--zip build/worm-game-0.1.0.zip]   (сначала npm run pack)

Что делает: распаковывает именно архив, раздаёт его по вложенному пути /g/42/1/ (на хостинге игра лежит не в корне),
а /sdk.js отдаёт из корня сайта, как платформа. Проверяет запуск с SDK и без него: готовность, отсутствие отладочной панели
и ошибок, относительные пути, частоту кадров, язык. Снимки пишет в build/shots.
"""
import argparse
import http.server
import shutil
import sys
import threading
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402
from test_game import FAKE_SDK, RESULTS, check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREFIX = '/g/42/1/'
MIME = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
    '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
    '.webp': 'image/webp', '.woff2': 'font/woff2', '.wasm': 'application/wasm', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
}
FPS_JS = """new Promise(function(r){var n=0,t0=performance.now();(function f(){n++;
  if(performance.now()-t0>2000)r(n/2);else requestAnimationFrame(f);})();})"""


class Site:
    """Мини-сервер: игра по PREFIX, /sdk.js в корне (или 404, если SDK нет)."""

    def __init__(self, root, sdk_js):
        self.root, self.sdk_js, self.log = root.resolve(), sdk_js, []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = self.path.split('?', 1)[0]
                status, body, ctype = outer.resolve(path)
                outer.log.append((path, status))
                self.send_response(status)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def resolve(self, path):
        if path == '/sdk.js':
            if self.sdk_js is None:
                return 404, b'not found', 'text/plain'
            return 200, self.sdk_js.encode('utf-8'), 'text/javascript'
        if path.startswith(PREFIX):
            rel = path[len(PREFIX):] or 'index.html'
            f = (self.root / rel).resolve()
            if self.root in f.parents and f.is_file():
                return 200, f.read_bytes(), MIME.get(f.suffix.lower(), 'application/octet-stream')
        return 404, b'not found', 'text/plain'

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}{PREFIX}index.html'

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def unpack(zip_path):
    dest = ROOT / 'build' / 'zip-check'
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    return dest


def common_checks(b, site, shots, name, slug, on_select=None):
    t0 = time.time()
    b.wait_for("!!document.querySelector('canvas') && !document.getElementById('loader')", 40)
    check(f'{name}: игра запустилась, экран загрузки убран', True, f'за {time.time() - t0:.1f} с')
    time.sleep(1.0)
    check(f'{name}: отладочных средств нет (window.__dev и __platform не определены)',
          b.eval("typeof window.__dev === 'undefined' && typeof window.__platform === 'undefined'"))
    check(f'{name}: на странице нет отладочной панели и слова DEV', 'DEV' not in b.eval('document.body.innerText'))
    size = b.eval("(function(){var c=document.querySelector('canvas');var r=c.getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)]})()")
    check(f'{name}: холст на весь экран 1280x720', size == [1280, 720], str(size))
    fps = b.eval(FPS_JS)
    check(f'{name}: частота кадров не ниже 30', fps >= 30, f'{fps:.0f} кадров/с')
    # первый запуск: экран выбора персонажа (ready уже вызван), игрок выбирает клавишей
    b.screenshot(shots / f'p-{slug}-select.png')
    if on_select:
        on_select()
    b.key('Digit2')
    time.sleep(0.9)
    # управление мышью и клавишами не ломает игру
    b.mouse(900, 500, 'move')
    time.sleep(0.6)
    b.click(300, 450)
    b.key('Escape')
    time.sleep(0.4)
    b.key('Escape')
    time.sleep(1.0)
    b.screenshot(shots / f'p-{slug}.png')
    origin = f'http://127.0.0.1:{site.port}'
    urls = b.eval("performance.getEntriesByType('resource').map(function(e){return e.name})")
    foreign = [u for u in urls if not u.startswith(origin)]
    check(f'{name}: все запросы только к своему серверу', not foreign, str(foreign))
    return urls


def run_with_sdk(root, shots):
    site = Site(root, FAKE_SDK.replace('__LANG__', 'ru'))
    try:
        with Browser(1280, 720) as b:
            b.open(site.url)
            b.wait_for("window.__sdkLog && window.__sdkLog.indexOf('ready') >= 0", 40)
            def before_choice():
                log0 = b.eval('window.__sdkLog')
                check('с SDK: на экране выбора персонажа ready уже вызван, а start ещё нет (пп. 1.19.2, 1.19.3)',
                      'ready' in log0 and 'start' not in log0, str(log0))

            urls = common_checks(b, site, shots, 'с SDK', 'with-sdk', before_choice)
            log = b.eval('window.__sdkLog')
            check('с SDK: порядок вызовов init -> getPlayer -> ready -> start (после выбора персонажа)', log[0] == 'init' and
                  log.index('getPlayer') < log.index('ready') < log.index('start'), str(log))
            check('с SDK: ready() вызван ровно один раз', log.count('ready') == 1, str(log.count('ready')))
            check('с SDK: язык интерфейса ru', b.eval('document.documentElement.lang') == 'ru')
            check('с SDK: реклама в начале и посреди игры не показывается', 'adv' not in log and 'rewarded' not in log)
            sdk_url = f'http://127.0.0.1:{site.port}/sdk.js'
            check('с SDK: игра подключила /sdk.js из корня сайта', sdk_url in urls, str(urls))
            bad = [(p, s) for p, s in site.log if s != 200 and p != '/favicon.ico']
            check('с SDK: все файлы найдены по относительным путям (нет 404 при вложенном пути)', not bad, str(bad))
            check('с SDK: в консоли нет ошибок и предупреждений', not [c for c in b.console if c[0] in ('error', 'exception', 'warning', 'warn')
                                                                       and 'favicon.ico' not in c[1]], str(b.console[:5]))
            # магазин в собранной игре: клавиша B открывает, gameplay останавливается; Escape закрывает, gameplay снова запускается
            n0 = len(b.eval('window.__sdkLog'))
            b.key('KeyB')
            time.sleep(0.9)
            opened = [e for e in b.eval('window.__sdkLog')[n0:] if e != 'setData']
            check('с SDK: магазин открывается клавишей B, gameplay останавливается (stop)', opened == ['stop'], str(opened))
            b.screenshot(shots / 'p-with-sdk-shop.png')
            b.key('Escape')
            time.sleep(0.9)
            closed = [e for e in b.eval('window.__sdkLog')[n0:] if e != 'setData']
            check('с SDK: после закрытия магазина gameplay запускается снова (start), пауза не включилась', closed == ['stop', 'start'], str(closed))
            check('с SDK: после магазина в консоли нет ошибок и предупреждений', not [c for c in b.console if c[0] in ('error', 'exception', 'warning', 'warn')
                                                                                      and 'favicon.ico' not in c[1]], str(b.console[:5]))
            # перезагрузка (F5) не ломает запуск
            b.open(site.url)
            b.wait_for("window.__sdkLog && window.__sdkLog.indexOf('ready') >= 0", 40)
            check('с SDK: после обновления страницы игра снова готова', True)
    finally:
        site.close()


def set_browser_language(b, accept_language):
    """Подменить язык браузера (navigator.language) до открытия страницы."""
    b.open('about:blank')
    b.cmd('Emulation.setUserAgentOverride', userAgent=b.eval('navigator.userAgent'), acceptLanguage=accept_language)


def run_without_sdk(root, shots):
    site = Site(root, None)
    try:
        with Browser(1280, 720) as b:
            set_browser_language(b, 'en-US')
            check('без SDK: подмена языка браузера сработала', b.eval('navigator.language') == 'en-US', b.eval('navigator.language'))
            b.open(site.url)
            common_checks(b, site, shots, 'без SDK', 'no-sdk')
            errs = [e for e in b.errors() if 'sdk.js' not in e[1]]
            check('без SDK: игра работает автономно, других ошибок нет', not errs, str(errs))
            check('без SDK: язык по языку браузера en-US -> en', b.eval('document.documentElement.lang') == 'en', b.eval('document.documentElement.lang'))
        with Browser(1280, 720) as b:
            set_browser_language(b, 'ru-RU')
            b.open(site.url)
            b.wait_for("!!document.querySelector('canvas') && !document.getElementById('loader')", 40)
            check('без SDK: язык по языку браузера ru-RU -> ru', b.eval('document.documentElement.lang') == 'ru', b.eval('document.documentElement.lang'))
    finally:
        site.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', default='')
    ap.add_argument('--shots', default=str(ROOT / 'build' / 'shots'))
    a = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    zips = sorted((ROOT / 'build').glob('worm-game-*.zip'), key=lambda p: p.stat().st_mtime)
    zip_path = Path(a.zip) if a.zip else (zips[-1] if zips else None)
    if not zip_path or not zip_path.is_file():
        print('Нет архива: сначала выполните npm run pack')
        return 1
    shots = Path(a.shots)
    shots.mkdir(parents=True, exist_ok=True)
    print(f'Архив: {zip_path.relative_to(ROOT).as_posix()}')
    root = unpack(zip_path)
    print('[с SDK]')
    run_with_sdk(root, shots)
    print('[без SDK]')
    run_without_sdk(root, shots)
    failed = [r for r in RESULTS if not r[1]]
    print(f'\nИтог: {len(RESULTS) - len(failed)} из {len(RESULTS)} проверок пройдено')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
