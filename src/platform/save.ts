import { DEFAULT_SKIN, isSkin, type SkinId } from '../data/skins';
import { MAX_TIER } from '../data/growth';
import { clampLevel, type Upgrades } from '../data/upgrades';
import { platform } from './platform';

/**
 * Прогресс игрока (п. 1.9): сохраняется сразу после действия, переживает обновление страницы и поворот экрана,
 * работает для гостя. Локально пишем мгновенно, в облако Яндекса реже: лимит setData 100 запросов за 5 минут,
 * поэтому облачные записи склеиваем и отправляем не чаще раза в 4 секунды.
 */
export interface SaveData {
  v: 1;
  savedAt: number;
  skin: SkinId;
  tier: number;
  growth: number;
  coins: number;
  up: Upgrades;
  sound: boolean;
}

export function defaultSave(): SaveData {
  return { v: 1, savedAt: 0, skin: DEFAULT_SKIN, tier: 1, growth: 0, coins: 0, up: { jump: 0, hp: 0, speed: 0 }, sound: true };
}

function num(v: unknown, def: number, min: number, max: number): number {
  return typeof v === 'number' && Number.isFinite(v) ? Math.max(min, Math.min(max, v)) : def;
}

/** Проверка и починка данных из хранилища: чужое и повреждённое не должно ломать игру. */
function sanitize(raw: unknown): SaveData | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const up = (r.up ?? {}) as Record<string, unknown>;
  const d = defaultSave();
  return {
    v: 1,
    savedAt: num(r.savedAt, 0, 0, Number.MAX_SAFE_INTEGER),
    skin: isSkin(r.skin) ? r.skin : d.skin,
    tier: Math.round(num(r.tier, 1, 1, MAX_TIER)),
    growth: num(r.growth, 0, 0, 1e9),
    coins: Math.round(num(r.coins, 0, 0, 1e12)),
    up: { jump: clampLevel(up.jump), hp: clampLevel(up.hp), speed: clampLevel(up.speed) },
    sound: r.sound !== false,
  };
}

function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k) => m.get(k) ?? null,
    key: (i) => Array.from(m.keys())[i] ?? null,
    removeItem: (k) => void m.delete(k),
    setItem: (k, v) => void m.set(k, String(v)),
  };
}

function pickStorage(): Storage {
  const safe = platform.storage();
  if (safe) return safe;
  try {
    localStorage.setItem('__t', '1');
    localStorage.removeItem('__t');
    return localStorage;
  } catch {
    return memoryStorage();
  }
}

const LOCAL_KEY = 'wormgame.save.v1';
const CLOUD_GAP_MS = 4000;

class SaveManager {
  data: SaveData = defaultSave();
  private store: Storage = memoryStorage();
  private cloudTimer: number | undefined;
  private cloudDirty = false;
  private lastCloudAt = 0;

  /** Загрузка: берём более свежее из локального хранилища и облака. */
  async init(): Promise<void> {
    this.store = pickStorage();
    let local: SaveData | null = null;
    try {
      local = sanitize(JSON.parse(this.store.getItem(LOCAL_KEY) ?? 'null'));
    } catch {
      local = null;
    }
    let cloud: SaveData | null = null;
    if (platform.player) {
      try {
        cloud = sanitize((await platform.player.getData(['save'])).save);
      } catch (e) {
        console.warn('Облачное сохранение недоступно', e);
      }
    }
    const best = [local, cloud].filter((x): x is SaveData => !!x).sort((a, b) => b.savedAt - a.savedAt)[0];
    if (best) this.data = best;
    platform.onPageHide(() => this.flushNow());
  }

  /** Изменить прогресс: локально пишем сразу, облако поставим в очередь. */
  patch(p: Partial<Omit<SaveData, 'up'>> & { up?: Partial<Upgrades> }): void {
    const { up, ...rest } = p;
    Object.assign(this.data, rest);
    if (up) Object.assign(this.data.up, up);
    this.data.savedAt = Date.now();
    this.writeLocal();
    this.scheduleCloud();
  }

  reset(): void {
    this.data = defaultSave();
    this.data.savedAt = Date.now();
    this.writeLocal();
    this.scheduleCloud();
  }

  private writeLocal(): void {
    try {
      this.store.setItem(LOCAL_KEY, JSON.stringify(this.data));
    } catch {
      /* хранилище переполнено или закрыто: игра продолжается */
    }
  }

  private scheduleCloud(): void {
    this.cloudDirty = true;
    if (!platform.player || this.cloudTimer !== undefined) return;
    const wait = Math.max(0, this.lastCloudAt + CLOUD_GAP_MS - Date.now());
    this.cloudTimer = window.setTimeout(() => void this.flushCloud(), wait);
  }

  private async flushCloud(): Promise<void> {
    this.cloudTimer = undefined;
    if (!this.cloudDirty || !platform.player) return;
    this.cloudDirty = false;
    this.lastCloudAt = Date.now();
    try {
      await platform.player.setData({ save: this.data }, false);
    } catch (e) {
      console.warn('Облачное сохранение не удалось, повторим позже', e);
      this.cloudDirty = true;
      this.scheduleCloud();
    }
  }

  /** Закрытие вкладки или уход со страницы: пишем всё, что накопилось, не нарушая лимитов. */
  flushNow(): void {
    this.writeLocal();
    if (this.cloudDirty && platform.player && Date.now() - this.lastCloudAt > 1500) {
      if (this.cloudTimer !== undefined) {
        window.clearTimeout(this.cloudTimer);
        this.cloudTimer = undefined;
      }
      void this.flushCloud();
    }
  }
}

export const save = new SaveManager();
