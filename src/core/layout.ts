/**
 * Раскладка холста: всегда на всю доступную область (п. 1.6.2.1), но на ПК длинная сторона не больше
 * двух коротких (п. 1.6.2.2). Лишнее поле заливает фон страницы. Плотность пикселей ограничена: 2 хватает.
 */

export interface Layout {
  cssW: number;
  cssH: number;
  dpr: number;
  width: number; // размер холста в px устройства
  height: number;
}

export function isCoarsePointer(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
}

export function computeLayout(): Layout {
  // Меряем сам контейнер игры (position: fixed на весь экран): он совпадает с видимой областью и обновляется
  // синхронно с изменением окна, в отличие от visualViewport, который может отставать на кадр.
  const host = document.getElementById('game');
  const w = Math.max(1, Math.floor(host?.clientWidth || window.innerWidth));
  const h = Math.max(1, Math.floor(host?.clientHeight || window.innerHeight));
  // На телефонах поле занимает весь экран (в том числе вытянутые 20:9), на ПК не шире 2:1.
  const maxAspect = isCoarsePointer() ? 2.6 : 2;
  let cssW = w;
  let cssH = h;
  if (cssW / cssH > maxAspect) cssW = Math.floor(cssH * maxAspect);
  else if (cssH / cssW > maxAspect) cssH = Math.floor(cssW * maxAspect);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  return { cssW, cssH, dpr, width: Math.round(cssW * dpr), height: Math.round(cssH * dpr) };
}
