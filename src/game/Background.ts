import Phaser from 'phaser';
import { WORLD_WIDTH } from '../data/world';
import { atlasScale } from './assets';

/**
 * Фон зоны 1: небо с облаками, кромка с травой, три слоя почвы с параллаксом, затемнение с глубиной и каменные стены
 * по краям карты. Рисунки лежат в design/zone-1-underground/background. Почва не растёт вместе с червём: по мере роста камера
 * отъезжает, и земля становится мельче («сначала масштаб земли»). Всё рисуется только в видимой области.
 */
/** alpha: средний и ближний слои приглушены, чтобы червь и добыча читались на фоне. */
const LAYERS: Array<{ key: string; depth: number; parallax: number; alpha: number }> = [
  { key: 'bg-z1-far', depth: -98, parallax: 0.35, alpha: 1 },
  { key: 'bg-z1-mid', depth: -97.5, parallax: 0.65, alpha: 0.55 },
  { key: 'bg-z1-near', depth: -97, parallax: 1, alpha: 0.72 },
];
const EDGE_GROUND = 190; // линия земли на полосе кромки, px рисунка (tools/gen_zone1.py)
const EDGE_HEIGHT = 512;
const CLOUD_TOP = -820; // верх полосы облаков в мире
const CLOUD_PARALLAX = 0.15;

export class WorldBackground {
  private sky: Phaser.GameObjects.Rectangle;
  private horizon: Phaser.GameObjects.Image;
  private clouds: Phaser.GameObjects.TileSprite;
  private layers: Phaser.GameObjects.TileSprite[] = [];
  private shade: Phaser.GameObjects.Image;
  private deep: Phaser.GameObjects.Rectangle;
  private edge: Phaser.GameObjects.TileSprite;
  private walls: Phaser.GameObjects.TileSprite[] = [];
  private rims: Phaser.GameObjects.Rectangle[] = [];
  private edges: Phaser.GameObjects.Rectangle[] = [];

  constructor(scene: Phaser.Scene) {
    this.sky = scene.add.rectangle(0, 0, 10, 10, 0x3f9cff).setOrigin(0, 0).setDepth(-100);
    this.horizon = scene.add.image(0, 0, 'bg-horizon').setOrigin(0, 0).setDepth(-99);
    this.clouds = scene.add.tileSprite(0, 0, 10, 256, 'bg-z1-clouds').setOrigin(0, 0).setDepth(-98.8);
    for (const l of LAYERS) this.layers.push(scene.add.tileSprite(0, 0, 10, 10, l.key).setOrigin(0, 0).setDepth(l.depth).setAlpha(l.alpha));
    this.shade = scene.add.image(0, 0, 'bg-depth').setOrigin(0, 0).setDepth(-96.5);
    this.deep = scene.add.rectangle(0, 0, 10, 10, 0x120806, 0.9).setOrigin(0, 0).setDepth(-96.5);
    this.edge = scene.add.tileSprite(0, 0, 10, EDGE_HEIGHT, 'bg-z1-edge').setOrigin(0, 0).setDepth(-60);
    // стены: слева (индекс 0) и справа (индекс 1) за краем карты, поверх почвы и травы, под добычей
    for (let i = 0; i < 2; i++) {
      this.walls.push(scene.add.tileSprite(0, 0, 10, 10, 'bg-z1-far').setOrigin(0, 0).setDepth(-59).setTint(0x8c93ad));
      this.rims.push(scene.add.rectangle(0, 0, 10, 10, 0x120806, 0.6).setOrigin(0, 0).setDepth(-58));
      this.edges.push(scene.add.rectangle(0, 0, 10, 10, 0xd7dcec, 1).setOrigin(0, 0).setDepth(-57));
    }
  }

  update(cam: Phaser.Cameras.Scene2D.Camera, S: number): void {
    // cam.worldView Phaser пересчитывает уже после шага сцены, то есть он отстаёт на кадр, а у большого червя камера
    // за кадр уходит далеко. Поэтому видимую область считаем сами по актуальным scroll и zoom и берём запас в экранных пикселях.
    const vw = cam.width / cam.zoom;
    const vh = cam.height / cam.zoom;
    const margin = 14 / cam.zoom;
    const left = cam.scrollX + cam.width / 2 - vw / 2 - margin;
    const width = vw + 2 * margin;
    const top = cam.scrollY + cam.height / 2 - vh / 2 - margin;
    const bottom = top + vh + 2 * margin;

    // небо над землёй: градиент и облака
    const skyH = Math.max(0, Math.min(bottom, 0) - top);
    this.sky.setVisible(skyH > 0).setPosition(left, top).setSize(width, Math.max(1, skyH));
    const hz = 1100 * S;
    this.horizon.setVisible(bottom > -hz).setPosition(left, -hz).setDisplaySize(width, hz);
    const cs = 1 / atlasScale('bg-z1-clouds');
    const cloudH = 256 * cs;
    const cloudTop = CLOUD_TOP * Math.max(1, S * 0.6);
    this.clouds.setVisible(bottom > cloudTop && top < cloudTop + cloudH);
    if (this.clouds.visible) {
      this.clouds.setPosition(left, cloudTop).setSize(width, cloudH).setTileScale(cs, cs);
      this.clouds.tilePositionX = (left * CLOUD_PARALLAX) / cs;
    }

    // слои почвы под землёй: рисунок в px мира (масштаб 1), параллакс по слоям
    const y0 = Math.max(top, 0);
    const soilH = bottom - y0;
    for (let i = 0; i < LAYERS.length; i++) {
      const layer = this.layers[i];
      const f = LAYERS[i].parallax;
      const k = 1 / atlasScale(LAYERS[i].key);
      layer.setVisible(soilH > 0).setPosition(left, y0).setSize(width, Math.max(1, soilH)).setTileScale(k, k);
      layer.tilePositionX = (left * f) / k;
      layer.tilePositionY = (y0 * f) / k;
    }

    const shadeH = 3200 * S;
    this.shade.setVisible(soilH > 0 && y0 < shadeH).setPosition(left, 0).setDisplaySize(width, shadeH);
    this.deep.setVisible(bottom > shadeH).setPosition(left, shadeH).setSize(width, Math.max(1, bottom - shadeH));

    // кромка: трава над землёй, дёрн и корешки под ней; линия земли на y = 0
    const ek = 1 / atlasScale('bg-z1-edge');
    const eTop = -EDGE_GROUND * ek;
    this.edge.setVisible(bottom > eTop && top < eTop + EDGE_HEIGHT * ek);
    if (this.edge.visible) {
      this.edge.setPosition(left, eTop).setSize(width, EDGE_HEIGHT * ek).setTileScale(ek, ek);
      this.edge.tilePositionX = left / ek;
    }

    // каменные стены по краям карты, от неба до глубины
    const half = WORLD_WIDTH / 2;
    const right = left + width;
    const rimW = Math.max(40, 70 * S);
    const wallH = bottom - top;
    const wk = 1 / atlasScale('bg-z1-far');
    const sides: Array<[number, number, number]> = [
      [left, -half, 0], // слева: от края видимой области до границы мира
      [half, right, 1], // справа: от границы мира до края видимой области
    ];
    for (const [x0, x1, i] of sides) {
      const w = x1 - x0;
      const wall = this.walls[i];
      const rim = this.rims[i];
      wall.setVisible(w > 0);
      rim.setVisible(i === 0 ? left < -half + rimW && right > -half : right > half - rimW && left < half);
      if (w > 0) {
        wall.setPosition(x0, top).setSize(w, Math.max(1, wallH));
        wall.setTileScale(wk, wk);
        wall.tilePositionX = x0 / wk;
        wall.tilePositionY = top / wk;
      }
      // тёмная полоса у кромки внутри карты и светлая кромка самой стены: граница читается сразу
      if (rim.visible) rim.setPosition(i === 0 ? -half : half - rimW, top).setSize(rimW, Math.max(1, wallH));
      const edge = this.edges[i];
      const ew = Math.max(8, 14 * S);
      edge.setVisible(w > 0).setPosition(i === 0 ? -half - ew : half, top).setSize(ew, Math.max(1, wallH));
    }
  }
}
