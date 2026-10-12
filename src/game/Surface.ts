import Phaser from 'phaser';
import { WORLD_WIDTH, SURFACE_TIER } from '../data/world';
import { wormScale } from '../data/growth';
import {
  DECOR_COUNT,
  DECOR_FRAMES,
  SURFACE_COUNT,
  SURFACE_SPECS,
  guardRange,
  specOf,
  surfaceWeight,
  type SurfaceKind,
  type SurfaceSpec,
} from '../data/surface';
import type { View } from './Prey';

/** Точка опоры рисунка на земле: нижний край фигуры лежит на 4 px выше нижнего края холста (tools/z2kit.py, PAD). */
const PAD = 4;
const DEPTH_BODY = -61;
const DEPTH_DECOR = -62;
const DEPTH_SHOT = -40;
const HALO_COLOR = 0xfff3a0;
/** Начиная с какого тира размеры добычи растут вместе с червём (временно, до зон 3–4): дальше 12-го лесенка зоны 2 кончается. */
const LAST_TIER = 12;

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
}

export interface Shot {
  img: Phaser.GameObjects.Image;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  damage: number;
  life: number;
}

export interface BodyCircle {
  x: number;
  y: number;
  r: number;
}

/** Кусочек информации о черве для добычи: где он, виден ли над землёй. */
export interface WormInfo {
  x: number;
  y: number;
  /** Скорость червя: охрана целится с упреждением. */
  vx: number;
  vy: number;
  scale: number;
  /** Часть червя над землёй: охрана видит и стреляет только в такого. */
  exposed: boolean;
  /** Червь над землёй может «пугать» людей, под землёй глубоко их не тревожит. */
  scary: boolean;
}

export interface SurfaceEvents {
  /** Охрана выстрелила из точки (x, y) снарядом такого-то вида. */
  onShoot: (x: number, y: number, big: boolean) => void;
  /** Снаряд упал на землю или ушёл далеко. */
  onImpact: (x: number, y: number, big: boolean) => void;
}

/**
 * Поверхность зоны 2: люди бегут от червя, машины ездят, дома и башни стоят, техника охраны целится и стреляет в червя,
 * пока он над землёй (над землёй, а не под ней: под землёй безопасно). Всё стоит на земле (y = 0), камера и фон общие.
 * Съедобное определяет та же ёмкость челюстей, что в зоне 1: добыча с радиусом не больше радиуса пасти.
 */
export class SurfaceSystem {
  items: SurfaceItem[] = [];
  shots: Shot[] = [];
  private decor: Array<{ img: Phaser.GameObjects.Image; x: number }> = [];

  constructor(private scene: Phaser.Scene, private ev: SurfaceEvents) {}

  /** Добыча растёт с миром после последнего тира зоны 2 (временная замена зон 3–4). */
  private boost(S: number): number {
    return Math.max(1, S / wormScale(LAST_TIER));
  }

  populate(wx: number, S: number, view: View, tier: number): void {
    for (let i = 0; i < SURFACE_COUNT; i++) this.spawn(wx, S, view, tier, false);
    for (let i = 0; i < DECOR_COUNT; i++) this.spawnDecor(wx, S, view, false);
  }

  update(dt: number, worm: WormInfo, view: View, tier: number, scared: boolean): void {
    const bound = WORLD_WIDTH / 2 - 260 * worm.scale;
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
    this.updateShots(dt, worm);
    // удаляем ушедших далеко и добавляем новых у краёв области
    const halfW = view.w * 1.0;
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.dying) continue;
      if (Math.abs(it.x - worm.x) > halfW * 1.3) {
        this.destroyItem(it);
        this.items.splice(i, 1);
      }
    }
    while (this.items.filter((it) => !it.dying).length < SURFACE_COUNT) this.spawn(worm.x, worm.scale, view, tier, true);
    for (let i = this.decor.length - 1; i >= 0; i--) {
      if (Math.abs(this.decor[i].x - worm.x) > halfW * 1.35) {
        this.decor[i].img.destroy();
        this.decor.splice(i, 1);
      }
    }
    while (this.decor.length < DECOR_COUNT) this.spawnDecor(worm.x, worm.scale, view, true);
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

  /** Попадания: круги тела червя против снарядов над землёй. Возвращает суммарный урон; попавшие снаряды исчезают. */
  collide(circles: BodyCircle[], onHit: (x: number, y: number, dmg: number) => void): number {
    let total = 0;
    for (let i = this.shots.length - 1; i >= 0; i--) {
      const s = this.shots[i];
      for (const c of circles) {
        const dx = s.x - c.x;
        const dy = s.y - c.y;
        const rr = c.r + s.r;
        if (dx * dx + dy * dy < rr * rr) {
          total += s.damage;
          onHit(s.x, s.y, s.damage);
          s.img.destroy();
          this.shots.splice(i, 1);
          break;
        }
      }
    }
    return total;
  }

  clear(): void {
    this.items.forEach((it) => this.destroyItem(it));
    this.items = [];
    this.shots.forEach((s) => s.img.destroy());
    this.shots = [];
    this.decor.forEach((d) => d.img.destroy());
    this.decor = [];
  }

  // ---------- создание ----------
  private pickSpec(tier: number): SurfaceSpec {
    const list = SURFACE_SPECS.map((s) => ({ s, w: surfaceWeight(s, Math.max(tier, SURFACE_TIER), SURFACE_TIER) })).filter((o) => o.w > 0);
    let roll = Math.random() * list.reduce((a, o) => a + o.w, 0);
    for (const o of list) {
      if (roll < o.w) return o.s;
      roll -= o.w;
    }
    return list[0].s;
  }

  private spawn(wx: number, S: number, view: View, tier: number, atEdge: boolean, forced?: { spec: SurfaceSpec; x: number }): SurfaceItem {
    const spec = forced ? forced.spec : this.pickSpec(tier);
    const boost = this.boost(S);
    const bound = WORLD_WIDTH / 2 - 260 * S;
    const variant = spec.variants[Math.floor(Math.random() * spec.variants.length)];
    const fr = this.scene.textures.getFrame('z2', variant[0]);
    const scale = spec.scale * boost;
    const w = fr.realWidth * scale;
    const h = fr.realHeight * scale;
    let x = forced ? forced.x : wx;
    // подальше от соседей, чтобы дома и машины не слипались
    for (let attempt = 0; attempt < 10 && !forced; attempt++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      x = atEdge ? wx + side * view.w * (0.62 + Math.random() * 0.38) : wx + (Math.random() * 2 - 1) * view.w * 0.95;
      x = Math.max(-bound, Math.min(bound, x));
      const free = this.items.every((o) => Math.abs(o.x - x) > (o.w + w) * 0.38);
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
      spec, img, halo, barrel, frames: variant, x, cy: -(h - PAD * scale) / 2, r: spec.r * boost, w, h, scale,
      vx: spec.behavior === 'static' ? 0 : dir * speed * (spec.behavior === 'person' ? 0.25 : 1),
      dir, think: 1 + Math.random() * 3, step: Math.random() * 0.1, frame: 0, phase: Math.random() * 6, dying: false,
      aim: dir > 0 ? -0.9 : -Math.PI + 0.9, cooldown: 1 + Math.random() * 2, charge: 0,
    };
    this.items.push(item);
    halo.setPosition(x, item.cy);
    return item;
  }

  private spawnDecor(wx: number, S: number, view: View, atEdge: boolean): void {
    const d = DECOR_FRAMES[Math.floor(Math.random() * DECOR_FRAMES.length)];
    const fr = this.scene.textures.getFrame('z2', d.frame);
    const side = Math.random() < 0.5 ? -1 : 1;
    const bound = WORLD_WIDTH / 2 - 200 * S;
    const x = Math.max(-bound, Math.min(bound, atEdge ? wx + side * view.w * (0.62 + Math.random() * 0.4) : wx + (Math.random() * 2 - 1) * view.w * 0.98));
    const img = this.scene.add
      .image(x, 0, 'z2', d.frame)
      .setOrigin(0.5, (fr.realHeight - PAD) / fr.realHeight)
      .setScale(d.scale * this.boost(S))
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
    const range = 520 + 160 * worm.scale;
    if (b === 'person') {
      if (scared && worm.scary && Math.abs(dxw) < range) {
        // бежит от червя
        const away = dxw > 0 ? -1 : 1;
        it.vx += (away * it.spec.speed - it.vx) * Math.min(1, 6 * dt);
      } else {
        if (it.think <= 0) {
          it.think = 2 + Math.random() * 4;
          const r = Math.random();
          it.vx = r < 0.35 ? 0 : (r < 0.68 ? -1 : 1) * it.spec.speed * 0.25;
        }
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

  /** Точка крепления ствола на корпусе и положение дульного среза в мире. */
  private mountPoint(it: SurfaceItem): { x: number; y: number } {
    const g = it.spec.guard as NonNullable<SurfaceSpec['guard']>;
    const fr = this.scene.textures.getFrame('z2', it.frames[0]);
    const lx = (g.mount[0] - fr.realWidth / 2) * it.scale * it.dir;
    const ly = (g.mount[1] - (fr.realHeight - PAD)) * it.scale;
    return { x: it.x + lx, y: ly };
  }

  private placeBarrel(it: SurfaceItem): void {
    if (!it.barrel) return;
    const m = this.mountPoint(it);
    it.barrel.setPosition(m.x, m.y).setRotation(it.aim);
    // перед выстрелом ствол «заряжается»: мигает жёлтым
    if (it.charge > 0) it.barrel.setTint(Math.sin(it.phase * 40) > 0 ? 0xfff27a : 0xffffff);
    else it.barrel.clearTint();
  }

  private guard(it: SurfaceItem, dt: number, worm: WormInfo): void {
    const g = it.spec.guard as NonNullable<SurfaceSpec['guard']>;
    const m = this.mountPoint(it);
    const dx = worm.x - m.x;
    const dy = worm.y - m.y;
    const inRange = dx * dx + dy * dy < guardRange(worm.scale) ** 2;
    // перезарядка идёт всегда: когда червь появится, охрана готова и ей остаётся навестись и «зарядить» выстрел
    it.cooldown = Math.max(0, it.cooldown - dt);
    if (worm.exposed && inRange) {
      // упреждение: целимся туда, где червь окажется к прилёту снаряда (не дальше 0,9 с вперёд)
      const tt = Math.min(0.9, Math.hypot(dx, dy) / g.speed);
      const want = Math.atan2(dy + worm.vy * tt * 0.75, dx + worm.vx * tt * 0.75);
      let d = want - it.aim;
      while (d > Math.PI) d -= Math.PI * 2;
      while (d < -Math.PI) d += Math.PI * 2;
      const rate = 3.2 * dt;
      it.aim += Math.max(-rate, Math.min(rate, d));
      if (it.charge > 0) {
        it.charge -= dt;
        if (it.charge <= 0) this.fire(it, g, m);
      } else if (it.cooldown <= 0 && Math.abs(d) < 0.3) {
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

  private fire(it: SurfaceItem, g: NonNullable<SurfaceSpec['guard']>, m: { x: number; y: number }): void {
    const len = g.length * it.scale;
    const x = m.x + Math.cos(it.aim) * len;
    const y = m.y + Math.sin(it.aim) * len;
    const img = this.scene.add.image(x, y, 'z2', g.shot).setScale(g.shotScale * Math.max(1, it.scale * 0.9)).setDepth(DEPTH_SHOT);
    this.shots.push({
      img, x, y, vx: Math.cos(it.aim) * g.speed, vy: Math.sin(it.aim) * g.speed,
      r: (g.shot === 'z2-shell' ? 15 : 9) * g.shotScale * Math.max(1, it.scale * 0.9), damage: g.damage, life: 4,
    });
    it.cooldown = g.reload * (0.8 + Math.random() * 0.4);
    this.ev.onShoot(x, y, g.shot === 'z2-shell');
  }

  private updateShots(dt: number, worm: WormInfo): void {
    for (let i = this.shots.length - 1; i >= 0; i--) {
      const s = this.shots[i];
      s.life -= dt;
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.img.setPosition(s.x, s.y).setRotation(Math.atan2(s.vy, s.vx));
      const far = Math.abs(s.x - worm.x) > 4200 + 900 * worm.scale || s.y < -5200 * worm.scale;
      if (s.life <= 0 || far) {
        s.img.destroy();
        this.shots.splice(i, 1);
      } else if (s.y >= 0) {
        // упал на землю
        this.ev.onImpact(s.x, 0, s.damage > 10);
        s.img.destroy();
        this.shots.splice(i, 1);
      }
    }
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
