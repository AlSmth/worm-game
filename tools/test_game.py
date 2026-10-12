#!/usr/bin/env python3
"""Автопроверки игры в фоновом браузере (протокол DevTools, без внешних библиотек).

Запуск (сервер игры должен работать: node tools/dev.mjs):
  python tools/test_game.py [--url http://127.0.0.1:5173/] [--only имя1,имя2] [--shots папка]

Каждая проверка печатает OK или FAIL с причиной; в конце итог. Код выхода 1, если есть провалы.
Проверяет то, что можно проверить без глаз: загрузку, рост от еды, прыжок, крылья, скины, паузу, сохранения,
размеры окна и касания. Снимки для просмотра глазами сохраняются в папку --shots.
"""
import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

URL = 'http://127.0.0.1:5173/'
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print(('  OK   ' if cond else '  FAIL ') + name + (f'  [{detail}]' if detail else ''))
    return bool(cond)


def state(b):
    return b.eval('window.__dev.state()')


def boot(b, url, wait=30):
    b.open(url)
    b.wait_for('!!window.__dev', wait)
    time.sleep(0.8)


def world_to_client(b, wx, wy):
    """Мировая точка -> координаты клиентской области (CSS px) для отправки мыши."""
    return b.eval(
        "(function(){var s=window.__dev.scene, c=s.cameras.main, v=c.worldView, cv=s.game.canvas.getBoundingClientRect();"
        f"var px=({wx}-v.x)*c.zoom, py=({wy}-v.y)*c.zoom;"
        "return {x: cv.left + px * (cv.width / c.width), y: cv.top + py * (cv.height / c.height)};})()"
    )


def t_boot(b, shots):
    boot(b, URL)
    s = state(b)
    # червь стартует в точке (0, 260*масштаб) и сразу плывёт, поэтому мерим от точки старта, а не от текущего положения
    near = b.eval("(function(){var s=window.__dev.scene, S=s.worm.scale, m=1e9; s.prey.items.forEach(function(it){m=Math.min(m, Math.hypot(it.x, it.y-260*S)/S)}); return m})()")
    check('загрузка: вокруг точки старта свободная зона, добыча не появляется во рту', near > 250, f'ближайшая добыча: {near:.0f} px (в масштабе червя)')
    check('загрузка: игра готова, 30 добыч вокруг', s['prey'] >= 25, f"prey={s['prey']}")
    check('загрузка: холст на весь экран 1280x720', (s['canvasW'], s['canvasH']) == (1280, 720), f"{s['canvasW']}x{s['canvasH']}")
    time.sleep(1.0)
    fps = state(b)['fps']
    check('загрузка: частота кадров не ниже 30', fps >= 30, f'fps={fps}')
    b.screenshot(shots / 'g01-start.png')
    check('загрузка: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_autopilot_growth(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    b.eval('window.__dev.autopilot(true)')
    t0 = time.time()
    s = state(b)
    while time.time() - t0 < 40 and state(b)['eaten'] < 12:
        time.sleep(0.5)
    s = state(b)
    check('рост: автопилот съел не меньше 10 жуков за 40 с', s['eaten'] >= 10, f"eaten={s['eaten']}, tier={s['tier']}, growth={s['growth']}/{s['need']}")
    check('рост: прогресс изменился (шкала или тир)', s['tier'] > 1 or s['growth'] > 0, f"tier={s['tier']}")
    check('рост: червь стал крупнее или длиннее', s['scale'] > 1.0 or s['segs'] > 5, f"scale={s['scale']}, segs={s['segs']}")
    b.screenshot(shots / 'g02-grown.png')
    b.eval('window.__dev.autopilot(false)')


def t_jump(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    s0 = state(b)
    # цель у верхнего края видимой области, справа от червя (там небо над землёй)
    view_top = b.eval('window.__dev.scene.cameras.main.worldView.y')
    target = world_to_client(b, s0['x'] + 500, view_top + 60)
    b.mouse(target['x'], target['y'], 'move')
    min_y, got_air = 0, False
    t0 = time.time()
    while time.time() - t0 < 6:
        time.sleep(0.05)
        s = state(b)
        if s['inAir']:
            got_air = True
        min_y = min(min_y, s['y'])
    check('прыжок: червь вышел на поверхность и взлетел', got_air)
    check('прыжок: высота разумная (есть, но не выше полёта)', -900 < min_y < -40, f'min_y={min_y}')
    b.screenshot(shots / 'g03-jump.png')
    # возвращается под землю
    t0 = time.time()
    while time.time() - t0 < 6 and state(b)['inAir']:
        time.sleep(0.1)
    check('прыжок: после прыжка червь возвращается под землю', not state(b)['inAir'])


def t_wings(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    count = "window.__dev.scene.children.list.filter(function(c){return c.texture && c.texture.key==='wings'}).length"
    check('крылья: по умолчанию нет', b.eval(count) == 0, f'{b.eval(count)}')
    for n in range(1, 6):
        b.eval(f"window.__dev.setUpgrade('jump', {n})")
        time.sleep(0.5)
        c = b.eval(count)
        h0 = b.eval("window.__dev.scene.worm.jumpHeight")
        check(f'крылья {n}: два слоя на черве, прыжок выше', c == 2 and (n == 1 or h0 > prev), f'слоёв={c}, высота={h0:.0f}')
        prev = h0
        b.screenshot(shots / f'g04-wings-{n}.png')
    # под землёй крылья сложены, в прыжке раскрыты
    check('крылья 5: под землёй сложены', b.eval('window.__dev.scene.worm.wingOpen') < 0.2, str(b.eval('window.__dev.scene.worm.wingOpen')))
    s0 = state(b)
    view_top = b.eval('window.__dev.scene.cameras.main.worldView.y')
    target = world_to_client(b, s0['x'] + 500, view_top + 60)
    b.mouse(target['x'], target['y'], 'move')
    best, shot_done, t0 = 0.0, False, time.time()
    while time.time() - t0 < 8:
        time.sleep(0.05)
        if state(b)['inAir']:
            w = b.eval('window.__dev.scene.worm.wingOpen')
            best = max(best, w)
            if w > 0.95 and not shot_done:
                b.screenshot(shots / 'g04-wings-5-air.png')
                shot_done = True
        if shot_done and not state(b)['inAir']:
            break
    check('крылья 5: в прыжке раскрываются', best > 0.9, f'раскрытие до {best:.2f}')
    b.eval("window.__dev.setUpgrade('jump', 0)")
    time.sleep(0.3)
    check('крылья: ступень 0 убирает крылья', b.eval(count) == 0)


def t_skins(b, shots):
    boot(b, URL)
    for sk in ('peach', 'salad', 'plum'):
        b.eval(f"window.__dev.setSkin('{sk}')")
        time.sleep(0.4)
        n = b.eval(f"window.__dev.scene.children.list.filter(function(c){{return c.texture && c.texture.key==='worm-{sk}'}}).length")
        check(f'скин {sk}: части червя на сцене', n >= 7, f'частей={n}')
        b.screenshot(shots / f'g05-skin-{sk}.png')
    other = b.eval("window.__dev.scene.children.list.filter(function(c){return c.texture && /^worm-(peach|salad)$/.test(c.texture.key)}).length")
    check('скин: частей прежних скинов не осталось', other == 0, f'{other}')


def t_pause(b, shots):
    boot(b, URL)
    b.key('Escape')
    time.sleep(0.2)
    x0 = state(b)['x']
    time.sleep(1.0)
    s = state(b)
    check('пауза (Esc): состояние «пауза» и червь стоит', s['paused'] and abs(s['x'] - x0) < 2, f"paused={s['paused']}, dx={s['x'] - x0}")
    b.screenshot(shots / 'g06-pause.png')
    b.key('Escape')
    time.sleep(0.2)
    x1 = state(b)['x']
    time.sleep(0.8)
    check('пауза: снимается, червь плывёт', (not state(b)['paused']) and abs(state(b)['x'] - x1) > 20)
    # пауза платформы (реклама, смена вкладки)
    b.eval("window.__platform.sdk.emit('game_api_pause')")
    time.sleep(0.2)
    x2 = state(b)['x']
    time.sleep(0.8)
    check('пауза платформы: червь стоит', abs(state(b)['x'] - x2) < 2, f"dx={state(b)['x'] - x2}")
    b.eval("window.__platform.sdk.emit('game_api_resume')")
    time.sleep(0.2)
    x3 = state(b)['x']
    time.sleep(0.8)
    check('возобновление платформы: червь снова плывёт', abs(state(b)['x'] - x3) > 20)


def t_keyboard(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    y0 = state(b)['y']
    b.key_down('ArrowDown')
    time.sleep(1.2)
    b.key_up('ArrowDown')
    y1 = state(b)['y']
    check('клавиатура: стрелка вниз уводит червя глубже', y1 > y0 + 80, f'{y0:.0f} -> {y1:.0f}')
    # KeyS по коду, независимо от раскладки
    b.key_down('KeyW')
    time.sleep(1.0)
    b.key_up('KeyW')
    y2 = state(b)['y']
    check('клавиатура: код KeyW (раскладка не важна) поднимает', y2 < y1 - 60, f'{y1:.0f} -> {y2:.0f}')


def t_save(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    b.eval("window.__dev.setSkin('salad'); window.__dev.setUpgrade('jump', 3); window.__dev.setTier(4); window.__dev.addGrowth(7)")
    time.sleep(0.3)
    before = state(b)
    boot(b, URL)  # обновление страницы (F5)
    after = state(b)
    # червь без ввода плывёт вперёд и мог что-то съесть, поэтому рост после перезагрузки не меньше прежнего, но может быть больше
    ok = (after['skin'], after['wings'], after['tier']) == ('salad', 3, 4) and after['growth'] >= before['growth'] - 0.5
    check('сохранение: после обновления страницы всё на месте', ok, f'{before["skin"]}/{before["wings"]}/{before["tier"]}/{before["growth"]} -> {after["skin"]}/{after["wings"]}/{after["tier"]}/{after["growth"]}')
    calls = b.eval('window.__platform.sdk.setDataCalls()')
    check('сохранение: запросов в облако мало (лимит 100 за 5 мин)', calls < 20, f'calls={calls}')
    b.eval("localStorage.clear(); 0")


def t_save_burst(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    b.eval("for (var i=0;i<300;i++) window.__dev.addGrowth(0.2)")
    time.sleep(0.5)
    calls = b.eval('window.__platform.sdk.setDataCalls()')
    check('сохранение: 300 действий подряд = единицы запросов в облако', calls <= 3, f'calls={calls}')
    check('сохранение: ошибок и предупреждений о лимите нет', not b.errors(), str(b.errors()))


SIZES = [
    (1280, 1024, 1), (1920, 1080, 1), (2560, 1440, 1), (3840, 2160, 1), (1680, 1050, 1), (2560, 1600, 1),
    (1024, 819, 1), (1536, 864, 1),  # 80% от 1280x1024 и 1920x1080
    (3440, 1440, 1),  # 21:9: поле не шире 2:1
    (700, 1400, 1),   # очень узкое окно: поле не выше 2:1
]


def t_resize(b, shots):
    boot(b, URL)
    for (w, h, dpr) in SIZES:
        b.set_viewport(w, h, dpr, False)
        time.sleep(0.5)
        m = b.eval(
            "(function(){var c=document.querySelector('#game canvas').getBoundingClientRect(); return {cw:c.width,ch:c.height,l:c.left,t:c.top,"
            "iw:innerWidth,ih:innerHeight,sw:document.documentElement.scrollWidth,sh:document.documentElement.scrollHeight}})()"
        )
        aspect = max(m['cw'], m['ch']) / min(m['cw'], m['ch'])
        fill = (abs(m['cw'] - m['iw']) <= 2 or abs(m['ch'] - m['ih']) <= 2)
        ok = aspect <= 2.01 and fill and m['sw'] <= m['iw'] and m['sh'] <= m['ih']
        check(f'окно {w}x{h}: поле {m["cw"]:.0f}x{m["ch"]:.0f}, не шире 2:1, до края области, без прокрутки', ok,
              f'аспект={aspect:.2f}, scroll={m["sw"]}x{m["sh"]}')
        if (w, h) in ((1280, 1024), (3440, 1440), (700, 1400)):
            b.screenshot(shots / f'g07-size-{w}x{h}.png')
    b.set_viewport(1280, 720, 1, False)
    check('окно: ошибок в консоли нет', not b.errors(), str(b.errors()))


def t_mobile(b, shots):
    b.set_viewport(844, 390, 3, True)
    boot(b, URL)
    time.sleep(0.5)
    info = b.eval("({coarse: matchMedia('(pointer: coarse)').matches, cw: document.querySelector('#game canvas').getBoundingClientRect().width, ch: document.querySelector('#game canvas').getBoundingClientRect().height, cwpx: window.__dev.state().canvasW, chpx: window.__dev.state().canvasH, dpr: devicePixelRatio})")
    check('телефон 844x390: поле на весь экран, плотность пикселей ограничена 2', abs(info['cw'] - 844) <= 2 and info['cwpx'] <= 844 * 2 + 2, str(info))
    s0 = state(b)
    # палец: ведём вправо-вверх
    b.touch(422, 300, 'start')
    for i in range(10):
        b.touch(422 + i * 20, 300 - i * 12, 'move')
        time.sleep(0.05)
    time.sleep(0.5)
    b.touch(0, 0, 'end')
    s1 = state(b)
    check('касание: червь реагирует на палец (смещается)', abs(s1['x'] - s0['x']) + abs(s1['y'] - s0['y']) > 60, f"({s0['x']},{s0['y']}) -> ({s1['x']},{s1['y']})")
    b.screenshot(shots / 'g08-mobile.png')
    b.set_viewport(1280, 720, 1, False)


def t_guards(b, shots):
    """Нет выделения, контекстного меню и перехвата системных сочетаний (пп. 1.6.1.8, 1.6.2.6, 1.6.2.7, 1.10.2)."""
    boot(b, URL)
    b.eval("window.__ctx = []; window.addEventListener('contextmenu', function(e){ window.__ctx.push(e.defaultPrevented); }); 0")
    cv = b.eval("(function(){var r=document.querySelector('canvas').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
    b.mouse(cv['x'], cv['y'], 'move')
    b.mouse(cv['x'], cv['y'], 'down', button='right')
    b.mouse(cv['x'], cv['y'], 'up', button='right')
    time.sleep(0.2)
    ctx = b.eval('window.__ctx')
    check('правый клик: контекстное меню отменено', len(ctx) >= 1 and all(ctx), str(ctx))
    r = b.eval("""(function(){
      function fire(type, target, init){
        var e = (type === 'keydown') ? new KeyboardEvent(type, Object.assign({bubbles:true, cancelable:true}, init))
              : new Event(type, {bubbles:true, cancelable:true});
        target.dispatchEvent(e); return e.defaultPrevented;
      }
      var cv = document.querySelector('canvas'), cs = getComputedStyle(document.body);
      return {
        selectstart: fire('selectstart', document.body), dragstart: fire('dragstart', cv),
        f5: fire('keydown', document, {code:'F5', key:'F5'}), f11: fire('keydown', document, {code:'F11', key:'F11'}),
        ctrlR: fire('keydown', document, {code:'KeyR', key:'r', ctrlKey:true}),
        ctrlPlus: fire('keydown', document, {code:'Equal', key:'+', ctrlKey:true}),
        altLeft: fire('keydown', document, {code:'ArrowLeft', key:'ArrowLeft', altKey:true}),
        cmdW: fire('keydown', document, {code:'KeyW', key:'w', metaKey:true}),
        userSelect: cs.userSelect || cs.webkitUserSelect, overflow: getComputedStyle(document.documentElement).overflow,
        touchAction: cs.touchAction, selected: String(getSelection())
      };
    })()""")
    check('выделение текста и перетаскивание отменены, user-select: none', r['selectstart'] and r['dragstart'] and r['userSelect'] == 'none', str(r))
    check('системные сочетания не перехватываются (F5, F11, Ctrl+R, Ctrl++, Alt+стрелка, Cmd+W)',
          not any(r[k] for k in ('f5', 'f11', 'ctrlR', 'ctrlPlus', 'altLeft', 'cmdW')), str(r))
    check('страница не прокручивается: overflow hidden, touch-action none', r['overflow'] == 'hidden' and r['touchAction'] == 'none', f"{r['overflow']}, {r['touchAction']}")
    # колесо мыши и Ctrl+колесо (масштаб страницы браузера, им проверяют 80-125%) не ломают игру и не блокируются
    w = b.eval("(function(){var e=new WheelEvent('wheel',{deltaY:300,ctrlKey:true,bubbles:true,cancelable:true});document.querySelector('canvas').dispatchEvent(e);return e.defaultPrevented})()")
    check('Ctrl+колесо (масштаб браузера) не блокируется', w is False, str(w))
    check('защита: ошибок в консоли нет', not b.errors(), str(b.errors()))


HUD_JS = """(function(){
  var s = window.__dev.scene, ui = s.scene.get('UI'), W = ui.scale.width, H = ui.scale.height, u = ui.u, bw = ui.barWidth();
  function box(o){ return {l: o.x - o.width / 2, t: o.y - o.height / 2, r: o.x + o.width / 2, b: o.y + o.height / 2}; }
  function tb(o){ var g = o.getBounds(); return {l: g.left, t: g.top, r: g.right, b: g.bottom}; }
  return { W: W, H: H, u: u, pause: box(ui.pauseBtn.box), sound: box(ui.soundBtn.box), hint: tb(ui.hint),
           bar: {l: 11 * u, t: 11 * u, r: 68 * u + bw + 3 * u, b: 65 * u},
           title: tb(ui.overlayTitle), resume: box(ui.overlayBtn) };
})()"""

HUD_SIZES = [(1280, 720, 1, False), (1920, 1080, 1, False), (3840, 2160, 1, False), (700, 1400, 1, False),
             (844, 390, 3, True), (568, 320, 2, True), (390, 844, 3, True), (320, 568, 2, True)]


def overlap(a, c):
    return a['l'] < c['r'] and c['l'] < a['r'] and a['t'] < c['b'] and c['t'] < a['b']


def inside(a, W, H, tol=1.5):
    return a['l'] >= -tol and a['t'] >= -tol and a['r'] <= W + tol and a['b'] <= H + tol


def t_hud(b, shots):
    """Интерфейс не обрезается и не накладывается друг на друга при любом размере и повороте (пп. 1.10.1, 1.10.3)."""
    boot(b, URL)
    for (w, h, dpr, mobile) in HUD_SIZES:
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.7)
        r = b.eval(HUD_JS)
        W, H = r['W'], r['H']
        parts = {k: r[k] for k in ('pause', 'sound', 'hint', 'bar')}
        cut = [k for k, v in parts.items() if not inside(v, W, H)]
        pairs = [('pause', 'sound'), ('bar', 'sound'), ('bar', 'pause'), ('hint', 'bar'), ('hint', 'sound'), ('hint', 'pause')]
        over = [f'{a}/{c}' for a, c in pairs if overlap(r[a], r[c])]
        check(f'интерфейс {w}x{h}: ничего не обрезано и не накладывается', not cut and not over, f'обрезано: {cut}, накладывается: {over}, поле {W}x{H}')
        b.key('Escape')
        time.sleep(0.3)
        r = b.eval(HUD_JS)
        cut = [k for k in ('title', 'resume') if not inside(r[k], r['W'], r['H'])]
        check(f'окно паузы {w}x{h}: заголовок и кнопка целиком на экране и не накладываются',
              not cut and not overlap(r['title'], r['resume']), f'обрезано: {cut}')
        b.key('Escape')
        time.sleep(0.2)
    b.set_viewport(1280, 720, 1, False)


def t_canvas(b, shots):
    """Нет WebGL (пп. 1.6.1.7, 1.20): игра работает на запасном рендере Canvas и ничего не предупреждает."""
    with Browser(1280, 720, args=('--disable-3d-apis',)) as bb:
        boot(bb, URL)
        gl = bb.eval("(function(){var c=document.createElement('canvas');return !!(c.getContext('webgl')||c.getContext('experimental-webgl'))})()")
        check('Canvas: в этом браузере WebGL выключен (условие проверки)', gl is False, str(gl))
        rt = bb.eval('window.__dev.scene.game.renderer.type')  # Phaser.CANVAS = 1, Phaser.WEBGL = 2
        check('Canvas: игра выбрала запасной рендер Canvas', rt == 1, f'renderer.type={rt}')
        bb.eval('window.__dev.autopilot(true)')
        t0 = time.time()
        while time.time() - t0 < 30 and state(bb)['eaten'] < 3:
            time.sleep(0.5)
        s = state(bb)
        check('Canvas: червь плывёт и ест', s['eaten'] >= 3, f"съедено {s['eaten']}, {s['fps']} кадров/с")
        check('Canvas: частота кадров не ниже 20', s['fps'] >= 20, f"{s['fps']} кадров/с")
        bb.screenshot(shots / 'g10-canvas.png')
        bad = [c for c in bb.console if c[0] in ('error', 'exception', 'warning', 'warn') and 'favicon.ico' not in c[1]]
        check('Canvas: в консоли нет ошибок и предупреждений', not bad, str(bad[:4]))


def t_legacy(b, shots):
    """Старые браузеры (п. 1.20): нет ResizeObserver, visualViewport и Web Audio. Игра запускается и подстраивается под окно."""
    b.add_init_script("delete window.ResizeObserver; delete window.AudioContext; delete window.webkitAudioContext;"
                      "try { Object.defineProperty(window, 'visualViewport', {value: undefined, configurable: true}); } catch (e) {}")
    boot(b, URL)
    check('старый браузер: ResizeObserver, visualViewport и Web Audio действительно отсутствуют',
          b.eval("typeof ResizeObserver === 'undefined' && !window.visualViewport && typeof AudioContext === 'undefined'"))
    b.click(640, 360)  # жест игрока: попытка включить звук не должна ломать игру
    b.set_viewport(1000, 640, 1, False)
    time.sleep(0.8)
    s = state(b)
    check('старый браузер: холст следует за окном 1000x640', (s['canvasW'], s['canvasH']) == (1000, 640), f"{s['canvasW']}x{s['canvasH']}")
    b.eval('window.__dev.autopilot(true)')
    t0 = time.time()
    while time.time() - t0 < 30 and state(b)['eaten'] < 2:
        time.sleep(0.5)
    check('старый браузер: игра идёт без звука', state(b)['eaten'] >= 2, f"съедено {state(b)['eaten']}")
    check('старый браузер: ошибок в консоли нет', not b.errors(), str(b.errors()))
    b.set_viewport(1280, 720, 1, False)


def t_nostorage(b, shots):
    """Хранилище недоступно (приватный режим, запрет cookies): игра всё равно запускается, ошибок нет."""
    b.add_init_script("Object.defineProperty(window, 'localStorage', {get: function(){ throw new Error('denied'); }, configurable: true});"
                      "Object.defineProperty(window, 'sessionStorage', {get: function(){ throw new Error('denied'); }, configurable: true});")
    boot(b, URL)
    b.eval('window.__dev.addGrowth(5)')
    time.sleep(0.5)
    s = state(b)
    check('без хранилища: игра запущена и растёт', s['prey'] >= 25 and s['growth'] >= 5, f"prey={s['prey']}, growth={s['growth']}")
    bad = [c for c in b.console if c[0] in ('error', 'exception') and 'favicon.ico' not in c[1]]
    check('без хранилища: нет ошибок в консоли', not bad, str(bad[:3]))


FAKE_SDK = """
(function(){
  var log = window.__sdkLog = [];
  var handlers = {};
  var store = {};
  var sdk = {
    environment: { i18n: { lang: '__LANG__' } },
    features: {
      LoadingAPI: { ready: function(){ log.push('ready'); } },
      GameplayAPI: { start: function(){ log.push('start'); }, stop: function(){ log.push('stop'); } }
    },
    on: function(e, f){ (handlers[e] = handlers[e] || []).push(f); log.push('on:' + e); },
    off: function(){},
    getPlayer: function(){
      log.push('getPlayer');
      return Promise.resolve({
        isAuthorized: function(){ return false; },
        getData: function(){ log.push('getData'); return Promise.resolve(store); },
        setData: function(d){ log.push('setData'); for (var k in d) store[k] = d[k]; return Promise.resolve(); }
      });
    },
    adv: {
      showFullscreenAdv: function(o){ log.push('adv'); if (o && o.callbacks && o.callbacks.onClose) o.callbacks.onClose(true); },
      showRewardedVideo: function(o){ log.push('rewarded'); if (o && o.callbacks) { if (o.callbacks.onRewarded) o.callbacks.onRewarded(); if (o.callbacks.onClose) o.callbacks.onClose(true); } }
    }
  };
  window.__sdkEmit = function(e){ (handlers[e] || []).forEach(function(f){ f(); }); };
  window.YaGames = { init: function(){ log.push('init'); return Promise.resolve(sdk); } };
})();
"""


def audio_state(b):
    return b.eval('window.__dev.state().audio')


def t_sdk(b, shots):
    """Интеграция с SDK Яндекса на подставной платформе: порядок вызовов, пауза, язык, лимиты."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'en'))
    boot(b, URL)
    time.sleep(1.0)
    log = b.eval('window.__sdkLog')
    check('SDK: init вызван первым', log[:1] == ['init'], str(log[:4]))
    check('SDK: LoadingAPI.ready() вызван ровно один раз', log.count('ready') == 1, f"{log.count('ready')}")
    check('SDK: ready вызван после init и getPlayer', log.index('ready') > log.index('getPlayer') > log.index('init'), str(log))
    check('SDK: подписка на game_api_pause и game_api_resume', 'on:game_api_pause' in log and 'on:game_api_resume' in log)
    check('SDK: GameplayAPI.start() вызван, когда игра началась', 'start' in log, str(log))
    hint = b.eval("window.__dev.scene.scene.get('UI').hint.text")
    check('язык en: интерфейс на английском', b.eval('document.documentElement.lang') == 'en' and ('Move the mouse' in hint or 'Drag your finger' in hint), hint)
    # пауза платформы останавливает и звук, и игру
    b.click(640, 360)  # жест игрока открывает звук
    time.sleep(0.3)
    check('звук: после жеста игрока контекст запущен', audio_state(b) == 'running', audio_state(b))
    b.eval("window.__sdkEmit('game_api_pause')")
    time.sleep(0.5)
    x1 = state(b)['x']
    time.sleep(0.5)
    check('пауза платформы: игра стоит, звук остановлен', abs(state(b)['x'] - x1) < 2 and audio_state(b) == 'suspended',
          f"dx={state(b)['x'] - x1}, audio={audio_state(b)}")
    b.eval("window.__sdkEmit('game_api_resume')")
    time.sleep(0.6)
    check('возобновление: игра идёт, звук включён', abs(state(b)['x'] - x1) > 10 and audio_state(b) == 'running')
    time.sleep(3)
    log = b.eval('window.__sdkLog')
    check('реклама: посреди захода не показывается', 'adv' not in log and 'rewarded' not in log)
    check('SDK: getPlayer вызван один раз (лимит 20 за 5 минут)', log.count('getPlayer') == 1, f"{log.count('getPlayer')}")
    check('SDK: setData редко (лимит 100 за 5 минут)', log.count('setData') <= 2, f"{log.count('setData')}")


def t_lang(b, shots):
    """Автоопределение языка (п. 2.14): ru и родственные дают русский, остальные английский."""
    for code, want in (('ru', 'ru'), ('be', 'ru'), ('en', 'en'), ('tr', 'en'), ('de', 'en')):
        with Browser(1280, 720) as bb:
            bb.add_init_script(FAKE_SDK.replace('__LANG__', code))
            boot(bb, URL)
            got = bb.eval('document.documentElement.lang')
            check(f'язык: SDK отдаёт «{code}» -> интерфейс «{want}»', got == want, got)


def t_audio(b, shots):
    boot(b, URL)
    check('звук: до жеста игрока контекст не создан', audio_state(b) == 'none', audio_state(b))
    check('звук: нет элементов <audio> и <video> (нет системного плеера)', b.eval("document.querySelectorAll('audio,video').length") == 0)
    b.click(640, 360)
    time.sleep(0.3)
    check('звук: после клика контекст запущен', audio_state(b) == 'running', audio_state(b))
    b.key('KeyM')
    time.sleep(0.2)
    check('звук: клавиша M выключает звук', audio_state(b) == 'suspended', audio_state(b))
    b.key('KeyM')
    time.sleep(0.2)
    check('звук: повторное M включает', audio_state(b) == 'running', audio_state(b))
    b.eval("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    time.sleep(0.3)
    check('звук: при уходе со вкладки замолкает', audio_state(b) == 'suspended', audio_state(b))
    b.eval("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    time.sleep(0.3)
    check('звук: при возврате на вкладку снова звучит', audio_state(b) == 'running', audio_state(b))


CAMERA_BG = (63, 156, 255)  # цвет, которым камера заливает кадр там, где фон не нарисован


def edge_gaps(path):
    """Доля проверенных пикселей у краёв кадра, залитых цветом фона камеры. None, если нет библиотеки PIL."""
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(path).convert('RGB')
    w, h = im.size
    bad = total = 0
    for x in (0, 1, 2, 3, w - 4, w - 3, w - 2, w - 1):
        for y in range(0, h, 10):
            total += 1
            bad += im.getpixel((x, y)) == CAMERA_BG
    return bad / total


def t_tiers(b, shots):
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    prev = 0
    for tier in (1, 5, 10, 15, 21):
        b.eval(f"window.__dev.setTier({tier})")
        time.sleep(2.2)
        r = b.eval("(function(){var s=window.__dev.scene, c=s.cameras.main; return {S:s.worm.scale, head:s.worm.headRadius*c.zoom/(window.devicePixelRatio||1), segs:Math.floor(s.worm.segs), fps:Math.round(s.game.loop.actualFps)}})()")
        check(f'тир {tier}: масштаб {r["S"]:.2f}, сегментов {r["segs"]}, голова на экране {r["head"]:.0f} px, {r["fps"]} fps',
              r['S'] > prev and 30 < r['head'] < 160 and r['fps'] >= 25, str(r))
        prev = r['S']
        shot = shots / f'g09-tier-{tier}.png'
        b.screenshot(shot)
        gap = edge_gaps(shot)
        if gap is not None:
            check(f'тир {tier}: фон доходит до краёв кадра (нет полос цвета камеры)', gap == 0, f'доля пустых пикселей у краёв: {gap:.3f}')
    b.eval("localStorage.clear(); 0")


TESTS = {
    'boot': t_boot, 'growth': t_autopilot_growth, 'jump': t_jump, 'wings': t_wings, 'skins': t_skins,
    'sdk': t_sdk, 'lang': t_lang, 'audio': t_audio, 'tiers': t_tiers,
    'pause': t_pause, 'keyboard': t_keyboard, 'save': t_save, 'saveburst': t_save_burst, 'resize': t_resize, 'mobile': t_mobile,
    'guards': t_guards, 'hud': t_hud, 'canvas': t_canvas, 'legacy': t_legacy, 'nostorage': t_nostorage,
}


def main():
    global URL
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=URL)
    ap.add_argument('--only', default='')
    ap.add_argument('--shots', default=str(Path(__file__).resolve().parent.parent / 'build' / 'shots'))
    a = ap.parse_args()
    URL = a.url
    shots = Path(a.shots)
    shots.mkdir(parents=True, exist_ok=True)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    names = [n for n in a.only.split(',') if n] or list(TESTS)
    for name in names:
        print(f'[{name}]')
        try:
            with Browser(1280, 720) as b:
                TESTS[name](b, shots)
        except Exception as e:  # noqa: BLE001
            check(f'{name}: выполнение без исключений', False, f'{type(e).__name__}: {e}')
            traceback.print_exc()
    bad = [r for r in RESULTS if not r[1]]
    print(f'\nИтог: {len(RESULTS) - len(bad)} из {len(RESULTS)} проверок пройдено')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
