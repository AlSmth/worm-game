import type { Layout } from './layout';
import type { TextKey } from './i18n';

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
  /** Короткое сообщение игроку сверху по центру: ключ строки и сколько секунд ещё показывать. */
  toast: { key: null as TextKey | null, left: 0, total: 0 },
};

export function hitsUi(x: number, y: number): boolean {
  return state.uiRects.some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
}

/** Показать сообщение игроку на несколько секунд (текст берётся из словаря, язык подставляет UI). */
export function showToast(key: TextKey, seconds: number): void {
  state.toast.key = key;
  state.toast.left = state.toast.total = seconds;
}
