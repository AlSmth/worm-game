/** Рост червя: тиры размера T1…T21 (концепт, раздел 5). Все числа здесь, чтобы балансировать без правки кода. */

export const MAX_TIER = 21;

const SCALE_STEP = 1.14;

/** Масштаб червя на (дробном) тире t ≥ 1. */
export function wormScale(t: number): number {
  return Math.pow(SCALE_STEP, t - 1);
}

/** Число сегментов тела на (дробном) тире t. */
export function segmentsAt(t: number): number {
  return 5 + 1.5 * (t - 1);
}

/**
 * Сколько очков роста нужно, чтобы пройти тир. Темп зоны 1 (решение автора): поверхность открывается не позже чем
 * через 2 минуты живой игры, автопилот проходит T1-T5 примерно за минуту.
 */
export function growthNeeded(tier: number): number {
  return Math.round(55 * Math.pow(1.12, tier - 1));
}

/** Очки роста за добычу с радиусом r (в «мировых» px) при масштабе червя S: чем крупнее добыча относительно червя, тем больше. */
export function growthFor(radius: number, S: number): number {
  const rel = radius / S;
  return Math.pow(rel, 1.6) / 100;
}
