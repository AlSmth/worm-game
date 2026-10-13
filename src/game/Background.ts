import Phaser from 'phaser';
import { skyTop, spaceHalf, worldHalf, type Zone } from '../data/world';
import { state } from '../core/state';
import { atlasScale } from './assets';

/**
 * Фон: небо с облаками, кромка с травой, три слоя почвы с параллаксом, затемнение с глубиной и каменные стены по краям карты (зоны 1-2).
 * Рисунки лежат в design/zone-1-underground/background. Над землёй видны дальние дома и холмы зоны 2 (design/zone-2-surface/background):
 * сверху видно, что ждёт червя, когда он вырастет. Почва не растёт вместе с червём: по мере роста камера отъезжает, и земля становится
 * мельче («сначала масштаб земли»). В небе (зона 3) цвет неба темнеет с высотой, над землёй плывут полосы облаков, на большой высоте
 * проступают звёзды; в космосе (зона 4) только тёмная пустота и звёзды в два слоя параллакса, по краям арены светящиеся барьеры.
 * Всё рисуется только в видимой области.
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
/**
 * Дальние дома и холмы «на бесконечности»: стоят на земле (низ полосы чуть ниже линии земли, траву рисует кромка), параллакс по слоям,
 * а размер привязан к размеру экрана (доля высоты вида), а не к миру: с отъездом камеры они не становятся крошечными.
 */
const SKYLINE_H = 512;
const HILLS_H = 256;
const SKYLINE_FRAC = 0.27;
const HILLS_FRAC = 0.13;
const SKYLINE_PARALLAX = 0.3;
const HILLS_PARALLAX = 0.55;
const GROUND_SINK = 8;

/** Полосы облаков в небе: высота центра в долях высоты неба, параллакс. */
const SKY_BANDS: Array<{ alt: number; par: number; alpha: number }> = [
  { alt: 0.06, par: 0.1, alpha: 0.95 },
  { alt: 0.16, par: 0.16, alpha: 0.9 },
  { alt: 0.28, par: 0.22, alpha: 0.9 },
  { alt: 0.42, par: 0.3, alpha: 0.8 },
  { alt: 0.58, par: 0.38, alpha: 0.6 },
];
const BAND_FRAC = 0.3;
/** Цвет неба по высоте (доля высоты неба): у земли голубой, выше синеет и темнеет к космосу. */
const SKY_KEYS: Array<[number, number]> = [
  [0, 0x3f9cff],
  [0.3, 0x2d73e2],
  [0.6, 0x1f3a96],
  [0.85, 0x0f1750],
  [1, 0x060a26],
];
const SPACE_COLOR = 0x050a1e;
const SPACE_BARRIER = 0x1a2f7a;
const SPACE_BARRIER_EDGE = 0x7fd0ff;

function lerpColor(a: number, b: number, t: number): number {
  const ar = (a >> 16) & 255;
  const ag = (a >> 8) & 255;
  const ab = a & 255;
  const br = (b >> 16) & 255;
  const bg = (b >> 8) & 255;
  const bb = b & 255;
  return (Math.round(ar + (br - ar) * t) << 16) | (Math.round(ag + (bg - ag) * t) << 8) | Math.round(ab + (bb - ab) * t);
}

export function skyColor(alt: number): number {
  const a = Math.max(0, Math.min(1, alt));
  for (let i = 1; i < SKY_KEYS.length; i++) {
    if (a <= SKY_KEYS[i][0]) {
      const [x0, c0] = SKY_KEYS[i - 1];
      const [x1, c1] = SKY_KEYS[i];
      return lerpColor(c0, c1, (a - x0) / (x1 - x0));
    }
  }
  return SKY_KEYS[SKY_KEYS.length - 1][1];
}

export class WorldBackground {
  private sky: Phaser.GameObjects.Rectangle;
  private horizon: Phaser.GameObjects.Image;
  private clouds: Phaser.GameObjects.TileSprite;
  private skyline: Phaser.GameObjects.TileSprite;
  private hills: Phaser.GameObjects.TileSprite;
  private layers: Phaser.GameObjects.TileSprite[] = [];
  private shade: Phaser.GameObjects.Image;
  private deep: Phaser.GameObjects.Rectangle;
  private edge: Phaser.GameObjects.TileSprite;
  private walls: Phaser.GameObjects.TileSprite[] = [];
  private rims: Phaser.GameObjects.Rectangle[] = [];
  private edges: Phaser.GameObjects.Rectangle[] = [];
  private bands: Phaser.GameObjects.TileSprite[] = [];
  private spaceRect: Phaser.GameObjects.Rectangle;
  private starsA: Phaser.GameObjects.TileSprite;
  private starsB: Phaser.GameObjects.TileSprite;
  private mode: Zone | 'init' = 'init';

  constructor(private scene: Phaser.Scene) {
    this.sky = scene.add.rectangle(0, 0, 10, 10, 0x3f9cff).setOrigin(0, 0).setDepth(-100);
    this.spaceRect = scene.add.rectangle(0, 0, 10, 10, SPACE_COLOR).setOrigin(0, 0).setDepth(-100).setVisible(false);
    this.starsB = scene.add.tileSprite(0, 0, 10, 10, 'bg-z4-stars-b').setOrigin(0, 0).setDepth(-99.8).setVisible(false);
    this.starsA = scene.add.tileSprite(0, 0, 10, 10, 'bg-z4-stars-a').setOrigin(0, 0).setDepth(-99.7).setVisible(false);
    this.horizon = scene.add.image(0, 0, 'bg-horizon').setOrigin(0, 0).setDepth(-99);
    this.clouds = scene.add.tileSprite(0, 0, 10, 256, 'bg-z1-clouds').setOrigin(0, 0).setDepth(-98.8);
    for (let i = 0; i < SKY_BANDS.length; i++) {
      this.bands.push(scene.add.tileSprite(0, 0, 10, 256, 'bg-z1-clouds').setOrigin(0, 0).setDepth(-98.9 + i * 0.01).setVisible(false));
    }
    this.skyline = scene.add.tileSprite(0, 0, 10, SKYLINE_H, 'bg-z2-skyline').setOrigin(0, 0).setDepth(-98.6);
    this.hills = scene.add.tileSprite(0, 0, 10, HILLS_H, 'bg-z2-hills').setOrigin(0, 0).setDepth(-98.4);
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

  update(cam: Phaser.Cameras.Scene2D.Camera, S: number, zone: Zone = 'ground'): void {
    // cam.worldView Phaser пересчитывает уже после шага сцены, то есть он отстаёт на кадр, а у большого червя камера
    // за кадр уходит далеко. Поэтому видимую область считаем сами по актуальным scroll и zoom и берём запас в экранных пикселях.
    const vw = cam.width / cam.zoom;
    const vh = cam.height / cam.zoom;
    const margin = 14 / cam.zoom;
    const left = cam.scrollX + cam.width / 2 - vw / 2 - margin;
    const width = vw + 2 * margin;
    const top = cam.scrollY + cam.height / 2 - vh / 2 - margin;
    const bottom = top + vh + 2 * margin;

    this.setMode(zone);
    if (zone === 'space') {
      this.updateSpace(cam, left, top, width, bottom - top, S);
      return;
    }

    // небо над землёй: градиент (в небе темнеет с высотой) и облака
    const sky = zone === 'sky';
    const topY = skyTop(S);
    const centerY = cam.scrollY + cam.height / 2;
    const alt = sky ? Math.max(0, Math.min(1, -centerY / topY)) : 0;
    const skyH = Math.max(0, Math.min(bottom, 0) - top);
    this.sky.setVisible(skyH > 0).setPosition(left, top).setSize(width, Math.max(1, skyH));
    if (sky) {
      const col = skyColor(alt);
      this.sky.setFillStyle(col);
      cam.setBackgroundColor(col);
    }
    const hz = 1100 * S;
    this.horizon.setVisible(bottom > -hz && alt < 0.2).setPosition(left, -hz).setDisplaySize(width, hz).setAlpha(sky ? Math.max(0, 1 - alt * 6) : 1);
    // звёзды проступают на большой высоте (в космосе они всегда)
    const starA = sky ? Math.max(0, Math.min(1, (alt - 0.5) / 0.35)) : 0;
    this.drawStars(cam, left, top, width, bottom - top, starA);
    const cs = 1 / atlasScale('bg-z1-clouds');
    if (sky) {
      // полосы облаков на разных высотах: размер привязан к размеру экрана, чтобы с отъездом камеры они не мельчали
      const bh = BAND_FRAC * vh;
      const ts = bh / 256;
      for (let i = 0; i < SKY_BANDS.length; i++) {
        const b = SKY_BANDS[i];
        const y0 = -b.alt * topY - bh / 2;
        const band = this.bands[i];
        band.setVisible(bottom > y0 && top < y0 + bh);
        if (band.visible) {
          band.setPosition(left, y0).setSize(width, bh).setTileScale(ts, ts).setAlpha(b.alpha * Math.max(0, 1 - Math.max(0, alt - b.alt - 0.25) * 4));
          band.tilePositionX = (left * b.par) / ts;
        }
      }
      this.clouds.setVisible(false);
    } else {
      const cloudH = 256 * cs;
      const cloudTop = CLOUD_TOP * Math.max(1, S * 0.6);
      this.clouds.setVisible(bottom > cloudTop && top < cloudTop + cloudH);
      if (this.clouds.visible) {
        this.clouds.setPosition(left, cloudTop).setSize(width, cloudH).setTileScale(cs, cs);
        this.clouds.tilePositionX = (left * CLOUD_PARALLAX) / cs;
      }
    }

    // дальние дома и холмы над землёй
    const sk = (SKYLINE_FRAC * vh) / SKYLINE_H;
    const skTop = GROUND_SINK - SKYLINE_H * sk;
    this.skyline.setVisible(bottom > skTop && top < GROUND_SINK);
    if (this.skyline.visible) {
      this.skyline.setPosition(left, skTop).setSize(width, SKYLINE_H * sk).setTileScale(sk, sk);
      this.skyline.tilePositionX = (left * SKYLINE_PARALLAX) / sk;
    }
    const hk = (HILLS_FRAC * vh) / HILLS_H;
    const hTop = GROUND_SINK - HILLS_H * hk;
    this.hills.setVisible(bottom > hTop && top < GROUND_SINK);
    if (this.hills.visible) {
      this.hills.setPosition(left, hTop).setSize(width, HILLS_H * hk).setTileScale(hk, hk);
      this.hills.tilePositionX = (left * HILLS_PARALLAX) / hk;
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
    const half = worldHalf(S);
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

  /** Звёзды двумя слоями параллакса: на экране они всегда одного размера (1 px плитки = 1 px экрана), прозрачность alpha. */
  private drawStars(cam: Phaser.Cameras.Scene2D.Camera, left: number, top: number, width: number, height: number, alpha: number): void {
    const on = alpha > 0.01;
    this.starsA.setVisible(on);
    this.starsB.setVisible(on);
    if (!on) return;
    const ts = (state.layout.dpr || 1) / cam.zoom;
    this.starsA.setPosition(left, top).setSize(width, height).setTileScale(ts, ts).setAlpha(alpha);
    this.starsA.tilePositionX = (left * 0.05) / ts;
    this.starsA.tilePositionY = (top * 0.05) / ts;
    this.starsB.setPosition(left, top).setSize(width, height).setTileScale(ts * 1.6, ts * 1.6).setAlpha(alpha * 0.8);
    this.starsB.tilePositionX = (left * 0.02) / (ts * 1.6);
    this.starsB.tilePositionY = (top * 0.02) / (ts * 1.6);
  }

  /** Космос: тёмная пустота, звёзды, светящиеся барьеры по краям арены. Всё наземное скрыто. */
  private updateSpace(cam: Phaser.Cameras.Scene2D.Camera, left: number, top: number, width: number, height: number, S: number): void {
    cam.setBackgroundColor(SPACE_COLOR);
    this.spaceRect.setVisible(true).setPosition(left, top).setSize(width, height);
    this.drawStars(cam, left, top, width, height, 1);
    const half = spaceHalf(S);
    const right = left + width;
    const bw = Math.max(1, 14 / cam.zoom);
    for (let i = 0; i < 2; i++) {
      const x = i === 0 ? -half : half;
      const near = i === 0 ? left < x + bw * 6 : right > x - bw * 6;
      this.rims[i].setVisible(near).setPosition(i === 0 ? x : x - bw * 6, top).setSize(bw * 6, Math.max(1, height));
      this.edges[i].setVisible(near).setPosition(i === 0 ? x - bw : x, top).setSize(bw, Math.max(1, height));
    }
  }

  /** Переключение режима: видимость и цвета слоёв, которые зависят от зоны. */
  private setMode(zone: Zone): void {
    if (this.mode === zone) return;
    const prev = this.mode;
    this.mode = zone;
    const space = zone === 'space';
    this.spaceRect.setVisible(space);
    if (space) {
      this.sky.setVisible(false);
      this.horizon.setVisible(false);
      this.clouds.setVisible(false);
      this.skyline.setVisible(false);
      this.hills.setVisible(false);
      this.layers.forEach((l) => l.setVisible(false));
      this.shade.setVisible(false);
      this.deep.setVisible(false);
      this.edge.setVisible(false);
      this.walls.forEach((w) => w.setVisible(false));
      this.bands.forEach((b) => b.setVisible(false));
      this.rims.forEach((r) => r.setFillStyle(SPACE_BARRIER, 0.45));
      this.edges.forEach((e) => e.setFillStyle(SPACE_BARRIER_EDGE, 1));
    } else {
      this.starsA.setVisible(false);
      this.starsB.setVisible(false);
      this.rims.forEach((r) => r.setFillStyle(0x120806, 0.6));
      this.edges.forEach((e) => e.setFillStyle(0xd7dcec, 1));
      if (zone !== 'sky') this.bands.forEach((b) => b.setVisible(false));
      if (zone !== 'sky' || prev === 'init') this.sky.setFillStyle(0x3f9cff);
      this.scene.cameras.main.setBackgroundColor(0x3f9cff);
    }
  }
}
