import { HP_BONUS } from './upgrades';

/**
 * Зона 2 «Поверхность»: добыча над землёй (люди, машины, дома, техника охраны), здоровье и урон.
 * Все числа здесь, чтобы балансировать без правки кода (концепт, разделы 3, 5 и 7).
 *
 * Мир в реальных пропорциях: человек ростом 1500 px, легковая машина 3900 px длиной, дом 6000 px, небоскрёб 36 000 px, а подземные
 * жуки и червячки (зона 1) остаются крошками до 200 px. Червь растёт по таблице масштабов (`wormScale`), камера отъезжает.
 * Размер добычи задаёт «ёмкость» челюстей: съедобно то, что помещается в раскрытую пасть (радиус пасти 60 × масштаб червя).
 * Радиус `r` берётся примерно как половина большей стороны рисунка, поэтому лесенка тиров получается сама:
 * люди с 5-го тира, машины с 7-го, дома и лёгкая техника охраны с 8-го, грузовики и ракетные установки с 9-го, автобусы с 10-го,
 * многоэтажки и тяжёлая техника с 11-го, башни и небоскрёбы с 12-го.
 */
export type SurfaceKind = 'person' | 'car' | 'house' | 'truck' | 'patrol' | 'launcher' | 'bus' | 'apartment' | 'heavy' | 'tower' | 'skyscraper';

/** Что делает добыча: бежит от червя, ездит туда-сюда, стоит или стреляет ракетами в червя. */
export type SurfaceBehavior = 'person' | 'car' | 'static' | 'guard';

export interface GuardSpec {
  /** Кадр ствола (пусковой трубы) и точка его крепления на корпусе (px рисунка корпуса от левого верхнего угла). */
  barrel: string;
  mount: [number, number];
  /** Ось вращения и длина ствола в px рисунка ствола. */
  pivot: [number, number];
  length: number;
  /** Ракета: длина в px мира, скорость как доля скорости плавания червя, поворот на цель рад/с, урон одного попадания. */
  rocketLen: number;
  speedK: number;
  turn: number;
  damage: number;
  /** Залп: сколько ракет подряд и пауза между ними, с. */
  salvo: number;
  salvoGap: number;
  /** Пауза между залпами и «зарядка» ствола перед залпом (мигает), с. */
  reload: number;
  charge: number;
}

export interface SurfaceSpec {
  kind: SurfaceKind;
  /** Варианты внешнего вида: у каждого один или несколько кадров анимации (у людей два кадра бега). Кадры атласа `z2`. */
  variants: string[][];
  /** Масштаб рисунка: px мира на px рисунка. */
  scale: number;
  /** Ширина на экране, px мира (для расстановки). */
  width: number;
  r: number;
  points: number;
  /** Монеты за съеденное на 1-м тире экономики (дальше растут с тиром, econScale); у людей нет. */
  coins: number;
  behavior: SurfaceBehavior;
  /** Скорость хода, px/с (людям и машинам: в мире, не зависит от червя). */
  speed: number;
  /** Вес появления по тирам: индекс 0 — тир 5 (SURFACE_TIER), последний берётся для всех следующих. */
  weights: number[];
  guard?: GuardSpec;
}

export const SURFACE_SPECS: SurfaceSpec[] = [
  {
    kind: 'person',
    variants: [['z2-person-a-run1', 'z2-person-a-run2'], ['z2-person-b-run1', 'z2-person-b-run2'], ['z2-person-c-run1', 'z2-person-c-run2']],
    scale: 15.6,
    width: 870,
    r: 720,
    points: 1,
    coins: 0,
    behavior: 'person',
    speed: 2400,
    weights: [60, 60, 34, 26, 16, 12, 8, 6],
  },
  {
    kind: 'car',
    variants: [['z2-car-a-red'], ['z2-car-a-blue'], ['z2-car-a-yellow'], ['z2-car-b-green'], ['z2-car-b-orange'], ['z2-car-b-white']],
    scale: 18.75,
    width: 3900,
    r: 1900,
    points: 5,
    coins: 1.5,
    behavior: 'car',
    speed: 1500,
    weights: [10, 12, 26, 20, 14, 12, 8, 6],
  },
  {
    kind: 'house',
    variants: [['z2-house-a-cream'], ['z2-house-a-blue'], ['z2-house-b-salmon'], ['z2-house-b-sage']],
    scale: 20,
    width: 5600,
    r: 2950,
    points: 8,
    coins: 2.5,
    behavior: 'static',
    speed: 0,
    weights: [0, 6, 8, 18, 14, 10, 8, 6],
  },
  {
    kind: 'truck',
    variants: [['z2-truck-white'], ['z2-truck-orange']],
    scale: 27,
    width: 8260,
    r: 4100,
    points: 9,
    coins: 3,
    behavior: 'car',
    speed: 1100,
    weights: [0, 0, 4, 8, 14, 12, 8, 6],
  },
  {
    kind: 'patrol',
    variants: [['z2-patrol']],
    scale: 23,
    width: 4550,
    r: 2300,
    points: 10,
    coins: 4,
    behavior: 'guard',
    speed: 500,
    weights: [0, 0, 8, 20, 22, 18, 16, 14],
    guard: {
      barrel: 'z2-patrol-barrel',
      mount: [112, 44],
      pivot: [16, 16],
      length: 70,
      rocketLen: 2100,
      speedK: 1.15,
      turn: 1.8,
      damage: 9,
      salvo: 1,
      salvoGap: 0,
      reload: 1.7,
      charge: 0.4,
    },
  },
  {
    kind: 'launcher',
    variants: [['z2-launcher']],
    scale: 24,
    width: 6900,
    r: 3500,
    points: 12,
    coins: 4.5,
    behavior: 'guard',
    speed: 360,
    weights: [0, 0, 0, 0, 12, 18, 20, 18],
    guard: {
      barrel: 'z2-launcher-rack',
      mount: [110, 62],
      pivot: [16, 32],
      length: 118,
      rocketLen: 1800,
      speedK: 1.3,
      turn: 2.1,
      damage: 8,
      salvo: 4,
      salvoGap: 0.22,
      reload: 3.0,
      charge: 0.5,
    },
  },
  {
    kind: 'bus',
    variants: [['z2-bus-yellow'], ['z2-bus-blue']],
    scale: 26,
    width: 9720,
    r: 4850,
    points: 14,
    coins: 4,
    behavior: 'car',
    speed: 900,
    weights: [0, 0, 0, 3, 6, 14, 10, 8],
  },
  {
    kind: 'apartment',
    variants: [['z2-apartment-beige'], ['z2-apartment-pink']],
    scale: 31,
    width: 6630,
    r: 6800,
    points: 20,
    coins: 6,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 3, 5, 14, 10],
  },
  {
    kind: 'heavy',
    variants: [['z2-heavy']],
    scale: 30,
    width: 10620,
    r: 5700,
    points: 24,
    coins: 7,
    behavior: 'guard',
    speed: 300,
    weights: [0, 0, 0, 0, 0, 10, 20, 26],
    guard: {
      barrel: 'z2-heavy-barrel',
      mount: [150, 74],
      pivot: [24, 24],
      length: 138,
      rocketLen: 3600,
      speedK: 1.0,
      turn: 1.4,
      damage: 16,
      salvo: 2,
      salvoGap: 0.38,
      reload: 3.2,
      charge: 0.55,
    },
  },
  {
    kind: 'tower',
    variants: [['z2-tower']],
    scale: 37.5,
    width: 7000,
    r: 12000,
    points: 28,
    coins: 8,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 0, 2, 4, 8],
  },
  {
    kind: 'skyscraper',
    variants: [['z2-skyscraper']],
    scale: 47,
    width: 6860,
    r: 17500,
    points: 30,
    coins: 10,
    behavior: 'static',
    speed: 0,
    weights: [0, 0, 0, 0, 0, 0, 3, 8],
  },
];

export function specOf(kind: SurfaceKind): SurfaceSpec {
  return SURFACE_SPECS.find((s) => s.kind === kind) as SurfaceSpec;
}

/** Вес появления вида на тире: после последней записи берётся последняя. Ниже SURFACE_TIER берём первую (фон из людей и машин). */
export function surfaceWeight(spec: SurfaceSpec, tier: number, firstTier: number): number {
  const i = Math.max(0, Math.min(spec.weights.length - 1, tier - firstTier));
  return spec.weights[i];
}

/** С какого тира над землёй вообще есть люди и машины (раньше червь слишком мал и на экране остались бы одни ноги великанов). */
export const SURFACE_VISIBLE_TIER = 4;

/** Сколько предметов держим на поверхности в двух ширинах экрана: от ширины вида и средней ширины добычи на этом тире. */
export function surfaceCount(viewW: number, tier: number, firstTier: number): number {
  let sum = 0;
  let w = 0;
  for (const s of SURFACE_SPECS) {
    const k = surfaceWeight(s, tier, firstTier);
    sum += k;
    w += k * s.width;
  }
  const mean = sum ? w / sum : 1500;
  return Math.max(14, Math.min(44, Math.round((2 * viewW) / (mean * 0.9))));
}

/** Сколько машин охраны держим рядом: растёт с тиром (с 7-го тира одна, к 12-му шесть). */
export function guardQuota(tier: number): number {
  return Math.max(0, Math.min(6, tier - 6));
}

/** Сколько деталей обстановки (деревья, кусты, фонари). */
export const DECOR_COUNT = 12;

/** Декор: кадры и масштаб (px мира на px рисунка); съесть нельзя, лежит за добычей. Дерево около 4 человеческих ростов. */
export const DECOR_FRAMES: Array<{ frame: string; scale: number }> = [
  { frame: 'z2-tree-a', scale: 28 },
  { frame: 'z2-tree-b', scale: 28 },
  { frame: 'z2-bush', scale: 14 },
  { frame: 'z2-lamp', scale: 26 },
];

// ---------------- здоровье и урон
/** С 5-го тира подземная добыча даёт лишь эту долю очков роста: рост идёт за счёт поверхности. */
export const SOIL_GROWTH_FACTOR = 0.15;

/** Базовый запас здоровья червя. */
export const BASE_HP = 100;
/** Под землёй червь лечится: единиц здоровья в секунду. */
export const HP_REGEN = 7;
/** После попадания червь неуязвим столько секунд (чтобы залп не убивал сразу). */
export const HIT_GRACE = 0.6;
/** После возрождения неуязвим столько секунд. */
export const RESPAWN_GRACE = 2.5;

/** Запас здоровья: база плюс бонус брони (ступени 0–5, `HP_BONUS`). */
export function maxHp(hpLevel: number): number {
  return Math.round(BASE_HP * (1 + (HP_BONUS[Math.max(0, Math.min(HP_BONUS.length - 1, hpLevel))] ?? 0)));
}

/** Дальность стрельбы охраны, px мира: растёт с масштабом червя (камера отъезжает, червь виден издалека). */
export function guardRange(S: number): number {
  return 4000 + 330 * S;
}
