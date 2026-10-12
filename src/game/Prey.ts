import Phaser from 'phaser';

export type PreyKind = 'soil' | 'surface' | 'air';

export interface PreyItem {
  img: Phaser.GameObjects.Image;
  x: number;
  y: number;
  r: number;
  kind: PreyKind;
  vx: number;
  baseY: number;
  phase: number;
  turnIn: number;
  dying: boolean;
}

const BEETLE_RADIUS = 48; // радиус тела жука на рисунке 128×128
const BEETLE_FEET = 52; // от центра рисунка до лапок
const COUNT = 30;
const START_CLEARANCE = 320; // свободная зона вокруг червя при начальной расстановке, px при масштабе 1
const TINTS = [0xffffff, 0xffe2b0, 0xd2f5a8, 0xffbcbc, 0xbddcff, 0xf3c6ff];

export interface View {
  w: number; // видимая область в px мира
  h: number;
}

/**
 * Добыча-болванки для прототипа: жуки разных размеров под землёй, на поверхности и в воздухе.
 * Съедобной считается добыча не крупнее пасти червя.
 */
export class PreySystem {
  items: PreyItem[] = [];

  constructor(private scene: Phaser.Scene) {}

  /** Заполнить всю область вокруг червя при старте. */
  populate(wx: number, wy: number, S: number, view: View, jumpH: number): void {
    for (let i = 0; i < COUNT; i++) this.spawn(wx, wy, S, view, jumpH, false);
  }

  update(dt: number, t: number, wx: number, wy: number, S: number, view: View, jumpH: number): void {
    for (const it of this.items) {
      if (it.dying) continue;
      it.phase += dt;
      if (it.kind === 'surface') {
        it.turnIn -= dt;
        if (it.turnIn <= 0) {
          it.vx = -it.vx || 30 * S;
          it.turnIn = 2 + Math.random() * 4;
        }
        it.x += it.vx * dt;
        it.y = -(it.r / BEETLE_RADIUS) * BEETLE_FEET;
      } else if (it.kind === 'soil') {
        it.x += it.vx * dt;
        it.y = it.baseY + Math.sin(t * 1.5 + it.phase) * 6 * S;
      } else {
        it.x += it.vx * dt * 0.4;
        it.y = it.baseY + Math.sin(t * 2 + it.phase) * 10 * S;
      }
      it.img.setPosition(it.x, it.y).setFlipX(it.vx < 0);
    }
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
    while (this.items.filter((it) => !it.dying).length < COUNT) this.spawn(wx, wy, S, view, jumpH, true);
  }

  private spawn(wx: number, wy: number, S: number, view: View, jumpH: number, atEdge: boolean): void {
    const roll = Math.random();
    const kind: PreyKind = roll < 0.62 ? 'soil' : roll < 0.8 ? 'surface' : 'air';
    const r = S * (16 + 48 * Math.pow(Math.random(), 1.1));
    let x = wx;
    let y = wy;
    // При начальной расстановке вокруг червя остаётся свободная зона: первая добыча достаётся игроку, а не появляется во рту.
    for (let attempt = 0; attempt < 8; attempt++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      x = atEdge ? wx + side * view.w * (0.6 + Math.random() * 0.4) : wx + (Math.random() * 2 - 1) * view.w * 0.9;
      if (kind === 'soil') y = Math.max(r + 40 * S, wy + (Math.random() * 2 - 0.6) * view.h * 0.9);
      else if (kind === 'surface') y = -(r / BEETLE_RADIUS) * BEETLE_FEET;
      else y = -(0.25 + Math.random() * 0.65) * jumpH - r;
      if (kind === 'soil') y = Math.min(y, 1700 * S);
      if (atEdge || Math.hypot(x - wx, y - wy) > START_CLEARANCE * S) break;
    }
    const vx = (Math.random() < 0.5 ? -1 : 1) * (10 + Math.random() * 30) * S;
    const img = this.scene.add
      .image(x, y, 'props', 'z1-beetle')
      .setScale(r / BEETLE_RADIUS)
      .setDepth(-50)
      .setTint(TINTS[Math.floor(Math.random() * TINTS.length)])
      .setFlipX(vx < 0);
    this.items.push({ img, x, y, r, kind, vx, baseY: y, phase: Math.random() * 6, turnIn: 2 + Math.random() * 4, dying: false });
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
  }
}
