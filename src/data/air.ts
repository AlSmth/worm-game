import { SKY_TIER, SPACE_TIER } from './world';

/**
 * Зоны 3 «Небо» и 4 «Космос»: добыча в воздухе и в пустоте, опасности, очки роста. Все числа здесь, чтобы балансировать без правки кода.
 *
 * Размеры задаёт радиус `r` в px мира, то есть «ёмкость челюстей»: съедобно то, что помещается в раскрытую пасть (радиус пасти 60 × масштаб
 * червя). Пасть: T13 25 000, T14 40 000, T15 55 000, T16 75 000; T17 200 000, T18 800 000, T19 3 000 000, T20 12 000 000, T21 40 000 000.
 * Масштаб рисунка вычисляется из радиуса (рисунок целиком помещается в круг радиуса `r`), так что размер спрайта и съедобность не расходятся.
 * Скорости заданы долями скорости плавания червя (она растёт вместе с червём), чтобы добычу можно было догнать на любом тире.
 */
export type AirKind =
  | 'plane'
  | 'heli'
  | 'fighter'
  | 'heavy'
  | 'airliner'
  | 'cargo'
  | 'cargoXL'
  | 'sat'
  | 'station'
  | 'rockS'
  | 'rockM'
  | 'rockL'
  | 'moon'
  | 'earth';

export type AirZone = 'sky' | 'space';

/** Что делает: летит по прямой туда-сюда, висит и покачивается, патрулирует и стреляет, плывёт и вращается, стоит. */
export type AirBehavior = 'cruise' | 'hover' | 'fighter' | 'drift' | 'static';

/** Пуск ракет (истребитель, тяжёлый вертолёт): те же ракеты, что у охраны на земле. */
export interface AirGuard {
  /** Длина ракеты, px мира (не меньше 6 % высоты вида), скорость в долях скорости плавания, поворот на цель рад/с, урон. */
  rocketLen: number;
  speedK: number;
  turn: number;
  damage: number;
  /** Залп: сколько ракет и пауза между ними, с; пауза между залпами; «зарядка» перед пуском; дальность в высотах вида. */
  salvo: number;
  salvoGap: number;
  reload: number;
  charge: number;
}

export interface AirSpec {
  kind: AirKind;
  zone: AirZone;
  /** Варианты вида: у каждого один или несколько кадров анимации (винт). Кадры атласов `z3` и `z4`. */
  variants: string[][];
  /** Атлас с кадрами: z3 или z4. */
  atlas: 'z3' | 'z4';
  /** Радиус (в расчёте на половину большей стороны рисунка), px мира; на спавне ±8 %. */
  r: number;
  points: number;
  coins: number;
  behavior: AirBehavior;
  /** Скорость в долях скорости плавания червя. */
  speedK: number;
  /** Диапазон высоты над землёй в долях высоты неба (только небо). */
  alt: [number, number];
  /** Вес появления по тирам зоны: индекс 0 — первый тир зоны (T13 или T17), последний берётся для всех следующих. */
  weights: number[];
  guard?: AirGuard;
  /** Вращение, рад/с (астероиды). */
  spin?: number;
  /** Урон при касании, если не по зубам (астероиды). */
  touch?: number;
}

export const AIR_SPECS: AirSpec[] = [
  // ---------------- небо (T13-T16)
  {
    kind: 'plane', zone: 'sky', atlas: 'z3', variants: [['z3-plane-a-1', 'z3-plane-a-2'], ['z3-plane-b-1', 'z3-plane-b-2']],
    r: 5600, points: 30, coins: 1, behavior: 'cruise', speedK: 0.35, alt: [0.03, 0.6], weights: [40, 24, 14, 8],
  },
  {
    kind: 'heli', zone: 'sky', atlas: 'z3', variants: [['z3-heli-a-1', 'z3-heli-a-2'], ['z3-heli-b-1', 'z3-heli-b-2']],
    r: 6500, points: 36, coins: 1, behavior: 'hover', speedK: 0.1, alt: [0.02, 0.4], weights: [34, 22, 12, 8],
  },
  {
    kind: 'fighter', zone: 'sky', atlas: 'z3', variants: [['z3-fighter']],
    r: 8500, points: 50, coins: 2, behavior: 'fighter', speedK: 0.5, alt: [0.0, 0.85], weights: [8, 20, 24, 24],
    guard: { rocketLen: 7000, speedK: 1.2, turn: 2.2, damage: 12, salvo: 2, salvoGap: 0.3, reload: 2.6, charge: 0.4 },
  },
  {
    kind: 'heavy', zone: 'sky', atlas: 'z3', variants: [['z3-heavy-1', 'z3-heavy-2']],
    r: 12000, points: 80, coins: 2.5, behavior: 'hover', speedK: 0.08, alt: [0.04, 0.55], weights: [6, 14, 18, 16],
    guard: { rocketLen: 9000, speedK: 1.0, turn: 1.5, damage: 16, salvo: 2, salvoGap: 0.4, reload: 3.4, charge: 0.55 },
  },
  {
    kind: 'airliner', zone: 'sky', atlas: 'z3', variants: [['z3-airliner-a'], ['z3-airliner-b']],
    r: 32000, points: 150, coins: 4, behavior: 'cruise', speedK: 0.25, alt: [0.0, 0.9], weights: [0, 14, 20, 20],
  },
  {
    kind: 'cargo', zone: 'sky', atlas: 'z3', variants: [['z3-cargo']],
    r: 48000, points: 220, coins: 6, behavior: 'cruise', speedK: 0.18, alt: [0.0, 0.85], weights: [0, 0, 16, 20],
  },
  {
    kind: 'cargoXL', zone: 'sky', atlas: 'z3', variants: [['z3-cargo']],
    r: 68000, points: 320, coins: 8, behavior: 'cruise', speedK: 0.14, alt: [0.0, 0.9], weights: [0, 0, 6, 14],
  },
  // ---------------- космос (T17-T21)
  {
    kind: 'sat', zone: 'space', atlas: 'z4', variants: [['z4-sat-a'], ['z4-sat-b']],
    r: 100000, points: 140, coins: 3, behavior: 'drift', speedK: 0.03, alt: [0, 1], weights: [40, 22, 12, 8, 6], spin: 0.15,
  },
  {
    kind: 'station', zone: 'space', atlas: 'z4', variants: [['z4-station']],
    r: 190000, points: 260, coins: 5, behavior: 'drift', speedK: 0.015, alt: [0, 1], weights: [14, 18, 14, 10, 8], spin: 0.04,
  },
  {
    kind: 'rockS', zone: 'space', atlas: 'z4', variants: [['z4-rock-a'], ['z4-rock-b'], ['z4-rock-c']],
    r: 600000, points: 330, coins: 3, behavior: 'drift', speedK: 0.05, alt: [0, 1], weights: [10, 30, 20, 14, 10], spin: 0.3, touch: 10,
  },
  {
    kind: 'rockM', zone: 'space', atlas: 'z4', variants: [['z4-rock-a'], ['z4-rock-b'], ['z4-rock-c']],
    r: 2300000, points: 620, coins: 5, behavior: 'drift', speedK: 0.03, alt: [0, 1], weights: [0, 12, 30, 20, 14], spin: 0.15, touch: 16,
  },
  {
    kind: 'rockL', zone: 'space', atlas: 'z4', variants: [['z4-rock-a'], ['z4-rock-b'], ['z4-rock-c']],
    r: 8200000, points: 1000, coins: 8, behavior: 'drift', speedK: 0.015, alt: [0, 1], weights: [0, 0, 12, 28, 18], spin: 0.06, touch: 24,
  },
  // ---------------- небесные тела: стоят на своих местах (src/data/world.ts: MOON_*, EARTH_R)
  {
    kind: 'moon', zone: 'space', atlas: 'z4', variants: [['z4-moon']],
    r: 9800000, points: 2500, coins: 30, behavior: 'static', speedK: 0, alt: [0, 1], weights: [0], touch: 28,
  },
  {
    kind: 'earth', zone: 'space', atlas: 'z4', variants: [['z4-earth']],
    r: 36000000, points: 0, coins: 0, behavior: 'static', speedK: 0, alt: [0, 1], weights: [0],
  },
];

export function airSpecOf(kind: AirKind): AirSpec {
  return AIR_SPECS.find((s) => s.kind === kind) as AirSpec;
}

/** Первый тир зоны. */
export function firstTierOf(zone: AirZone): number {
  return zone === 'sky' ? SKY_TIER : SPACE_TIER;
}

/** Вес появления вида на тире (после последней записи берётся последняя). */
export function airWeight(spec: AirSpec, tier: number): number {
  const i = Math.max(0, Math.min(spec.weights.length - 1, tier - firstTierOf(spec.zone)));
  return spec.weights[i];
}

/** Сколько летающих предметов держим в окне вокруг червя: в небе 18, в космосе 14. */
export function airCount(tier: number): number {
  return tier < SPACE_TIER ? 18 : 14;
}

/** Сколько стреляющих машин держим рядом: истребителей и тяжёлых вертолётов (T13 одна, T14 две, T15 три, T16 четыре). */
export function airGuardQuota(tier: number): number {
  if (tier < SKY_TIER || tier >= SPACE_TIER) return 0;
  return Math.min(4, tier - SKY_TIER + 1);
}

/** Дальность стрельбы в высотах вида (чем выше, тем дальше): 1,1 высоты. */
export const AIR_GUARD_RANGE = 1.1;

/** Здоровье в небе и космосе: червь лечится сам, если 3 секунды его не ранили (под землёй быстрее). */
export const AIR_REGEN = 3;
export const AIR_REGEN_DELAY = 3;

/** Сколько урона наносит касание не по зубам (астероид, Луна) задаёт `touch` вида; неуязвимость после удара та же, что у ракет. */
