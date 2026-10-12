import type { Layout } from './layout';

export interface UiRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Общее состояние между сценами (простая замена шине событий). */
export const state = {
  tier: 1,
  growth: 0,
  need: 30,
  /** Пауза по кнопке игрока (показываем окно паузы). */
  paused: false,
  /** Занятые интерфейсом прямоугольники в px холста: игра не принимает там касания за управление червём. */
  uiRects: [] as UiRect[],
  layout: { cssW: 0, cssH: 0, dpr: 1, width: 0, height: 0 } as Layout,
};

export function hitsUi(x: number, y: number): boolean {
  return state.uiRects.some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
}
