import Phaser from 'phaser';
import { SKINS } from '../data/skins';
import { setLoaderProgress } from '../core/loader';
import { setAtlasInfo } from '../game/assets';
import { makeTextures } from '../game/textures';

/** Загрузка графики и временных текстур, затем запуск игры. */
export class BootScene extends Phaser.Scene {
  constructor() {
    super('Boot');
  }

  preload(): void {
    this.load.on('progress', (p: number) => setLoaderProgress(p));
    this.load.json('atlas-info', 'assets/atlas-info.json');
    for (const s of SKINS) this.load.atlas(`worm-${s.id}`, `assets/worm-${s.id}.png`, `assets/worm-${s.id}.json`);
    this.load.atlas('wings', 'assets/wings.png', 'assets/wings.json');
    this.load.atlas('props', 'assets/props.png', 'assets/props.json');
  }

  create(): void {
    setAtlasInfo(this.cache.json.get('atlas-info') as Record<string, { scale: number }>);
    makeTextures(this);
    this.scene.start('Game');
  }
}
