import Phaser from 'phaser';
import { WORLD_WIDTH } from '../data/world';

export type PreyLayer = 'soil' | 'surface';
export type Species = 'beetle' | 'worm';

export interface PreyItem {
  img: Phaser.GameObjects.Image;
  x: number;
  y: number;
  /** «Размер» добычи: радиус, который должен поместиться в раскрытые челюсти. */
  r: number;
  kind: PreyLayer;
  species: Species;
  vx: number;
  baseY: number;
  phase: number;
  turnIn: number;
  dying: boolean;
  /** Таймер смены кадра лап и текущий кадр (0 или 1). */
  step: number;
  frame: number;
  /** Пройдено с последней метки следа, px. */
  trail: number;
}

/** Радиус тела на рисунке 128×128, px: по нему задаётся масштаб спрайта. */
const BODY_R: Record<Species, number> = { beetle: 34, worm: 40 };
const STEP_SECONDS: Record<Species, number> = { beetle: 0.12, worm: 0.22 };
const COUNT = 30;
const START_CLEARANCE = 320; // свободная зона вокруг червя при начальной расстановке, px при масштабе 1
const TINTS: Record<Species, number[]> = {
  beetle: [0xffffff, 0xffe2b0, 0xd2f5a8, 0xffbcbc, 0xbddcff, 0xf3c6ff],
  worm: [0xffffff, 0xffdcd2, 0xe6ffd2, 0xd8e8ff],
};
const TRAIL_COLOR = 0x2a170e;
const TRAIL_LIFE = 1.7;

export interface View {
  w: number; // видимая область в px мира
  h: number;
}

interface Mark {
  img: Phaser.GameObjects.Image;
  life: number;
  max: number;
  s0: number;
}

/**
 * Добыча зоны 1: жуки и червячки, вид сверху. Ползают по земле и оставляют за собой небольшой след.
 * Съедобной считается добыча, которая помещается в раскрытые челюсти червя (радиус не больше радиуса пасти).
 */
export class PreySystem {
  items: PreyItem[] = [];
  private freeMarks: Mark[] = [];
  private liveMarks: Mark[] = [];

  constructor(private scene: Phaser.Scene) {}

  /** Заполнить область вокруг червя при старте. */
  populate(wx: number, wy: number, S: number, view: View, surfaceOpen: boolean): void {
    for (let i = 0; i < COUNT; i++) this.spawn(wx, wy, S, view, surfaceOpen, false);
  }

  update(dt: number, t: number, wx: number, wy: number, S: number, view: View, surfaceOpen: boolean): void {
    const bound = WORLD_WIDTH / 2 - 300 * S;
    for (const it of this.items) {
      if (it.dying) continue;
      it.phase += dt;
      const k = it.r / BODY_R[it.species];
      if (it.kind === 'surface') {
        it.turnIn -= dt;
        if (it.turnIn <= 0) {
          it.vx = -it.vx || 30 * S;
          it.turnIn = 2 + Math.random() * 4;
        }
        it.y = -0.22 * it.r;
      } else {
        it.turnIn -= dt;
        if (it.turnIn <= 0) {
          it.vx = (Math.random() < 0.3 ? -it.vx : it.vx) || 20 * S;
          it.turnIn = 3 + Math.random() * 6;
        }
        it.y = it.baseY + Math.sin(t * 1.4 + it.phase) * 6 * S;
      }
      const dx = it.vx * dt;
      it.x += dx;
      if (Math.abs(it.x) > bound) {
        it.x = Math.sign(it.x) * bound;
        it.vx = -it.vx;
      }
      // лапки: кадры сменяются, пока добыча ползёт
      it.step += dt;
      if (it.step >= STEP_SECONDS[it.species]) {
        it.step = 0;
        it.frame ^= 1;
        it.img.setFrame(`z1-${it.species}-${it.frame ? 'b' : 'a'}`);
      }
      // след: тёмные точки за ползущей добычей, постепенно тают
      it.trail += Math.abs(dx);
      const every = 15 * k;
      if (it.trail >= every) {
        it.trail = 0;
        const behind = -Math.sign(it.vx || 1) * 40 * k;
        this.addMark(it.x + behind, it.y + (Math.random() - 0.5) * 6 * k, (0.1 + 0.07 * Math.random()) * k);
      }
      it.img.setPosition(it.x, it.y).setFlipX(it.vx < 0);
    }
    this.updateMarks(dt);
    // удаляем ушедших далеко и добавляем новых у краёв области
    const halfW = view.w * 1.0;
    const halfH = view.h * 1.3;
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.dying) continue;
      if (Math.abs(it.x - wx) > halfW * 1.25 || (it.kind === 'soil' && Math.abs(it.y - wy) > halfH * 1.2)) {
        it.img.destroy();
        this.items.splice(i, 1);
      }
    }
    while (this.items.filter((it) => !it.dying).length < COUNT) this.spawn(wx, wy, S, view, surfaceOpen, true);
  }

  private spawn(wx: number, wy: number, S: number, view: View, surfaceOpen: boolean, atEdge: boolean): void {
    const kind: PreyLayer = surfaceOpen && Math.random() < 0.22 ? 'surface' : 'soil';
    const species: Species = Math.random() < 0.55 ? 'beetle' : 'worm';
    const r = S * (14 + 70 * Math.pow(Math.random(), 1.1));
    const bound = WORLD_WIDTH / 2 - 300 * S;
    let x = wx;
    let y = wy;
    // При начальной расстановке вокруг червя остаётся свободная зона: первая добыча достаётся игроку, а не появляется во рту.
    for (let attempt = 0; attempt < 8; attempt++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      x = atEdge ? wx + side * view.w * (0.6 + Math.random() * 0.4) : wx + (Math.random() * 2 - 1) * view.w * 0.9;
      x = Math.max(-bound, Math.min(bound, x));
      if (kind === 'soil') y = Math.max(r + 60 * S, wy + (Math.random() * 2 - 0.6) * view.h * 0.9);
      else y = -0.22 * r;
      if (kind === 'soil') y = Math.min(y, 1700 * S);
      if (atEdge || Math.hypot(x - wx, y - wy) > START_CLEARANCE * S) break;
    }
    const vx = (Math.random() < 0.5 ? -1 : 1) * (10 + Math.random() * 30) * S;
    const tints = TINTS[species];
    const img = this.scene.add
      .image(x, y, 'props', `z1-${species}-a`)
      .setScale(r / BODY_R[species])
      .setDepth(-50)
      .setTint(tints[Math.floor(Math.random() * tints.length)])
      .setFlipX(vx < 0);
    this.items.push({
      img, x, y, r, kind, species, vx, baseY: y, phase: Math.random() * 6, turnIn: 2 + Math.random() * 4,
      dying: false, step: Math.random() * 0.1, frame: 0, trail: Math.random() * 10,
    });
  }

  // ---------- след ----------
  private addMark(x: number, y: number, s: number): void {
    const m =
      this.freeMarks.pop() ??
      ({ img: this.scene.add.image(0, 0, 'fx-dot').setDepth(-56), life: 0, max: 1, s0: 1 } as Mark);
    m.life = m.max = TRAIL_LIFE * (0.8 + Math.random() * 0.4);
    m.s0 = s;
    m.img.setPosition(x, y).setTint(TRAIL_COLOR).setScale(s).setAlpha(0.5).setVisible(true);
    this.liveMarks.push(m);
  }

  private updateMarks(dt: number): void {
    for (let i = this.liveMarks.length - 1; i >= 0; i--) {
      const m = this.liveMarks[i];
      m.life -= dt;
      if (m.life <= 0) {
        m.img.setVisible(false);
        this.liveMarks.splice(i, 1);
        this.freeMarks.push(m);
        continue;
      }
      m.img.setAlpha(0.5 * (m.life / m.max)).setScale(m.s0 * (0.6 + 0.4 * (m.life / m.max)));
    }
  }

  isEdible(it: PreyItem, mouthRadius: number): boolean {
    return it.r <= mouthRadius;
  }

  /** Съеденное улетает в рот и исчезает (без крови, п. 3.4.3). */
  consume(it: PreyItem, mx: number, my: number): void {
    it.dying = true;
    this.scene.tweens.add({
      targets: it.img,
      x: mx,
      y: my,
      scaleX: 0,
      scaleY: 0,
      alpha: 0.2,
      duration: 140,
      ease: 'Quad.easeIn',
      onComplete: () => {
        it.img.destroy();
        const i = this.items.indexOf(it);
        if (i >= 0) this.items.splice(i, 1);
      },
    });
  }

  clear(): void {
    this.items.forEach((it) => it.img.destroy());
    this.items = [];
    this.liveMarks.forEach((m) => m.img.destroy());
    this.freeMarks.forEach((m) => m.img.destroy());
    this.liveMarks = [];
    this.freeMarks = [];
  }
}
