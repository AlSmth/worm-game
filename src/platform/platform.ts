import { createMockSdk } from './mock';
import { detectLang, type Lang } from '../core/i18n';

type PauseListener = (paused: boolean) => void;

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('timeout')), ms);
    p.then(
      (v) => {
        window.clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        window.clearTimeout(timer);
        reject(e);
      },
    );
  });
}

/**
 * Единая точка работы с платформой Яндекс Игр: SDK, пауза, язык, разметка геймплея, реклама.
 * Если SDK нет (разработка, запуск с диска), подставляется локальная имитация, игра работает так же.
 */
class Platform {
  sdk: YSDK = createMockSdk();
  isYandex = false;
  lang: Lang = 'ru';
  player: YPlayer | null = null;

  private platformPaused = false;
  private pageHidden = false;
  private listeners: PauseListener[] = [];
  private playing = false;
  private wantPlaying = false;
  private hideListeners: Array<() => void> = [];

  async init(): Promise<void> {
    if (typeof YaGames !== 'undefined') {
      try {
        this.sdk = await withTimeout(YaGames.init(), 10000);
        this.isYandex = true;
      } catch (e) {
        console.warn('SDK не инициализировался, работаем автономно', e);
      }
    }
    const sdk = this.sdk;
    this.lang = detectLang(sdk.environment?.i18n?.lang ?? navigator.language);

    // Пауза и возобновление: реклама, смена вкладки, сворачивание окна (пп. 1.3, 4.7, 1.19.4)
    sdk.on('game_api_pause', () => this.setPlatformPaused(true));
    sdk.on('game_api_resume', () => this.setPlatformPaused(false));
    // Страховка на случай, если платформа события не пришлёт
    document.addEventListener('visibilitychange', () => this.setPageHidden(document.hidden));
    window.addEventListener('pagehide', () => this.hideListeners.forEach((l) => l()));

    try {
      this.player = await withTimeout(sdk.getPlayer(), 6000);
    } catch (e) {
      console.warn('Игрок недоступен, сохраняем только локально', e);
      this.player = null;
    }
  }

  /** Игра загрузилась, игрок может начинать (п. 1.19.2). Вызывать один раз. */
  ready(): void {
    this.sdk.features?.LoadingAPI?.ready();
  }

  /** true, пока платформа или браузер просят паузу. */
  get paused(): boolean {
    return this.platformPaused || this.pageHidden;
  }

  onPause(cb: PauseListener): void {
    this.listeners.push(cb);
  }

  onPageHide(cb: () => void): void {
    this.hideListeners.push(cb);
  }

  /** Разметка геймплея (п. 1.19.3): true — игрок играет, false — меню, пауза, итоги. */
  gameplay(active: boolean): void {
    this.wantPlaying = active;
    this.syncGameplay();
  }

  private syncGameplay(): void {
    // Пока платформа держит паузу, start/stop за нас вызывает сам SDK.
    if (this.platformPaused) return;
    if (this.wantPlaying === this.playing) return;
    this.playing = this.wantPlaying;
    const api = this.sdk.features?.GameplayAPI;
    if (this.playing) api?.start();
    else api?.stop();
  }

  private setPlatformPaused(v: boolean): void {
    if (this.platformPaused === v) return;
    this.platformPaused = v;
    this.emit();
    if (!v) this.syncGameplay();
  }

  private setPageHidden(v: boolean): void {
    if (this.pageHidden === v) return;
    this.pageHidden = v;
    this.emit();
  }

  private emit(): void {
    const p = this.paused;
    for (const l of this.listeners) l(p);
  }

  /** Облако и локальное хранилище: безопасное хранилище SDK, если есть. */
  storage(): Storage | null {
    try {
      return this.sdk.getStorage?.() ?? null;
    } catch {
      return null;
    }
  }

  /** Полноэкранная реклама (Э7). Возвращает true, если реклама была показана. */
  showInterstitial(): Promise<boolean> {
    return new Promise((resolve) => {
      this.sdk.adv.showFullscreenAdv({
        callbacks: { onClose: (shown) => resolve(!!shown), onError: () => resolve(false) },
      });
    });
  }

  /** Реклама за вознаграждение (Э7). Возвращает true, если награда засчитана. */
  showRewarded(): Promise<boolean> {
    return new Promise((resolve) => {
      let rewarded = false;
      this.sdk.adv.showRewardedVideo({
        callbacks: {
          onRewarded: () => {
            rewarded = true;
          },
          onClose: () => resolve(rewarded),
          onError: () => resolve(false),
        },
      });
    });
  }
}

export const platform = new Platform();
