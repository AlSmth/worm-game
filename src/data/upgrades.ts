import wingsData from '../../design/upgrades/wings/wings.json';

/** Три линии улучшений по 5 ступеней (концепт, раздел 9). Ступень 0 — червь без деталей. */
export const MAX_UPGRADE = 5;

export interface Upgrades {
  jump: number; // крылья
  hp: number; // броня
  speed: number; // чешуя
}

export const NO_UPGRADES: Upgrades = { jump: 0, hp: 0, speed: 0 };

/** Прибавка высоты прыжка по ступеням (доля от базовой). Числа предварительные, настроим на Э4. */
export const JUMP_BONUS = [0, 0.2, 0.4, 0.65, 0.95, 1.35];

/** Прибавка скорости по ступеням (доля от базовой). */
export const SPEED_BONUS = [0, 0.08, 0.16, 0.25, 0.35, 0.5];

export const WINGS_CANVAS: number = wingsData.canvas;
/** Длина крыла по ступеням (px при масштабе 1:1), индекс = ступень. */
export const WING_LENGTH: number[] = [0, ...wingsData.tiers.map((x) => x.L)];

export function clampLevel(n: unknown): number {
  const v = typeof n === 'number' && Number.isFinite(n) ? Math.round(n) : 0;
  return Math.max(0, Math.min(MAX_UPGRADE, v));
}
