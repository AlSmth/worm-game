import { DEFAULT_SKIN, isSkin, type SkinId } from '../data/skins';
import { MAX_TIER } from '../data/growth';
import { clampLevel, type Upgrades } from '../data/upgrades';
import { CHALLENGE_COUNT, isKind, type ChallengeState } from '../data/challenges';
import { platform } from './platform';

/**
 * Прогресс игрока (п. 1.9): сохраняется сразу после действия, переживает обновление страницы и поворот экрана,
 * работает для гостя. Локально пишем мгновенно, в облако Яндекса реже: лимит setData 100 запросов за 5 минут,
 * поэтому облачные записи склеиваем и отправляем не чаще раза в 4 секунды.
 */
export interface SaveData {
  v: 3;
  savedAt: number;
  skin: SkinId;
  /** Игрок уже выбирал персонажа (экран выбора показываем один раз, потом он в меню). */
  skinChosen: boolean;
  tier: number;
  growth: number;
  coins: number;
  up: Upgrades;
  sound: boolean;
  /** Что из обучения пройдено (битовая маска, TUTORIAL_*): подсказки показываем один раз. */
  tutorial: number;
  /** Активные испытания (концепт, раздел 10). */
  ch: ChallengeState[];
}

/** Биты обучения. */
export const TUTORIAL_EAT = 1; // первая добыча съедена
export const TUTORIAL_COIN = 2; // первое сокровище съедено
export const TUTORIAL_SHOP_HINT = 4; // подсказка «хватает монет на улучшение» уже показана
export const TUTORIAL_SHOP_OPENED = 8; // магазин уже открывали
export const TUTORIAL_CH_SEEN = 16; // вкладку испытаний уже открывали (красная точка на вкладке гаснет)

export function defaultSave(): SaveData {
  return { v: 3, savedAt: 0, skin: DEFAULT_SKIN, skinChosen: false, tier: 1, growth: 0, coins: 0, up: { jump: 0, hp: 0, speed: 0 }, sound: true, tutorial: 0, ch: [] };
}

function num(v: unknown, def: number, min: number, max: number): number {
  return typeof v === 'number' && Number.isFinite(v) ? Math.max(min, Math.min(max, v)) : def;
}

function sanitizeChallenges(raw: unknown): ChallengeState[] {
  if (!Array.isArray(raw)) return [];
  const out: ChallengeState[] = [];
  for (const c of raw.slice(0, CHALLENGE_COUNT)) {
    if (!c || typeof c !== 'object') continue;
    const r = c as Record<string, unknown>;
    if (!isKind(r.k)) continue;
    const n = Math.round(num(r.n, 1, 1, 1e6));
    out.push({ k: r.k, n, p: Math.round(num(r.p, 0, 0, n)), r: Math.round(num(r.r, 5, 1, 1e6)) });
  }
  return out;
}

/** Проверка и починка данных из хранилища: чужое и повреждённое не должно ломать игру. Старые версии сохранения читаются. */
function sanitize(raw: unknown): SaveData | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const up = (r.up ?? {}) as Record<string, unknown>;
  const d = defaultSave();
  return {
    v: 3,
    savedAt: num(r.savedAt, 0, 0, Number.MAX_SAFE_INTEGER),
    skin: isSkin(r.skin) ? r.skin : d.skin,
    skinChosen: r.skinChosen === true,
    tier: Math.round(num(r.tier, 1, 1, MAX_TIER)),
    growth: num(r.growth, 0, 0, 1e9),
    coins: Math.round(num(r.coins, 0, 0, 1e12)),
    up: { jump: clampLevel(up.jump), hp: clampLevel(up.hp), speed: clampLevel(up.speed) },
    sound: r.sound !== false,
    tutorial: Math.round(num(r.tutorial, 0, 0, 255)),
    ch: sanitizeChallenges(r.ch),
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
