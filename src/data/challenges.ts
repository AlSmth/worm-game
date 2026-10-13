import type { TextKey } from '../core/i18n';
import { MAX_TIER, econScale } from './growth';
import { SKY_TIER, SPACE_TIER, SURFACE_TIER } from './world';

const ANY = 99;
/** Последний тир зоны 2: после него под землёй и на поверхности делать нечего. */
const GROUND_END = SKY_TIER - 1;

/**
 * Испытания (концепт, раздел 10): три активных одновременно, за выполнение монеты, после выполнения заменяются новыми.
 * Версия 1 для зоны 1: что можно сделать под землёй и при первом выходе на поверхность. Все числа здесь.
 */
export type ChallengeKind =
  | 'eat'
  | 'beetle'
  | 'worm'
  | 'coins'
  | 'gems'
  | 'chests'
  | 'tier'
  | 'jump'
  | 'people'
  | 'cars'
  | 'buildings'
  | 'guards'
  | 'planes'
  | 'space';

export interface ChallengeState {
  k: ChallengeKind;
  /** Цель. */
  n: number;
  /** Прогресс. */
  p: number;
  /** Награда, монет. */
  r: number;
}

interface Def {
  kind: ChallengeKind;
  key: TextKey;
  /** Цель на 1-м тире. */
  base: number;
  /** Рост цели за тир (доля от базовой). */
  step: number;
  /** Награда на 1-м тире; дальше растёт вместе с тиром (econScale), как ценность сокровищ. */
  reward: number;
  /** С какого тира предлагается (самоцветы лежат глубже, прыжок нужен поверхности). */
  minTier: number;
  /** До какого тира предлагается: подземное и наземное в небе и космосе уже не встретить. */
  maxTier: number;
}

export const CHALLENGE_COUNT = 3;

export const DEFS: Def[] = [
  { kind: 'eat', key: 'ch_eat', base: 15, step: 0.3, reward: 12, minTier: 1, maxTier: ANY },
  { kind: 'beetle', key: 'ch_beetle', base: 8, step: 0.3, reward: 12, minTier: 1, maxTier: GROUND_END },
  { kind: 'worm', key: 'ch_worm', base: 8, step: 0.3, reward: 12, minTier: 1, maxTier: GROUND_END },
  { kind: 'coins', key: 'ch_coins', base: 15, step: 0.45, reward: 15, minTier: 1, maxTier: ANY },
  { kind: 'gems', key: 'ch_gems', base: 2, step: 0.25, reward: 20, minTier: 2, maxTier: GROUND_END },
  { kind: 'chests', key: 'ch_chests', base: 1, step: 0.2, reward: 30, minTier: 3, maxTier: GROUND_END },
  { kind: 'tier', key: 'ch_tier', base: 0, step: 0, reward: 25, minTier: 1, maxTier: ANY },
  { kind: 'jump', key: 'ch_jump', base: 3, step: 0.2, reward: 15, minTier: SURFACE_TIER, maxTier: GROUND_END },
  // зона 2: люди, машины, дома, техника охраны
  { kind: 'people', key: 'ch_people', base: 12, step: 0.12, reward: 14, minTier: SURFACE_TIER, maxTier: GROUND_END },
  { kind: 'cars', key: 'ch_cars', base: 4, step: 0.12, reward: 18, minTier: 7, maxTier: GROUND_END },
  { kind: 'buildings', key: 'ch_buildings', base: 3, step: 0.1, reward: 20, minTier: 8, maxTier: GROUND_END },
  { kind: 'guards', key: 'ch_guards', base: 2, step: 0.1, reward: 28, minTier: 8, maxTier: GROUND_END },
  // зоны 3-4: самолёты и вертолёты, спутники и астероиды
  { kind: 'planes', key: 'ch_planes', base: 10, step: 0.1, reward: 18, minTier: SKY_TIER, maxTier: SPACE_TIER - 1 },
  { kind: 'space', key: 'ch_space', base: 8, step: 0.1, reward: 22, minTier: SPACE_TIER, maxTier: ANY },
];

const KINDS = new Set<string>(DEFS.map((d) => d.kind));

export function isKind(v: unknown): v is ChallengeKind {
  return typeof v === 'string' && KINDS.has(v);
}

export function defOf(kind: ChallengeKind): Def {
  return DEFS.find((d) => d.kind === kind) as Def;
}

/** Испытание устарело на этом тире (после выхода в небо и космос наземные заменяются новыми). */
export function expiredKind(kind: ChallengeKind, tier: number): boolean {
  return tier > defOf(kind).maxTier;
}

/** Ключ текста испытания в словаре. */
export function challengeKey(kind: ChallengeKind): TextKey {
  return defOf(kind).key;
}

/** Новое испытание этого вида для данного тира. */
export function makeChallenge(kind: ChallengeKind, tier: number): ChallengeState {
  const d = defOf(kind);
  const n = kind === 'tier' ? Math.min(MAX_TIER, tier + 2) : Math.max(1, Math.round(d.base * (1 + d.step * (tier - 1))));
  const r = Math.max(5, Math.round(d.reward * econScale(tier)));
  return { k: kind, n, p: 0, r };
}

/** Какой вид испытания предложить: из доступных на этом тире, кроме уже идущих и только что выполненного. */
export function pickKind(tier: number, taken: ChallengeKind[], rnd: () => number = Math.random): ChallengeKind {
  const here = DEFS.filter((d) => d.minTier <= tier && tier <= d.maxTier);
  const ok = here.filter((d) => !taken.includes(d.kind) && !(d.kind === 'tier' && tier >= MAX_TIER));
  const pool = ok.length ? ok : here.filter((d) => !taken.includes(d.kind));
  const list = pool.length ? pool : here;
  return list[Math.min(list.length - 1, Math.floor(rnd() * list.length))].kind;
}
