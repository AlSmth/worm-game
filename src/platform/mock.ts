/**
 * Локальная имитация SDK Яндекс Игр. Нужна, чтобы игра работала вне платформы:
 * при разработке, при показе без интернета, при открытии собранной версии с диска.
 * Облако имитируется через localStorage и проверяет лимиты Яндекса (setData: 100 запросов за 5 минут).
 */

const CLOUD_KEY = 'wg.mockcloud';
const SET_DATA_LIMIT = 100;
const WINDOW_MS = 5 * 60 * 1000;

type Listener = () => void;

function readCloud(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(CLOUD_KEY) ?? '{}') as Record<string, unknown>;
  } catch {
    return {};
  }
}

export interface MockSdk extends YSDK {
  /** Для тестов: послать событие платформы (game_api_pause / game_api_resume). */
  emit(event: string): void;
  setDataCalls(): number;
}

export function createMockSdk(): MockSdk {
  const listeners = new Map<string, Set<Listener>>();
  const calls: number[] = [];

  const player: YPlayer = {
    isAuthorized: () => false,
    getData(keys) {
      const all = readCloud();
      if (!keys) return Promise.resolve(all);
      const out: Record<string, unknown> = {};
      for (const k of keys) if (k in all) out[k] = all[k];
      return Promise.resolve(out);
    },
    setData(data) {
      const now = Date.now();
      while (calls.length && now - calls[0] > WINDOW_MS) calls.shift();
      calls.push(now);
      if (calls.length > SET_DATA_LIMIT) {
        return Promise.reject(new Error('mock: превышен лимит setData (100 запросов за 5 минут)'));
      }
      try {
        localStorage.setItem(CLOUD_KEY, JSON.stringify({ ...readCloud(), ...data }));
      } catch {
        /* хранилище недоступно: как «облако без связи» */
      }
      return Promise.resolve();
    },
  };

  return {
    environment: { i18n: { lang: (navigator.language || 'ru').slice(0, 2) } },
    features: { LoadingAPI: { ready() {} }, GameplayAPI: { start() {}, stop() {} } },
    on(event, listener) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event)!.add(listener);
    },
    off(event, listener) {
      listeners.get(event)?.delete(listener);
    },
    getPlayer: () => Promise.resolve(player),
    adv: {
      showFullscreenAdv(o) {
        window.setTimeout(() => {
          o?.callbacks?.onOpen?.();
          window.setTimeout(() => o?.callbacks?.onClose?.(true), 400);
        }, 30);
      },
      showRewardedVideo(o) {
        window.setTimeout(() => {
          o?.callbacks?.onOpen?.();
          window.setTimeout(() => {
            o?.callbacks?.onRewarded?.();
            o?.callbacks?.onClose?.(true);
          }, 400);
        }, 30);
      },
    },
    emit(event) {
      listeners.get(event)?.forEach((l) => l());
    },
    setDataCalls: () => calls.length,
  };
}
