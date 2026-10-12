import wingsData from '../../design/upgrades/wings/wings.json';
import type { TextKey } from '../core/i18n';

/**
 * Три линии улучшений по 5 ступеней (концепт, раздел 9). Ступень 0 — червь без деталей.
 * Прыжок даёт крылья, здоровье даёт броню (чешуя превращается в рога), скорость даёт гребень и плавники.
 * Все числа здесь, чтобы балансировать без правки кода.
 */
export const MAX_UPGRADE = 5;

export type LineId = 'jump' | 'hp' | 'speed';

/** Порядок линий в магазине. */
export const LINES: readonly LineId[] = ['jump', 'hp', 'speed'];

export interface Upgrades {
  jump: number; // крылья
  hp: number; // броня
  speed: number; // гребень и плавники
}

export const NO_UPGRADES: Upgrades = { jump: 0, hp: 0, speed: 0 };

/** Цена покупки ступени 1…5 в монетах (индекс = ступень − 1). Растёт примерно в 2,4 раза за ступень (концепт, раздел 8). */
export const PRICES = [25, 60, 150, 350, 800];

/** Прибавка высоты прыжка по ступеням (доля от базовой). */
export const JUMP_BONUS = [0, 0.2, 0.4, 0.65, 0.95, 1.35];

/**
 * Полёт на крыльях по ступеням 0…5 (прыжок + парение). Всё в долях силы тяжести g или в px при масштабе червя 1.
 * Ступень 1 замедляет падение, ступень 2 почти парит, с 3-й червь висит в воздухе на месте, с 4-й и 5-й быстро набирает высоту.
 * Намерение игрока по вертикали (палец или стрелки выше/ниже червя): вверх — взмахи, вровень — парение, вниз — пикирование.
 */
/** Ускорение вниз при нейтральном управлении (доля g): 1 — свободное падение, 0 — висит на месте. */
export const WING_SINK = [1, 0.6, 0.3, 0, 0, 0];
/** Ускорение вниз при «вверх» (доля g): положительное только замедляет падение, отрицательное — набор высоты. */
export const WING_UP = [1, 0.3, -0.1, -0.6, -1.2, -2.0];
/** Потолок парения над землёй, px: выше крылья уже не поднимают. */
export const WING_CEIL = [0, 0, 480, 820, 1400, 2300];
/** Во сколько раз сильнее управление по горизонтали (множитель к воздушному ускорению). */
export const WING_STEER = [1, 1.6, 2.4, 3.3, 4.4, 5.6];
/** Предел скорости по горизонтали в воздухе в скоростях плавания червя. */
export const WING_VMAX = [2.2, 2.4, 2.7, 3.0, 3.4, 3.8];
/** Предел скорости набора высоты в скоростях плавания. */
export const WING_CLIMB = [0, 0, 1.0, 1.4, 1.9, 2.6];
/** Быстрое падение при пикировании (доля g). */
export const WING_DIVE = 1.6;

/** Прибавка скорости по ступеням (доля от базовой). */
export const SPEED_BONUS = [0, 0.08, 0.16, 0.25, 0.35, 0.5];

/** Прибавка запаса здоровья по ступеням (доля от базового). Здоровье начнёт работать с опасностями зоны 2 (Э5). */
export const HP_BONUS = [0, 0.2, 0.45, 0.75, 1.1, 1.6];

const BONUS: Record<LineId, number[]> = { jump: JUMP_BONUS, hp: HP_BONUS, speed: SPEED_BONUS };

/** Прибавка линии на ступени level в процентах для показа игроку. */
export function bonusPercent(line: LineId, level: number): number {
  return Math.round((BONUS[line][clampLevel(level)] ?? 0) * 100);
}

/** Цена следующей ступени, если червь сейчас на ступени level; null, если уже максимум. */
export function priceFor(level: number): number | null {
  const l = clampLevel(level);
  return l >= MAX_UPGRADE ? null : PRICES[l];
}

/** Ключ названия ступени (level от 1 до 5) в словаре: «крылья», «броня» или «гребень». */
export function levelNameKey(line: LineId, level: number): TextKey {
  const p = line === 'jump' ? 'wings' : line === 'hp' ? 'armor' : 'fins';
  return `${p}.${Math.max(1, Math.min(MAX_UPGRADE, level))}` as TextKey;
}

/** Можно ли купить хоть одно улучшение за имеющиеся монеты. */
export function canAffordAny(up: Upgrades, coins: number): boolean {
  return LINES.some((l) => {
    const p = priceFor(up[l]);
    return p !== null && coins >= p;
  });
}

export const WINGS_CANVAS: number = wingsData.canvas;
/** Длина крыла по ступеням (px при масштабе 1:1), индекс = ступень. */
export const WING_LENGTH: number[] = [0, ...wingsData.tiers.map((x) => x.L)];

export function clampLevel(n: unknown): number {
  const v = typeof n === 'number' && Number.isFinite(n) ? Math.round(n) : 0;
  return Math.max(0, Math.min(MAX_UPGRADE, v));
}
