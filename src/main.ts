import Phaser from 'phaser';
import { platform } from './platform/platform';
import { save } from './platform/save';
import { setLang } from './core/i18n';
import { sfx } from './core/audio';
import { computeLayout } from './core/layout';
import { state } from './core/state';
import { BootScene } from './scenes/BootScene';
import { GameScene } from './scenes/GameScene';
import { UIScene } from './scenes/UIScene';
import { SelectScene } from './scenes/SelectScene';

/**
 * Никаких системных меню, выделения, масштабирования щипком и прокрутки (пп. 1.6.1.8, 1.6.2.7, 1.10.2).
 * Масштаб страницы браузера (Ctrl+колесо, Ctrl+плюс) не блокируем: им проверяют игру при 80–125%, игра подстраивается.
 */
function installGuards(): void {
  const stop = (e: Event) => e.preventDefault();
  window.addEventListener('contextmenu', stop);
  document.addEventListener('selectstart', stop);
  document.addEventListener('dragstart', stop);
  ['gesturestart', 'gesturechange', 'gestureend'].forEach((n) => document.addEventListener(n, stop));
  document.addEventListener('touchmove', stop, { passive: false });
}

async function boot(): Promise<void> {
  installGuards();
  await platform.init();
  if (import.meta.env.DEV) (window as unknown as { __platform: typeof platform }).__platform = platform;
  setLang(platform.lang);
  await save.init();
  sfx.setMuted(!save.data.sound);

  const layout = computeLayout();
  state.layout = layout;

  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game',
    width: layout.width,
    height: layout.height,
    backgroundColor: '#1d1410',
    scale: { mode: Phaser.Scale.NONE, zoom: 1 / layout.dpr },
    audio: { noAudio: true }, // звук только через наш Web Audio (без <audio>)
    banner: false,
    disableContextMenu: true,
    render: { antialias: true, powerPreference: 'high-performance' },
    fps: { target: 60, smoothStep: true },
    // колесо мыши игре не нужно, а Phaser по умолчанию гасит его и мешает масштабу страницы браузера (Ctrl+колесо)
    input: { activePointers: 3, mouse: { preventDefaultWheel: false } },
    scene: [BootScene, GameScene, UIScene, SelectScene],
  });

  // CSS-размер холста задаём сами: Phaser при нулевом зуме оставляет прежний
  const setCanvasCss = () => {
    const c = game.canvas;
    if (!c) return;
    c.style.width = `${state.layout.cssW}px`;
    c.style.height = `${state.layout.cssH}px`;
  };
  game.events.once(Phaser.Core.Events.READY, setCanvasCss);
  game.scale.on(Phaser.Scale.Events.RESIZE, setCanvasCss);

  // Размер окна, поворот экрана, выход из полного экрана: поле всегда на всю область (п. 1.10)
  const apply = () => {
    const l = computeLayout();
    const c = state.layout;
    if (l.width === c.width && l.height === c.height && l.dpr === c.dpr) return;
    state.layout = l;
    game.scale.setZoom(1 / l.dpr);
    game.scale.resize(l.width, l.height);
  };
  let raf = 0;
  const schedule = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(apply);
  };
  window.addEventListener('resize', schedule);
  window.visualViewport?.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', () => window.setTimeout(schedule, 150));
  const host = document.getElementById('game');
  if (host && typeof ResizeObserver !== 'undefined') new ResizeObserver(schedule).observe(host);
}

boot().catch((e) => console.error('Не удалось запустить игру', e));
