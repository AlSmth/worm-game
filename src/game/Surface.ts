import Phaser from 'phaser';
import { SURFACE_TIER, SWIM_SPEED, worldHalf } from '../data/world';
import {
  DECOR_FRAMES,
  SURFACE_SPECS,
  SURFACE_VISIBLE_TIER,
  guardQuota,
  guardRange,
  specOf,
  surfaceCount,
  surfaceWeight,
  type GuardSpec,
  type SurfaceKind,
  type SurfaceSpec,
} from '../data/surface';
import type { View } from './Prey';
import type { RocketSystem, WormInfo } from './Rockets';

/** Точка опоры рисунка на земле: нижний край фигуры лежит на 4 px выше нижнего края холста (tools/z2kit.py, PAD). */
const PAD = 4;
const DEPTH_BODY = -61;
const DEPTH_DECOR = -62;
const HALO_COLOR = 0xfff3a0;

export interface SurfaceItem {
  spec: SurfaceSpec;
  img: Phaser.GameObjects.Image;
  halo: Phaser.GameObjects.Image;
  barrel: Phaser.GameObjects.Image | null;
  frames: string[];
  x: number;
  /** Высота центра над землёй (отрицательная): по ней меряем расстояние до рта. */
  cy: number;
  /** Радиус, который должен поместиться в челюсти, px мира. */
  r: number;
  /** Размеры на экране, px мира. */
  w: number;
  h: number;
  scale: number;
  vx: number;
  dir: number;
  think: number;
  step: number;
  frame: number;
  phase: number;
  dying: boolean;
  // охрана
  aim: number;
  cooldown: number;
  charge: number;
  salvoLeft: number;
  salvoT: number;
}

/**
 * Поверхность зоны 2: люди бегут от червя, машины ездят, дома и башни стоят, техника охраны целится и стреляет ракетами
 * в червя, пока он над землёй (под землёй безопасно). Всё стоит на земле (y = 0), камера и фон общие. Мир в реальных пропорциях
 * (человек 1500 px, машина 3900 px, небоскрёб 36 000 px), размеры в src/data/surface.ts.
 * Съедобное определяет та же ёмкость челюстей, что в зоне 1: добыча с радиусом не больше радиуса пасти.
 */
export class SurfaceSystem {
  items: SurfaceItem[] = [];
  private decor: Array<{ img: Phaser.GameObjects.Image; x: number }> = [];

  constructor(private scene: Phaser.Scene, private rockets: RocketSystem) {}

  populate(wx: number, S: number, view: View, tier: number): void {
    if (tier < SURFACE_VISIBLE_TIER) return;
    const n = surfaceCount(view.w, tier, SURFACE_TIER);
    for (let i = 0; i < n; i++) this.spawn(wx, S, view, tier, false);
    const d = this.decorCount(view);
    for (let i = 0; i < d; i++) this.spawnDecor(wx, S, view, false);
  }

  private decorCount(view: View): number {
    return Math.max(8, Math.min(30, Math.round(view.w / 6500)));
  }

  update(dt: number, worm: WormInfo, view: View, tier: number, scared: boolean): void {
    const bound = worldHalf(worm.scale) - 260 * worm.scale;
    for (const it of this.items) {
      if (it.dying) continue;
      it.phase += dt;
      this.move(it, dt, worm, bound, scared);
      if (it.spec.behavior === 'guard') this.guard(it, dt, worm);
      it.img.setPosition(it.x, 0).setFlipX(it.dir < 0);
      if (it.frames.length > 1) {
        const moving = Math.abs(it.vx) > 12;
        it.step += dt;
        if (moving && it.step > 0.11) {
          it.step = 0;
          it.frame ^= 1;
          it.img.setFrame(it.frames[it.frame]);
        } else if (!moving && it.frame !== 0) {
          it.frame = 0;
          it.img.setFrame(it.frames[0]);
        }
      }
      if (it.barrel) this.placeBarrel(it);
    }
    // удаляем ушедших далеко и добавляем новых у краёв области
    const halfW = view.w * 1.0;
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.dying) continue;
      if (Math.abs(it.x - worm.x) > halfW * 1.3 || tier < SURFACE_VISIBLE_TIER) {
        this.destroyItem(it);
        this.items.splice(i, 1);
      }
    }
    if (tier >= SURFACE_VISIBLE_TIER) {
      const want = surfaceCount(view.w, tier, SURFACE_TIER);
      let alive = this.items.filter((it) => !it.dying).length;
      while (alive < want) {
        this.spawn(worm.x, worm.scale, view, tier, true);
        alive++;
      }
    }
    for (let i = this.decor.length - 1; i >= 0; i--) {
      if (Math.abs(this.decor[i].x - worm.x) > halfW * 1.35 || tier < SURFACE_VISIBLE_TIER) {
        this.decor[i].img.destroy();
        this.decor.splice(i, 1);
      }
    }
    if (tier >= SURFACE_VISIBLE_TIER) {
      const want = this.decorCount(view);
      while (this.decor.length < want) this.spawnDecor(worm.x, worm.scale, view, true);
    }
  }

  /** Подсветить съедобное (мягкое свечение): вызывает сцена, она знает радиус пасти и можно ли выходить на поверхность. */
  highlight(mouthR: number, canExit: boolean, t: number): void {
    for (const it of this.items) {
      if (it.dying) continue;
      const edible = canExit && this.isEdible(it, mouthR);
      if (edible) {
        const pulse = 0.28 + 0.12 * Math.sin(t * 4.2 + it.phase);
        it.halo.setVisible(true).setPosition(it.x, it.cy).setAlpha(pulse);
      } else if (it.halo.visible) it.halo.setVisible(false);
    }
  }

  isEdible(it: { r: number }, mouthRadius: number): boolean {
    return it.r <= mouthRadius;
  }

  /** Съеденное улетает в рот и исчезает (без крови, п. 3.4.3). */
  consume(it: SurfaceItem, mx: number, my: number): void {
    it.dying = true;
    it.halo.setVisible(false);
    this.scene.tweens.add({
      targets: it.img,
      x: mx,
      y: my,
      scaleX: 0,
      scaleY: 0,
      alpha: 0.2,
      duration: 170,
      ease: 'Quad.easeIn',
      onComplete: () => {
        this.destroyItem(it);
        const i = this.items.indexOf(it);
        if (i >= 0) this.items.splice(i, 1);
      },
    });
    if (it.barrel) {
      const b = it.barrel;
      this.scene.tweens.add({ targets: b, x: mx, y: my, scaleX: 0, scaleY: 0, alpha: 0.2, duration: 170, ease: 'Quad.easeIn' });
    }
  }

  clear(): void {
    this.items.forEach((it) => this.destroyItem(it));
    this.items = [];
    this.decor.forEach((d) => d.img.destroy());
    this.decor = [];
  }

  // ---------- создание ----------
  private pickSpec(tier: number): SurfaceSpec {
    const t = Math.max(tier, SURFACE_TIER);
    let list = SURFACE_SPECS.map((s) => ({ s, w: surfaceWeight(s, t, SURFACE_TIER) })).filter((o) => o.w > 0);
    // охраны на тире должно быть не меньше положенного: чем выше тир, тем больше стреляющей техники
    const guards = this.items.filter((it) => !it.dying && it.spec.behavior === 'guard').length;
    if (guards < guardQuota(tier) && Math.random() < 0.85) {
      const g = list.filter((o) => o.s.behavior === 'guard');
      if (g.length) list = g;
    }
    let roll = Math.random() * list.reduce((a, o) => a + o.w, 0);
    for (const o of list) {
      if (roll < o.w) return o.s;
      roll -= o.w;
    }
    return list[0].s;
  }

  private spawn(wx: number, S: number, view: View, tier: number, atEdge: boolean, forced?: { spec: SurfaceSpec; x: number }): SurfaceItem {
    const spec = forced ? forced.spec : this.pickSpec(tier);
    const bound = worldHalf(S) - 260 * S;
    const variant = spec.variants[Math.floor(Math.random() * spec.variants.length)];
    const fr = this.scene.textures.getFrame('z2', variant[0]);
    const scale = spec.scale;
    const w = fr.realWidth * scale;
    const h = fr.realHeight * scale;
    let x = forced ? forced.x : wx;
    // подальше от соседей, чтобы дома и машины не слипались
    for (let attempt = 0; attempt < 12 && !forced; attempt++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      x = atEdge ? wx + side * view.w * (0.62 + Math.random() * 0.38) : wx + (Math.random() * 2 - 1) * view.w * 0.95;
      x = Math.max(-bound, Math.min(bound, x));
      const free = this.items.every((o) => Math.abs(o.x - x) > (o.w + w) * 0.4);
      // при начальной расстановке рядом с червём (над ним) никого, чтобы первая добыча доставалась игроку
      if (free && (atEdge || Math.abs(x - wx) > 220 * S)) break;
    }
    const img = this.scene.add
      .image(x, 0, 'z2', variant[0])
      .setOrigin(0.5, (fr.realHeight - PAD) / fr.realHeight)
      .setScale(scale)
      .setDepth(DEPTH_BODY);
    const halo = this.scene.add
      .image(x, 0, 'fx', 'fx-glow')
      .setScale((Math.max(w, h) * 1.15) / 128)
      .setDepth(DEPTH_BODY - 0.5)
      .setTint(HALO_COLOR)
      .setBlendMode(Phaser.BlendModes.ADD)
      .setVisible(false);
    let barrel: Phaser.GameObjects.Image | null = null;
    if (spec.guard) {
      const bf = this.scene.textures.getFrame('z2', spec.guard.barrel);
      barrel = this.scene.add
        .image(x, 0, 'z2', spec.guard.barrel)
        .setOrigin(spec.guard.pivot[0] / bf.realWidth, spec.guard.pivot[1] / bf.realHeight)
        .setScale(scale)
        .setDepth(DEPTH_BODY + 0.01);
    }
    const dir = Math.random() < 0.5 ? -1 : 1;
    const speed = spec.speed * (0.7 + Math.random() * 0.6);
    const item: SurfaceItem = {
      spec, img, halo, barrel, frames: variant, x, cy: -(h - PAD * scale) / 2, r: spec.r, w, h, scale,
      vx: spec.behavior === 'static' ? 0 : dir * speed * (spec.behavior === 'person' ? 0.25 : 1),
      dir, think: 1 + Math.random() * 3, step: Math.random() * 0.1, frame: 0, phase: Math.random() * 6, dying: false,
      aim: dir > 0 ? -0.9 : -Math.PI + 0.9, cooldown: 0.5 + Math.random() * 1.5, charge: 0, salvoLeft: 0, salvoT: 0,
    };
    this.items.push(item);
    halo.setPosition(x, item.cy);
    return item;
  }

  private spawnDecor(wx: number, S: number, view: View, atEdge: boolean): void {
    const d = DECOR_FRAMES[Math.floor(Math.random() * DECOR_FRAMES.length)];
    const fr = this.scene.textures.getFrame('z2', d.frame);
    const side = Math.random() < 0.5 ? -1 : 1;
    const bound = worldHalf(S) - 200 * S;
    const x = Math.max(-bound, Math.min(bound, atEdge ? wx + side * view.w * (0.62 + Math.random() * 0.4) : wx + (Math.random() * 2 - 1) * view.w * 0.98));
    const img = this.scene.add
      .image(x, 0, 'z2', d.frame)
      .setOrigin(0.5, (fr.realHeight - PAD) / fr.realHeight)
      .setScale(d.scale)
      .setDepth(DEPTH_DECOR)
      .setFlipX(Math.random() < 0.5);
    this.decor.push({ img, x });
  }

  private destroyItem(it: SurfaceItem): void {
    if (it.barrel) this.scene.tweens.killTweensOf(it.barrel);
    it.img.destroy();
    it.halo.destroy();
    it.barrel?.destroy();
  }

  // ---------- поведение ----------
  private move(it: SurfaceItem, dt: number, worm: WormInfo, bound: number, scared: boolean): void {
    const b = it.spec.behavior;
    if (b === 'static') return;
    it.think -= dt;
    const dxw = worm.x - it.x;
    const range = 1500 + 260 * worm.scale;
    if (b === 'person') {
      if (scared && worm.scary && Math.abs(dxw) < range) {
        // бежит от червя
        const away = dxw > 0 ? -1 : 1;
        it.vx += (away * it.spec.speed - it.vx) * Math.min(1, 6 * dt);
      } else if (it.think <= 0) {
        it.think = 2 + Math.random() * 4;
        const r = Math.random();
        it.vx = r < 0.35 ? 0 : (r < 0.68 ? -1 : 1) * it.spec.speed * 0.25;
      }
    } else {
      // машины и охрана ездят туда-сюда; при тревоге ускоряются, охрана остаётся на месте и целится
      if (it.think <= 0) {
        it.think = 5 + Math.random() * 7;
        it.vx = (Math.random() < 0.5 ? -1 : 1) * it.spec.speed * (0.6 + Math.random() * 0.6);
      }
      if (scared && worm.scary && Math.abs(dxw) < range && b === 'car') it.vx += (Math.sign(it.vx || 1) * it.spec.speed * 1.6 - it.vx) * Math.min(1, 3 * dt);
    }
    it.x += it.vx * dt;
    if (Math.abs(it.x) > bound) {
      it.x = Math.sign(it.x) * bound;
      it.vx = -it.vx;
    }
    if (Math.abs(it.vx) > 8) it.dir = it.vx > 0 ? 1 : -1;
  }

  /** Точка крепления ствола на корпусе в мире. */
  private mountPoint(it: SurfaceItem): { x: number; y: number } {
    const g = it.spec.guard as GuardSpec;
    const fr = this.scene.textures.getFrame('z2', it.frames[0]);
    const lx = (g.mount[0] - fr.realWidth / 2) * it.scale * it.dir;
    const ly = (g.mount[1] - (fr.realHeight - PAD)) * it.scale;
    return { x: it.x + lx, y: ly };
  }

  private placeBarrel(it: SurfaceItem): void {
    if (!it.barrel) return;
    const m = this.mountPoint(it);
    it.barrel.setPosition(m.x, m.y).setRotation(it.aim);
    // перед залпом ствол «заряжается»: мигает жёлтым
    if (it.charge > 0) it.barrel.setTint(Math.sin(it.phase * 40) > 0 ? 0xfff27a : 0xffffff);
    else it.barrel.clearTint();
  }

  private guard(it: SurfaceItem, dt: number, worm: WormInfo): void {
    const g = it.spec.guard as GuardSpec;
    const m = this.mountPoint(it);
    const dx = worm.x - m.x;
    const dy = worm.y - m.y;
    const inRange = dx * dx + dy * dy < guardRange(worm.scale) ** 2;
    // перезарядка идёт всегда: когда червь появится, охрана готова и ей остаётся навестись и «зарядить» залп
    it.cooldown = Math.max(0, it.cooldown - dt);
    // червь нырнул: незаконченный залп отменяется
    if (!worm.exposed) it.salvoLeft = 0;
    if (it.salvoLeft > 0) {
      it.salvoT -= dt;
      if (it.salvoT <= 0) {
        this.launch(it, g, m, worm);
        it.salvoLeft--;
        it.salvoT = g.salvoGap;
      }
    }
    if (worm.exposed && inRange) {
      // упреждение: целимся туда, где червь окажется к прилёту ракеты (не дальше 0,9 с вперёд)
      const tt = Math.min(0.9, Math.hypot(dx, dy) / (SWIM_SPEED * worm.scale * g.speedK));
      const want = Math.atan2(dy + worm.vy * tt * 0.6, dx + worm.vx * tt * 0.6);
      let d = want - it.aim;
      while (d > Math.PI) d -= Math.PI * 2;
      while (d < -Math.PI) d += Math.PI * 2;
      const rate = 3.4 * dt;
      it.aim += Math.max(-rate, Math.min(rate, d));
      if (it.charge > 0) {
        it.charge -= dt;
        if (it.charge <= 0) {
          it.salvoLeft = g.salvo;
          it.salvoT = 0;
          it.cooldown = g.reload * (0.85 + Math.random() * 0.3);
        }
      } else if (it.cooldown <= 0 && it.salvoLeft <= 0 && Math.abs(d) < 0.3) {
        it.charge = g.charge;
      }
    } else {
      it.charge = 0;
      const rest = it.dir > 0 ? -0.9 : -Math.PI + 0.9;
      let d = rest - it.aim;
      while (d > Math.PI) d -= Math.PI * 2;
      while (d < -Math.PI) d += Math.PI * 2;
      it.aim += Math.max(-1.2 * dt, Math.min(1.2 * dt, d));
    }
  }

  /** Пуск одной ракеты из залпа: чуть разбрасываем углы, чтобы залп веером шёл к цели. */
  private launch(it: SurfaceItem, g: GuardSpec, m: { x: number; y: number }, worm: WormInfo): void {
    const spread = g.salvo > 1 ? (Math.random() - 0.5) * 0.5 : 0;
    const x = m.x + Math.cos(it.aim) * g.length * it.scale;
    const y = m.y + Math.sin(it.aim) * g.length * it.scale;
    this.rockets.launch(x, y, it.aim + spread, g.rocketLen, SWIM_SPEED * worm.scale * g.speedK, g.turn, g.damage);
  }

  /** Для проверок: виды добычи, что сейчас есть. */
  kinds(): SurfaceKind[] {
    return this.items.filter((it) => !it.dying).map((it) => it.spec.kind);
  }

  /** Для проверок и dev-панели: поставить добычу заданного вида на землю в точке x (стоит на месте). */
  place(kind: SurfaceKind, x: number, S: number): SurfaceItem {
    const it = this.spawn(x, S, { w: 1, h: 1 }, SURFACE_TIER, false, { spec: specOf(kind), x });
    it.vx = 0;
    it.think = 1e9;
    return it;
  }
}
