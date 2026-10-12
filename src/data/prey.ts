import { SURFACE_TIER } from './world';
import { wormScale } from './growth';

/**
 * Добыча зоны 1: размеры в px мира (радиус, который должен поместиться в раскрытые челюсти).
 * Размеры абсолютные, не привязаны к масштабу червя: по мере роста мелочь становится слишком мелкой, а крупное
 * становится съедобным («цели крупнее», концепт, раздел 5). Все числа здесь, чтобы балансировать без правки кода.
 */
export interface SizeClass {
  min: number;
  max: number;
}

/** Классы: крошки, мелкие, средние, крупные, гиганты. Челюсти червя 1-го тира вмещают радиус до 60. */
export const SIZE_CLASSES: SizeClass[] = [
  { min: 12, max: 20 },
  { min: 22, max: 34 },
  { min: 36, max: 52 },
  { min: 56, max: 74 },
  { min: 80, max: 104 },
];

/** Вес появления каждого класса по тирам (тир 1 — первая строка). Дальше берётся последняя строка. */
export const SIZE_WEIGHTS: number[][] = [
  [26, 34, 28, 11, 1],
  [20, 30, 28, 16, 6],
  [14, 24, 28, 22, 12],
  [8, 18, 26, 28, 20],
  [4, 12, 22, 30, 32],
];

/**
 * После выхода зоны 1 (тир 5) её добыча растёт вместе с червём. Это временная замена настоящей добыче зон 2–4,
 * чтобы прототип оставался играбельным на любом тире.
 */
export function sizeScale(S: number): number {
  return Math.max(1, S / wormScale(SURFACE_TIER));
}

/** Случайный радиус добычи для данного тира и масштаба червя. */
export function pickRadius(tier: number, S: number, rnd: () => number = Math.random): number {
  const row = SIZE_WEIGHTS[Math.min(tier, SIZE_WEIGHTS.length) - 1] ?? SIZE_WEIGHTS[SIZE_WEIGHTS.length - 1];
  const total = row.reduce((a, b) => a + b, 0);
  let roll = rnd() * total;
  let k = 0;
  while (k < row.length - 1 && roll >= row[k]) {
    roll -= row[k];
    k++;
  }
  const c = SIZE_CLASSES[k];
  return (c.min + (c.max - c.min) * rnd()) * sizeScale(S);
}
