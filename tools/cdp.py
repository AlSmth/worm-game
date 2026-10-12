#!/usr/bin/env python3
"""Мини-драйвер браузера (Edge или Chrome) по протоколу DevTools, без внешних библиотек.

Нужен для проверки страниц и игры без ручного клика: открыть URL, дождаться готовности,
снять скриншот, выполнить JS, нажать клавишу или кнопку мыши, собрать ошибки консоли.
Запускает свой браузер в фоне (headless) с отдельным временным профилем; ваш браузер не трогает.

Из командной строки:
  python tools/cdp.py shot <url> <out.png> [--w 1280] [--h 900] [--full] [--wait "<js-выражение>"] [--sel "<css>"]
      --wait   ждать, пока выражение станет истинным (по умолчанию: все картинки загружены)
      --full   снять страницу целиком; --sel — снять только элемент
  python tools/cdp.py eval <url> "<js-выражение>"

Из Python:
  from cdp import Browser
  with Browser(1280, 900) as b:
      b.open(url); b.wait_for('window.ready'); b.screenshot('out.png'); print(b.eval('1+1'))
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
ALL_IMAGES_LOADED = '[...document.images].every(i => i.complete)'


def find_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError('Не найден Edge или Chrome')


class WebSocket:
    """Минимальный клиент WebSocket (RFC 6455): только то, что нужно DevTools."""

    def __init__(self, host, port, path, timeout=60):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n'
                           f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                           f'Sec-WebSocket-Version: 13\r\n\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('WebSocket: соединение закрыто при рукопожатии')
            head += chunk
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise ConnectionError('WebSocket: рукопожатие отклонено: ' + head.split(b'\r\n', 1)[0].decode())
        expect = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if expect not in head:
            raise ConnectionError('WebSocket: неверный Sec-WebSocket-Accept')
        self.buf = head.split(b'\r\n\r\n', 1)[1]

    def _exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise ConnectionError('WebSocket: соединение закрыто')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text, opcode=0x1):
        data = text.encode() if isinstance(text, str) else text
        n = len(data)
        head = bytearray([0x80 | opcode])
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack('>H', n)
        else:
            head.append(0x80 | 127)
            head += struct.pack('>Q', n)
        mask = os.urandom(4)
        self.sock.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        msg = b''
        while True:
            b1, b2 = self._exact(2)
            fin, opcode, n = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._exact(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._exact(8))[0]
            payload = self._exact(n)
            if opcode == 0x8:
                raise ConnectionError('WebSocket: закрыт сервером')
            if opcode == 0x9:
                self.send(payload, 0xA)
                continue
            if opcode in (0x0, 0x1, 0x2):
                msg += payload
                if fin:
                    return msg.decode('utf-8', 'replace')

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Browser:
    def __init__(self, width=1280, height=900, dpr=1.0, mobile=False, args=()):
        """args: дополнительные ключи запуска браузера, например ('--disable-3d-apis',) чтобы отключить WebGL."""
        self.width, self.height, self.dpr, self.mobile = width, height, dpr, mobile
        self.profile = tempfile.mkdtemp(prefix='cdp-profile-')
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.proc = subprocess.Popen(
            [find_browser(), '--headless=new', '--disable-gpu', '--hide-scrollbars', '--mute-audio',
             '--no-first-run', '--no-default-browser-check', '--disable-extensions',
             f'--remote-debugging-port={self.port}', f'--user-data-dir={self.profile}',
             f'--window-size={width},{height}', *args, 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.id = 0
        self.console = []      # (тип, текст): console.* и исключения
        self.ws = WebSocket('127.0.0.1', self.port, self._page_path())
        self.cmd('Runtime.enable')
        self.cmd('Page.enable')
        self.cmd('Log.enable')
        self.set_viewport(width, height, dpr, mobile)

    def _page_path(self):
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/list', timeout=2) as r:
                    for t in json.load(r):
                        if t.get('type') == 'page':
                            return '/devtools/page/' + t['id']
            except OSError:
                pass
            time.sleep(0.2)
        raise TimeoutError('Браузер не запустился')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            shutil.rmtree(self.profile, ignore_errors=True)

    # --- протокол ---
    def _event(self, m):
        method = m.get('method')
        p = m.get('params', {})
        if method == 'Runtime.consoleAPICalled':
            text = ' '.join(str(a.get('value', a.get('description', ''))) for a in p.get('args', []))
            self.console.append((p.get('type', 'log'), text))
        elif method == 'Runtime.exceptionThrown':
            d = p.get('exceptionDetails', {})
            self.console.append(('exception', (d.get('exception', {}).get('description') or d.get('text', ''))))
        elif method == 'Log.entryAdded':
            e = p.get('entry', {})
            self.console.append((e.get('level', 'log'), e.get('text', '') + ' ' + e.get('url', '')))

    def cmd(self, method, **params):
        self.id += 1
        i = self.id
        self.ws.send(json.dumps({'id': i, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == i:
                if 'error' in m:
                    raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})
            self._event(m)

    def pump(self, seconds=0.2):
        """Принять накопившиеся события (консоль) без команды."""
        self.ws.sock.settimeout(seconds)
        try:
            while True:
                self._event(json.loads(self.ws.recv()))
        except (socket.timeout, TimeoutError):
            pass
        finally:
            self.ws.sock.settimeout(60)

    # --- действия ---
    def set_viewport(self, w, h, dpr=1.0, mobile=False):
        self.cmd('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=dpr, mobile=mobile)
        if mobile:
            self.cmd('Emulation.setTouchEmulationEnabled', enabled=True, maxTouchPoints=5)

    def add_init_script(self, js):
        """Выполнить JS перед любым скриптом страницы (например, подставить свой YaGames)."""
        self.cmd('Page.addScriptToEvaluateOnNewDocument', source=js)

    def open(self, url, timeout=30):
        self.cmd('Page.navigate', url=url)
        self.wait_for("document.readyState === 'complete'", timeout)

    def eval(self, expr, await_promise=True):
        r = self.cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=await_promise)
        if 'exceptionDetails' in r:
            d = r['exceptionDetails']
            raise RuntimeError('JS: ' + (d.get('exception', {}).get('description') or d.get('text', '')))
        return r['result'].get('value')

    def wait_for(self, expr, timeout=30, step=0.15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.eval(expr):
                    return True
            except RuntimeError:
                pass
            time.sleep(step)
        raise TimeoutError('Не дождались: ' + expr)

    def screenshot(self, path, selector=None, full=False):
        params = {'format': 'png'}
        restore = None
        if selector:
            r = self.eval(f"(function(){{var e=document.querySelector({json.dumps(selector)});if(!e)return null;"
                          f"var b=e.getBoundingClientRect();return {{x:b.left+scrollX,y:b.top+scrollY,width:b.width,height:b.height}};}})()")
            if not r:
                raise LookupError('Нет элемента ' + selector)
            params['clip'] = {**r, 'scale': 1}
            params['captureBeyondViewport'] = True
        elif full:
            h = int(self.eval('Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)'))
            self.set_viewport(self.width, h, self.dpr, self.mobile)
            restore = True
        try:
            data = self.cmd('Page.captureScreenshot', **params)['data']
        finally:
            if restore:
                self.set_viewport(self.width, self.height, self.dpr, self.mobile)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(base64.b64decode(data))
        return path

    # --- ввод ---
    def key(self, code, key=None, text=None, down_ms=60):
        """Нажать и отпустить клавишу по коду (например code='ArrowLeft', key='ArrowLeft', 'KeyA' / 'a')."""
        key = key or code
        vk = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Space': 32, 'Enter': 13,
              'Escape': 27}.get(code, ord(key.upper()) if len(key) == 1 else 0)
        base = dict(code=code, key=key, windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
        self.cmd('Input.dispatchKeyEvent', type='keyDown', **base, **({'text': text} if text else {}))
        time.sleep(down_ms / 1000)
        self.cmd('Input.dispatchKeyEvent', type='keyUp', **base)

    def key_down(self, code, key=None):
        key = key or code
        vk = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Space': 32}.get(
            code, ord(key.upper()) if len(key) == 1 else 0)
        self.cmd('Input.dispatchKeyEvent', type='keyDown', code=code, key=key, windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)

    def key_up(self, code, key=None):
        key = key or code
        vk = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Space': 32}.get(
            code, ord(key.upper()) if len(key) == 1 else 0)
        self.cmd('Input.dispatchKeyEvent', type='keyUp', code=code, key=key, windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)

    def mouse(self, x, y, kind='move', button='left'):
        t = {'move': 'mouseMoved', 'down': 'mousePressed', 'up': 'mouseReleased'}[kind]
        self.cmd('Input.dispatchMouseEvent', type=t, x=x, y=y, button=button if kind != 'move' else 'none',
                 buttons=1 if kind == 'down' else 0, clickCount=1 if kind != 'move' else 0)

    def click(self, x, y):
        self.mouse(x, y, 'move')
        self.mouse(x, y, 'down')
        self.mouse(x, y, 'up')

    def touch(self, x, y, kind='start'):
        t = {'start': 'touchStart', 'move': 'touchMove', 'end': 'touchEnd'}[kind]
        pts = [] if kind == 'end' else [{'x': x, 'y': y}]
        self.cmd('Input.dispatchTouchEvent', type=t, touchPoints=pts)

    def errors(self):
        self.pump(0.3)
        return [c for c in self.console if c[0] in ('error', 'exception') and 'favicon.ico' not in c[1]]


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Мини-драйвер браузера')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('shot')
    s.add_argument('url')
    s.add_argument('out')
    s.add_argument('--w', type=int, default=1280)
    s.add_argument('--h', type=int, default=900)
    s.add_argument('--full', action='store_true')
    s.add_argument('--sel')
    s.add_argument('--wait', default=ALL_IMAGES_LOADED)
    e = sub.add_parser('eval')
    e.add_argument('url')
    e.add_argument('expr')
    e.add_argument('--w', type=int, default=1280)
    e.add_argument('--h', type=int, default=900)
    a = ap.parse_args()
    with Browser(a.w, a.h) as b:
        b.open(a.url)
        if a.cmd == 'shot':
            b.wait_for(a.wait, 40)
            time.sleep(0.3)
            b.screenshot(a.out, selector=a.sel, full=a.full)
            print('saved', a.out)
        else:
            print(json.dumps(b.eval(a.expr), ensure_ascii=False))
        errs = b.errors()
        if errs:
            print('Ошибки консоли:', *errs, sep='\n  ')
            sys.exit(1)


if __name__ == '__main__':
    main()
