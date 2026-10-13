import Phaser from 'phaser';
import { EARTH_R, FINAL_TIER, MOON_R, MOON_X, MOON_Y, SWIM_SPEED, SPACE_TIER, skyTop, spaceHalf, spaceTop, worldHalf } from '../data/world';
import {
  AIR_GUARD_RANGE,
  AIR_SPECS,
  airCount,
  airGuardQuota,
  airSpecOf,
  airWeight,
  type AirKind,
  type AirSpec,
  type AirZone,
} from '../data/air';
import type { View } from './Prey';
import type { BodyCircle, RocketSystem, WormInfo } from './Rockets';

const DEPTH_BODY = -55;
const DEPTH_MOON = -69;
const DEPTH_EARTH = -70;
const HALO_COLOR = 0xfff3a0;
/** Радиус диска планеты на рисунке (px): свечение атмосферы лежит снаружи, масштаб считаем по самому шару. */
const DISC_R: Partial<Record<AirKind, number>> = { earth: 226, moon: 236 };

export interface AirItem {
  spec: AirSpec;
  img: Phaser.GameObjects.Image;
  halo: Phaser.GameObjects.Image;
  frames: string[];
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** Радиус для челюстей и касаний, px мира. */
  r: number;
  /** Размеры на экране, px мира. */
  w: number;
  h: number;
  scale: number;
  dir: number;
  phase: number;
  /** Высота покачивания, px, и точка, около которой качается. */
  bob: number;
  y0: number;
  frame: number;
  step: number;
  think: number;
  dying: boolean;
  /** Стоит на месте и не пропадает при удалении (Земля, Луна). */
  fixed: boolean;
  // пуск ракет
  cooldown: number;
  charge: number;
  salvoLeft: number;
  salvoT: number;
}

/**
 * Небо и космос (зоны 3 и 4): самолёты, вертолёты, истребители, спутники, станции, астероиды, Луна и Земля. Предметы летают в пустоте
 * вокруг червя (в окне вокруг него, за пределами экрана появляются, далеко позади исчезают). Съедобное определяет та же ёмкость
 * челюстей, что в остальных зонах; истребители и тяжёлые вертолёты стреляют ракетами (общая система `RocketSystem`), крупные
 * астероиды и Луна не по зубам бьют при касании. Данные в src/data/air.ts.
 */
export class AirSystem {
  items: AirItem[] = [];
  /** Земля съедена в этом заходе (финал): больше не появляется до перезагрузки. */
  earthGone = false;

  constructor(private scene: Phaser.Scene, private rockets: RocketSystem) {}

  /** Начальная расстановка вокруг (wx, wy) на тире tier. */
  populate(wx: number, wy: number, S: number, view: View, tier: number): void {
    const zone: AirZone = tier >= SPACE_TIER ? 'space' : 'sky';
    if (zone === 'space') this.ensurePlanets();
    const n = airCount(tier);
    for (let i = 0; i < n; i++) this.spawn(wx, wy, S, view, tier, zone, false);
  }

  /** Земля и Луна: на своих местах, внизу и сбоку (src/data/world.ts). */
  ensurePlanets(): void {
    if (!this.earthGone && !this.items.some((it) => it.spec.kind === 'earth')) this.add(airSpecOf('earth'), 0, EARTH_R, true);
    if (!this.items.some((it) => it.spec.kind === 'moon')) this.add(airSpecOf('moon'), MOON_X, MOON_Y, true);
  }

  update(dt: number, worm: WormInfo, view: View, tier: number): void {
    const zone: AirZone = tier >= SPACE_TIER ? 'space' : 'sky';
    const S = worm.scale;
    const swim = SWIM_SPEED * S;
    this.rockets.viewH = view.h;
    const wx = worm.x;
    const wy = worm.y;
    for (const it of this.items) {
      if (it.dying) continue;
      it.phase += dt;
      this.move(it, dt, swim, view, worm, zone);
      if (it.spec.guard) this.guard(it, dt, swim, view, worm);
      this.draw(it);
    }
    // далеко позади удаляем, новые появляются у границы окна
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it.dying || it.fixed) continue;
      const far = Math.abs(it.x - wx) > view.w * 1.35 + it.r || Math.abs(it.y - wy) > view.h * 1.5 + it.r;
      if (far || it.spec.zone !== zone) {
        this.destroyItem(it);
        this.items.splice(i, 1);
      }
    }
    if (zone === 'space') this.ensurePlanets();
    let alive = this.items.filter((it) => !it.dying && !it.fixed).length;
    const want = airCount(tier);
    let guard = 0;
    while (alive < want && guard++ < 6) {
      if (this.spawn(wx, wy, S, view, tier, zone, true)) alive++;
    }
  }

  /** Подсветить съедобное мягким свечением. */
  highlight(mouthR: number, tier: number, t: number): void {
    for (const it of this.items) {
      if (it.dying) continue;
      if (this.isEdible(it, mouthR, tier)) {
        it.halo.setVisible(true).setPosition(it.x, it.y).setAlpha(0.28 + 0.12 * Math.sin(t * 4.2 + it.phase));
      } else if (it.halo.visible) it.halo.setVisible(false);
    }
  }

  isEdible(it: { r: number; spec: AirSpec }, mouthRadius: number, tier: number): boolean {
    if (it.spec.kind === 'earth') return tier >= FINAL_TIER && mouthRadius >= it.r * 0.95;
    return it.r <= mouthRadius;
  }

  /** Съеденное улетает в рот и исчезает (без крови, п. 3.4.3). */
  consume(it: AirItem, mx: number, my: number, ms = 170): void {
    it.dying = true;
    it.halo.setVisible(false);
    this.scene.tweens.add({
      targets: it.img,
      x: mx,
      y: my,
      scaleX: 0,
      scaleY: 0,
      alpha: 0.2,
      duration: ms,
      ease: 'Quad.easeIn',
      onComplete: () => {
        this.destroyItem(it);
        const i = this.items.indexOf(it);
        if (i >= 0) this.items.splice(i, 1);
      },
    });
  }

  /** Касание не по зубам (астероид, Луна): предмет, в который червь врезался головой или пастью (тело проходит насквозь), или null. */
  touching(circles: BodyCircle[], mouthR: number): AirItem | null {
    circles = circles.slice(0, 2);
    for (const it of this.items) {
      const touch = it.spec.touch;
      if (it.dying || !touch || it.r <= mouthR) continue;
      const rr = it.r * 0.9;
      for (const c of circles) {
        const dx = c.x - it.x;
        const dy = c.y - it.y;
        const R = rr + c.r;
        if (dx * dx + dy * dy < R * R) return it;
      }
    }
    return null;
  }

  clear(): void {
    this.items.forEach((it) => this.destroyItem(it));
    this.items = [];
  }

  /** Для проверок: виды, что сейчас есть. */
  kinds(): AirKind[] {
    return this.items.filter((it) => !it.dying).map((it) => it.spec.kind);
  }

  /** Для проверок и dev-панели: поставить предмет в точку (стоит на месте). */
  place(kind: AirKind, x: number, y: number): AirItem {
    const it = this.add(airSpecOf(kind), x, y, true);
    it.vx = 0;
    it.vy = 0;
    it.think = 1e9;
    it.fixed = true;
    return it;
  }

  // ---------- создание
  private pickSpec(tier: number, zone: AirZone, S: number, y0: number, y1: number): AirSpec | null {
    const top = skyTop(S);
    const fits = (s: AirSpec) => {
      if (zone === 'space') return true;
      // высота вида должна пересекаться с диапазоном высот вида: у лайнеров повыше, у вертолётов пониже
      const lo = -s.alt[1] * top;
      const hi = -s.alt[0] * top;
      return y1 >= lo && y0 <= hi;
    };
    let list = AIR_SPECS.filter((s) => s.zone === zone && s.behavior !== 'static' && airWeight(s, tier) > 0 && fits(s));
    if (!list.length) return null;
    if (zone === 'sky') {
      const guards = this.items.filter((it) => !it.dying && it.spec.guard).length;
      if (guards < airGuardQuota(tier) && Math.random() < 0.85) {
        const g = list.filter((s) => s.guard);
        if (g.length) list = g;
      }
    }
    let roll = Math.random() * list.reduce((a, s) => a + airWeight(s, tier), 0);
    for (const s of list) {
      const w = airWeight(s, tier);
      if (roll < w) return s;
      roll -= w;
    }
    return list[0];
  }

  private spawn(wx: number, wy: number, S: number, view: View, tier: number, zone: AirZone, atEdge: boolean): AirItem | null {
    const top = skyTop(S);
    // окно вокруг червя, где держим предметы; новые появляются вне экрана
    const wy0 = wy - view.h * 1.2;
    const wy1 = wy + view.h * 1.2;
    const lowY = zone === 'sky' ? Math.max(wy0, -top) : Math.max(wy0, -spaceTop(S));
    const highY = zone === 'sky' ? Math.min(wy1, -view.h * 0.04) : Math.min(wy1, -view.h * 0.04);
    if (highY <= lowY) return null;
    const spec = this.pickSpec(tier, zone, S, lowY, highY);
    if (!spec) return null;
    const variantR = spec.r * (0.92 + Math.random() * 0.16);
    const half = zone === 'sky' ? worldHalf(S) - 260 * S : spaceHalf(S);
    let x = wx;
    let y = wy;
    for (let attempt = 0; attempt < 16; attempt++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      x = wx + (atEdge ? side * view.w * (0.6 + Math.random() * 0.7) : (Math.random() * 2 - 1) * view.w * 1.0);
      y = lowY + Math.random() * (highY - lowY);
      if (zone === 'sky') {
        // высота по виду: попадаем в свой диапазон
        const lo = Math.max(lowY, -spec.alt[1] * top);
        const hi = Math.min(highY, -spec.alt[0] * top);
        if (hi <= lo) continue;
        y = lo + Math.random() * (hi - lo);
      }
      x = Math.max(-half + variantR, Math.min(half - variantR, x));
      // у земли предмет не должен упираться в траву; в космосе не залезаем в Землю и Луну
      const clearance = variantR * 0.7 + view.h * 0.02;
      if (y > -clearance) continue;
      if (zone === 'space' && Math.hypot(x - MOON_X, y - MOON_Y) < variantR + MOON_R + view.h * 0.05) continue;
      const free = this.items.every((o) => o.dying || Math.hypot(o.x - x, o.y - y) > (o.r + variantR) * 0.9);
      // при начальной расстановке нет ничего прямо на червя и в кадре на старте
      const offscreen = Math.abs(x - wx) > view.w * 0.5 || Math.abs(y - wy) > view.h * 0.5;
      if (free && (offscreen || !atEdge)) {
        if (!atEdge && !offscreen) continue;
        return this.add(spec, x, y, false, variantR);
      }
    }
    return null;
  }

  private add(spec: AirSpec, x: number, y: number, fixed: boolean, rOverride?: number): AirItem {
    const variant = spec.variants[Math.floor(Math.random() * spec.variants.length)];
    const fr = this.scene.textures.getFrame(spec.atlas, variant[0]);
    const r = rOverride ?? spec.r;
    const disc = DISC_R[spec.kind];
    const scale = disc ? r / disc : r / (0.5 * Math.max(fr.realWidth, fr.realHeight));
    const w = fr.realWidth * scale;
    const h = fr.realHeight * scale;
    const depth = spec.kind === 'earth' ? DEPTH_EARTH : spec.kind === 'moon' ? DEPTH_MOON : DEPTH_BODY;
    const img = this.scene.add.image(x, y, spec.atlas, variant[0]).setScale(scale).setDepth(depth);
    const halo = this.scene.add
      .image(x, y, 'fx', 'fx-glow')
      .setScale((Math.max(w, h) * 1.15) / 128)
      .setDepth(depth - 0.5)
      .setTint(HALO_COLOR)
      .setBlendMode(Phaser.BlendModes.ADD)
      .setVisible(false);
    const dir = Math.random() < 0.5 ? -1 : 1;
    const item: AirItem = {
      spec, img, halo, frames: variant, x, y, vx: 0, vy: 0, r, w, h, scale, dir, phase: Math.random() * 6, bob: r * 0.06, y0: y,
      frame: 0, step: Math.random() * 0.1, think: 2 + Math.random() * 4, dying: false, fixed,
      cooldown: 0.8 + Math.random() * 1.6, charge: 0, salvoLeft: 0, salvoT: 0,
    };
    if (spec.behavior === 'static') item.dir = 1;
    this.items.push(item);
    return item;
  }

  private destroyItem(it: AirItem): void {
    this.scene.tweens.killTweensOf(it.img);
    it.img.destroy();
    it.halo.destroy();
  }

  // ---------- поведение
  private move(it: AirItem, dt: number, swim: number, view: View, worm: WormInfo, zone: AirZone): void {
    const b = it.spec.behavior;
    if (b === 'static' || it.fixed && it.think > 1e8) return;
    const sp = it.spec.speedK * swim;
    it.think -= dt;
    const half = zone === 'sky' ? worldHalf(worm.scale) - 260 * worm.scale : spaceHalf(worm.scale);
    const ceil = spaceTop(worm.scale);
    if (b === 'cruise' || b === 'fighter') {
      // летит по прямой; у края окна разворачивается к червю, чтобы не улетать насовсем
      it.vx = it.dir * sp * (b === 'fighter' ? 1 : 1);
      if (it.think <= 0) {
        it.think = b === 'fighter' ? 3 + Math.random() * 4 : 8 + Math.random() * 10;
        if (Math.abs(it.x - worm.x) > view.w * 0.9) it.dir = it.x > worm.x ? -1 : 1;
        else if (b === 'fighter' && Math.random() < 0.5) it.dir = -it.dir;
      }
      it.x += it.vx * dt;
      it.y = it.y0 + Math.sin(it.phase * 0.8) * it.bob;
    } else if (b === 'hover') {
      if (it.think <= 0) {
        it.think = 3 + Math.random() * 5;
        it.dir = Math.random() < 0.5 ? -1 : 1;
        it.vx = Math.random() < 0.3 ? 0 : it.dir * sp;
      }
      it.x += it.vx * dt;
      it.y = it.y0 + Math.sin(it.phase * 1.3) * it.bob;
    } else if (b === 'drift') {
      if (it.vx === 0 && it.vy === 0) {
        const a = Math.random() * Math.PI * 2;
        it.vx = Math.cos(a) * sp;
        it.vy = Math.sin(a) * sp;
      }
      it.x += it.vx * dt;
      it.y += it.vy * dt;
      it.y0 = it.y;
      it.img.rotation += (it.spec.spin ?? 0) * dt * (it.dir > 0 ? 1 : -1);
      // стены космоса и край атмосферы
      if (it.x < -half + it.r || it.x > half - it.r) it.vx = -it.vx;
      if (it.y < -ceil + it.r || it.y > -it.r * 1.1) it.vy = -it.vy;
    }
    if (Math.abs(it.vx) > 1 && (b === 'cruise' || b === 'hover' || b === 'fighter')) it.dir = it.vx > 0 ? 1 : -1;
    // винт и лопасти: два кадра
    if (it.frames.length > 1) {
      it.step += dt;
      if (it.step > 0.05) {
        it.step = 0;
        it.frame ^= 1;
        it.img.setFrame(it.frames[it.frame]);
      }
    }
  }

  private draw(it: AirItem): void {
    it.img.setPosition(it.x, it.y);
    const b = it.spec.behavior;
    if (b === 'cruise' || b === 'hover' || b === 'fighter') it.img.setFlipX(it.dir < 0);
  }

  /** Истребитель или тяжёлый вертолёт целится в червя и пускает ракеты залпом; под землёй (не виден) не стреляет. */
  private guard(it: AirItem, dt: number, swim: number, view: View, worm: WormInfo): void {
    const g = it.spec.guard;
    if (!g) return;
    const nx = it.x + it.dir * it.w * 0.42;
    const dx = worm.x - nx;
    const dy = worm.y - it.y;
    const inRange = dx * dx + dy * dy < (view.h * AIR_GUARD_RANGE) ** 2;
    it.cooldown = Math.max(0, it.cooldown - dt);
    // червь нырнул или вышел из зоны: залп отменяется
    if (!worm.exposed) it.salvoLeft = 0;
    if (it.salvoLeft > 0) {
      it.salvoT -= dt;
      if (it.salvoT <= 0) {
        this.fire(it, g, nx, worm, swim);
        it.salvoLeft--;
        it.salvoT = g.salvoGap;
      }
    }
    if (worm.exposed && inRange) {
      if (it.charge > 0) {
        it.charge -= dt;
        // перед пуском слегка «моргает» красным
        it.img.setTint(Math.sin(it.phase * 40) > 0 ? 0xffb0a0 : 0xffffff);
        if (it.charge <= 0) {
          it.salvoLeft = g.salvo;
          it.salvoT = 0;
          it.cooldown = g.reload * (0.85 + Math.random() * 0.3);
          it.img.clearTint();
        }
      } else if (it.cooldown <= 0 && it.salvoLeft <= 0) {
        it.charge = g.charge;
      }
    } else {
      it.charge = 0;
      if (it.img.isTinted) it.img.clearTint();
    }
  }

  private fire(it: AirItem, g: NonNullable<AirSpec['guard']>, nx: number, worm: WormInfo, swim: number): void {
    const spread = g.salvo > 1 ? (Math.random() - 0.5) * 0.5 : 0;
    const ang = Math.atan2(worm.y - it.y, worm.x - nx) + spread;
    this.rockets.launch(nx, it.y, ang, g.rocketLen, swim * g.speedK, g.turn, g.damage);
  }
}
