import Phaser from 'phaser';
import { SKINS } from '../data/skins';
import { setLoaderProgress } from '../core/loader';
import { setAtlasInfo } from '../game/assets';
import { makeTextures } from '../game/textures';

/** Фоны зоны 1 (одиночные картинки, повторяющиеся плитки). */
export const BACKGROUNDS = ['bg-z1-far', 'bg-z1-mid', 'bg-z1-near', 'bg-z1-edge', 'bg-z1-clouds', 'bg-z2-skyline', 'bg-z2-hills', 'bg-z4-stars-a', 'bg-z4-stars-b'];

/** Загрузка графики и градиентов, затем запуск игры. */
export class BootScene extends Phaser.Scene {
  constructor() {
    super('Boot');
  }

  preload(): void {
    this.load.on('progress', (p: number) => setLoaderProgress(p));
    this.load.json('atlas-info', 'assets/atlas-info.json');
    for (const s of SKINS) this.load.atlas(`worm-${s.id}`, `assets/worm-${s.id}.png`, `assets/worm-${s.id}.json`);
    for (const s of SKINS) this.load.atlas(`gear-${s.id}`, `assets/gear-${s.id}.png`, `assets/gear-${s.id}.json`);
    this.load.atlas('wings', 'assets/wings.png', 'assets/wings.json');
    this.load.atlas('props', 'assets/props.png', 'assets/props.json');
    this.load.atlas('treasure', 'assets/treasure.png', 'assets/treasure.json');
    this.load.atlas('fx', 'assets/fx.png', 'assets/fx.json');
    this.load.atlas('z2', 'assets/z2.png', 'assets/z2.json');
    this.load.atlas('z3', 'assets/z3.png', 'assets/z3.json');
    this.load.atlas('z4', 'assets/z4.png', 'assets/z4.json');
    for (const n of BACKGROUNDS) this.load.image(n, `assets/${n}.png`);
  }

  create(): void {
    setAtlasInfo(this.cache.json.get('atlas-info') as Record<string, { scale: number }>);
    makeTextures(this);
    this.scene.start('Game');
  }
}
