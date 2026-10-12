import rig from '../../design/worm/rig.json';

export type SkinId = 'peach' | 'salad' | 'plum';

export interface SkinInfo {
  id: SkinId;
  tag: string;
  crown: boolean;
}

export const SKINS: SkinInfo[] = rig.skins.map((s) => ({ id: s.id as SkinId, tag: s.tag, crown: s.crown }));

export const DEFAULT_SKIN: SkinId = 'plum';

export function isSkin(id: unknown): id is SkinId {
  return SKINS.some((s) => s.id === id);
}

export function skinInfo(id: SkinId): SkinInfo {
  return SKINS.find((s) => s.id === id) ?? SKINS[0];
}
