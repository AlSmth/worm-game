import Phaser from 'phaser';
import { WORLD_WIDTH } from '../data/world';

/**
 * Временный фон прототипа: небо, трава, почва с затемнением на глубине и каменные стены по краям карты.
 * Всё привязано к миру и рисуется только в видимой области, поэтому тянется бесконечно. Настоящие слои (параллакс) будут на этапе 3.
 */
export class WorldBackground {
  private sky: Phaser.GameObjects.Rectangle;
  private horizon: Phaser.GameObjects.Image;
  private soil: Phaser.GameObjects.TileSprite;
  private shade: Phaser.GameObjects.Image;
  private deep: Phaser.GameObjects.Rectangle;
  private grass: Phaser.GameObjects.TileSprite;
  private walls: Phaser.GameObjects.TileSprite[] = [];
  private rims: Phaser.GameObjects.Rectangle[] = [];
  private edges: Phaser.GameObjects.Rectangle[] = [];

  constructor(scene: Phaser.Scene) {
    this.sky = scene.add.rectangle(0, 0, 10, 10, 0x3f9cff).setOrigin(0, 0).setDepth(-100);
    this.horizon = scene.add.image(0, 0, 'bg-horizon').setOrigin(0, 0).setDepth(-99);
    this.soil = scene.add.tileSprite(0, 0, 10, 10, 'bg-soil').setOrigin(0, 0).setDepth(-98);
    this.shade = scene.add.image(0, 0, 'bg-depth').setOrigin(0, 0).setDepth(-97);
    this.deep = scene.add.rectangle(0, 0, 10, 10, 0x120806, 0.9).setOrigin(0, 0).setDepth(-97);
    this.grass = scene.add.tileSprite(0, 0, 10, 48, 'bg-grass').setOrigin(0, 0).setDepth(-60);
    // стены: слева (индекс 0) и справа (индекс 1) за краем карты, поверх почвы и травы, под добычей
    for (let i = 0; i < 2; i++) {
      this.walls.push(scene.add.tileSprite(0, 0, 10, 10, 'bg-soil').setOrigin(0, 0).setDepth(-59).setTint(0x8c93ad));
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

    // небо над землёй
    const skyH = Math.max(0, Math.min(bottom, 0) - top);
    this.sky.setVisible(skyH > 0).setPosition(left, top).setSize(width, Math.max(1, skyH));
    const hz = 1100 * S;
    this.horizon.setVisible(bottom > -hz).setPosition(left, -hz).setDisplaySize(width, hz);

    // почва под землёй с затемнением на глубине
    const y0 = Math.max(top, 0);
    const soilH = bottom - y0;
    const ts = Math.max(0.2, S);
    this.soil.setVisible(soilH > 0).setPosition(left, y0).setSize(width, Math.max(1, soilH));
    this.soil.setTileScale(ts, ts);
    this.soil.tilePositionX = left / ts;
    this.soil.tilePositionY = y0 / ts;

    const shadeH = 3200 * S;
    this.shade.setVisible(soilH > 0 && y0 < shadeH).setPosition(left, 0).setDisplaySize(width, shadeH);
    this.deep.setVisible(bottom > shadeH).setPosition(left, shadeH).setSize(width, Math.max(1, bottom - shadeH));

    // полоса травы на линии земли
    const gh = 48 * ts;
    this.grass.setVisible(bottom > -gh && top < gh).setPosition(left, -26 * ts).setSize(width, gh);
    this.grass.setTileScale(ts, ts);
    this.grass.tilePositionX = left / ts;

    // каменные стены по краям карты, от неба до глубины
    const half = WORLD_WIDTH / 2;
    const right = left + width;
    const rimW = Math.max(40, 70 * S);
    const wallH = bottom - top;
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
        wall.setTileScale(ts, ts);
        wall.tilePositionX = x0 / ts;
        wall.tilePositionY = top / ts;
      }
      // тёмная полоса у кромки внутри карты и светлая кромка самой стены: граница читается сразу
      if (rim.visible) rim.setPosition(i === 0 ? -half : half - rimW, top).setSize(rimW, Math.max(1, wallH));
      const edge = this.edges[i];
      const ew = Math.max(8, 14 * S);
      edge.setVisible(w > 0).setPosition(i === 0 ? -half - ew : half, top).setSize(ew, Math.max(1, wallH));
    }
  }
}
