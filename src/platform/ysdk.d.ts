/** Минимальное описание SDK Яндекс Игр: только то, чем пользуется игра. */

interface YPlayer {
  isAuthorized(): boolean;
  getData(keys?: string[]): Promise<Record<string, unknown>>;
  setData(data: Record<string, unknown>, flush?: boolean): Promise<void>;
}

interface YAdvCallbacks {
  onOpen?: () => void;
  onClose?: (wasShown?: boolean) => void;
  onError?: (error: unknown) => void;
  onRewarded?: () => void;
}

interface YSDK {
  environment: { i18n: { lang: string } };
  features: {
    LoadingAPI?: { ready(): void };
    GameplayAPI?: { start(): void; stop(): void };
  };
  on(event: string, listener: () => void): void;
  off(event: string, listener: () => void): void;
  getPlayer(options?: Record<string, unknown>): Promise<YPlayer>;
  getStorage?: () => Storage;
  adv: {
    showFullscreenAdv(options?: { callbacks?: YAdvCallbacks }): void;
    showRewardedVideo(options?: { callbacks?: YAdvCallbacks }): void;
  };
  auth?: { openAuthDialog(): Promise<void> };
}

/** Появляется, когда подключён скрипт /sdk.js (на платформе). Локально его нет. */
declare const YaGames: { init(options?: Record<string, unknown>): Promise<YSDK> } | undefined;
