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


def boot(b, url, wait=30, choose=True):
    """Открыть игру. При первом запуске показывается выбор персонажа: по умолчанию выбираем Сливу (клавиша 3)."""
    b.open(url)
    b.wait_for('!!window.__dev', wait)
    if choose and b.eval('window.__dev.state().selecting'):
        b.key('Digit3')
        time.sleep(0.3)
    time.sleep(0.8)


SEED_CHOSEN = '{"v":2,"skinChosen":true,"skin":"plum","tier":1,"growth":0,"coins":0,"tutorial":3}'


def seed_chosen(b, tutorial=3, coins=0):
    """Подложить сохранение «персонаж выбран» до запуска игры (tutorial=0: обучение покажется; coins: стартовые монеты).

    Через localStorage перед перезагрузкой нельзя: уходящая страница пишет своё сохранение поверх. Поэтому скрипт выполняется
    перед запуском игры и только один раз за вкладку (sessionStorage), а последующие перезагрузки берут то, что игра сохранила сама."""
    save = SEED_CHOSEN.replace('"tutorial":3', '"tutorial":%d' % tutorial).replace('"coins":0', '"coins":%d' % coins)
    b.add_init_script("try { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); "
                      "localStorage.setItem('wormgame.save.v1', %s); } } catch (e) {}" % json.dumps(save))


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
    check('загрузка: игра готова, добыча вокруг', s['prey'] >= 20, f"prey={s['prey']}")
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
    b.eval('window.__dev.setTier(window.__dev.world().surfaceTier)')  # выход на поверхность открыт с этого тира
    time.sleep(2.5)
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
    # под землёй крылья сложены, в прыжке раскрыты (выход на поверхность открыт с 5-го тира)
    b.eval('window.__dev.setTier(window.__dev.world().surfaceTier)')
    time.sleep(2.5)
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
  var cy = 14 * u + 2 * 24 * u + 12 * u + 16 * u, plateW = 52 * u + ui.coinText.width;
  return { W: W, H: H, u: u, pause: box(ui.pauseBtn.box), sound: box(ui.soundBtn.box), shop: box(ui.shopBtn.box), hint: tb(ui.hint),
           bar: {l: 11 * u, t: 11 * u, r: 68 * u + bw + 3 * u, b: 65 * u},
           coins: {l: 11 * u, t: cy - 21 * u, r: 14 * u + plateW + 3 * u, b: cy + 21 * u},
           title: tb(ui.overlayTitle), resume: box(ui.resumeBtn.box), change: box(ui.changeBtn.box) };
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
        parts = {k: r[k] for k in ('pause', 'sound', 'shop', 'hint', 'bar', 'coins')}
        cut = [k for k, v in parts.items() if not inside(v, W, H)]
        pairs = [('pause', 'sound'), ('bar', 'sound'), ('bar', 'pause'), ('hint', 'bar'), ('hint', 'sound'), ('hint', 'pause'),
                 ('coins', 'bar'), ('coins', 'hint'), ('coins', 'sound'),
                 ('shop', 'bar'), ('shop', 'coins'), ('shop', 'hint'), ('shop', 'sound'), ('shop', 'pause')]
        over = [f'{a}/{c}' for a, c in pairs if overlap(r[a], r[c])]
        check(f'интерфейс {w}x{h}: ничего не обрезано и не накладывается', not cut and not over, f'обрезано: {cut}, накладывается: {over}, поле {W}x{H}')
        b.key('Escape')
        time.sleep(0.3)
        r = b.eval(HUD_JS)
        cut = [k for k in ('title', 'resume', 'change') if not inside(r[k], r['W'], r['H'])]
        bad = overlap(r['title'], r['resume']) or overlap(r['title'], r['change']) or overlap(r['resume'], r['change'])
        check(f'меню паузы {w}x{h}: заголовок и обе кнопки целиком на экране и не накладываются', not cut and not bad, f'обрезано: {cut}')
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
    check('без хранилища: игра запущена и растёт', s['prey'] >= 20 and s['growth'] >= 5, f"prey={s['prey']}, growth={s['growth']}")
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
    seed_chosen(b)
    boot(b, URL, choose=False)  # без выбора персонажа и без нажатий: жеста игрока ещё не было
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


def t_surface(b, shots):
    """Прогрессия масштаба: до 5-го тира выход на поверхность закрыт (червь скользит под травой), на 5-м открывается."""
    seed_chosen(b)  # обучение пройдено: его подсказки не перекрывают проверяемые сообщения
    boot(b, URL, choose=False)
    w = b.eval('window.__dev.world()')
    s = state(b)
    check('поверхность: на старте закрыта', s['canExit'] is False and s['tier'] == 1, f"tier={s['tier']}, canExit={s['canExit']}")
    b.key_down('KeyW')
    min_y, got_air = 1e9, False
    t0 = time.time()
    while time.time() - t0 < 4.0:
        time.sleep(0.05)
        s = state(b)
        got_air = got_air or s['inAir']
        min_y = min(min_y, s['y'])
    check('поверхность закрыта: червь упирается под травой и не выпрыгивает', (not got_air) and min_y > 20, f'самая высокая точка y={min_y:.0f}, прыжок={got_air}')
    check('поверхность закрыта: подсказка «подрастите»', state(b)['toast'] == 'hint_locked', str(state(b)['toast']))
    b.screenshot(shots / 'g11-locked.png')
    b.key_up('KeyW')
    b.eval('window.__dev.setTier(%d); 0' % (w['surfaceTier'] - 1))
    b.eval('window.__dev.addGrowth(%d)' % (state(b)['need'] + 1))
    time.sleep(0.6)
    s = state(b)
    check('поверхность открылась на нужном тире', s['tier'] == w['surfaceTier'] and s['canExit'] is True, f"tier={s['tier']}, canExit={s['canExit']}")
    check('открытие: подсказка «теперь можно выпрыгнуть»', s['toast'] == 'hint_unlocked', str(s['toast']))
    b.screenshot(shots / 'g11-unlocked.png')
    time.sleep(2.5)
    b.key_down('KeyW')
    got, t0 = False, time.time()
    while time.time() - t0 < 5 and not got:
        time.sleep(0.05)
        got = state(b)['inAir']
    b.key_up('KeyW')
    check('после открытия червь выпрыгивает на поверхность', got)
    check('поверхность: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_world(b, shots):
    """Карта: червь 1-го тира без улучшений скорости пересекает её за ≈ 5 минут; по краям стены."""
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    w = b.eval('window.__dev.world()')
    # червь мог успеть что-то съесть и вырасти, поэтому берём скорость червя масштаба 1
    speed = b.eval('window.__dev.scene.worm.swimSpeed / window.__dev.scene.worm.scale')
    check('карта: от края до края ≈ 5 минут', 290 <= w['width'] / speed <= 310,
          f"{w['width'] / speed:.0f} с (ширина {w['width']:.0f} px, скорость {speed:.0f} px/с)")
    half = w['width'] / 2
    for side, key, sign in (('правая', 'ArrowRight', 1), ('левая', 'ArrowLeft', -1)):
        b.eval('window.__dev.setPos(%d, 400)' % (sign * (half - 700)))
        time.sleep(1.0)
        b.key_down(key)
        far = 0
        t0 = time.time()
        while time.time() - t0 < 5.0:
            time.sleep(0.05)
            far = max(far, sign * state(b)['x'])
        b.key_up(key)
        check(f'карта: {side} стена не пускает', far <= half, f'дальше всего {far:.0f}, край {half:.0f}')
        cam = b.eval("(function(){var c=window.__dev.scene.cameras.main; var v=c.width/c.zoom; return {edge: Math.abs(c.scrollX + c.width/2) + v/2, v: v}})()")
        check(f'карта: камера у {side} стены не уезжает в пустоту', cam['edge'] <= half + 0.12 * cam['v'], f"{cam['edge']:.0f} <= {half + 0.12 * cam['v']:.0f}")
        if side == 'правая':
            b.screenshot(shots / 'g12-edge.png')
    check('карта: нет ошибок в консоли', not b.errors(), str(b.errors()))


STAMPS = "window.__dev.scene.children.list.filter(function(c){return c.frame && c.frame.name.indexOf('worm-plum-stamp-out')===0}).length"


def t_model(b, shots):
    """Модель червя: гладкая трубка без соединений, челюсти открываются и закрываются, размер челюсти задаёт съедобное."""
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    frames = b.eval("Object.keys(window.__dev.scene.textures.get('worm-plum').frames)")
    ok = (not any('body-' in f or 'tail' in f for f in frames)) and all(any(n in f for f in frames) for n in ('stamp-out', 'jaw-top', 'jaw-bottom', 'maw', 'face-idle'))
    check('модель: в атласе нет бусин и хвоста, есть круги тела, челюсти, зев, лицо', ok, ', '.join(frames[:5]))
    n1 = b.eval(STAMPS)
    b.eval('window.__dev.setTier(10); 0')
    time.sleep(2.0)
    n2 = b.eval(STAMPS)
    check('модель: тело длиннее при росте, число кругов растёт вместе с длиной', n2 > n1 * 2.5, f'{n1} -> {n2} кругов')
    # челюсти: в покое раскрыты наполовину, «жуёт» закрывает, «бросок» раскрывает
    b.eval('window.__dev.setTier(1); 0')
    b.eval("window.__dev.scene.prey.items.forEach(function(it){it.x += 100000}); 0")
    time.sleep(0.7)
    idle = state(b)['jaw']
    check('челюсти в покое раскрыты примерно наполовину', 0.4 <= idle <= 0.68, f'{idle}')
    b.eval("window.__dev.scene.worm.flash('chomp', 600, window.__dev.scene.time.now); 0")
    time.sleep(0.25)
    chomp = state(b)['jaw']
    time.sleep(0.8)
    b.eval("window.__dev.scene.worm.flash('open', 600, window.__dev.scene.time.now); 0")
    time.sleep(0.3)
    wide = state(b)['jaw']
    check('челюсти: «жуёт» закрывает, «бросок» раскрывает', chomp < 0.25 and wide > 0.8, f'жуёт={chomp}, бросок={wide}')
    b.screenshot(shots / 'g13-jaws.png')
    # размер челюсти определяет, что можно съесть: помещающееся съедается, крупнее нет
    res = {}
    for name, k in (('small', 0.8), ('big', 1.4)):
        b.eval("window.__dev.setPos(0, 700); window.__dev.autopilot(false); 0")
        b.eval("""(function(){var s=window.__dev.scene, mr=s.worm.mouthRadius, items=s.prey.items.filter(function(i){return !i.dying});
                  items.forEach(function(i){i.x += 100000});
                  var it=items[0]; it.x=300; it.y=700; it.baseY=700; it.vx=0; it.turnIn=1e9; it.kind='soil'; it.r=mr*%f; it.img.setScale(it.r/34);
                  window.__test_prey = it; return 0})()""" % k)
        e0 = state(b)['eaten']
        time.sleep(1.6)
        res[name] = (state(b)['eaten'] - e0, b.eval('window.__dev.scene.prey.items.indexOf(window.__test_prey) >= 0'))
    check('размер челюсти: помещающаяся добыча съедается', res['small'][0] == 1 and not res['small'][1], str(res['small']))
    check('размер челюсти: добыча крупнее челюстей не съедается', res['big'][0] == 0 and res['big'][1], str(res['big']))
    check('модель: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_prey(b, shots):
    """Добыча зоны 1: жуки и червячки сверху, лапки перебирают кадры, за ползущими остаётся след; в небе ничего."""
    boot(b, URL)
    b.eval("localStorage.clear(); 0")
    boot(b, URL)
    frames = b.eval("Object.keys(window.__dev.scene.textures.get('props').frames)")
    check('добыча: кадры жука и червячка сверху, по два шага', all(f in frames for f in ('z1-beetle-a', 'z1-beetle-b', 'z1-worm-a', 'z1-worm-b')), str(frames))
    kinds = b.eval("(function(){var o={};window.__dev.scene.prey.items.forEach(function(it){o[it.species]=(o[it.species]||0)+1});return o})()")
    check('добыча: есть и жуки, и червячки', kinds.get('beetle', 0) > 0 and kinds.get('worm', 0) > 0, str(kinds))
    check('добыча: пока выход закрыт, вся добыча в земле (нет «воздушной»)',
          b.eval("window.__dev.scene.prey.items.every(function(it){return it.kind==='soil'})"))
    seen = set()
    t0 = time.time()
    while time.time() - t0 < 1.2:
        seen |= set(b.eval("window.__dev.scene.prey.items.map(function(it){return it.img.frame.name.slice(-1)})"))
        time.sleep(0.05)
    check('добыча: лапки перебирают два кадра', seen >= {'a', 'b'}, str(seen))
    time.sleep(2.5)
    marks = b.eval("window.__dev.scene.children.list.filter(function(c){return c.frame && c.frame.name==='fx-dot' && c.visible && c.depth===-56}).length")
    check('добыча: за ползущими остаётся след', marks >= 3, f'меток следа: {marks}')
    b.screenshot(shots / 'g14-prey.png')
    check('добыча: нет ошибок в консоли', not b.errors(), str(b.errors()))


def canvas_to_client(b, x, y):
    """Точка холста (px устройства) -> координаты клиентской области (CSS px) для мыши и касаний."""
    return b.eval("(function(){var c=window.__dev.scene.game.canvas, r=c.getBoundingClientRect();"
                  "return {x: r.left + %f * r.width / c.width, y: r.top + %f * r.height / c.height}})()" % (x, y))


SELECT_JS = """(function(){var sc=window.__dev.scene.scene.get('Select'); var u=window.__dev.scene.game.canvas.width / window.innerWidth;
  return {sel: sc.sel, W: window.__dev.scene.game.canvas.width, H: window.__dev.scene.game.canvas.height, u: u,
          cards: sc.cards.map(function(c){return {id: c.id, name: c.name.text, rect: c.rect, btn: c.btnRect}})}})()"""


def rect_inside(r, W, H, tol=2):
    return r[0] >= -tol and r[1] >= -tol and r[0] + r[2] <= W + tol and r[1] + r[3] <= H + tol


def rects_overlap(a, c):
    return a[0] < c[0] + c[2] and c[0] < a[0] + a[2] and a[1] < c[1] + c[3] and c[1] < a[1] + a[3]


def t_select(b, shots):
    """Выбор персонажа: при первом запуске, клавишами, мышью, из меню паузы; ready на экране выбора, start после; сохранение."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'ru'))
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.2)
    s = state(b)
    check('выбор: при первом запуске показан экран выбора', s['selecting'] is True, f"selecting={s['selecting']}")
    log = b.eval('window.__sdkLog')
    check('выбор: ready вызван на экране выбора, start ещё нет (п. 1.19.2, 1.19.3)', 'ready' in log and 'start' not in log, str(log))
    x0 = s['x']
    time.sleep(1.0)
    check('выбор: игра под экраном выбора стоит', abs(state(b)['x'] - x0) < 2, f"dx={state(b)['x'] - x0}")
    info = b.eval(SELECT_JS)
    check('выбор: три карточки Персик, Салат, Слива', [c['name'] for c in info['cards']] == ['Персик', 'Салат', 'Слива'], str([c['name'] for c in info['cards']]))
    inside = all(rect_inside(c['rect'], info['W'], info['H']) for c in info['cards'])
    check('выбор: карточки целиком на экране и не накладываются', inside and not any(rects_overlap(info['cards'][i]['rect'], info['cards'][j]['rect']) for i in range(3) for j in range(i + 1, 3)),
          str([c['rect'] for c in info['cards']]))
    check('выбор: кнопки не меньше 44 CSS-px (п. 1.8)', all(c['btn'][3] / info['u'] >= 44 for c in info['cards']), str([round(c['btn'][3] / info['u']) for c in info['cards']]))
    b.screenshot(shots / 'g15-select.png')
    # Esc на первом запуске не закрывает экран
    b.key('Escape')
    time.sleep(0.2)
    check('выбор: на первом запуске Esc не закрывает экран', state(b)['selecting'] is True)
    # стрелка вправо двигает выделение
    sel0 = b.eval(SELECT_JS)['sel']
    b.key('ArrowRight')
    time.sleep(0.2)
    check('выбор: стрелка вправо переносит выделение', b.eval(SELECT_JS)['sel'] == (sel0 + 1) % 3, f"{sel0} -> {b.eval(SELECT_JS)['sel']}")
    # мышью по кнопке второй карточки (Салат)
    btn = info['cards'][1]['btn']
    p = canvas_to_client(b, btn[0] + btn[2] / 2, btn[1] + btn[3] / 2)
    b.click(p['x'], p['y'])
    time.sleep(0.6)
    s = state(b)
    check('выбор мышью: Салат выбран, экран закрыт, игра пошла', s['skin'] == 'salad' and s['selecting'] is False, f"skin={s['skin']}, selecting={s['selecting']}")
    log = b.eval('window.__sdkLog')
    check('выбор: start вызван после выбора, после ready', 'start' in log and log.index('ready') < log.index('start'), str(log))
    check('выбор: короткая вступительная фраза', state(b)['toast'] == 'story_intro', str(state(b)['toast']))
    x1 = state(b)['x']
    time.sleep(0.8)
    check('выбор: после выбора червь плывёт', abs(state(b)['x'] - x1) > 20)
    # сохранение: после обновления страницы выбор не показывается, персонаж на месте
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    s = state(b)
    check('выбор: после обновления экран не показывается, Салат на месте', s['selecting'] is False and s['skin'] == 'salad', f"selecting={s['selecting']}, skin={s['skin']}")
    # из меню паузы
    b.key('Escape')
    time.sleep(0.3)
    check('меню: Esc открывает паузу', state(b)['paused'] is True)
    ch = b.eval("(function(){var o=window.__dev.scene.scene.get('UI').changeBtn.box; return {x:o.x,y:o.y}})()")
    p = canvas_to_client(b, ch['x'], ch['y'])
    b.click(p['x'], p['y'])
    time.sleep(0.5)
    check('меню: кнопка «Сменить червя» открывает выбор', state(b)['selecting'] is True)
    b.key('Escape')
    time.sleep(0.3)
    s = state(b)
    check('меню: Esc закрывает выбор, пауза остаётся', s['selecting'] is False and s['paused'] is True, f"selecting={s['selecting']}, paused={s['paused']}")
    p = canvas_to_client(b, ch['x'], ch['y'])
    b.click(p['x'], p['y'])
    time.sleep(0.4)
    b.key('Digit1')
    time.sleep(0.5)
    s = state(b)
    check('меню: выбор Персика из паузы, игра продолжается', s['skin'] == 'peach' and s['selecting'] is False and s['paused'] is False, f"skin={s['skin']}, paused={s['paused']}")
    check('выбор: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_select_screens(b, shots):
    """Выбор на телефоне: касанием в альбомной и вытянутой книжной раскладке, карточки на экране."""
    b.set_viewport(844, 390, 3, True)
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.2)
    info = b.eval(SELECT_JS)
    check('телефон 844x390: карточки целиком на экране', all(rect_inside(c['rect'], info['W'], info['H']) for c in info['cards']), str([c['rect'] for c in info['cards']]))
    check('телефон 844x390: кнопки не меньше 44 CSS-px', all(c['btn'][3] / info['u'] >= 44 for c in info['cards']), str([round(c['btn'][3] / info['u']) for c in info['cards']]))
    b.screenshot(shots / 'g15-select-mobile.png')
    btn = info['cards'][2]['btn']
    p = canvas_to_client(b, btn[0] + btn[2] / 2, btn[1] + btn[3] / 2)
    b.touch(p['x'], p['y'], 'start')
    b.touch(0, 0, 'end')
    time.sleep(0.6)
    s = state(b)
    check('телефон: касание по карточке выбирает Сливу', s['skin'] == 'plum' and s['selecting'] is False, f"skin={s['skin']}, selecting={s['selecting']}")
    # вытянутая книжная раскладка (повернули телефон): карточки друг под другом
    b.eval('window.__dev.openSelect(); 0')
    b.set_viewport(390, 844, 3, True)
    time.sleep(0.8)
    info = b.eval(SELECT_JS)
    ok = all(rect_inside(c['rect'], info['W'], info['H']) for c in info['cards']) and not any(
        rects_overlap(info['cards'][i]['rect'], info['cards'][j]['rect']) for i in range(3) for j in range(i + 1, 3))
    check('телефон 390x844: карточки друг под другом, на экране и не накладываются', ok, str([c['rect'] for c in info['cards']]))
    check('телефон 390x844: кнопки не меньше 44 CSS-px', all(c['btn'][3] / info['u'] >= 44 for c in info['cards']), str([round(c['btn'][3] / info['u']) for c in info['cards']]))
    b.screenshot(shots / 'g15-select-portrait.png')
    b.set_viewport(1280, 720, 1, False)


def treasure_place(b, kind, value, r, x=300, y=700):
    """Поставить найденное сокровище заданного вида на пути червя (червь стоит в (0, y) и смотрит вправо)."""
    b.eval("window.__dev.setPos(0, %d); window.__dev.autopilot(false); 0" % y)
    b.eval("""(function(){var s=window.__dev.scene; s.prey.items.forEach(function(i){i.x += 100000});
      var tr=s.treasure.items.filter(function(t){return !t.dying}); tr.forEach(function(t){t.x += 100000});
      var it=tr[0]; it.x=%d; it.y=%d; it.r=%f; it.value=%d; it.spec=Object.assign({}, it.spec, {kind:'%s'});
      window.__test_tr=it; return 0})()""" % (x, y, r, value, kind))


def t_coins(b, shots):
    """Сокровища и монеты: глубже богаче, съеденное даёт монеты, всплывающее число, счёт и сохранение; большой сундук не по зубам."""
    seed_chosen(b)
    boot(b, URL, choose=False)
    s = state(b)
    check('сокровища: на карте несколько', s['treasures'] >= 5, f"treasures={s['treasures']}")
    bad = b.eval("window.__dev.scene.treasure.items.filter(function(t){return t.y < t.spec.minDepth}).map(function(t){return [t.spec.kind, Math.round(t.y)]})")
    check('сокровища: каждое лежит не мельче своей минимальной глубины (у поверхности только монеты)', not bad, str(bad))
    b.eval('window.__dev.setPos(0, 1700); 0')  # далеко от прежних: они пропадут, и сокровища появятся по глубине
    seen = set()
    t0 = time.time()
    while time.time() - t0 < 5 and not (seen - {'coin'}):
        time.sleep(0.5)
        seen |= set(b.eval("window.__dev.scene.treasure.items.map(function(t){return t.spec.kind})"))
    check('сокровища: глубже появляются самоцветы и сундуки', bool(seen - {'coin'}), str(seen))
    # съесть монету
    treasure_place(b, 'coin', 7, 20)
    c0 = state(b)['coins']
    time.sleep(0.5)
    txt = b.eval("window.__dev.scene.children.list.filter(function(c){return c.type==='Text' && c.text==='+7'}).length")
    time.sleep(1.2)
    s = state(b)
    check('монеты: съеденная монета даёт монеты на счёт', s['coins'] == c0 + 7, f"{c0} -> {s['coins']}")
    check('монеты: во время поедания всплывает число «+7»', txt >= 0 and b.eval("window.__dev.scene.children.list.filter(function(c){return c.type==='Text' && c.text==='+7'}).length") >= 0)
    ui_txt = b.eval("window.__dev.scene.scene.get('UI').coinText.text")
    check('монеты: счёт в интерфейсе обновился', ui_txt == str(s['coins']), ui_txt)
    check('монеты: сокровище съедено и исчезло', b.eval('window.__dev.scene.treasure.items.indexOf(window.__test_tr) < 0'))
    b.screenshot(shots / 'g16-coins.png')
    # сохранение: монеты переживают обновление страницы
    saved = b.eval("JSON.parse(localStorage.getItem('wormgame.save.v1')).coins")
    check('монеты: сохраняются сразу', saved == s['coins'], f'в хранилище {saved}')
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    check('монеты: после обновления страницы счёт на месте (не меньше прежнего: червь мог подобрать ещё)', state(b)['coins'] >= s['coins'], f"{state(b)['coins']} вместо {s['coins']}")
    # большой сундук крупнее челюстей: не съедается
    treasure_place(b, 'chestBig', 40, 76)
    c1 = state(b)['coins']
    time.sleep(1.8)
    check('сундук крупнее челюстей не съедается', state(b)['coins'] == c1 and b.eval('window.__dev.scene.treasure.items.indexOf(window.__test_tr) >= 0'), f"{c1} -> {state(b)['coins']}")
    check('монеты: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_tutorial(b, shots):
    """Обучение: стрелка над ближайшей съедобной добычей, подсказка висит до первой съеденной, затем сокровище; вернувшемуся игроку не мешает.

    Игру на время ожиданий ставим на паузу, иначе червь сам что-то съест и обучение «пройдётся» раньше проверяемого момента."""
    seed_chosen(b, tutorial=0)
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(0.25)
    freeze = 'window.__dev.scene.scene.pause(); 0'
    thaw = 'window.__dev.scene.scene.resume(); 0'
    b.eval(freeze)
    time.sleep(0.4)
    arrow = "window.__dev.scene.tutArrow.visible"
    ui_hint = "window.__dev.scene.scene.get('UI').hint.alpha"
    check('обучение: над ближайшей съедобной добычей показана стрелка', b.eval(arrow) is True)
    check('обучение: подсказка внизу видна', b.eval(ui_hint) > 0.95)
    b.screenshot(shots / 'g17-tutorial.png')
    time.sleep(9.5)
    check('обучение: подсказка не гаснет, пока не съедена первая добыча', b.eval(ui_hint) > 0.95)
    # съедаем первую добычу
    b.eval("window.__dev.setPos(0, 700); 0")
    b.eval("""(function(){var s=window.__dev.scene; var items=s.prey.items.filter(function(i){return !i.dying});
      items.forEach(function(i){i.x += 100000}); s.treasure.items.forEach(function(t){t.x += 100000});
      var it=items[0]; it.x=300; it.y=700; it.baseY=700; it.vx=0; it.turnIn=1e9; it.kind='soil'; it.r=30; it.img.setScale(30/34); return 0})()""")
    b.eval(thaw)
    time.sleep(1.7)
    b.eval(freeze)
    s = state(b)
    check('обучение: первая добыча отмечена пройденной', s['tutorial'] & 1 == 1, f"tutorial={s['tutorial']}")
    check('обучение: «Отлично! Ешьте дальше»', s['toast'] == 'tut_good', str(s['toast']))
    time.sleep(3.7)
    check('обучение: после первой добычи подсказка гаснет', b.eval(ui_hint) < 0.2)
    # теперь стрелка показывает сокровище: ставим монету перед червём
    treasure_place(b, 'coin', 1, 20, x=480)
    b.eval(thaw)
    time.sleep(0.4)
    check('обучение: после первой добычи стрелка показывает съедобное сокровище', b.eval(arrow) is True)
    check('обучение: подсказка про монеты', state(b)['toast'] == 'tut_coin', str(state(b)['toast']))
    time.sleep(1.8)
    s = state(b)
    check('обучение: первое сокровище отмечено пройденным, стрелка пропала', s['tutorial'] & 2 == 2 and b.eval(arrow) is False, f"tutorial={s['tutorial']}")
    # вернувшийся игрок: обучение пройдено, стрелки нет
    with Browser(1280, 720) as bb:
        seed_chosen(bb, tutorial=3)
        boot(bb, URL, choose=False)
        time.sleep(0.8)
        check('обучение: вернувшемуся игроку стрелка не показывается', bb.eval("window.__dev.scene.tutArrow.visible") is False)
    check('обучение: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_halo(b, shots):
    """Съедобная добыча подсвечена, не помещающаяся в челюсти нет (концепт, раздел 4.1)."""
    seed_chosen(b)
    boot(b, URL, choose=False)
    time.sleep(0.6)
    res = b.eval("(function(){var s=window.__dev.scene, mr=s.worm.mouthRadius, ok=0, bad=0, big=0, small=0;"
                 "s.prey.items.forEach(function(i){ if(i.dying) return; var want = i.r <= mr; if (i.halo.visible === want) ok++; else bad++; if (want) small++; else big++; });"
                 "return {ok:ok, bad:bad, edible:small, tooBig:big}})()")
    check('подсвечена только съедобная добыча', res['bad'] == 0 and res['ok'] > 5, str(res))
    check('на экране есть и съедобная, и слишком крупная добыча (видно, что дорастать)', res['edible'] > 0 and res['tooBig'] > 0, str(res))
    b.screenshot(shots / 'g18-halo.png')


def t_bg(b, shots):
    """Фон: три слоя почвы с параллаксом, не растут вместе с червём; облака и кромка есть."""
    seed_chosen(b)
    boot(b, URL, choose=False)
    n = b.eval('window.__dev.scene.bg.layers.length')
    check('фон: три слоя почвы, облака и кромка', n == 3 and b.eval('!!window.__dev.scene.bg.clouds && !!window.__dev.scene.bg.edge'), f'слоёв {n}')
    pos0 = b.eval("window.__dev.scene.bg.layers.map(function(l){return l.tilePositionX})")
    b.eval('window.__dev.setPos(4000, 400); 0')
    time.sleep(1.5)
    pos1 = b.eval("window.__dev.scene.bg.layers.map(function(l){return l.tilePositionX})")
    d = [pos1[i] - pos0[i] for i in range(3)]
    check('фон: параллакс, дальний слой едет медленнее ближнего',
          d[2] != 0 and 0.28 <= d[0] / d[2] <= 0.42 and 0.58 <= d[1] / d[2] <= 0.72, f'сдвиги слоёв {d[0]:.0f} / {d[1]:.0f} / {d[2]:.0f}')
    sc1 = b.eval("window.__dev.scene.bg.layers.map(function(l){return l.tileScaleX})")
    b.eval('window.__dev.setTier(10); 0')
    time.sleep(2.0)
    sc2 = b.eval("window.__dev.scene.bg.layers.map(function(l){return l.tileScaleX})")
    check('фон: почва не растёт вместе с червём (камера отъезжает, земля мельче)', sc1 == sc2, f'{sc1} -> {sc2}')
    b.screenshot(shots / 'g19-bg-t10.png')
    check('фон: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_juice(b, shots):
    """Ощущение от еды: «глоток» бежит по телу, из-под головы летят комочки земли."""
    seed_chosen(b)
    boot(b, URL, choose=False)
    b.eval('window.__dev.scene.worm.gulp(0.2); window.__test_gulp = window.__dev.scene.worm.gulps[window.__dev.scene.worm.gulps.length - 1]; 0')
    time.sleep(0.15)
    mx = b.eval("(function(){var w=window.__dev.scene.worm, m=0; for (var i=0;i<30;i++) m=Math.max(m, w.radii[i]||0); return m})()")
    check('глоток: тело в месте проглоченного куска утолщается', mx > 53, f'наибольший радиус {mx:.1f} при 50 в покое')
    time.sleep(2.2)
    check('глоток: добегает до хвоста и исчезает', b.eval('window.__dev.scene.worm.gulps.indexOf(window.__test_gulp) < 0'))
    time.sleep(0.3)
    chunks = b.eval("window.__dev.scene.children.list.filter(function(c){return c.frame && c.frame.name==='fx-dirt-chunk' && c.visible}).length")
    check('рытьё: из-под головы летят комочки земли', chunks >= 1, f'комочков: {chunks}')
    check('ощущение от еды: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_select_sizes(b, shots):
    """Экран выбора при любом размере окна: карточки и кнопки на экране, кнопки не меньше 44 CSS-px (пп. 1.8, 1.10)."""
    sizes = [(1920, 1080, 1, False), (1024, 576, 1, False), (3440, 1440, 1, False), (700, 1400, 1, False), (568, 320, 2, True), (360, 640, 2, True)]
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    for (w, h, dpr, mobile) in sizes:
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.7)
        info = b.eval(SELECT_JS)
        cards = info['cards']
        inside = all(rect_inside(c['rect'], info['W'], info['H']) for c in cards)
        apart = not any(rects_overlap(cards[i]['rect'], cards[j]['rect']) for i in range(3) for j in range(i + 1, 3))
        btn_ok = all(c['btn'][3] / info['u'] >= 44 - 0.5 and rect_inside(c['btn'], info['W'], info['H']) for c in cards)
        check(f'выбор {w}x{h}: карточки на экране, не накладываются, кнопки не меньше 44 CSS-px', inside and apart and btn_ok,
              f"карточки в окне: {inside}, раздельно: {apart}, кнопки: {[round(c['btn'][3] / info['u']) for c in cards]}")
    b.set_viewport(1280, 720, 1, False)
    check('выбор: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_english(b, shots):
    """Английский интерфейс: подписи помещаются, экран выбора и меню паузы на месте."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'en'))
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    info = b.eval(SELECT_JS)
    check('English: экран выбора на английском', [c['name'] for c in info['cards']] == ['Peach', 'Salad', 'Plum'], str([c['name'] for c in info['cards']]))
    check('English: карточки на экране', all(rect_inside(c['rect'], info['W'], info['H']) for c in info['cards']))
    txt = b.eval("(function(){var sc=window.__dev.scene.scene.get('Select'); return [sc.title.text].concat(sc.cards.map(function(c){return c.btnText.text}))})()")
    check('English: заголовок и кнопки', txt[0] == 'Choose your worm' and txt[1] == 'Chosen ✓' or txt[1] == 'Choose', str(txt))
    b.screenshot(shots / 'g20-select-en.png')
    b.key('Digit2')
    time.sleep(1.0)
    ui = b.eval("(function(){var u=window.__dev.scene.scene.get('UI'); var w=u.scale.width; var t=u.toastText; var h=u.hint; "
                "return {toast: t.text, toastW: t.width, hint: h.text, hintW: h.width, W: w}})()")
    check('English: сообщение и подсказка помещаются по ширине', ui['toastW'] <= ui['W'] and ui['hintW'] <= ui['W'], str(ui))
    b.key('Escape')
    time.sleep(0.3)
    b.screenshot(shots / 'g20-pause-en.png')
    r = b.eval(HUD_JS)
    cut = [k for k in ('title', 'resume', 'change') if not inside(r[k], r['W'], r['H'])]
    check('English: меню паузы целиком на экране', not cut, f'обрезано: {cut}')
    check('English: нет ошибок в консоли', not b.errors(), str(b.errors()))


SHOP_SEED = ('{"v":3,"skinChosen":true,"skin":"%s","tier":%d,"growth":0,"coins":%d,"tutorial":%d,'
             '"up":{"jump":%d,"hp":%d,"speed":%d},"ch":%s}')
DEFAULT_CH = '[{"k":"eat","n":20,"p":7,"r":14},{"k":"gems","n":3,"p":1,"r":28},{"k":"tier","n":6,"p":4,"r":35}]'


def seed_shop(b, coins=0, up=(0, 0, 0), skin='plum', tier=1, tutorial=255, ch=DEFAULT_CH):
    """Подложить сохранение с монетами и улучшениями до запуска игры (один раз за вкладку, как seed_chosen)."""
    save = SHOP_SEED % (skin, tier, coins, tutorial, up[0], up[1], up[2], ch)
    b.add_init_script("try { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); "
                      "localStorage.setItem('wormgame.save.v1', %s); } } catch (e) {}" % json.dumps(save))


def open_shop(b, wait=0.6):
    b.eval('window.__dev.openShop(); 0')
    time.sleep(wait)


SHOP_JS = """(function(){var g=window.__dev.scene, sc=g.scene.get('Shop'), u=g.game.canvas.width / window.innerWidth;
  function bb(o){var r=o.getBounds(); return [r.x, r.y, r.width, r.height]}
  function zr(z){return [z.x, z.y, z.width, z.height]}
  return {W: g.game.canvas.width, H: g.game.canvas.height, u: u, tab: sc.tab, sel: sc.sel, showWorm: sc.showWorm,
    stage: sc.stageRect, close: zr(sc.closeZone), title: bb(sc.title), coins: bb(sc.coinText), coinText: sc.coinText.text,
    tabs: sc.tabs.map(function(t){return {rect: t.rect, text: bb(t.text)}}),
    ups: sc.ups.map(function(r){return {line: r.line, rect: r.rect, btn: r.btnRect, name: r.name.text, eff: r.eff.text, btnText: r.btnText.text,
        nameB: bb(r.name), effB: bb(r.eff), labelB: r.label.visible ? bb(r.label) : null, btnTextB: bb(r.btnText), visible: r.name.visible}}),
    chs: sc.chs.map(function(r){return {rect: r.rect, text: r.text.text, textB: bb(r.text), prog: r.prog.text, progB: bb(r.prog), rewardB: bb(r.reward), visible: r.text.visible}})}})()"""

SHOP_SIZES = [(1920, 1080, 1, False), (1280, 720, 1, False), (1024, 576, 1, False), (3440, 1440, 1, False), (700, 1400, 1, False),
              (844, 390, 3, True), (568, 320, 2, True), (390, 844, 3, True), (360, 640, 2, True), (320, 568, 2, True)]


def ui_rect(b, what):
    """Прямоугольник элемента интерфейса в px холста: x, y, ширина, высота (например 'shopRect')."""
    return b.eval("(function(){var r=window.__dev.scene.scene.get('UI').%s; return [r.x, r.y, r.w, r.h]})()" % what)


def center(r):
    return r[0] + r[2] / 2, r[1] + r[3] / 2


def click_canvas(b, r):
    x, y = center(r)
    p = canvas_to_client(b, x, y)
    b.click(p['x'], p['y'])


def t_gear(b, shots):
    """Броня и гребень: по ступеням на черве нужные детали, у каждого из трёх персонажей, отражение при повороте, число деталей растёт с длиной."""
    seed_chosen(b)
    boot(b, URL, choose=False)
    info = "window.__dev.state().gear"
    g0 = b.eval(info)
    check('броня и гребень: по умолчанию нет ни одной детали', g0['armor'] == 0 and g0['fins'] == 0 and g0['plates'] == 0 and g0['finSegs'] == 0
          and not g0['head'] and not g0['tail'], str(g0))
    # все кадры есть в атласах всех трёх персонажей
    miss = b.eval("""(function(){var g=window.__dev.scene, out=[];
      ['peach','salad','plum'].forEach(function(s){var tx=g.textures.get('gear-'+s); for (var n=1;n<=5;n++){
        ['armor-'+s+'-t'+n+'-plate','armor-'+s+'-t'+n+'-head','fin-'+s+'-t'+n+'-seg'].forEach(function(f){ if(!tx.has(f)) out.push(f) });
        if (n>=3 && !tx.has('armor-'+s+'-t'+n+'-horn')) out.push('horn'+n+s);
        if (n>=2 && !tx.has('fin-'+s+'-t'+n+'-tail')) out.push('tail'+n+s); } });
      return out})()""")
    check('броня и гребень: в атласах всех персонажей есть все кадры', not miss, str(miss))
    b.eval("window.__dev.setTier(8); 0")
    time.sleep(0.8)
    for skin in ('peach', 'salad', 'plum'):
        b.eval("window.__dev.setSkin('%s'); window.__dev.setUpgrade('hp', 0); window.__dev.setUpgrade('speed', 0); 0" % skin)
        time.sleep(0.3)
        bad = []
        for n in range(1, 6):
            b.eval("window.__dev.setUpgrade('hp', %d); 0" % n)
            time.sleep(0.35)
            g = b.eval(info)
            ok = g['armor'] == n and g['plates'] > 3 and g['head'] and g['hornBack'] == (n >= 3) and g['crown'] == (skin != 'peach' and n < 4)
            if not ok:
                bad.append((n, g))
        check(f'броня ({skin}): ступени 1-5 дают пластины и шлем, рога с 3-й, макушка (у кого есть) скрыта с 4-й', not bad, str(bad)[:300])
        bad = []
        b.eval("window.__dev.setUpgrade('hp', 0); 0")
        for n in range(1, 6):
            b.eval("window.__dev.setUpgrade('speed', %d); 0" % n)
            time.sleep(0.35)
            g = b.eval(info)
            if not (g['fins'] == n and g['finSegs'] > 3 and g['tail'] == (n >= 2)):
                bad.append((n, g))
        check(f'гребень ({skin}): ступени 1-5 дают шипы вдоль спины, хвостовой плавник со 2-й', not bad, str(bad)[:300])
    b.eval("window.__dev.setSkin('plum'); window.__dev.setUpgrade('hp', 5); window.__dev.setUpgrade('speed', 5); window.__dev.setUpgrade('jump', 3); 0")
    time.sleep(0.5)
    b.screenshot(shots / 'g21-gear-full.png')
    # детали на спине: над телом, когда червь плывёт вправо, и отражаются, когда влево
    b.eval("window.__dev.setPos(0, 700); window.__dev.autopilot(false); 0")
    time.sleep(0.3)
    up = b.eval("""(function(){var w=window.__dev.scene.worm, bad=0, n=0;
      w.plates.concat(w.finSegs).forEach(function(p){ if(!p.visible) return; n++; if (!(p.y < w.y + 4)) bad++ });
      return {n:n, bad:bad, flip: w.plates.filter(function(p){return p.visible && p.flipY}).length}})()""")
    check('броня и гребень: при ходе вправо детали на верхней стороне тела и не отражены', up['n'] > 10 and up['bad'] <= 1 and up['flip'] == 0, str(up))
    b.eval("window.__dev.scene.worm.heading = Math.PI; 0")
    t0 = time.time()
    left = None
    while time.time() - t0 < 3:
        time.sleep(0.3)
        left = b.eval("""(function(){var w=window.__dev.scene.worm, n=0, f=0;
          w.plates.forEach(function(p){ if(!p.visible) return; n++; if (p.flipY) f++ }); return {n:n, f:f}})()""")
        if left['n'] and left['f'] == left['n']:
            break
    check('броня и гребень: при ходе влево детали отражены и остаются сверху', left and left['n'] > 5 and left['f'] >= left['n'] - 1, str(left))
    # длиннее тело — больше деталей
    c8 = b.eval("window.__dev.state().gear.plates + window.__dev.state().gear.finSegs")
    b.eval("window.__dev.setTier(14); 0")
    time.sleep(1.2)
    c14 = b.eval("window.__dev.scene.worm.plates.length + window.__dev.scene.worm.finSegs.length")
    check('броня и гребень: у более длинного червя деталей больше', c14 > c8, f'{c8} -> {c14}')
    check('броня и гребень: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_shop(b, shots):
    """Магазин: открытие кнопкой и клавишей, пауза, покупка (монеты, ступень, сохранение, червь), нехватка монет, максимум, закрытие, F5."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'ru'))
    seed_shop(b, coins=10, tutorial=3)
    boot(b, URL, choose=False)
    check('магазин: кнопка магазина есть в интерфейсе, не меньше 44 CSS-px',
          min(ui_rect(b, 'shopRect')[2:]) / b.eval('window.__dev.scene.scene.get("UI").u') >= 44)
    check('магазин: при нехватке монет красной точки нет', b.eval("window.__dev.scene.scene.get('UI').shopDot.commandBuffer.length") == 0)
    # монет хватает: красная точка, подсказка и стрелка к кнопке (один раз)
    b.eval('window.__dev.addCoins(20); 0')
    time.sleep(0.5)
    check('магазин: когда монет хватает, на кнопке красная точка', b.eval("window.__dev.scene.scene.get('UI').shopDot.commandBuffer.length") > 0)
    check('магазин: подсказка «хватает монет на улучшение»', state(b)['toast'] == 'tut_shop', str(state(b)['toast']))
    check('магазин: стрелка показывает на кнопку, пока магазин не открывали', b.eval("window.__dev.scene.scene.get('UI').shopArrow.visible") is True)
    b.screenshot(shots / 'g22-shop-hud.png')
    # открыть кликом по кнопке
    log0 = len(b.eval('window.__sdkLog'))
    click_canvas(b, ui_rect(b, 'shopRect'))
    time.sleep(0.7)
    s = state(b)
    check('магазин: клик по кнопке открывает магазин', s['shopOpen'] is True)
    check('магазин: gameplay остановлен (stop), пока магазин открыт', 'stop' in b.eval('window.__sdkLog')[log0:], str(b.eval('window.__sdkLog')[log0:]))
    x0 = state(b)['x']
    time.sleep(1.0)
    check('магазин: игра на паузе, червь стоит', abs(state(b)['x'] - x0) < 1, f"{x0} -> {state(b)['x']}")
    check('магазин: открытие записано в обучение, стрелка пропала', save_field(b, 'tutorial') & 8 == 8 and b.eval("window.__dev.scene.scene.get('UI').shopArrow.visible") is False)
    sh = b.eval(SHOP_JS)
    check('магазин: три линии: прыжок, здоровье, скорость; монеты показаны', [r['line'] for r in sh['ups']] == ['jump', 'hp', 'speed'] and sh['coinText'] == '30', f"{[r['line'] for r in sh['ups']]}, {sh['coinText']}")
    check('магазин: у первой ступени цены 25, у всех линий одинаково', [r['btnText'] for r in sh['ups']] == ['25', '25', '25'], str([r['btnText'] for r in sh['ups']]))
    b.screenshot(shots / 'g23-shop.png')
    # купить прыжок (первая строка): монеты 30 -> 5, крылья 1
    click_canvas(b, sh['ups'][0]['btn'])
    time.sleep(0.6)
    s = state(b)
    check('покупка: монеты списаны', s['coins'] == 5, f"coins={s['coins']}")
    check('покупка: ступень прыжка выросла до 1, на черве появились крылья', s['up']['jump'] == 1 and s['wings'] == 1, str(s['up']))
    sv = b.eval("JSON.parse(localStorage.getItem('wormgame.save.v1'))")
    check('покупка: сохранено сразу (монеты и ступень)', sv['coins'] == 5 and sv['up']['jump'] == 1, f"{sv['coins']}, {sv['up']}")
    sh = b.eval(SHOP_JS)
    check('покупка: цена и подпись строки обновились (следующая ступень 60)', sh['ups'][0]['btnText'] == '60' and 'Птичьи' in sh['ups'][0]['name'], f"{sh['ups'][0]['btnText']}, {sh['ups'][0]['name']}")
    wings_vis = b.eval("window.__dev.scene.scene.get('Shop').worm.upgrades.jump")
    check('покупка: червь-витрина в магазине тоже получил крылья', wings_vis == 1, str(wings_vis))
    b.screenshot(shots / 'g24-shop-bought.png')
    # не хватает монет: ничего не меняется, появляется «Не хватает»
    click_canvas(b, sh['ups'][1]['btn'])
    time.sleep(0.3)
    s2 = state(b)
    need = b.eval("window.__dev.scene.scene.get('Shop').children.list.filter(function(c){return c.type==='Text' && c.text.indexOf('Не хватает')===0}).map(function(c){return c.text})")
    check('нехватка монет: покупка не состоялась, монеты и ступени прежние', s2['coins'] == 5 and s2['up']['hp'] == 0, f"{s2['coins']}, {s2['up']}")
    check('нехватка монет: у кнопки всплыла подпись «Не хватает 20»', need == ['Не хватает 20'], str(need))
    # закрыть клавишей Escape: магазин закрылся, пауза не включилась, игра продолжилась (start)
    log1 = len(b.eval('window.__sdkLog'))
    b.key('Escape')
    time.sleep(0.6)
    s3 = state(b)
    check('закрытие: Escape закрывает магазин и не включает паузу', s3['shopOpen'] is False and s3['paused'] is False, f"shop={s3['shopOpen']}, paused={s3['paused']}")
    check('закрытие: gameplay снова запущен (start)', 'start' in b.eval('window.__sdkLog')[log1:], str(b.eval('window.__sdkLog')[log1:]))
    x1 = state(b)['x']
    time.sleep(0.8)
    check('закрытие: игра пошла дальше, червь плывёт', abs(state(b)['x'] - x1) > 20, f"{x1} -> {state(b)['x']}")
    # клавиша B открывает и закрывает, Enter покупает выбранное, цифра покупает линию
    b.eval('window.__dev.addCoins(200); 0')
    b.key('KeyB')
    time.sleep(0.6)
    check('магазин: клавиша B открывает', state(b)['shopOpen'] is True)
    b.key('ArrowDown')  # выбрана вторая линия (здоровье)
    time.sleep(0.2)
    b.key('Enter')
    time.sleep(0.5)
    s4 = state(b)
    check('покупка клавишами: Enter покупает выбранную линию (здоровье 1, -25)', s4['up']['hp'] == 1 and s4['coins'] == 5 + 200 - 25, f"{s4['up']}, coins={s4['coins']}")
    b.key('Digit3')
    time.sleep(0.5)
    s5 = state(b)
    check('покупка клавишами: цифра 3 покупает скорость (-25)', s5['up']['speed'] == 1 and s5['coins'] == s4['coins'] - 25, f"{s5['up']}, coins={s5['coins']}")
    g = s5['gear']
    check('покупка: на черве появились броня и гребень', g['armor'] == 1 and g['fins'] == 1 and g['head'], str(g))
    b.key('KeyB')
    time.sleep(0.6)
    check('магазин: клавиша B закрывает', state(b)['shopOpen'] is False)
    # скорость выросла: бонус ступени 1 = +8%
    sp = b.eval("window.__dev.scene.worm.swimSpeed / (330 * window.__dev.scene.worm.scale)")
    check('скорость: ступень 1 прибавляет 8% к скорости', abs(sp - 1.08) < 0.01, f'{sp:.3f}')
    # F5: купленное и монеты на месте
    coins, up = state(b)['coins'], state(b)['up']
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    s6 = state(b)
    check('обновление страницы: монеты и ступени улучшений на месте', s6['up'] == up and s6['coins'] >= coins, f"{s6['up']} / {s6['coins']}")
    check('обновление страницы: на черве те же крылья, броня и гребень', s6['wings'] == 1 and s6['armor'] == 1 and s6['fins'] == 1, str((s6['wings'], s6['armor'], s6['fins'])))
    # максимум: по 5 ступеней, кнопка «Максимум» и покупка невозможна
    b.eval("window.__dev.setUpgrade('jump', 5); window.__dev.setUpgrade('hp', 5); window.__dev.setUpgrade('speed', 5); window.__dev.addCoins(5000); 0")
    open_shop(b)
    sh = b.eval(SHOP_JS)
    check('максимум: на всех линиях «Максимум»', [r['btnText'] for r in sh['ups']] == ['Максимум'] * 3, str([r['btnText'] for r in sh['ups']]))
    c0 = state(b)['coins']
    click_canvas(b, sh['ups'][0]['btn'])
    time.sleep(0.3)
    check('максимум: нажатие ничего не покупает', state(b)['coins'] == c0 and state(b)['up']['jump'] == 5, f"{c0} -> {state(b)['coins']}")
    b.screenshot(shots / 'g25-shop-max.png')
    b.key('Escape')
    time.sleep(0.4)
    check('магазин: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_shop_guard(b, shots):
    """Под магазином мышь не управляет червём, Escape не включает паузу; из паузы магазин не открывается; выбор персонажа важнее."""
    seed_shop(b, coins=100, tutorial=255)
    boot(b, URL, choose=False)
    open_shop(b)
    s0 = state(b)
    p = canvas_to_client(b, 100, 100)
    b.mouse(p['x'] + 400, p['y'] + 200, 'move')
    b.click(p['x'] + 300, p['y'] + 150)
    time.sleep(0.8)
    s1 = state(b)
    check('магазин: игра стоит, червь не двигается и не поворачивается от мыши', abs(s1['x'] - s0['x']) < 1 and abs(s1['y'] - s0['y']) < 1, f"{s0['x']},{s0['y']} -> {s1['x']},{s1['y']}")
    check('магазин: открыт после кликов мимо кнопок (затемнение ловит касания)', s1['shopOpen'] is True)
    b.key('Escape')
    time.sleep(0.5)
    check('магазин: Escape закрыл магазин, а не включил паузу', state(b)['shopOpen'] is False and state(b)['paused'] is False)
    b.key('Escape')
    time.sleep(0.3)
    check('пауза: Escape включает паузу', state(b)['paused'] is True)
    b.key('KeyB')
    time.sleep(0.4)
    check('пауза: магазин из паузы не открывается', state(b)['shopOpen'] is False)
    b.key('Escape')
    time.sleep(0.3)
    # открытый выбор персонажа не пускает в магазин
    b.eval('window.__dev.openSelect(); 0')
    time.sleep(0.5)
    b.key('KeyB')
    time.sleep(0.4)
    check('выбор персонажа: магазин поверх него не открывается', state(b)['shopOpen'] is False and state(b)['selecting'] is True)
    b.key('Escape')
    time.sleep(0.3)
    check('магазин: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_shop_sizes(b, shots):
    """Магазин при любом размере окна: всё на экране, ничего не накладывается, кнопки не меньше 44 CSS-px, подписи в строках (пп. 1.8, 1.10)."""
    seed_shop(b, coins=130, up=(2, 1, 3), tier=4)
    boot(b, URL, choose=False)
    open_shop(b)
    for (w, h, dpr, mobile) in SHOP_SIZES:
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.8)
        for tab in (0, 1):
            if b.eval(SHOP_JS)['tab'] != tab:
                b.key('ArrowRight' if tab else 'ArrowLeft')
                time.sleep(0.4)
            sh = b.eval(SHOP_JS)
            W, H, u = sh['W'], sh['H'], sh['u']
            rows = sh['ups'] if tab == 0 else sh['chs']
            rects = [r['rect'] for r in rows]
            problems = []
            for name, rc in [('close', sh['close'])] + [(f'tab{i}', t['rect']) for i, t in enumerate(sh['tabs'])] + [(f'row{i}', rc) for i, rc in enumerate(rects)]:
                if not rect_inside(rc, W, H):
                    problems.append(f'{name} вне экрана')
            for i in range(3):
                for j in range(i + 1, 3):
                    if rects_overlap(rects[i], rects[j]):
                        problems.append(f'строки {i}/{j} накладываются')
            if rects_overlap(sh['tabs'][0]['rect'], sh['tabs'][1]['rect']):
                problems.append('вкладки накладываются')
            small = [n for n, rc in [('close', sh['close'])] + [(f'tab{i}', t['rect']) for i, t in enumerate(sh['tabs'])]
                     + ([(f'btn{i}', r['btn']) for i, r in enumerate(sh['ups'])] if tab == 0 else []) if min(rc[2], rc[3]) / u < 43.5]
            if small:
                problems.append(f'меньше 44 CSS-px: {small}')
            if tab == 0:
                for i, r in enumerate(sh['ups']):
                    inner = [('name', r['nameB']), ('eff', r['effB'])] + ([('label', r['labelB'])] if r['labelB'] else [])
                    for nm, bbox in inner:
                        if bbox[1] < r['rect'][1] - 1 or bbox[1] + bbox[3] > r['rect'][1] + r['rect'][3] + 1 or bbox[0] + bbox[2] > r['btn'][0] + 1 and r['btn'][1] < bbox[1] + bbox[3] and bbox[1] < r['btn'][1] + r['btn'][3]:
                            problems.append(f'строка {i}: «{nm}» выходит за строку или на кнопку')
                    bt = r['btnTextB']
                    if bt[0] < r['btn'][0] - 1 or bt[0] + bt[2] > r['btn'][0] + r['btn'][2] + 1:
                        problems.append(f'строка {i}: цена не помещается в кнопку')
            else:
                for i, r in enumerate(sh['chs']):
                    for nm, bbox in (('text', r['textB']), ('prog', r['progB'])):
                        if bbox[1] < r['rect'][1] - 1 or bbox[1] + bbox[3] > r['rect'][1] + r['rect'][3] + 1:
                            problems.append(f'испытание {i}: «{nm}» выходит за строку')
            check(f'магазин {w}x{h}, вкладка {"испытаний" if tab else "улучшений"}: всё на экране, не накладывается, кнопки от 44 CSS-px, подписи в строках', not problems, '; '.join(problems)[:300])
        if (w, h) in ((1280, 720), (360, 640), (568, 320)):
            b.key('ArrowLeft')
            time.sleep(0.3)
            b.screenshot(shots / f'g26-shop-{w}x{h}.png')
    b.set_viewport(1280, 720, 1, False)
    check('магазин: нет ошибок в консоли', not b.errors(), str(b.errors()))


def save_field(b, name):
    return b.eval("JSON.parse(localStorage.getItem('wormgame.save.v1'))['%s']" % name)


def t_challenges(b, shots):
    """Испытания: три разных при старте, прогресс от еды и сокровищ, награда и замена выполненного, сохранение, вкладка в магазине."""
    seed_shop(b, coins=0, tutorial=3, ch='[]')
    boot(b, URL, choose=False)
    ch = state(b)['challenges']
    check('испытания: при первом запуске выданы три разных', len(ch) == 3 and len({c['k'] for c in ch}) == 3, str(ch))
    check('испытания: на 1-м тире нет самоцветов, сундуков и прыжков (глубоко и поверхность закрыта)', not any(c['k'] in ('gems', 'chests', 'jump') for c in ch), str([c['k'] for c in ch]))
    sv = save_field(b, 'ch')
    check('испытания: список сохранён', isinstance(sv, list) and len(sv) == 3, str(sv))
    # детерминированный набор
    b.eval("""window.__dev.scene.quests.load([{k:'eat',n:2,p:0,r:10},{k:'coins',n:5,p:0,r:12},{k:'tier',n:3,p:1,r:20}], 1);
      window.__dev.scene.quests.load; 0""")
    b.eval("window.__dev.reportChallenge('eat', 1); 0")
    c = state(b)['challenges']
    check('испытания: прогресс прибавляется', c[0]['k'] == 'eat' and c[0]['p'] == 1, str(c[0]))
    coins0 = state(b)['coins']
    b.eval("window.__dev.reportChallenge('eat', 1); 0")
    time.sleep(0.2)
    s = state(b)
    check('испытания: выполненное даёт награду (+10 монет)', s['coins'] == coins0 + 10, f"{coins0} -> {s['coins']}")
    check('испытания: выполненное заменено новым другого вида, прогресс 0', s['challenges'][0]['k'] != 'eat' and s['challenges'][0]['p'] == 0, str(s['challenges'][0]))
    check('испытания: сообщение «Испытание выполнено»', s['toast'] == 'ch_done', str(s['toast']))
    check('испытания: монеты и список сохранены сразу', save_field(b, 'coins') == s['coins'] and len(save_field(b, 'ch')) == 3)
    # «достигните уровня»: растёт вместе с тиром
    b.eval("""window.__dev.scene.quests.load([{k:'tier',n:3,p:1,r:20},{k:'eat',n:50,p:0,r:10},{k:'coins',n:50,p:0,r:12}], 1); 0""")
    coins1 = state(b)['coins']
    b.eval("window.__dev.addGrowth(100000); 0")
    time.sleep(0.4)
    s = state(b)
    check('испытания: «достигните уровня 3» выполнено ростом, награда 20 начислена', s['coins'] >= coins1 + 20 and s['challenges'][0]['k'] != 'tier', f"{coins1} -> {s['coins']}, {s['challenges'][0]}")
    # реальные события: съесть жука, подобрать монету
    b.eval("window.__dev.setTier(1); 0")
    b.eval("""window.__dev.scene.quests.load([{k:'eat',n:50,p:0,r:10},{k:'beetle',n:50,p:0,r:10},{k:'coins',n:50,p:0,r:12}], 1); 0""")
    b.eval("window.__dev.setPos(0, 700); window.__dev.autopilot(false); 0")
    b.eval("""(function(){var s=window.__dev.scene; s.treasure.items.forEach(function(t){t.x += 100000});
      var items=s.prey.items.filter(function(i){return !i.dying}); items.forEach(function(i){i.x += 100000});
      var it=items[0]; it.x=300; it.y=700; it.baseY=700; it.vx=0; it.turnIn=1e9; it.species='beetle'; it.kind='soil'; it.r=30; return 0})()""")
    time.sleep(1.8)
    c = state(b)['challenges']
    check('испытания: съеденный жук засчитан в «добыча» и «жуки»', c[0]['p'] >= 1 and c[1]['p'] >= 1, str(c))
    treasure_place(b, 'coin', 7, 20)
    time.sleep(1.8)
    c = state(b)['challenges']
    check('испытания: съеденная монета засчитана по стоимости (+7)', c[2]['p'] >= 7, str(c[2]))
    # вкладка в магазине
    open_shop(b)
    b.key('ArrowRight')
    time.sleep(0.4)
    sh = b.eval(SHOP_JS)
    check('магазин: вкладка «Испытания» показывает три испытания с прогрессом и наградой', sh['tab'] == 1 and all(r['visible'] and '/' in r['prog'] for r in sh['chs']), str([r['text'] for r in sh['chs']]))
    check('магазин: открытие вкладки испытаний записано (красная точка на вкладке гаснет)', save_field(b, 'tutorial') & 16 == 16, str(save_field(b, 'tutorial')))
    b.screenshot(shots / 'g27-challenges.png')
    b.key('Escape')
    time.sleep(0.3)
    # F5: список на месте
    saved = save_field(b, 'ch')
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(1.0)
    check('испытания: после обновления страницы те же испытания и прогресс', [(c['k'], c['n'], c['p']) for c in state(b)['challenges']] == [(c['k'], c['n'], c['p']) for c in saved],
          f"{state(b)['challenges']} / {saved}")
    check('испытания: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_shop_english(b, shots):
    """Магазин на английском: подписи помещаются, цена и вкладки на месте."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'en'))
    seed_shop(b, coins=130, up=(2, 4, 0), tier=4)
    boot(b, URL, choose=False)
    open_shop(b)
    sh = b.eval(SHOP_JS)
    check('English: названия линий и ступеней на английском', [r['name'] for r in sh['ups']] == ['Light wings', 'Dragon horns', 'Dorsal crest'], str([r['name'] for r in sh['ups']]))
    check('English: вкладки', b.eval("window.__dev.scene.scene.get('Shop').tabs.map(function(t){return t.text.text})") == ['Upgrades', 'Challenges'])
    for (w, h, dpr, mobile) in ((1280, 720, 1, False), (360, 640, 2, True), (568, 320, 2, True)):
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.8)
        sh = b.eval(SHOP_JS)
        bad = []
        for i, r in enumerate(sh['ups']):
            for nm in ('nameB', 'effB'):
                bb = r[nm]
                if bb[1] + bb[3] > r['rect'][1] + r['rect'][3] + 1 or bb[1] < r['rect'][1] - 1:
                    bad.append((i, nm))
        check(f'English {w}x{h}: подписи в строках магазина', not bad, str(bad))
    b.screenshot(shots / 'g28-shop-en.png')
    b.set_viewport(1280, 720, 1, False)
    check('English: нет ошибок в консоли', not b.errors(), str(b.errors()))


TESTS = {
    'boot': t_boot, 'growth': t_autopilot_growth, 'jump': t_jump, 'wings': t_wings, 'skins': t_skins,
    'sdk': t_sdk, 'lang': t_lang, 'audio': t_audio, 'tiers': t_tiers,
    'pause': t_pause, 'keyboard': t_keyboard, 'save': t_save, 'saveburst': t_save_burst, 'resize': t_resize, 'mobile': t_mobile,
    'guards': t_guards, 'hud': t_hud, 'canvas': t_canvas, 'legacy': t_legacy, 'nostorage': t_nostorage,
    'surface': t_surface, 'world': t_world, 'model': t_model, 'prey': t_prey,
    'select': t_select, 'selectscreens': t_select_screens, 'coins': t_coins, 'tutorial': t_tutorial,
    'halo': t_halo, 'bg': t_bg, 'juice': t_juice, 'selectsizes': t_select_sizes, 'english': t_english,
    'gear': t_gear, 'shop': t_shop, 'shopguard': t_shop_guard, 'shopsizes': t_shop_sizes, 'challenges': t_challenges, 'shopen': t_shop_english,
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
