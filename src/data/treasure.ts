import { sizeScale } from './prey';

/**
 * Сокровища зоны 1: за съеденное даются монеты (концепт, раздел 8). Чем глубже, тем богаче.
 * Размеры абсолютные, как у добычи: большой сундук съедобен, когда червь подрастёт (с 3-го тира).
 */
export type TreasureKind = 'coin' | 'gem' | 'chestSmall' | 'chestBig';

export interface TreasureSpec {
  kind: TreasureKind;
  frame: string;
  /** Радиус, который должен поместиться в челюсти, px мира. */
  r: number;
  /** Масштаб спрайта относительно холста. */
  look: number;
  value: number;
  /** С какой глубины появляется, px мира при масштабе 1. */
  minDepth: number;
  /** Вес появления среди доступных по глубине. */
  weight: number;
}

export const TREASURES: TreasureSpec[] = [
  { kind: 'coin', frame: 'treasure-coin', r: 20, look: 0.72, value: 1, minDepth: 130, weight: 60 },
  { kind: 'gem', frame: 'treasure-gem', r: 24, look: 0.8, value: 5, minDepth: 480, weight: 26 },
  { kind: 'chestSmall', frame: 'treasure-chest-small', r: 44, look: 0.78, value: 15, minDepth: 850, weight: 10 },
  { kind: 'chestBig', frame: 'treasure-chest-big', r: 76, look: 0.62, value: 40, minDepth: 1250, weight: 4 },
];

/** Оттенки самоцвета (умножение цвета) и цена: аметист редкий и дороже. */
export const GEM_TINTS: Array<{ tint: number; value: number; weight: number }> = [
  { tint: 0xff6b7d, value: 5, weight: 3 },
  { tint: 0x57e08a, value: 5, weight: 3 },
  { tint: 0x58a6ff, value: 5, weight: 3 },
  { tint: 0xc58bff, value: 8, weight: 1 },
];

/** Сколько сокровищ держим в мире одновременно. */
export const TREASURE_COUNT = 7;

/** Какие сокровища доступны на глубине y (px мира) при масштабе червя S. */
export function availableAt(y: number, S: number): TreasureSpec[] {
  return TREASURES.filter((t) => y >= t.minDepth * Math.max(1, S * 0.6));
}

export function scaledRadius(spec: TreasureSpec, S: number): number {
  return spec.r * sizeScale(S);
}
