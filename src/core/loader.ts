/** Экран загрузки в HTML: полоса прогресса без текста (язык на этом этапе ещё не известен). Клик его не пропускает (п. 1.19.2). */

export function setLoaderProgress(p: number): void {
  const fill = document.getElementById('loaderFill');
  if (fill) fill.style.width = `${Math.round(Math.max(0, Math.min(1, p)) * 100)}%`;
}

export function hideLoader(): void {
  const el = document.getElementById('loader');
  if (!el) return;
  el.style.opacity = '0';
  window.setTimeout(() => el.remove(), 400);
}
