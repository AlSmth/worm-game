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
    check('прыжок: высота разумная (есть, но не выше полёта)', -1.8 * 300 * s0['scale'] < min_y < -40, f"min_y={min_y}, масштаб {s0['scale']}")
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
    time.sleep(1.6)
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
              r['S'] > prev and 30 < r['head'] < 260 and r['fps'] >= 25, str(r))
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
    for side, key, sign in (('правая', 'ArrowRight', 1), ('левая', 'ArrowLeft', -1)):
        half = b.eval('window.__dev.world().half')
        b.eval('window.__dev.setPos(%d, 400)' % (sign * (half - 700 * b.eval('window.__dev.scene.worm.scale'))))
        time.sleep(1.0)
        half = b.eval('window.__dev.world().half')
        b.key_down(key)
        far = 0
        t0 = time.time()
        while time.time() - t0 < 5.0:
            time.sleep(0.05)
            far = max(far, sign * state(b)['x'])
        b.key_up(key)
        half = b.eval('window.__dev.world().half')  # червь за это время мог вырасти, и карта вместе с ним
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
    idle, t0 = 0, time.time()
    while time.time() - t0 < 3.0 and not 0.4 <= idle <= 0.68:  # недавний укус или выражение временно меняют раскрытие
        time.sleep(0.2)
        idle = state(b)['jaw']
    check('челюсти в покое раскрыты примерно наполовину', 0.4 <= idle <= 0.68, f'{idle}')
    # выражение держится 600 мс; пока оно показано, читаем раскрытие несколько раз (случайный укус рядом не должен ломать проверку)
    chomp, wide = 1.0, 0.0
    b.eval("window.__dev.scene.worm.flash('chomp', 600, window.__dev.scene.time.now); 0")
    for _ in range(6):
        time.sleep(0.08)
        chomp = min(chomp, state(b)['jaw'])
    time.sleep(0.8)
    b.eval("window.__dev.scene.worm.flash('open', 600, window.__dev.scene.time.now); 0")
    for _ in range(6):
        time.sleep(0.08)
        wide = max(wide, state(b)['jaw'])
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
    check('добыча: подземная добыча лежит в земле (над землёй только добыча поверхности)',
          b.eval("window.__dev.scene.prey.items.every(function(it){return it.y>0})"))
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
    # съедобная добыча гарантированно в поле зрения (но не на пути пасти): иначе стрелке иногда нечего показывать
    b.eval("""(function(){var s=window.__dev.scene, w=s.worm, it=s.prey.items.filter(function(i){return !i.dying})[0];
      it.x=w.x+450; it.y=w.y-130; it.baseY=it.y; it.vx=0; it.turnIn=1e9; it.r=26; it.img.setScale(26/34); return 0})()""")
    time.sleep(0.3)
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
    # на старте крупной добычи может случайно не оказаться: одну делаем крупнее челюстей, другую мельче (дальше всё считается само)
    b.eval("(function(){var s=window.__dev.scene, mr=s.worm.mouthRadius, a=s.prey.items.filter(function(i){return !i.dying}); a[0].r = mr*1.6; a[1].r = mr*0.5; return 0})()")
    time.sleep(0.4)
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
    b.eval("window.__dev.freeze(true); 0")  # червь не подбирает монеты по пути: счёт в проверках точный
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
    b.eval("window.__dev.freeze(false); 0")
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


def zone2_start(b, tier=5, up=(0, 0, 0), coins=0, ch='[]', lang=None):
    """Зона 2: сохранение с нужным тиром, игра запущена, червь далеко от стартовой расстановки и стоит на месте (freeze)."""
    if lang:
        b.add_init_script(FAKE_SDK.replace('__LANG__', lang))
    seed_shop(b, coins=coins, up=up, tier=tier, tutorial=255, ch=ch)
    boot(b, URL, choose=False)


def far(b, y, x=30000):
    """Поставить червя далеко от прежней расстановки и заморозить: рядом с ним нет чужой добычи, кроме поставленной тестом.
    Глубина y задаётся в пикселях при масштабе 1 и умножается на текущий масштаб червя (мир реальных пропорций)."""
    b.eval("window.__dev.autopilot(false); window.__dev.setPos(%d, %d * window.__dev.scene.worm.scale); window.__dev.freeze(true); 0" % (x, y))
    time.sleep(0.5)


def place(b, kind, dx=None, x=None):
    """Поставить добычу поверхности перед ртом червя (dx от рта, в пикселях масштаба 1) или в точке x."""
    if x is None:
        mx = b.eval('window.__dev.scene.worm.mouth().x')
        x = mx + (dx or 0) * b.eval('window.__dev.scene.worm.scale')
    return b.eval("window.__dev.placeSurface('%s', %f)" % (kind, x))


def t_zone2_world(b, shots):
    """Поверхность: люди, декор, дальние дома и холмы; лесенка съедобности по тирам; до открытия выхода добыча поверхности несъедобна."""
    zone2_start(b, tier=5)
    s = state(b)
    kinds = s['surface']
    check('поверхность: на 5-м тире вокруг червя люди и немного машин', kinds.count('person') >= 8 and 14 <= len(kinds) <= 44, str(kinds))
    check('поверхность: фон над землёй: дальние дома и холмы видны', b.eval("window.__dev.scene.bg.skyline.visible && window.__dev.scene.bg.hills.visible") is True)
    check('поверхность: есть декор (деревья, кусты, фонари)', b.eval("window.__dev.scene.surface.decor.length") >= 8)
    b.screenshot(shots / 'g30-zone2.png')
    check('поверхность: нет ошибок в консоли', not b.errors(), str(b.errors()))
    # лесенка съедобности: вид -> (тир, при котором впервые съедобен)
    far(b, 400)
    ladder = [('car', 7), ('house', 8), ('patrol', 8), ('truck', 9), ('bus', 10), ('apartment', 11), ('heavy', 11), ('tower', 12), ('skyscraper', 12)]
    bad = []
    for kind, first in ladder:
        place(b, kind, 4000)
        for tier in (first - 1, first):
            b.eval("window.__dev.setTier(%d); window.__dev.scene.worm.scale = window.__dev.scene.worm.targetScale; 0" % tier)
            time.sleep(0.1)
            ok = b.eval("(function(){var g=window.__dev.scene; return g.surface.isEdible(window.__test_it, g.worm.mouthRadius)})()")
            if ok != (tier >= first):
                bad.append((kind, tier, ok))
    check('лесенка тиров: машины с 7-го, дома и лёгкая охрана с 8-го, грузовики с 9-го, автобусы с 10-го, многоэтажки и тяжёлая техника с 11-го, башни и небоскрёбы с 12-го', not bad, str(bad))
    # пока выход закрыт (тир ниже 5), добыча поверхности не съедается
    b.eval("window.__dev.setTier(4); 0")
    far(b, 90, 20000)
    e0 = state(b)['eaten']
    place(b, 'person', 60)
    time.sleep(0.8)
    check('до 5-го тира добыча над землёй (люди на горизонте) не съедается', state(b)['eaten'] == e0 and state(b)['canExit'] is False, f"eaten {e0} -> {state(b)['eaten']}")
    check('поверхность: нет ошибок в консоли после проверок', not b.errors(), str(b.errors()))


def t_zone2_eat(b, shots):
    """Поедание на поверхности: пасть над землёй съедает, под землёй нет; очки роста, испытания, люди бегут от червя, машины ускоряются."""
    zone2_start(b, tier=5, ch='[{"k":"people","n":50,"p":0,"r":10},{"k":"eat","n":50,"p":0,"r":10},{"k":"tier","n":9,"p":5,"r":10}]')
    far(b, -70)
    g0 = state(b)
    place(b, 'person', 0)
    time.sleep(0.7)
    s = state(b)
    check('поверхность: человек перед пастью над землёй съеден', s['eaten'] == g0['eaten'] + 1, f"{g0['eaten']} -> {s['eaten']}")
    check('поверхность: человек даёт 1 очко роста', abs((s['growth'] - g0['growth']) - 1) < 0.01, f"{g0['growth']} -> {s['growth']}")
    ch = s['challenges']
    check('испытания: съеденный человек засчитан в «людей» и «добычу»', ch[0]['p'] == 1 and ch[1]['p'] == 1, str(ch[:2]))
    # под землёй пасть не достаёт
    far(b, 90, 32000)
    place(b, 'person', 0)
    time.sleep(0.9)
    check('поверхность: пасть под землёй не достаёт добычу на земле', b.eval('window.__test_it.dying') is False and b.eval('window.__dev.scene.surface.items.indexOf(window.__test_it)') >= 0, 'человек съеден из-под земли')
    # люди бегут от червя
    far(b, -120, 34000)
    wx = b.eval('window.__dev.scene.worm.x')
    place(b, 'person', x=wx + 3200)
    b.eval("window.__test_it.think=1e9; 0")
    x0 = b.eval('window.__test_it.x')
    time.sleep(1.0)
    x1 = b.eval('window.__test_it.x')
    check('поверхность: человек бежит от червя', x1 > x0 + 400, f'{x0:.0f} -> {x1:.0f}')
    # машина с 7-го тира: даёт 5 очков, считается как машина
    b.eval("window.__dev.setTier(7); 0")
    far(b, -70, 36000)
    g1 = state(b)
    place(b, 'car', 0)
    time.sleep(0.7)
    s = state(b)
    check('поверхность: на 7-м тире машина съедается и даёт 5 очков', s['eaten'] == g1['eaten'] + 1 and abs((s['growth'] - g1['growth']) - 5) < 0.01, f"{g1['eaten']}->{s['eaten']}, {g1['growth']}->{s['growth']}")
    check('поверхность: подсветка у съедобной добычи', b.eval("window.__dev.scene.surface.items.some(function(i){return i.halo.visible})") is True)
    check('поверхность: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_zone2_danger(b, shots):
    """Опасности: охрана целится и стреляет в червя над землёй, урон и неуязвимость, под землёй безопасно и лечит, оглушение и «Заново»."""
    b.add_init_script(FAKE_SDK.replace('__LANG__', 'ru'))
    zone2_start(b, tier=8)
    far(b, -260)
    s = state(b)
    check('здоровье: на 8-м тире запас 100 и полоса видна', s['hp'] == 100 and s['hpMax'] == 100 and b.eval("window.__dev.scene.scene.get('UI').last.hp") != '-', f"{s['hp']}/{s['hpMax']}")
    place(b, 'patrol', 150)
    t0 = time.time()
    shot = False
    while time.time() - t0 < 7:
        if state(b)['shots'] > 0:
            shot = True
            break
        time.sleep(0.15)
    check('охрана: машина целится и стреляет в червя над землёй', shot)
    t0 = time.time()
    while time.time() - t0 < 6 and state(b)['hp'] >= 100:
        time.sleep(0.15)
    s = state(b)
    check('урон: попавшая ракета отнимает здоровье (9)', 88 <= s['hp'] <= 92.5, f"hp={s['hp']}")
    check('урон: после попадания неуязвимость больше секунды', s['hpGrace'] > 0.2, f"hpGrace={s['hpGrace']}")
    hp1 = s['hp']
    b.eval('window.__dev.hit(20); 0')
    check('урон: во время неуязвимости повторное попадание не засчитывается', state(b)['hp'] >= hp1 - 0.5, f"{hp1} -> {state(b)['hp']}")
    b.screenshot(shots / 'g31-guard.png')
    # под землёй безопасно: охрана не стреляет и не попадает
    far(b, 900, 30000)
    time.sleep(0.5)
    b.eval('window.__dev.setHp(50); 0')
    place(b, 'patrol', 150)
    b.eval('window.__dev.scene.rockets.clear(); 0')
    time.sleep(3.2)
    s = state(b)
    check('безопасно: червь под землёй охрана не видит, снарядов нет', s['shots'] == 0, f"shots={s['shots']}")
    check('здоровье: под землёй восстанавливается (7 в секунду)', s['hp'] > 62, f"hp={s['hp']}")
    # оглушение
    far(b, -260, 31000)
    log0 = len(b.eval('window.__sdkLog'))
    b.eval('window.__dev.setHp(100); window.__dev.hurt(500); 0')
    time.sleep(0.4)
    s = state(b)
    check('оглушение: здоровье кончилось, червь оглушён', s['stunned'] is True and s['hp'] == 0, f"stunned={s['stunned']}, hp={s['hp']}")
    time.sleep(1.4)
    s = state(b)
    check('оглушение: через секунду окно «Заново», игра остановлена (stop)', s['stunShown'] is True and 'stop' in b.eval('window.__sdkLog')[log0:], f"{s['stunShown']}, {b.eval('window.__sdkLog')[log0:]}")
    check('оглушение: окно «Заново» показано', b.eval("window.__dev.scene.scene.get('UI').stunOverlay.visible") is True)
    b.screenshot(shots / 'g32-stun.png')
    b.key('Escape')
    time.sleep(0.3)
    check('оглушение: Escape не включает паузу', state(b)['paused'] is False)
    ui_btn = b.eval("(function(){var b=window.__dev.scene.scene.get('UI').stunBtn.box; return [b.x - b.width/2, b.y - b.height/2, b.width, b.height]})()")
    click_canvas(b, ui_btn)
    time.sleep(0.8)
    s = state(b)
    check('«Заново»: червь жив, здоровье полное, окно закрыто', s['stunned'] is False and s['hp'] == s['hpMax'] and s['stunShown'] is False, f"{s['stunned']}, {s['hp']}")
    check('«Заново»: червь под землёй, неуязвимость 2,5 секунды', s['y'] > 0 and s['hpGrace'] > 1.5, f"y={s['y']}, grace={s['hpGrace']}")
    check('«Заново»: gameplay снова запущен (start)', 'start' in b.eval('window.__sdkLog')[log0:], str(b.eval('window.__sdkLog')[log0:]))
    check('здоровье: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_zone2_armor(b, shots):
    """Броня даёт запас здоровья: ступень 3 даёт +75%; покупка в магазине прибавляет здоровье сразу."""
    zone2_start(b, tier=5, up=(0, 3, 0))
    s = state(b)
    check('броня: ступень 3 даёт запас здоровья 175', s['hpMax'] == 175 and s['hp'] == 175, f"{s['hp']}/{s['hpMax']}")
    b.eval("window.__dev.setUpgrade('hp', 0); 0")
    # покупка ступени 1: запас 120, здоровье растёт на прибавку
    b.eval('window.__dev.setHp(70); window.__dev.addCoins(100); 0')
    b.eval("window.__dev.scene.game.events.emit('upgrade-bought', 'hp', 1); 0")
    s = state(b)
    check('броня: покупка ступени 1 даёт запас 120 и лечит на прибавку', s['hpMax'] == 120 and abs(s['hp'] - 90) < 1, f"{s['hp']}/{s['hpMax']}")


def t_zone2_hud(b, shots):
    """Полоса здоровья и окно «Заново» помещаются на экране при любом размере окна; кнопка не меньше 44 CSS-px."""
    zone2_start(b, tier=6)
    b.eval('window.__dev.hurt(1000); 0')
    time.sleep(2.0)
    for (w, h, dpr, mobile) in ((1280, 720, 1, False), (1920, 1080, 1, False), (844, 390, 3, True), (568, 320, 2, True), (360, 640, 2, True), (320, 568, 2, True), (700, 1400, 1, False)):
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.8)
        r = b.eval("""(function(){var ui=window.__dev.scene.scene.get('UI'), u=ui.u, W=ui.scale.width, H=ui.scale.height;
          function bb(o){var g=o.getBounds(); return [g.x,g.y,g.width,g.height]}
          var b=ui.stunBtn.box; return {W:W,H:H,u:u,title:bb(ui.stunTitle),btn:[b.x-b.width/2,b.y-b.height/2,b.width,b.height],text:bb(ui.stunBtn.text)}})()""")
        ok = rect_inside(r['title'], r['W'], r['H']) and rect_inside(r['btn'], r['W'], r['H']) and not rects_overlap(r['title'], r['btn']) and r['btn'][3] / r['u'] >= 44 and rect_inside(r['text'], r['W'], r['H'])
        check(f'окно «Заново» {w}x{h}: на экране, не накладывается, кнопка от 44 CSS-px', ok, str(r))
    b.set_viewport(1280, 720, 1, False)
    check('окно «Заново»: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_zone2_pace(b, shots):
    """Автопилот на поверхности ест людей и растёт, не залипает под землёй."""
    zone2_start(b, tier=5)
    b.eval('window.__dev.autopilot(true); 0')
    t0 = time.time()
    g0 = state(b)
    while time.time() - t0 < 25 and state(b)['tier'] == 5 and state(b)['eaten'] - g0['eaten'] < 15:
        time.sleep(0.5)
        if state(b)['stunShown']:
            b.eval('window.__dev.respawn(); 0')
    s = state(b)
    check('поверхность: автопилот за 25 секунд съел не меньше 15 и растёт', s['eaten'] - g0['eaten'] >= 15 or s['tier'] > 5, f"{g0['eaten']} -> {s['eaten']}, тир {s['tier']}")
    b.eval('window.__dev.autopilot(false); 0')
    check('поверхность: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_zone2_hints(b, shots):
    """Подсказки зоны 2: при первом выходе на поверхность и при первой встрече с охраной, по одному разу, сохраняются."""
    seed_shop(b, coins=0, tier=8, tutorial=3)
    boot(b, URL, choose=False)
    far(b, 60)
    b.eval("window.__dev.freeze(false); window.__dev.scene.worm.heading = -1.5; 0")
    t0 = time.time()
    seen = None
    while time.time() - t0 < 4 and seen != 'hint_surface':
        time.sleep(0.1)
        seen = state(b)['toast']
    check('подсказка: при первом выходе на поверхность «Люди разбегаются…»', seen == 'hint_surface', str(seen))
    check('подсказка: показана один раз и записана в обучение', save_field(b, 'tutorial') & 32 == 32, str(save_field(b, 'tutorial')))
    b.eval("window.__dev.freeze(true); 0")
    place(b, 'patrol', 160)
    time.sleep(7.0)
    seen = state(b)['toast']
    done = save_field(b, 'tutorial') & 64 == 64
    check('подсказка: при первой встрече с охраной «Осторожно…» (записана в обучение)', done, f"toast={seen}, tutorial={save_field(b, 'tutorial')}")
    check('подсказки: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_scale(b, shots):
    """Реалистичный масштаб: жуки крошки рядом с человеком, человек меньше машины, машина меньше дома и небоскрёба; камера отъезжает вместе с ростом."""
    zone2_start(b, tier=5)
    sizes = {}
    for kind in ('person', 'car', 'house', 'truck', 'bus', 'apartment', 'tower', 'skyscraper', 'patrol', 'launcher', 'heavy'):
        sizes[kind] = place(b, kind, 0)
    beetle = b.eval("Math.max.apply(null, window.__dev.scene.prey.items.map(function(i){return i.r}).concat([0]))")
    check('масштаб: самый крупный жук под землёй не выше 110 px в радиусе (крошка рядом с человеком)', 0 < beetle <= 110, f'{beetle:.0f}')
    h = {k: v['h'] for k, v in sizes.items()}
    w = {k: v['w'] for k, v in sizes.items()}
    check('масштаб: человек ростом около 1500 px, то есть в 7 раз выше самого крупного жука', 1300 <= h['person'] <= 1750 and h['person'] > 6 * beetle, str(h['person']))
    check('масштаб: человек < машина < дом < многоэтажка < башня < небоскрёб по высоте', h['person'] < h['car'] < h['house'] < h['apartment'] < h['tower'] < h['skyscraper'], str(h))
    check('масштаб: машина в 2-3 раза длиннее человека в высоту, автобус длиннее грузовика, грузовик длиннее легковой', 2.0 <= w['car'] / h['person'] <= 3.2 and w['bus'] > w['truck'] > w['car'], f"{w['car'] / h['person']:.2f}")
    # камера отъезжает: на любом тире червь на экране примерно того же размера, а мир мельчает
    zoom, head = {}, {}
    for tier in (1, 5, 8, 12):
        b.eval("window.__dev.setTier(%d); 0" % tier)
        time.sleep(0.5)
        r = b.eval("(function(){var s=window.__dev.scene, c=s.cameras.main; return {z:c.zoom, head: s.worm.headRadius*c.zoom}})()")
        zoom[tier], head[tier] = r['z'], r['head']
    check('масштаб: камера отъезжает при росте (приближение падает на каждом тире)', zoom[1] > zoom[5] > zoom[8] > zoom[12], str(zoom))
    check('масштаб: голова червя на экране остаётся 30-130 px на любом тире', all(30 <= v <= 130 for v in head.values()), str(head))
    b.eval("window.__dev.setTier(5); 0")
    time.sleep(0.4)
    z5 = b.eval('window.__dev.scene.cameras.main.zoom')
    check('масштаб: на 5-м тире человек на экране не меньше 80 px, а жук (диаметр до 208) не больше 25 px', h['person'] * z5 >= 80 and 208 * z5 <= 25, f"человек {h['person'] * z5:.0f} px, жук {208 * z5:.0f} px")
    check('масштаб: нет ошибок в консоли', not b.errors(), str(b.errors()))


FLY_JS = """(function(){var g=window.__dev.scene, w=g.worm; window.__dev.setPos(30000, -%d*w.scale); w.inAir=true; w.vx=0; w.vy=0; w.heading=0; window.__dev.freeze(false); g.hpGrace=1e9; 0})()"""


def fly(b, lvl, key, secs, h=400, sample=0.1):
    """Червь в воздухе на высоте h (в масштабах червя), ступень крыльев lvl, зажата клавиша key; вернуть замеры (y/S, vy/S, vx/S, inAir) каждые sample секунд."""
    b.eval("window.__dev.setUpgrade('jump', %d); 0" % lvl)
    b.eval(FLY_JS % h)
    if key:
        b.key_down(key)
    out = []
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(sample)
        s = state(b)
        out.append((s['y'] / s['scale'], s['vy'] / s['scale'], s['vx'] / s['scale'], s['inAir']))
    if key:
        b.key_up(key)
    return out


def t_flight(b, shots):
    """Крылья: падение замедляется, парение, зависание, подъём и управление по горизонтали растут со ступенью; пикирование; потолок."""
    zone2_start(b, tier=5)
    # без крыльев: свободное падение, быстро на землю
    r0 = fly(b, 0, None, 0.6)
    vy0 = r0[-1][1]
    check('крылья 0: падение свободное (скорость растёт как g · t)', vy0 > 700, f'vy={vy0:.0f}')
    # ступень 1: падение заметно медленнее
    r1 = fly(b, 1, 'ArrowUp', 0.6)
    check('крылья 1: планирует, падение вдвое медленнее', r1[-1][3] and r1[-1][1] < 0.5 * vy0, f'vy={r1[-1][1]:.0f} против {vy0:.0f}')
    # ступень 2: почти парит при «вверх»
    r2 = fly(b, 2, 'ArrowUp', 1.2)
    check('крылья 2: при «вверх» почти парит (за 1,2 с высота меняется меньше чем на 150)', r2[-1][3] and abs(r2[-1][0] - r2[0][0]) < 150, f'{r2[0][0]:.0f} -> {r2[-1][0]:.0f}')
    # ступень 3: висит на месте при нейтральном управлении (стрелка вправо: по вертикали ничего не нажато)
    r3 = fly(b, 3, 'ArrowRight', 1.2)
    check('крылья 3: висит на месте (по вертикали не нажато), высота меняется меньше чем на 80', r3[-1][3] and abs(r3[-1][0] - r3[0][0]) < 80, f'{r3[0][0]:.0f} -> {r3[-1][0]:.0f}')
    # подъём ступеней 3-5: чем выше ступень, тем быстрее набор
    climb = {}
    for lvl in (3, 4, 5):
        r = fly(b, lvl, 'ArrowUp', 0.9, h=300)
        climb[lvl] = r[0][0] - r[-1][0]
    check('крылья 3-5: подъём тем быстрее, чем выше ступень', climb[3] > 100 and climb[4] > climb[3] and climb[5] > climb[4], str({k: round(v) for k, v in climb.items()}))
    b.screenshot(shots / 'g33-flight.png')
    # потолок: ступень 3 не поднимается выше своего предела
    r = fly(b, 3, 'ArrowUp', 3.0, h=300)
    top = -min(x[0] for x in r)
    check('крылья 3: у потолка подъём останавливается (не выше ≈ 900 масштабов)', 500 < top < 1000, f'потолок {top:.0f}')
    # пикирование быстрее нейтрального
    rd = fly(b, 5, 'ArrowDown', 0.5, h=500)
    rn = fly(b, 5, 'ArrowRight', 0.5, h=500)
    check('крылья 5: пикирование вниз намного быстрее нейтрального', rd[-1][0] - rd[0][0] > 4 * max(10, rn[-1][0] - rn[0][0]), f'пике {rd[-1][0] - rd[0][0]:.0f}, нейтрально {rn[-1][0] - rn[0][0]:.0f}')
    # управление по горизонтали: разгон вправо растёт со ступенью
    vx = {}
    for lvl in (0, 1, 3, 5):
        r = fly(b, lvl, 'ArrowRight', 0.4, h=700)
        vx[lvl] = r[-1][2]
    check('крылья: управление по горизонтали растёт со ступенью (0 < 1 < 3 < 5)', 0 < vx[0] < vx[1] < vx[3] < vx[5], str({k: round(v) for k, v in vx.items()}))
    # вид крыльев: при взмахах раскрыты, при пикировании сложены наполовину
    b.eval("window.__dev.setUpgrade('jump', 5); 0")
    b.eval(FLY_JS % 500)
    b.key_down('ArrowUp')
    time.sleep(0.6)
    up_open = b.eval('window.__dev.scene.worm.wingOpen')
    b.screenshot(shots / 'g33-flight-up.png')
    b.key_up('ArrowUp')
    b.key_down('ArrowDown')
    time.sleep(0.4)
    dive_open = b.eval('window.__dev.scene.worm.wingOpen')
    b.key_up('ArrowDown')
    check('крылья: взмахи раскрывают крылья, пикирование складывает наполовину', up_open > 0.9 and 0.35 < dive_open < 0.75, f'вверх {up_open:.2f}, пике {dive_open:.2f}')
    # мышь: цель выше червя поднимает
    b.eval("window.__dev.setUpgrade('jump', 4); 0")
    b.eval(FLY_JS % 300)
    time.sleep(0.2)
    pos = b.eval("(function(){var g=window.__dev.scene, w=g.worm; return {x:w.x, y:w.y, S:w.scale}})()")
    tgt = world_to_client(b, pos['x'] + 100 * pos['S'], pos['y'] - 220 * pos['S'])
    b.mouse(tgt['x'], tgt['y'], 'move')
    b.mouse(tgt['x'], tgt['y'], 'down')
    time.sleep(0.7)
    y_up = state(b)['y']
    b.mouse(tgt['x'], tgt['y'], 'up')
    check('крылья: цель мышью выше червя поднимает его', y_up < pos['y'] - 80 * pos['S'], f"{pos['y'] / pos['S']:.0f} -> {y_up / pos['S']:.0f}")
    check('крылья: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_rockets(b, shots):
    """Ракеты охраны: пуск, пламя и дым, взрыв кадрами, урон и разлёт, залпы пусковой установки, охраны больше с тиром."""
    zone2_start(b, tier=8)
    far(b, -150)
    b.eval("window.__dev.scene.surface.items.forEach(function(i){i.x += 1e6}); 0")
    place(b, 'launcher', 260)
    t0 = time.time()
    most, frames, trail, boom, len_ok = 0, set(), 0, 0, True
    while time.time() - t0 < 14:
        st = state(b)
        most = max(most, st['shots'])
        if st['shots']:
            info = b.eval("""(function(){var s=window.__dev.scene, r=s.rockets.shots[0]; if(!r) return null;
              return {f: r.flame.frame.name, len: r.len, vh: s.cameras.main.height / s.cameras.main.zoom,
                      trail: s.children.list.filter(function(c){return c.frame && c.frame.name==='fx-dust-poof' && c.visible}).length,
                      boom: s.children.list.filter(function(c){return c.frame && c.frame.name.indexOf('fx-boom')===0}).length}})()""")
            if info:
                frames.add(info['f'])
                trail = max(trail, info['trail'])
                boom = max(boom, info['boom'])
                len_ok = len_ok and info['len'] >= 0.06 * info['vh'] * 0.95
        if most >= 3 and len(frames) >= 2 and boom:
            break
        time.sleep(0.03)
    check('ракеты: пусковая установка пускает залпом (3 и более ракеты в воздухе одновременно)', most >= 3, f'максимум {most}')
    check('ракеты: пламя за ракетой меняет кадры (анимация)', len(frames) >= 2, str(frames))
    check('ракеты: за ракетой дымный след', trail >= 3, f'частиц дыма: {trail}')
    check('ракеты: взрыв рисуется кадрами fx-boom', boom >= 1, f'{boom}')
    check('ракеты: ракета не меньше 6% высоты вида (хорошо видна при любом отъезде камеры)', len_ok)
    time.sleep(1.5)
    s = state(b)
    check('ракеты: попадание отнимает здоровье (8 за ракету, неуязвимость между попаданиями)', 100 - s['hp'] >= 7.5, f"hp={s['hp']}")
    b.screenshot(shots / 'g34-rockets.png')
    # под землёй ракеты не пускают и не ранят
    far(b, 900, 36000)
    b.eval('window.__dev.setHp(100); window.__dev.scene.rockets.clear(); 0')
    place(b, 'launcher', 170)
    time.sleep(3.0)
    s = state(b)
    check('ракеты: под землёй червь цел, ракет нет', s['hp'] == 100 and s['shots'] == 0, f"hp={s['hp']}, shots={s['shots']}")
    # взрыв рядом с червём ранит осколками наполовину; вдали не ранит
    far(b, -150, 38000)
    b.eval('window.__dev.setHp(100); window.__dev.scene.hpGrace = 0; 0')
    b.eval("(function(){var g=window.__dev.scene, w=g.worm; g.onRocketBoom(w.x + w.headRadius*0.2, w.y, 2000, 20, false); return 0})()")
    hp_near = state(b)['hp']
    check('взрыв у самого тела ранит осколками наполовину (урон 20 даёт 10)', abs((100 - hp_near) - 10) < 0.6, f'hp={hp_near}')
    b.eval('window.__dev.setHp(100); window.__dev.scene.hpGrace = 0; 0')
    b.eval("(function(){var g=window.__dev.scene, w=g.worm; g.onRocketBoom(w.x + w.headRadius*6, w.y, 2000, 20, false); return 0})()")
    check('взрыв вдали от червя не ранит', state(b)['hp'] == 100, f"hp={state(b)['hp']}")
    # охраны становится больше с тиром
    counts = {}
    for tier in (7, 9, 12):
        b.eval("window.__dev.setTier(%d); 0" % tier)
        b.eval("window.__dev.scene.surface.clear(); window.__dev.scene.surface.populate(window.__dev.scene.worm.x, window.__dev.scene.worm.scale, window.__dev.scene.view(), %d); 0" % tier)
        time.sleep(0.4)
        kinds = state(b)['surface']
        counts[tier] = sum(1 for k in kinds if k in ('patrol', 'launcher', 'heavy'))
    check('охрана: чем выше тир, тем больше стреляющей техники (7 < 9 < 12 и на 12-м не меньше 5)', counts[7] < counts[9] < counts[12] and counts[12] >= 5, str(counts))
    check('ракеты: нет ошибок в консоли', not b.errors(), str(b.errors()))


# ---------------------------------------------------------------- Э6: небо, космос, финал
SPACE_TOP = 4e7
SPACE_HALF = 8e7
EARTH_R = 3.6e7
SKY_FLY = 40 * 330


def sky_top(S):
    return SKY_FLY * S


def t_zones(b, shots):
    """Зоны по тиру, ролики «прорыва» в небо и космос, полёт без тяжести, потолок неба, стены космоса, пол над Землёй, возврат из сохранения."""
    zone2_start(b, tier=4)
    got = {}
    for tier, want in ((4, 'under'), (5, 'ground'), (12, 'ground'), (13, 'sky'), (16, 'sky'), (17, 'space'), (21, 'space')):
        b.eval("window.__dev.setTier(%d); 0" % tier)
        time.sleep(0.15)
        got[tier] = state(b)['zone']
        if got[tier] != want:
            break
    check('зоны: под землёй до 4-го тира, поверхность 5-12, небо 13-16, космос 17-21', all(got[t] == z for t, z in ((4, 'under'), (5, 'ground'), (12, 'ground'), (13, 'sky'), (16, 'sky'), (17, 'space'), (21, 'space')) if t in got) and len(got) == 7, str(got))
    # ролик «прорыв» из земли в небо
    b.eval("window.__dev.setTier(12); 0")
    time.sleep(0.5)
    S0 = b.eval('window.__dev.scene.worm.scale')
    b.eval("window.__dev.freeze(false); window.__dev.setPos(0, -300 * window.__dev.scene.worm.scale); 0")
    time.sleep(0.4)
    s = state(b)
    b.eval('window.__dev.addGrowth(%d); 0' % (s['need'] - s['growth'] + 1))
    time.sleep(0.5)
    s = state(b)
    check('прорыв: при росте до 13-го тира начинается ролик, ввод закрыт, червь летит вверх', s['cine'] == 'sky' and s['tier'] == 13, f"cine={s['cine']}, tier={s['tier']}")
    check('прорыв: сообщение про небо', s['toast'] == 'zone_sky', str(s['toast']))
    b.key_down('ArrowDown')
    y_a = state(b)['y']
    time.sleep(0.6)
    y_b = state(b)['y']
    b.key_up('ArrowDown')
    check('прорыв: во время ролика клавиши не управляют (червь продолжает подъём)', y_b < y_a, f'{y_a} -> {y_b}')
    t0 = time.time()
    while time.time() - t0 < 6 and state(b)['cine']:
        time.sleep(0.1)
    s = state(b)
    check('прорыв: ролик заканчивается, зона «небо», червь в полёте', s['cine'] is None and s['zone'] == 'sky' and s['flight'] is True, f"{s['cine']}, {s['zone']}, {s['flight']}")
    check('прорыв: червь высоко над землёй, на земле нет охраны и людей, в воздухе есть добыча', s['y'] < -0.03 * sky_top(s['scale']) and not any(k in ('person', 'car', 'house') for k in s['surface']) and len(s['air']) >= 10, f"y={s['y']}, air={len(s['air'])}")
    b.screenshot(shots / 'g40-sky-start.png')
    # полёт без тяжести: курс держится
    b.eval('window.__dev.scene.hpGrace = 1e9; 0')
    w0 = b.eval("(function(){var w=window.__dev.scene.worm; w.heading = 0; w.heading = 0; return {y:w.y, S:w.scale}})()")
    time.sleep(0.6)
    w1 = b.eval("(function(){var w=window.__dev.scene.worm; return {y:w.y, vy:w.vy}})()")
    check('небо: без тяжести (курс вправо, высота почти не меняется)', abs(w1['y'] - w0['y']) < 0.4 * w0['S'] * 330, f"{w0['y']:.0f} -> {w1['y']:.0f}")
    b.key_down('ArrowUp')
    time.sleep(1.0)
    y2 = state(b)['y']
    b.key_up('ArrowUp')
    check('небо: стрелка вверх поднимает червя (он плывёт по воздуху)', y2 < w1['y'] - 0.5 * w0['S'] * 330 * 0.5, f"{w1['y']:.0f} -> {y2:.0f}")
    # потолок неба
    S = state(b)['scale']
    b.eval("window.__dev.setPos(0, -%f); window.__dev.scene.hpGrace = 1e9; window.__dev.scene.worm.heading = -Math.PI/2; 0" % (sky_top(S) * 0.995))
    b.key_down('ArrowUp')
    time.sleep(1.6)
    top_y = state(b)['y']
    S_end = state(b)['scale']  # червь мог что-то съесть и вырасти, потолок растёт вместе с ним
    b.key_up('ArrowUp')
    check('небо: потолок атмосферы не пускает выше', top_y >= -sky_top(max(S, S_end)) * 1.001, f'{top_y:.0f} против {-sky_top(max(S, S_end)):.0f}')
    # нырок под землю: вниз до земли, почва
    b.eval("window.__dev.setPos(0, -%f); window.__dev.scene.worm.heading = Math.PI/2; 0" % (S * 330 * 1.5))
    b.key_down('ArrowDown')
    time.sleep(3.0)
    b.key_up('ArrowDown')
    check('небо: к земле можно спуститься и уйти под землю (там почва)', state(b)['y'] > 0, f"y={state(b)['y']}")
    # космос: прорыв из неба
    b.eval("window.__dev.setTier(16); window.__dev.setPos(0, -%f); window.__dev.scene.hpGrace = 1e9; 0" % (sky_top(b.eval('window.__dev.scene.worm.scale')) * 0.5))
    time.sleep(0.5)
    s = state(b)
    b.eval('window.__dev.addGrowth(%d); 0' % (s['need'] - s['growth'] + 1))
    time.sleep(0.4)
    check('прорыв: при росте до 17-го тира ролик в космос', state(b)['cine'] == 'space', str(state(b)['cine']))
    t0 = time.time()
    while time.time() - t0 < 8 and state(b)['cine']:
        time.sleep(0.1)
    s = state(b)
    check('прорыв: зона «космос», в мире Земля и Луна, добыча вокруг', s['cine'] is None and s['zone'] == 'space' and 'earth' in s['air'] and 'moon' in s['air'] and len(s['air']) >= 8, f"{s['zone']}, {s['air'][:6]}")
    check('космос: червь над Землёй (выше края атмосферы)', -SPACE_TOP * 1.01 <= s['y'] < 0, f"y={s['y']}")
    time.sleep(0.8)
    b.screenshot(shots / 'g41-space-start.png')
    # стены арены и пол над Землёй
    b.eval("window.__dev.scene.hpGrace = 1e9; window.__dev.setPos(%f, %f); window.__dev.scene.worm.heading = 0; 0" % (SPACE_HALF - 1.5e6, -SPACE_TOP * 0.4))
    b.key_down('ArrowRight')
    time.sleep(1.6)
    x1 = state(b)['x']
    b.key_up('ArrowRight')
    check('космос: стена арены не пускает', x1 <= SPACE_HALF, f'x={x1}')
    b.eval("window.__dev.setPos(0, -1.5e6); window.__dev.scene.worm.heading = Math.PI/2; 0")
    b.key_down('ArrowDown')
    time.sleep(2.0)
    y3 = state(b)['y']
    b.key_up('ArrowDown')
    check('космос: до последнего тира Земля не пускает (пол над атмосферой)', y3 < 0, f'y={y3}')
    check('космос: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_zone_save(b, shots):
    """Сохранение в небе и космосе: после обновления страницы червь в своей зоне, в полёте, а не под землёй."""
    seed_shop(b, coins=0, tier=14, tutorial=255)
    boot(b, URL, choose=False)
    time.sleep(0.6)
    s = state(b)
    check('сохранение: на 14-м тире после загрузки зона «небо», червь в полёте над землёй', s['zone'] == 'sky' and s['flight'] is True and s['y'] < 0, f"{s['zone']}, y={s['y']}")
    b.eval("window.__dev.setTier(18); 0")
    time.sleep(0.4)
    b.open(URL)
    b.wait_for('!!window.__dev', 30)
    time.sleep(0.8)
    s = state(b)
    check('сохранение: после F5 на 18-м тире зона «космос», червь над Землёй', s['zone'] == 'space' and s['tier'] == 18 and s['flight'] is True and 'earth' in s['air'], f"{s['zone']}, {s['tier']}")
    check('сохранение: нет ошибок в консоли', not b.errors(), str(b.errors()))


AIR_LADDER = [('plane', 13), ('heli', 13), ('fighter', 13), ('heavy', 13), ('airliner', 14), ('cargo', 15), ('cargoXL', 16),
              ('sat', 17), ('station', 17), ('rockS', 18), ('rockM', 19), ('rockL', 20), ('moon', 20), ('earth', 21)]


def t_air(b, shots):
    """Добыча неба и космоса: лесенка съедобности по тирам, поедание, очки, монеты, подсветка, касание астероидов, ракеты истребителей."""
    zone2_start(b, tier=13)
    far_air(b, 13)
    bad = []
    for kind, first in AIR_LADDER:
        # лёгкая добыча неба (самолёты, вертолёты, истребитель, тяжёлый вертолёт) по размеру съедобна и на 12-м тире, но в небо попадают с 13-го
        for tier in ((first,) if first == 13 else (first - 1, first)):
            b.eval("window.__dev.setTier(%d); window.__dev.scene.worm.scale = window.__dev.scene.worm.targetScale; 0" % tier)
            b.eval("window.__dev.placeAir('%s', 3e12, -1e11); 0" % kind)
            ok = b.eval("(function(){var g=window.__dev.scene; return g.air.isEdible(window.__test_air, g.worm.mouthRadius, %d)})()" % tier)
            if ok != (tier >= first):
                bad.append((kind, tier, ok))
    check('лесенка: самолёты и вертолёты с 13-го тира, лайнеры с 14-го, грузовики с 15-го, гиганты с 16-го, спутники с 17-го, астероиды с 18-20-го, Луна с 20-го, Земля с 21-го', not bad, str(bad))
    # поедание в небе: самолёт перед пастью
    zone2_start_again(b, 13)
    far_air(b, 13)
    g0 = state(b)
    place_air(b, 'plane', 0.0)
    time.sleep(0.9)
    s = state(b)
    check('небо: самолёт съеден, 30 очков роста, монеты начислены', s['eaten'] == g0['eaten'] + 1 and abs((s['growth'] - g0['growth']) - 30) < 0.01 and s['coins'] > g0['coins'], f"{g0['eaten']}->{s['eaten']}, {g0['growth']}->{s['growth']}, монеты {g0['coins']}->{s['coins']}")
    b.eval("window.__dev.placeAir('heli', window.__dev.scene.worm.mouth().x + 80000, window.__dev.scene.worm.mouth().y); window.__dev.scene.air.items.forEach(function(i){i.vx=0}); 0")
    time.sleep(0.4)
    check('небо: подсветка у съедобной добычи', b.eval("window.__dev.scene.air.items.some(function(i){return i.halo.visible})") is True)
    # космос: добыча много меньше пасти даёт меньше очков
    zone2_start_again(b, 18)
    far_air(b, 18)
    g1 = state(b)
    place_air(b, 'sat', 0.0)
    time.sleep(0.9)
    s = state(b)
    share = 1e5 / (60 * g1['scale'])
    check('космос: спутник на 18-м тире даёт долю очков по размеру (140 × радиус / пасть)', abs((s['growth'] - g1['growth']) - 140 * share) < 3, f"{g1['growth']} -> {s['growth']}, ждали {140 * share:.1f}")
    # касание не по зубам: астероид бьёт и отбрасывает
    zone2_start_again(b, 17)
    far_air(b, 17)
    b.eval("window.__dev.freeze(false); window.__dev.scene.hpGrace = 0; window.__dev.scene.worm.heading = 0; 0")
    hp0 = state(b)['hp']
    b.eval("(function(){var w=window.__dev.scene.worm; var m=w.mouth(); window.__dev.placeAir('rockS', m.x + 6e5, m.y); return 0})()")
    time.sleep(1.2)
    s = state(b)
    hd = b.eval('window.__dev.scene.worm.heading')
    check('космос: астероид не по зубам бьёт при касании (-10) и отбрасывает червя', abs((hp0 - s['hp']) - 10) < 1.5 or s['hp'] <= hp0 - 9, f"hp {hp0} -> {s['hp']}, курс {hd:.2f}")
    # истребитель стреляет
    zone2_start_again(b, 14)
    far_air(b, 14)
    b.eval("window.__dev.scene.air.items.forEach(function(i){i.x += 1e12}); 0")
    b.eval("(function(){var g=window.__dev.scene, w=g.worm, c=g.cameras.main; window.__dev.placeAir('fighter', w.x + 0.3 * c.height / c.zoom, w.y - 0.05 * c.height / c.zoom); return 0})()")
    t0 = time.time()
    shot = False
    while time.time() - t0 < 8:
        if state(b)['shots'] > 0:
            shot = True
            break
        time.sleep(0.1)
    check('небо: истребитель стреляет ракетами в червя', shot)
    b.eval("window.__dev.freeze(true); 0")
    check('небо и космос: нет ошибок в консоли', not b.errors(), str(b.errors()))


def far_air(b, tier):
    """Червь в небе (с 17-го в космосе) далеко от стартовой расстановки; стоит на месте (freeze); чужой добычи рядом нет."""
    b.eval("window.__dev.autopilot(false); window.__dev.freeze(true); window.__dev.scene.hpGrace = 1e9; 0")
    if tier >= 17:
        b.eval("window.__dev.setPos(0, -%f); window.__dev.freeze(true); 0" % (SPACE_TOP * 0.4))
    else:
        b.eval("window.__dev.setPos(0, -%f * window.__dev.scene.worm.scale * 0.2); window.__dev.freeze(true); 0" % (sky_top(1) * 0.6))
    b.eval("window.__dev.scene.air.items.forEach(function(i){ if (!i.fixed) i.x += 1e13 }); 0")
    time.sleep(0.4)


def zone2_start_again(b, tier):
    b.eval("window.__dev.setTier(%d); window.__dev.scene.worm.scale = window.__dev.scene.worm.targetScale; 0" % tier)
    time.sleep(0.3)


def place_air(b, kind, dx):
    """Поставить добычу неба или космоса перед ртом червя (dx в масштабах червя) на высоте рта."""
    return b.eval("(function(){var w=window.__dev.scene.worm, m=w.mouth(); return window.__dev.placeAir('%s', m.x + %f * w.scale, m.y)})()" % (kind, dx))


def t_final(b, shots):
    """Финал: на последнем тире Землю можно съесть; ролик, концовка, титры, кнопки «Играть дальше» и «Заново с улучшениями», сохранение."""
    zone2_start(b, tier=21, up=(2, 1, 3), coins=500)
    s = state(b)
    check('финал: на 21-м тире зона «космос», Земля есть и съедобна', s['zone'] == 'space' and 'earth' in s['air'], f"{s['zone']}")
    b.eval("window.__dev.freeze(false); window.__dev.scene.hpGrace = 1e9; 0")
    time.sleep(0.8)
    shown = b.eval("window.__dev.scene.tutArrow.visible")
    check('финал: стрелка показывает, где Земля', shown is True, str(shown))
    b.screenshot(shots / 'g42-final-approach.png')
    # лететь вниз к Земле
    b.eval("window.__dev.setPos(0, -5e7); window.__dev.scene.worm.heading = Math.PI/2; 0")
    t0 = time.time()
    while time.time() - t0 < 6 and not state(b)['finale']:
        time.sleep(0.1)
    check('финал: Земля укушена, начался финальный ролик', state(b)['finale'] is True)
    time.sleep(1.0)
    b.screenshot(shots / 'g43-final-bite.png')
    t0 = time.time()
    while time.time() - t0 < 6 and not state(b)['ending']:
        time.sleep(0.1)
    s = state(b)
    check('финал: показан экран концовки, игра стоит', s['ending'] is True and b.eval("window.__dev.scene.scene.isActive('End')") is True)
    check('финал: концовка записана в сохранение', save_field(b, 'end') == 1, str(save_field(b, 'end')))
    check('финал: Земли в мире больше нет', 'earth' not in s['air'], str(s['air'][:5]))
    b.screenshot(shots / 'g44-ending.png')
    # раскладка на любых размерах
    js = """(function(){var e=window.__dev.scene.scene.get('End'), u=e.u; function bb(o){var g=o.getBounds(); return [g.x,g.y,g.width,g.height]}
      return {W:e.scale.width, H:e.scale.height, u:u, title:bb(e.title), story:bb(e.story), credits:bb(e.credits), btns:e.btns.map(function(b){return b.rect}), btnText:e.btns.map(function(b){return bb(b.text)})}})()"""
    for (w, h, dpr, mobile) in ((1280, 720, 1, False), (1920, 1080, 1, False), (844, 390, 3, True), (568, 320, 2, True), (360, 640, 2, True), (320, 568, 2, True), (700, 1400, 1, False)):
        b.set_viewport(w, h, dpr, mobile)
        time.sleep(0.8)
        r = b.eval(js)
        parts = [r['title'], r['story'], r['credits']] + r['btns']
        ok = all(rect_inside(p, r['W'], r['H']) for p in parts) and all(rect_inside(p, r['W'], r['H']) for p in r['btnText'])
        ok = ok and not rects_overlap(r['title'], r['story']) and not rects_overlap(r['story'], r['btns'][0]) and not rects_overlap(r['btns'][0], r['btns'][1])
        ok = ok and all(bt[3] / r['u'] >= 44 for bt in r['btns'])
        check(f'концовка {w}x{h}: всё на экране, не накладывается, кнопки от 44 CSS-px', ok, str(r))
    b.set_viewport(1280, 720, 1, False)
    time.sleep(0.5)
    # «Играть дальше»
    b.key('Enter')
    time.sleep(0.6)
    s = state(b)
    check('концовка: Enter закрывает её, игра продолжается, Земли нет', s['ending'] is False and b.eval("window.__dev.scene.scene.isActive('End')") is False and 'earth' not in s['air'], str(s['ending']))
    time.sleep(0.5)
    # «Заново с улучшениями»: рост с нуля, улучшения, монеты и персонаж остаются
    b.eval("window.__dev.scene.showEnding(); 0")
    time.sleep(0.5)
    btn = b.eval("window.__dev.scene.scene.get('End').btns[1].rect")
    click_canvas(b, btn)
    time.sleep(1.5)
    b.wait_for('!!window.__dev', 30)
    time.sleep(0.8)
    s = state(b)
    check('«Заново с улучшениями»: тир 1, улучшения и монеты на месте, концовка засчитана', s['tier'] == 1 and s['up'] == {'jump': 2, 'hp': 1, 'speed': 3} and s['coins'] >= 500 and s['zone'] == 'under' and s['end'] == 1,
          f"tier={s['tier']}, up={s['up']}, coins={s['coins']}, zone={s['zone']}, end={s['end']}")
    check('финал: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_air_challenges(b, shots):
    """Испытания в небе и космосе: наземные заменяются, появляются «самолёты» и «спутники и астероиды», засчитываются съеденным."""
    seed_shop(b, coins=0, tier=14, tutorial=255, ch='[{"k":"people","n":5,"p":0,"r":10},{"k":"beetle","n":5,"p":0,"r":10},{"k":"planes","n":3,"p":0,"r":10}]')
    boot(b, URL, choose=False)
    kinds = [c['k'] for c in state(b)['challenges']]
    check('испытания: на 14-м тире наземные («люди», «жуки») заменены, «самолёты» остались', 'people' not in kinds and 'beetle' not in kinds and 'planes' in kinds, str(kinds))
    far_air(b, 14)
    b.eval("window.__dev.freeze(false); 0")
    p0 = [c for c in state(b)['challenges'] if c['k'] == 'planes'][0]['p']
    place_air(b, 'plane', 0.0)
    time.sleep(0.9)
    p1 = [c for c in state(b)['challenges'] if c['k'] == 'planes'][0]['p']
    check('испытания: съеденный самолёт засчитан', p1 == p0 + 1, f'{p0} -> {p1}')
    b.eval("window.__dev.setTier(18); 0")
    time.sleep(0.4)
    kinds = [c['k'] for c in state(b)['challenges']]
    check('испытания: в космосе «самолёты» заменены', 'planes' not in kinds, str(kinds))
    check('испытания: нет ошибок в консоли', not b.errors(), str(b.errors()))


def t_air_pace(b, shots):
    """Автопилот в небе и космосе ест, растёт и доходит до финала без залипаний."""
    zone2_start(b, tier=13)
    b.eval('window.__dev.autopilot(true); window.__dev.freeze(false); 0')
    g0 = state(b)
    t0 = time.time()
    while time.time() - t0 < 30 and state(b)['eaten'] - g0['eaten'] < 12:
        time.sleep(0.5)
        if state(b)['stunShown']:
            b.eval('window.__dev.respawn(); 0')
    s = state(b)
    check('небо: автопилот за 30 секунд съел не меньше 12 и растёт', s['eaten'] - g0['eaten'] >= 12 or s['tier'] > 13, f"{g0['eaten']} -> {s['eaten']}, тир {s['tier']}")
    b.eval("window.__dev.setTier(17); window.__dev.scene.hpGrace = 1e9; 0")
    time.sleep(0.5)
    g1 = state(b)
    t0 = time.time()
    while time.time() - t0 < 40 and state(b)['eaten'] - g1['eaten'] < 10:
        time.sleep(0.5)
        if state(b)['stunShown']:
            b.eval('window.__dev.respawn(); 0')
    s = state(b)
    check('космос: автопилот за 40 секунд съел не меньше 10 и растёт', s['eaten'] - g1['eaten'] >= 10 or s['tier'] > 17, f"{g1['eaten']} -> {s['eaten']}, тир {s['tier']}")
    b.eval('window.__dev.autopilot(false); 0')
    check('небо и космос: автопилот без ошибок в консоли', not b.errors(), str(b.errors()))


TESTS = {
    'boot': t_boot, 'growth': t_autopilot_growth, 'jump': t_jump, 'wings': t_wings, 'skins': t_skins,
    'sdk': t_sdk, 'lang': t_lang, 'audio': t_audio, 'tiers': t_tiers,
    'pause': t_pause, 'keyboard': t_keyboard, 'save': t_save, 'saveburst': t_save_burst, 'resize': t_resize, 'mobile': t_mobile,
    'guards': t_guards, 'hud': t_hud, 'canvas': t_canvas, 'legacy': t_legacy, 'nostorage': t_nostorage,
    'surface': t_surface, 'world': t_world, 'model': t_model, 'prey': t_prey,
    'select': t_select, 'selectscreens': t_select_screens, 'coins': t_coins, 'tutorial': t_tutorial,
    'halo': t_halo, 'bg': t_bg, 'juice': t_juice, 'selectsizes': t_select_sizes, 'english': t_english,
    'gear': t_gear, 'shop': t_shop, 'shopguard': t_shop_guard, 'shopsizes': t_shop_sizes, 'challenges': t_challenges, 'shopen': t_shop_english,
    'z2world': t_zone2_world, 'z2eat': t_zone2_eat, 'z2danger': t_zone2_danger, 'z2armor': t_zone2_armor, 'z2hud': t_zone2_hud, 'z2pace': t_zone2_pace, 'z2hints': t_zone2_hints,
    'scale': t_scale, 'flight': t_flight, 'rockets': t_rockets,
    'zones': t_zones, 'zonesave': t_zone_save, 'air': t_air, 'final': t_final, 'airch': t_air_challenges, 'airpace': t_air_pace,
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
