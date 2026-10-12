import Phaser from 'phaser';
import { WORLD_WIDTH } from '../data/world';
import { GEM_TINTS, TREASURE_COUNT, availableAt, scaledRadius, type TreasureSpec } from '../data/treasure';
import { sizeScale } from '../data/prey';
import type { View } from './Prey';

export interface TreasureItem {
  img: Phaser.GameObjects.Image;
  halo: Phaser.GameObjects.Image;
  spec: TreasureSpec;
  x: number;
  y: number;
  /** Радиус, который должен поместиться в челюсти. */
  r: number;
  /** Сколько монет даёт. */
  value: number;
  phase: number;
  glintIn: number;
  baseScale: number;
  dying: boolean;
}

const HALO_COLOR = 0xffd23f;

/**
 * Сокровища зоны 1: монеты, самоцветы, сундуки. Лежат в земле неподвижно, глубже богаче. За съеденное даются монеты
 * (концепт, раздел 8). Появляются рядом с игроком, как добыча, и пропадают, когда он уплыл далеко.
 */
export class TreasureSystem {
  items: TreasureItem[] = [];

  constructor(
    private scene: Phaser.Scene,
    /** Блеск на сокровище: сцена показывает искру в этой точке. */
    private onGlint: (x: number, y: number) => void,
  ) {}

  populate(wx: number, wy: number, S: number, view: View): void {
    for (let i = 0; i < TREASURE_COUNT; i++) this.spawn(wx, wy, S, view, false);
  }

  update(dt: number, t: number, wx: number, wy: number, S: number, view: View, mouthR: number): void {
    for (const it of this.items) {
      if (it.dying) continue;
      it.phase += dt;
      const p = it.phase;
      switch (it.spec.kind) {
        case 'coin':
          // вращение: сжатие по ширине
          it.img.setScale(it.baseScale * (0.18 + 0.82 * Math.abs(Math.cos(p * 3))), it.baseScale);
          break;
        case 'gem':
          it.img.setScale(it.baseScale * (1 + 0.06 * Math.sin(p * 3))).setRotation(0.1 * Math.sin(p * 2));
          break;
        default:
          it.img.setY(it.y + Math.sin(p * 2) * 3 * sizeScale(S));
      }
      const edible = this.isEdible(it, mouthR);
      it.halo.setAlpha(edible ? 0.34 + 0.12 * Math.sin(t * 4 + it.phase) : 0.1);
      it.glintIn -= dt;
      if (it.glintIn <= 0) {
        it.glintIn = 1.4 + Math.random() * 2.4;
        this.onGlint(it.x + (Math.random() - 0.5) * it.r * 1.2, it.y - Math.random() * it.r * 0.8);
      }
    }
    const halfW = view.w * 1.0;
    const halfH = view.h * 1.3;
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.dying) continue;
      if (Math.abs(it.x - wx) > halfW * 1.25 || Math.abs(it.y - wy) > halfH * 1.2) {
        it.img.destroy();
        it.halo.destroy();
        this.items.splice(i, 1);
      }
    }
    while (this.items.filter((it) => !it.dying).length < TREASURE_COUNT) {
      if (!this.spawn(wx, wy, S, view, true)) break;
    }
  }

  /** Выбрать сокровище по глубине; false, если на этой высоте ничего не положено (у самой поверхности). */
  private spawn(wx: number, wy: number, S: number, view: View, atEdge: boolean): boolean {
    const bound = WORLD_WIDTH / 2 - 300 * S;
    const minY = 130 * Math.max(1, S * 0.6);
    const maxY = 1700 * S;
    const side = Math.random() < 0.5 ? -1 : 1;
    const x = Math.max(-bound, Math.min(bound, atEdge ? wx + side * view.w * (0.6 + Math.random() * 0.4) : wx + (Math.random() * 2 - 1) * view.w * 0.9));
    // по вертикали рядом с игроком, но не выше глубины самой дешёвой находки
    const y = Math.max(minY, Math.min(maxY, wy + (Math.random() * 2 - 1) * view.h * 0.9));
    const opts = availableAt(y, S);
    if (!opts.length) return false;
    let roll = Math.random() * opts.reduce((a, o) => a + o.weight, 0);
    let spec = opts[0];
    for (const o of opts) {
      if (roll < o.weight) {
        spec = o;
        break;
      }
      roll -= o.weight;
    }
    let value = spec.value;
    let tint = 0xffffff;
    if (spec.kind === 'gem') {
      const total = GEM_TINTS.reduce((a, g) => a + g.weight, 0);
      let g = Math.random() * total;
      const pick = GEM_TINTS.find((c) => (g -= c.weight) < 0) ?? GEM_TINTS[0];
      tint = pick.tint;
      value = pick.value;
    }
    const k = sizeScale(S);
    const baseScale = spec.look * k;
    const r = scaledRadius(spec, S);
    const img = this.scene.add.image(x, y, 'treasure', spec.frame).setScale(baseScale).setDepth(-49).setTint(tint);
    const halo = this.scene.add
      .image(x, y, 'fx', 'fx-glow')
      .setScale((r * 3.8) / 128)
      .setDepth(-53)
      .setTint(HALO_COLOR)
      .setBlendMode(Phaser.BlendModes.ADD)
      .setAlpha(0.3);
    this.items.push({ img, halo, spec, x, y, r, value, phase: Math.random() * 6, glintIn: Math.random() * 2, baseScale, dying: false });
    return true;
  }

  isEdible(it: { r: number }, mouthRadius: number): boolean {
    return it.r <= mouthRadius;
  }

  /** Съеденное улетает в рот. */
  consume(it: TreasureItem, mx: number, my: number): void {
    it.dying = true;
    it.halo.setVisible(false);
    this.scene.tweens.add({
      targets: it.img,
      x: mx,
      y: my,
      scaleX: 0,
      scaleY: 0,
      alpha: 0.2,
      duration: 160,
      ease: 'Quad.easeIn',
      onComplete: () => {
        it.img.destroy();
        it.halo.destroy();
        const i = this.items.indexOf(it);
        if (i >= 0) this.items.splice(i, 1);
      },
    });
  }

  clear(): void {
    this.items.forEach((it) => {
      it.img.destroy();
      it.halo.destroy();
    });
    this.items = [];
  }
}

