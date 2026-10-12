import type { TextKey } from '../core/i18n';
import { MAX_TIER, econScale } from './growth';
import { SURFACE_TIER } from './world';

/**
 * Испытания (концепт, раздел 10): три активных одновременно, за выполнение монеты, после выполнения заменяются новыми.
 * Версия 1 для зоны 1: что можно сделать под землёй и при первом выходе на поверхность. Все числа здесь.
 */
export type ChallengeKind = 'eat' | 'beetle' | 'worm' | 'coins' | 'gems' | 'chests' | 'tier' | 'jump' | 'people' | 'cars' | 'buildings' | 'guards';

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
}

export const CHALLENGE_COUNT = 3;

export const DEFS: Def[] = [
  { kind: 'eat', key: 'ch_eat', base: 15, step: 0.3, reward: 12, minTier: 1 },
  { kind: 'beetle', key: 'ch_beetle', base: 8, step: 0.3, reward: 12, minTier: 1 },
  { kind: 'worm', key: 'ch_worm', base: 8, step: 0.3, reward: 12, minTier: 1 },
  { kind: 'coins', key: 'ch_coins', base: 15, step: 0.45, reward: 15, minTier: 1 },
  { kind: 'gems', key: 'ch_gems', base: 2, step: 0.25, reward: 20, minTier: 2 },
  { kind: 'chests', key: 'ch_chests', base: 1, step: 0.2, reward: 30, minTier: 3 },
  { kind: 'tier', key: 'ch_tier', base: 0, step: 0, reward: 25, minTier: 1 },
  { kind: 'jump', key: 'ch_jump', base: 3, step: 0.2, reward: 15, minTier: SURFACE_TIER },
  // зона 2: люди, машины, дома, техника охраны
  { kind: 'people', key: 'ch_people', base: 12, step: 0.12, reward: 14, minTier: SURFACE_TIER },
  { kind: 'cars', key: 'ch_cars', base: 4, step: 0.12, reward: 18, minTier: 7 },
  { kind: 'buildings', key: 'ch_buildings', base: 3, step: 0.1, reward: 20, minTier: 8 },
  { kind: 'guards', key: 'ch_guards', base: 2, step: 0.1, reward: 28, minTier: 8 },
];

const KINDS = new Set<string>(DEFS.map((d) => d.kind));

export function isKind(v: unknown): v is ChallengeKind {
  return typeof v === 'string' && KINDS.has(v);
}

export function defOf(kind: ChallengeKind): Def {
  return DEFS.find((d) => d.kind === kind) as Def;
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
  const ok = DEFS.filter((d) => d.minTier <= tier && !taken.includes(d.kind) && !(d.kind === 'tier' && tier >= MAX_TIER));
  const pool = ok.length ? ok : DEFS.filter((d) => d.minTier <= tier && !taken.includes(d.kind));
  const list = pool.length ? pool : DEFS.filter((d) => d.minTier <= tier);
  return list[Math.min(list.length - 1, Math.floor(rnd() * list.length))].kind;
}
