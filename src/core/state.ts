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
  /** Монеты (виртуальная валюта): сохраняются, тратятся на улучшения (Э4). */
  coins: 0,
  need: 30,
  /** Пауза по кнопке игрока (показываем окно паузы). */
  paused: false,
  /** Открыт экран выбора персонажа: игра стоит, касания не должны управлять червём и кнопками под ним. */
  selecting: false,
  /** Открыт магазин: игра стоит, касания не должны управлять червём и кнопками под ним. */
  shopOpen: false,
  /** Здоровье червя (зона 2: охрана стреляет) и его запас; flash — вспышка полосы после попадания, с. */
  hp: 100,
  hpMax: 100,
  hpFlash: 0,
  /** Червь оглушён (здоровье кончилось); stunShown — окно «Заново» уже открыто, игра стоит. */
  stunned: false,
  stunShown: false,
  /** Занятые интерфейсом прямоугольники в px холста: игра не принимает там касания за управление червём. */
  uiRects: [] as UiRect[],
  layout: { cssW: 0, cssH: 0, dpr: 1, width: 0, height: 0 } as Layout,
  /** Короткое сообщение игроку сверху по центру: ключ строки и сколько секунд ещё показывать. */
  toast: { key: null as TextKey | null, left: 0, total: 0, params: undefined as Record<string, number | string> | undefined },
};

export function hitsUi(x: number, y: number): boolean {
  return state.uiRects.some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
}

/** Показать сообщение игроку на несколько секунд (текст берётся из словаря, язык подставляет UI). */
export function showToast(key: TextKey, seconds: number, params?: Record<string, number | string>): void {
  state.toast.key = key;
  state.toast.params = params;
  state.toast.left = state.toast.total = seconds;
}
