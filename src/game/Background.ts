import Phaser from 'phaser';

/**
 * Временный фон прототипа: небо, трава, почва с затемнением на глубине. Всё привязано к миру и рисуется
 * только в видимой области, поэтому тянется бесконечно. Настоящие слои (параллакс) будут на этапе 3.
 */
export class WorldBackground {
  private sky: Phaser.GameObjects.Rectangle;
  private horizon: Phaser.GameObjects.Image;
  private soil: Phaser.GameObjects.TileSprite;
  private shade: Phaser.GameObjects.Image;
  private deep: Phaser.GameObjects.Rectangle;
  private grass: Phaser.GameObjects.TileSprite;

  constructor(scene: Phaser.Scene) {
    this.sky = scene.add.rectangle(0, 0, 10, 10, 0x3f9cff).setOrigin(0, 0).setDepth(-100);
    this.horizon = scene.add.image(0, 0, 'bg-horizon').setOrigin(0, 0).setDepth(-99);
    this.soil = scene.add.tileSprite(0, 0, 10, 10, 'bg-soil').setOrigin(0, 0).setDepth(-98);
    this.shade = scene.add.image(0, 0, 'bg-depth').setOrigin(0, 0).setDepth(-97);
    this.deep = scene.add.rectangle(0, 0, 10, 10, 0x120806, 0.9).setOrigin(0, 0).setDepth(-97);
    this.grass = scene.add.tileSprite(0, 0, 10, 48, 'bg-grass').setOrigin(0, 0).setDepth(-60);
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
  }
}
