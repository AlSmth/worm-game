import type { SkinId } from '../data/skins';
import type { ChallengeKind } from '../data/challenges';
import type { SurfaceKind } from '../data/surface';
import type { AirKind } from '../data/air';

/** Панель разработчика: только в dev-сборке (в релиз не попадает, п. 1.14: никакой «кухни» на экране). */
export interface DevApi {
  state(): Record<string, unknown>;
  setSkin(id: SkinId): void;
  setUpgrade(line: 'jump' | 'hp' | 'speed', level: number): void;
  addGrowth(n: number): void;
  setTier(n: number): void;
  autopilot(on: boolean): void;
  setPos(x: number, y: number): void;
  world(): { width: number; surfaceTier: number; half: number };
  addCoins(n: number): void;
  openSelect(): void;
  openShop(): void;
  placeSurface(kind: SurfaceKind, x: number): { r: number; cy: number; w: number; h: number };
  placeAir(kind: AirKind, x: number, y: number): { r: number; w: number; h: number };
  setHp(n: number): void;
  hit(n: number): void;
  hurt(n: number): void;
  respawn(): void;
  freeze(on: boolean): void;
  reportChallenge(kind: ChallengeKind, amount: number): void;
  resetTutorial(): void;
  resetSave(): void;
}

export function mountDevPanel(api: DevApi): void {
  const el = document.createElement('div');
  el.style.cssText =
    'position:fixed;left:8px;bottom:8px;z-index:20;background:rgba(20,22,31,.88);color:#eee;font:12px/1.5 system-ui,sans-serif;' +
    'padding:8px 10px;border-radius:10px;max-width:280px;user-select:none;-webkit-user-select:none';
  const btn = (label: string, id: string) =>
    `<button data-id="${id}" style="margin:2px 2px 0 0;padding:3px 7px;border:0;border-radius:6px;background:#3a4066;color:#fff;cursor:pointer;font:inherit">${label}</button>`;
  el.innerHTML =
    '<b>DEV</b> <span id="dv-info" style="color:#9aa0b8"></span>' +
    '<div>Персонаж: ' + btn('A', 'skin:peach') + btn('B', 'skin:salad') + btn('C', 'skin:plum') + '</div>' +
    '<div>Крылья: ' + [0, 1, 2, 3, 4, 5].map((n) => btn(String(n), 'wings:' + n)).join('') + '</div>' +
    '<div>Броня: ' + [0, 1, 2, 3, 4, 5].map((n) => btn(String(n), 'armor:' + n)).join('') + '</div>' +
    '<div>Гребень: ' + [0, 1, 2, 3, 4, 5].map((n) => btn(String(n), 'fins:' + n)).join('') + '</div>' +
    '<div>Рост: ' + btn('+10', 'grow:10') + btn('+100', 'grow:100') + btn('тир +1', 'tier:+1') + btn('тир −1', 'tier:-1') + '</div>' +
    '<div>Монеты: ' + btn('+10', 'coins:10') + btn('+100', 'coins:100') + btn('выбор червя', 'select') + btn('магазин', 'shop') + btn('обучение заново', 'tut') + '</div>' +
    '<div>' + btn('автопилот', 'auto') + btn('сброс сохранения', 'reset') + '</div>';
  let auto = false;
  let tier = 1;
  el.addEventListener('click', (ev) => {
    const b = (ev.target as HTMLElement).closest('button');
    if (!b) return;
    const [kind, arg] = (b.dataset.id ?? '').split(':');
    if (kind === 'skin') api.setSkin(arg as SkinId);
    else if (kind === 'wings') api.setUpgrade('jump', Number(arg));
    else if (kind === 'armor') api.setUpgrade('hp', Number(arg));
    else if (kind === 'fins') api.setUpgrade('speed', Number(arg));
    else if (kind === 'shop') api.openShop();
    else if (kind === 'grow') api.addGrowth(Number(arg));
    else if (kind === 'coins') api.addCoins(Number(arg));
    else if (kind === 'select') api.openSelect();
    else if (kind === 'tut') api.resetTutorial();
    else if (kind === 'tier') {
      tier = Number(api.state().tier) + Number(arg);
      api.setTier(tier);
    } else if (kind === 'auto') {
      auto = !auto;
      api.autopilot(auto);
      b.style.background = auto ? '#2f8f46' : '#3a4066';
    } else if (kind === 'reset') api.resetSave();
    b.blur();
  });
  // не даём панели управлять червём
  ['pointerdown', 'pointermove', 'pointerup'].forEach((n) => el.addEventListener(n, (e) => e.stopPropagation()));
  document.body.appendChild(el);
  const info = el.querySelector('#dv-info') as HTMLElement;
  window.setInterval(() => {
    const s = api.state();
    info.textContent = `тир ${s.tier} · ${s.fps} fps · ${s.skin} · кр ${s.wings} бр ${s.armor} гр ${s.fins} · монет ${s.coins}`;
  }, 300);
}
