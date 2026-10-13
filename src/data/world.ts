/** Мир: скорость червя, ширина карты и выход на поверхность. Числа здесь, чтобы балансировать без правки кода. */

/** Скорость червя 1-го тира без улучшений, px/с. */
export const SWIM_SPEED = 330;

/** За сколько секунд червь 1-го тира без улучшений скорости проплывает карту от края до края (концепт, раздел 2). */
export const CROSS_SECONDS = 300;

/** Ширина карты, px мира: 330 px/с × 300 с ≈ 100 000. Края закрыты каменными стенами. */
export const WORLD_WIDTH = SWIM_SPEED * CROSS_SECONDS;

/**
 * Половина ширины карты при масштабе червя S, px мира. Карта растёт вместе с червём (стены отъезжают), поэтому на любом тире
 * от края до края без улучшений скорости те же ≈ 5 минут: скорость червя тоже растёт вместе с масштабом.
 */
export function worldHalf(S: number): number {
  return (WORLD_WIDTH / 2) * Math.max(1, S);
}

/** Тир, с которого червь может выбраться на поверхность. До него он под землёй и видит поверхность только сверху. */
export const SURFACE_TIER = 5;

// ---------------- зоны 3-4 и финал (Э6)
/** Тир, с которого червь вылетает в небо (зона 3): прорыв из земли, дальше он плывёт по воздуху, как по почве. */
export const SKY_TIER = 13;
/** Тир, с которого червь вылетает за атмосферу (зона 4 «Космос»). */
export const SPACE_TIER = 17;
/** Последний тир: на нём можно съесть Землю (финал). */
export const FINAL_TIER = 21;

export type Zone = 'under' | 'ground' | 'sky' | 'space';

/** В какой зоне червь на этом тире: под землёй (1-4), на поверхности (5-12), в небе (13-16), в космосе (17-21). */
export function zoneOf(tier: number): Zone {
  if (tier >= SPACE_TIER) return 'space';
  if (tier >= SKY_TIER) return 'sky';
  if (tier >= SURFACE_TIER) return 'ground';
  return 'under';
}

/** Высота неба над землёй при масштабе червя S, px: сколько он летит на обычной скорости от земли до края атмосферы (40 с). */
export const SKY_FLY_SECONDS = 40;
export function skyTop(S: number): number {
  return SKY_FLY_SECONDS * SWIM_SPEED * S;
}

/**
 * Космос: арена в абсолютных px (не растёт с червём: к финалу червь размером с планету и космос тесен). Ширина вдвое от
 * SPACE_HALF (1,6·10⁸), потолок SPACE_TOP (4·10⁷) над краем атмосферы (y = 0). Земля внизу: шар радиуса EARTH_R с верхней точкой в y = 0.
 * Луна: шар радиуса MOON_R на высоте MOON_Y, левее или правее центра на MOON_X.
 */
export const SPACE_HALF = 8e7;
export const SPACE_TOP = 4e7;

/** Арена растёт, когда червь становится больше неё (последние тиры): потолок не меньше 6 радиусов головы, половина ширины не меньше 7. */
export function spaceTop(S: number): number {
  return Math.max(SPACE_TOP, 360 * S);
}
export function spaceHalf(S: number): number {
  return Math.max(SPACE_HALF, 420 * S);
}
export const EARTH_R = 3.6e7;
export const MOON_R = 9.8e6;
export const MOON_X = 4.8e7;
export const MOON_Y = -2.2e7;
