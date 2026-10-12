import { HP_BONUS } from './upgrades';

/**
 * Зона 2 «Поверхность»: добыча над землёй (люди, машины, дома, техника охраны), здоровье и урон.
 * Все числа здесь, чтобы балансировать без правки кода (концепт, разделы 3, 5 и 7).
 *
 * Размер добычи задаёт «ёмкость» челюстей: съедобно то, что помещается в раскрытую пасть (радиус пасти 60 × масштаб червя).
 * Радиус `r` берётся примерно как половина большей стороны рисунка, поэтому лесенка тиров получается сама:
 * люди с 5-го тира, машины с 7-го, дома и лёгкая техника охраны с 8-го, грузовики с 9-го, автобусы с 10-го,
 * многоэтажки с 11-го, тяжёлая техника и башни с 12-го.
 */
export type SurfaceKind = 'person' | 'car' | 'house' | 'truck' | 'patrol' | 'bus' | 'apartment' | 'heavy' | 'tower' | 'skyscraper';

/** Что делает добыча: бежит от червя, ездит туда-сюда, стоит или стреляет в червя. */
export type SurfaceBehavior = 'person' | 'car' | 'static' | 'guard';

export interface GuardSpec {
  /** Кадр ствола и точка крепления на корпусе (px рисунка корпуса от левого верхнего угла). */
  barrel: string;
  mount: [number, number];
  /** Ось вращения и длина ствола в px рисунка ствола. */
  pivot: [number, number];
  length: number;
  /** Снаряд: кадр, масштаб, скорость px/с, урон (доля базового здоровья 100), пауза между выстрелами и «заряд» перед выстрелом, с. */
  shot: string;
  shotScale: number;
  speed: number;
  damage: number;
  reload: number;
  charge: number;
}

export interface SurfaceSpec {
  kind: SurfaceKind;
  /** Варианты внешнего вида: у каждого один или несколько кадров анимации (у людей два кадра бега). Кадры атласа `z2`. */
  variants: string[][];
  scale: number;
  r: number;
  points: number;
  behavior: SurfaceBehavior;
  speed: number;
  /** Вес появления по тирам: индекс 0 — тир 5 (SURFACE_TIER), последний берётся для всех следующих. */
  weights: number[];
  guard?: GuardSpec;
}

export const SURFACE_SPECS: SurfaceSpec[] = [
  {
    kind: 'person',
    variants: [['z2-person-a-run1', 'z2-person-a-run2'], ['z2-person-b-run1', 'z2-person-b-run2'], ['z2-person-c-run1', 'z2-person-c-run2']],
    scale: 1.2,
    r: 48,
    points: 1,
    behavior: 'person',
    speed: 150,
    weights: [60, 60, 40, 40, 26, 26, 16, 14],
  },
  {
    kind: 'car',
    variants: [['z2-car-a-red'], ['z2-car-a-blue'], ['z2-car-a-yellow'], ['z2-car-b-green'], ['z2-car-b-orange'], ['z2-car-b-white']],
    scale: 1.18,
    r: 118,
    points: 5,
    behavior: 'car',
    speed: 90,
    weights: [10, 12, 26, 26, 20, 18, 14, 12],
  },
  {
    kind: 'house',
    variants: [['z2-house-a-cream'], ['z2-house-a-blue'], ['z2-house-b-salmon'], ['z2-house-b-sage']],
    scale: 0.95,
    r: 140,
    points: 8,
    behavior: 'static',
    speed: 0,
    weights: [0, 6, 8, 24, 22, 16, 12, 10],
  },
  {
    kind: 'truck',
    variants: [['z2-truck-white'], ['z2-truck-orange']],
    scale: 1,
    r: 165,
    points: 9,
    behavior: 'car',
    speed: 70,
    weights: [0, 0, 4, 8, 20, 18, 14, 10],
  },
  {
    kind: 'patrol',
    variants: [['z2-patrol']],
    scale: 1.2,
    r: 142,
    points: 10,
    behavior: 'guard',
    speed: 36,
    weights: [0, 0, 5, 16, 16, 14, 12, 10],
    guard: {
      barrel: 'z2-patrol-barrel',
      mount: [112, 44],
      pivot: [16, 16],
      length: 70,
      shot: 'z2-bullet',
      shotScale: 0.8,
      speed: 780,
      damage: 8,
      reload: 1.8,
      charge: 0.4,
    },
  },
  {
    kind: 'bus',
    variants: [['z2-bus-yellow'], ['z2-bus-blue']],
    scale: 1,
    r: 192,
    points: 14,
    behavior: 'car',
    speed: 60,
    weights: [0, 0, 0, 3, 6, 18, 16, 12],
  },
  {
    kind: 'apartment',
    variants: [['z2-apartment-beige'], ['z2-apartment-pink']],
    scale: 0.95,
    r: 215,
    points: 20,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 3, 5, 18, 14],
  },
  {
    kind: 'heavy',
    variants: [['z2-heavy']],
    scale: 1.2,
    r: 232,
    points: 24,
    behavior: 'guard',
    speed: 24,
    weights: [0, 0, 0, 0, 0, 3, 5, 12],
    guard: {
      barrel: 'z2-heavy-barrel',
      mount: [150, 74],
      pivot: [24, 24],
      length: 138,
      shot: 'z2-shell',
      shotScale: 1,
      speed: 640,
      damage: 16,
      reload: 3.0,
      charge: 0.55,
    },
  },
  {
    kind: 'tower',
    variants: [['z2-tower']],
    scale: 0.8,
    r: 245,
    points: 28,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 0, 2, 4, 10],
  },
  {
    kind: 'skyscraper',
    variants: [['z2-skyscraper']],
    scale: 0.75,
    r: 248,
    points: 30,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 0, 0, 3, 10],
  },
];

export function specOf(kind: SurfaceKind): SurfaceSpec {
  return SURFACE_SPECS.find((s) => s.kind === kind) as SurfaceSpec;
}

/** Вес появления вида на тире: после последней записи берётся последняя. Ниже SURFACE_TIER берём первую (фон из людей и домов). */
export function surfaceWeight(spec: SurfaceSpec, tier: number, firstTier: number): number {
  const i = Math.max(0, Math.min(spec.weights.length - 1, tier - firstTier));
  return spec.weights[i];
}

/** Сколько предметов держим на поверхности рядом с червём. */
export const SURFACE_COUNT = 18;
/** Сколько деталей обстановки (деревья, кусты, фонари). */
export const DECOR_COUNT = 12;

/** Декор: кадры и масштаб; съесть нельзя, лежит за добычей. */
export const DECOR_FRAMES: Array<{ frame: string; scale: number }> = [
  { frame: 'z2-tree-a', scale: 1.3 },
  { frame: 'z2-tree-b', scale: 1.2 },
  { frame: 'z2-bush', scale: 1.1 },
  { frame: 'z2-lamp', scale: 1.2 },
];

// ---------------- здоровье и урон
/** С 5-го тира подземная добыча даёт лишь эту долю очков роста: рост идёт за счёт поверхности. */
export const SOIL_GROWTH_FACTOR = 0.3;

/** Базовый запас здоровья червя. */
export const BASE_HP = 100;
/** Под землёй червь лечится: единиц здоровья в секунду. */
export const HP_REGEN = 7;
/** После попадания червь неуязвим столько секунд (чтобы очередь выстрелов не убивала сразу). */
export const HIT_GRACE = 1.2;
/** После возрождения неуязвим столько секунд. */
export const RESPAWN_GRACE = 2.5;

/** Запас здоровья: база плюс бонус брони (ступени 0–5, `HP_BONUS`). */
export function maxHp(hpLevel: number): number {
  return Math.round(BASE_HP * (1 + (HP_BONUS[Math.max(0, Math.min(HP_BONUS.length - 1, hpLevel))] ?? 0)));
}

/** Дальность стрельбы охраны, px мира: растёт с масштабом червя (камера отъезжает, червь виден издалека). */
export function guardRange(S: number): number {
  return 900 + 260 * S;
}

/** Очки роста за съеденную добычу поверхности: берутся из таблицы, а не от размера. */
export function surfacePoints(spec: SurfaceSpec): number {
  return spec.points;
}
