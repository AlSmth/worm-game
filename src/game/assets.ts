/** Масштаб растеризации атласов (из public/assets/atlas-info.json): рисунок в атласе может быть уменьшен, игра это компенсирует. */
const scales: Record<string, number> = {};

export function setAtlasInfo(info: Record<string, { scale: number }>): void {
  for (const key of Object.keys(info)) scales[key] = info[key].scale;
}

export function atlasScale(key: string): number {
  return scales[key] ?? 1;
}
