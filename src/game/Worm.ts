import Phaser from 'phaser';
import rig from '../../design/worm/rig.json';
import { skinInfo, type SkinId } from '../data/skins';
import { JUMP_BONUS, SPEED_BONUS, WINGS_CANVAS, type Upgrades } from '../data/upgrades';
import { SWIM_SPEED, WORLD_WIDTH } from '../data/world';
import { atlasScale } from './assets';

export type Expr = 'idle' | 'open' | 'chomp' | 'hurt' | 'happy';

/** Куда игрок хочет плыть: к точке (мышь, палец), по направлению (клавиатура) или никуда (держим курс). */
export interface Steer {
  mode: 'none' | 'target' | 'dir';
  tx: number;
  ty: number;
  dx: number;
  dy: number;
}

// Параметры движения при масштабе червя 1 (все скорости и длины умножаются на масштаб).
const TURN_RATE = 5.0;
const GRAVITY = 2000;
const JUMP_HEIGHT = 300;
const AIR_CONTROL = 900;
const MAX_DEPTH = 1800;
/** Добыча радиусом до этого помещается в раскрытые челюсти: размер челюсти определяет, что можно съесть. */
const MOUTH_RADIUS = 60;
const HEAD_RADIUS = 60;
const TRAIL_STEP = 3;
/** Пока выход на поверхность закрыт, центр червя не поднимается выше этой глубины («корка» под травой). */
const CEILING = 64;

const DEPTH: Record<string, number> = {
  wingBack: 0,
  crown: 5,
  out: 10,
  shade: 11,
  main: 12,
  light: 13,
  gloss: 14,
  maw: 20,
  jawBottom: 21,
  jawTop: 22,
  wingFront: 150,
  face: 160,
};

/** Раскрытие челюстей по выражению: 0 закрыты, 1 раскрыты полностью. */
const JAW_BY_EXPR: Record<Expr, number> = { idle: 0.53, open: 1, chomp: 0, hurt: 0.1, happy: 0.8 };
const DEG = Math.PI / 180;

interface Node {
  x: number;
  y: number;
  a: number;
}

function angleDiff(a: number, b: number): number {
  let d = a - b;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return d;
}

function smooth(u: number): number {
  const c = Math.max(0, Math.min(1, u));
  return c * c * (3 - 2 * c);
}

/**
 * Червь: гладкая трубка без соединений и две большие челюсти. Голова ведёт, тело идёт по следу головы.
 * Тело рисуется кругами вдоль пути в несколько проходов (контур, тень, тон, свет, блик), поэтому изгибается плавно
 * и растёт без швов. Длина и толщина растут с тиром. Устройство частей и порядок слоёв: design/README.md.
 */
export class Worm {
  x = 0;
  y = 0;
  heading = 0;
  vx = 0;
  vy = 0;
  speed = 0;
  inAir = false;
  /** Видимый масштаб (сглаживается к targetScale). */
  scale = 1;
  targetScale = 1;
  /** Число звеньев роста: длина тела = звенья × rig.step (дробное, плавный рост). */
  segs = 5;
  upgrades: Upgrades = { jump: 0, hp: 0, speed: 0 };
  /** Можно ли выбраться на поверхность (открывается ростом, см. data/world.ts). */
  canExit = true;
  onExit?: () => void;
  onEnter?: () => void;
  /** Червь упёрся в закрытую «корку» под травой (сцена показывает подсказку). */
  onBump?: () => void;

  private skin: SkinId;
  private atlas = '';
  private pools: Phaser.GameObjects.Image[][] = [];
  private jawTop!: Phaser.GameObjects.Image;
  private jawBottom!: Phaser.GameObjects.Image;
  private maw!: Phaser.GameObjects.Image;
  private faceImg!: Phaser.GameObjects.Image;
  private crown: Phaser.GameObjects.Image | null = null;
  private wingBack: Phaser.GameObjects.Image | null = null;
  private wingFront: Phaser.GameObjects.Image | null = null;
  private wingLevel = 0;
  private trail: Array<{ x: number; y: number }> = [];
  private expr: Expr = 'idle';
  private hintExpr: Expr = 'idle';
  private timedExpr: Expr | null = null;
  private timedUntil = 0;
  private facing = 1;
  private flapPhase = 0;
  private wingOpen = 0;
  private jawOpen: number = JAW_BY_EXPR.idle;
  private nodes: Node[] = [];
  private radii: number[] = [];
  /** «Глотки»: утолщения, бегущие по телу от головы к хвосту после укуса. d в px при масштабе 1. */
  private gulps: Array<{ d: number; a: number }> = [];

  constructor(private scene: Phaser.Scene, skin: SkinId, x: number, y: number) {
    this.skin = skin;
    this.build();
    this.reset(x, y, 0);
  }

  // ---------- сборка ----------
  private build(): void {
    const info = skinInfo(this.skin);
    this.atlas = `worm-${this.skin}`;
    const img = (frame: string, depth: number) =>
      this.scene.add.image(0, 0, this.atlas, `worm-${this.skin}-${frame}`).setDepth(depth);
    this.pools = (rig.passes as string[]).map(() => []);
    this.jawTop = img('jaw-top', DEPTH.jawTop);
    this.jawBottom = img('jaw-bottom', DEPTH.jawBottom);
    this.maw = img('maw', DEPTH.maw);
    this.faceImg = img(`face-${this.expr}`, DEPTH.face);
    this.crown = info.crown ? img('crown', DEPTH.crown) : null;
    this.buildWings();
  }

  private destroySprites(): void {
    this.pools.forEach((pool) => pool.forEach((s) => s.destroy()));
    this.pools = [];
    this.jawTop.destroy();
    this.jawBottom.destroy();
    this.maw.destroy();
    this.faceImg.destroy();
    this.crown?.destroy();
    this.wingBack?.destroy();
    this.wingFront?.destroy();
    this.crown = this.wingBack = this.wingFront = null;
  }

  private buildWings(): void {
    this.wingBack?.destroy();
    this.wingFront?.destroy();
    this.wingBack = this.wingFront = null;
    if (this.wingLevel <= 0) return;
    const n = this.wingLevel;
    this.wingBack = this.scene.add.image(0, 0, 'wings', `wings-t${n}-back`).setDepth(DEPTH.wingBack);
    this.wingFront = this.scene.add.image(0, 0, 'wings', `wings-t${n}-front`).setDepth(DEPTH.wingFront);
  }

  setSkin(skin: SkinId): void {
    if (skin === this.skin) return;
    this.destroySprites();
    this.skin = skin;
    this.build();
  }

  getSkin(): SkinId {
    return this.skin;
  }

  setUpgrades(u: Upgrades): void {
    this.upgrades = { ...u };
    if (u.jump !== this.wingLevel) {
      this.wingLevel = u.jump;
      this.buildWings();
    }
  }

  /** Тир с дробной частью: размер и длина растут плавно. */
  setSize(scale: number, segs: number): void {
    this.targetScale = scale;
    this.segs = segs;
  }

  /** Поставить червя на место и вытянуть тело позади головы. */
  reset(x: number, y: number, heading: number): void {
    this.x = x;
    this.y = y;
    this.heading = heading;
    this.vx = this.vy = 0;
    this.speed = 0;
    this.inAir = false;
    this.trail = [];
    const step = TRAIL_STEP * this.scale;
    for (let i = 500; i >= 1; i--) {
      this.trail.push({ x: x - Math.cos(heading) * i * step, y: y - Math.sin(heading) * i * step });
    }
  }

  // ---------- параметры ----------
  get mouthRadius(): number {
    return MOUTH_RADIUS * this.scale;
  }

  get headRadius(): number {
    return HEAD_RADIUS * this.scale;
  }

  get swimSpeed(): number {
    return SWIM_SPEED * this.scale * (1 + SPEED_BONUS[this.upgrades.speed]);
  }

  /** Максимальная высота прыжка вверх (px мира). */
  get jumpHeight(): number {
    return JUMP_HEIGHT * this.scale * (1 + JUMP_BONUS[this.upgrades.jump]);
  }

  /** Насколько раскрыты челюсти (0…1), для проверок. */
  get jaw(): number {
    return this.jawOpen;
  }

  /** Точка рта в мире: сюда «кусает» червь, между кончиками челюстей. */
  mouth(): { x: number; y: number } {
    const S = this.scale;
    const ox = rig.anchors.mouth[0] * S;
    const oy = rig.anchors.mouth[1] * S * this.facing;
    const c = Math.cos(this.heading);
    const s = Math.sin(this.heading);
    return { x: this.x + ox * c - oy * s, y: this.y + ox * s + oy * c };
  }

  /** Проглоченный кусок бежит по телу: мультяшное утолщение от головы к хвосту. */
  gulp(strength = 0.16): void {
    this.gulps.push({ d: 0, a: strength });
    if (this.gulps.length > 6) this.gulps.shift();
  }

  /** Неподвижная поза для портрета (экран выбора): тело не двигается, лицо и челюсти живут. Позицию задают через reset(). */
  hold(dt: number, now: number): void {
    this.scale = this.targetScale;
    this.updateExpression(now);
    this.layout(dt, now);
  }

  // ---------- выражение лица ----------
  /** Постоянное выражение: «открыт» рядом с добычей, иначе спокойный. */
  setHint(e: Expr): void {
    this.hintExpr = e;
  }

  /** Короткое выражение поверх (укус, радость). */
  flash(e: Expr, ms: number, now: number): void {
    this.timedExpr = e;
    this.timedUntil = now + ms;
  }

  // ---------- шаг ----------
  update(dt: number, steer: Steer, now: number): void {
    this.scale += (this.targetScale - this.scale) * Math.min(1, 4 * dt);
    this.move(dt, steer);
    this.pushTrail();
    this.updateExpression(now);
    this.layout(dt, now);
    for (let i = this.gulps.length - 1; i >= 0; i--) {
      const g = this.gulps[i];
      g.d += 420 * dt;
      g.a *= 1 - 0.4 * dt;
      if (g.d > this.segs * rig.step + 140) this.gulps.splice(i, 1);
    }
  }

  private move(dt: number, steer: Steer): void {
    const S = this.scale;
    const swim = this.swimSpeed;
    const half = WORLD_WIDTH / 2 - this.headRadius * 1.4;
    if (!this.inAir) {
      let want: number | null = null;
      if (steer.mode === 'target') {
        const dx = steer.tx - this.x;
        const dy = steer.ty - this.y;
        if (dx * dx + dy * dy > (0.9 * this.headRadius) ** 2) want = Math.atan2(dy, dx);
      } else if (steer.mode === 'dir') {
        want = Math.atan2(steer.dy, steer.dx);
      }
      if (want !== null) {
        const d = angleDiff(want, this.heading);
        const maxTurn = TURN_RATE * dt;
        this.heading += Math.max(-maxTurn, Math.min(maxTurn, d));
      }
      this.speed += (swim - this.speed) * Math.min(1, 5 * dt);
      this.vx = Math.cos(this.heading) * this.speed;
      this.vy = Math.sin(this.heading) * this.speed;
      this.x += this.vx * dt;
      this.y += this.vy * dt;

      // каменные стены по краям карты: червь скользит вдоль них
      if (this.x < -half) {
        this.x = -half;
        if (Math.cos(this.heading) < 0) this.heading = Math.sin(this.heading) >= 0 ? Math.PI / 2 : -Math.PI / 2;
      } else if (this.x > half) {
        this.x = half;
        if (Math.cos(this.heading) > 0) this.heading = Math.sin(this.heading) >= 0 ? Math.PI / 2 : -Math.PI / 2;
      }
      const maxY = MAX_DEPTH * S;
      if (this.y > maxY) {
        this.y = maxY;
        if (Math.sin(this.heading) > 0) this.heading = Math.cos(this.heading) >= 0 ? 0 : Math.PI;
      }
      if (!this.canExit) {
        // выход закрыт: упираемся в «корку» под травой и скользим вдоль неё
        const ceil = CEILING * S;
        if (this.y < ceil) {
          this.y = ceil;
          if (Math.sin(this.heading) < 0) {
            this.heading = Math.cos(this.heading) >= 0 ? 0 : Math.PI;
            this.onBump?.();
          }
        }
      } else if (this.y < 0 && this.vy < 0) {
        // выход на поверхность: прыжок. Чем круче вверх, тем выше (до полной высоты прыжка).
        const k = Math.max(0.35, -Math.sin(this.heading));
        const v0 = Math.sqrt(2 * GRAVITY * S * this.jumpHeight);
        this.vy = -v0 * k;
        this.vx = Math.cos(this.heading) * Math.max(this.speed, swim * 0.8);
        this.y = Math.min(this.y, -0.01);
        this.inAir = true;
        this.onExit?.();
      }
    } else {
      this.vy += GRAVITY * S * dt;
      let ax = 0;
      if (steer.mode === 'target') ax = Math.sign(steer.tx - this.x) * AIR_CONTROL * S;
      else if (steer.mode === 'dir') ax = steer.dx * AIR_CONTROL * S;
      this.vx += ax * dt;
      const maxVx = swim * 2.2;
      this.vx = Math.max(-maxVx, Math.min(maxVx, this.vx));
      this.x += this.vx * dt;
      this.y += this.vy * dt;
      if (this.x < -half) {
        this.x = -half;
        this.vx = Math.max(0, this.vx);
      } else if (this.x > half) {
        this.x = half;
        this.vx = Math.min(0, this.vx);
      }
      this.heading = Math.atan2(this.vy, this.vx);
      if (this.y >= 0 && this.vy > 0) {
        this.inAir = false;
        this.speed = Math.hypot(this.vx, this.vy);
        this.onEnter?.();
      }
    }
    const cx = Math.cos(this.heading);
    if (cx > 0.2) this.facing = 1;
    else if (cx < -0.2) this.facing = -1;
  }

  private pushTrail(): void {
    const last = this.trail[this.trail.length - 1];
    if (!last || Math.hypot(this.x - last.x, this.y - last.y) >= TRAIL_STEP * this.scale) {
      this.trail.push({ x: this.x, y: this.y });
      const maxPts = Math.ceil((this.segs * rig.step + 300) / TRAIL_STEP) + 40;
      if (this.trail.length > maxPts) this.trail.splice(0, this.trail.length - maxPts);
    }
  }

  /** Радиус тела (px при масштабе 1) на расстоянии d от центра головы; L — длина тела: утолщение у головы и сужение хвоста. */
  private radiusAt(d: number, L: number): number {
    let r = rig.bodyRadius;
    if (d < rig.headBulge) r = rig.headRadius + (rig.bodyRadius - rig.headRadius) * smooth(d / rig.headBulge);
    const ts = rig.taperFrom * L;
    if (d > ts && L > ts) r += (rig.tailRadius - r) * smooth((d - ts) / (L - ts));
    for (const g of this.gulps) {
      const x = (d - g.d) / 55;
      r += rig.bodyRadius * g.a * Math.exp(-x * x);
    }
    return r;
  }

  /** Узлы тела: count точек на равных расстояниях sp вдоль следа головы (последняя в конце тела total). */
  private computeNodes(count: number, sp: number, total: number): void {
    const nodes = this.nodes;
    while (nodes.length < count) nodes.push({ x: 0, y: 0, a: 0 });
    nodes[0].x = this.x;
    nodes[0].y = this.y;
    nodes[0].a = this.heading;
    let curX = this.x;
    let curY = this.y;
    let walked = 0;
    let j = 1;
    let lastAngle = this.heading;
    for (let k = this.trail.length - 1; k >= 0 && j < count; k--) {
      const p = this.trail[k];
      const segLen = Math.hypot(curX - p.x, curY - p.y);
      if (segLen < 1e-6) continue;
      const ang = Math.atan2(curY - p.y, curX - p.x);
      lastAngle = ang;
      while (j < count && walked + segLen >= Math.min(j * sp, total)) {
        const t = (Math.min(j * sp, total) - walked) / segLen;
        const n = nodes[j];
        n.x = curX + (p.x - curX) * t;
        n.y = curY + (p.y - curY) * t;
        n.a = ang;
        j++;
      }
      walked += segLen;
      curX = p.x;
      curY = p.y;
    }
    // следа не хватило (после резкого роста): продолжаем прямо назад
    while (j < count) {
      const rest = Math.min(j * sp, total) - walked;
      const n = nodes[j];
      n.x = curX - Math.cos(lastAngle) * rest;
      n.y = curY - Math.sin(lastAngle) * rest;
      n.a = lastAngle;
      j++;
    }
  }

  private layout(dt: number, now: number): void {
    const S = this.scale;
    const k0 = 1 / atlasScale(this.atlas);
    const L = Math.max(1, this.segs * rig.step);
    const sp = rig.spacing;
    const count = Math.max(2, Math.ceil(L / sp) + 1);
    this.computeNodes(count, sp * S, L * S);
    const nodes = this.nodes;

    // тело: пять проходов одинаковых кругов, поэтому швов нет; круги за пределами экрана не рисуем (длинный червь на слабых устройствах)
    const cam = this.scene.cameras.main;
    const vw = cam.width / cam.zoom;
    const vh = cam.height / cam.zoom;
    const vx0 = cam.scrollX + cam.width / 2 - vw / 2;
    const vy0 = cam.scrollY + cam.height / 2 - vh / 2;
    const pad = (rig.bodyRadius + rig.outline) * 1.3 * S;
    const radii = this.radii;
    for (let k = 0; k < count; k++) radii[k] = this.radiusAt(Math.min(k * sp, L), L);
    const passes = rig.passes as string[];
    for (let p = 0; p < passes.length; p++) {
      const pool = this.pools[p];
      const name = passes[p];
      while (pool.length < count) {
        pool.push(this.scene.add.image(0, 0, this.atlas, `worm-${this.skin}-stamp-${name}`).setDepth(DEPTH[name]));
      }
      while (pool.length > count) pool.pop()?.destroy();
      const outline = name === 'out';
      for (let k = 0; k < count; k++) {
        const r = radii[k];
        const n = nodes[k];
        const seen = n.x > vx0 - pad && n.x < vx0 + vw + pad && n.y > vy0 - pad && n.y < vy0 + vh + pad;
        const img = pool[k];
        if (img.visible !== seen) img.setVisible(seen);
        if (!seen) continue;
        const f = (outline ? (r + rig.outline) / (rig.bodyRadius + rig.outline) : r / rig.bodyRadius) * S * k0;
        img.setPosition(n.x, n.y).setScale(f);
      }
    }

    // голова: макушка, челюсти, зев, лицо
    const h = nodes[0];
    const face = this.facing;
    const ha = this.heading;
    const c = Math.cos(ha);
    const s = Math.sin(ha);
    const off = (ox: number, oy: number) => ({ x: h.x + (ox * c - oy * s) * S, y: h.y + (ox * s + oy * c) * S });
    const flip = face < 0;
    const sc = S * k0;
    this.crown?.setPosition(h.x, h.y).setRotation(ha).setScale(sc).setFlipY(flip);

    // челюсти плавно открываются и закрываются; в покое чуть «дышат»
    const base = JAW_BY_EXPR[this.expr] + (this.expr === 'idle' ? 0.06 * Math.sin(now / 260) : 0);
    this.jawOpen += (base - this.jawOpen) * Math.min(1, (this.expr === 'chomp' ? 40 : 14) * dt);
    const j = Math.max(0, Math.min(1, this.jawOpen));
    const th = (rig.jaw.closed + (rig.jaw.open - rig.jaw.closed) * j) * DEG;
    const [hx, hy] = rig.jaw.hinge;
    const pt = off(hx, hy * face);
    const pb = off(hx, -hy * face);
    this.maw.setPosition(h.x, h.y).setRotation(ha).setScale(sc, sc * (0.12 + 0.88 * j)).setFlipY(flip);
    this.jawBottom.setPosition(pb.x, pb.y).setRotation(ha - th * face).setScale(sc).setFlipY(flip);
    this.jawTop.setPosition(pt.x, pt.y).setRotation(ha + th * face).setScale(sc).setFlipY(flip);
    this.faceImg.setPosition(h.x, h.y).setRotation(ha).setScale(sc).setFlipY(flip);

    // крылья на спине в wingDist от головы
    if (this.wingBack && this.wingFront) {
      const wd = Math.min(rig.wingDist, L * 0.85);
      const n = nodes[Math.min(count - 1, Math.round(wd / sp))];
      const nFace = Math.cos(n.a) >= 0 ? 1 : -1;
      const ox = rig.anchors.wing[0] * S;
      const oy = rig.anchors.wing[1] * S * nFace;
      const cn = Math.cos(n.a);
      const sn = Math.sin(n.a);
      const ax = n.x + ox * cn - oy * sn;
      const ay = n.y + ox * sn + oy * cn;
      const k = S / atlasScale('wings');
      this.flapPhase += dt * (this.inAir ? 16 : 6);
      const amp = this.inAir ? 0.38 : 0.14;
      // под землёй крылья прижаты к спине и меньше, в воздухе раскрываются
      this.wingOpen += ((this.inAir ? 1 : 0) - this.wingOpen) * Math.min(1, 7 * dt);
      const fold = 1 - this.wingOpen;
      const foldRot = -0.85 * fold * nFace;
      const kk = k * (1 - 0.4 * fold);
      const offF = amp * (Math.sin(this.flapPhase) * 0.5 - 0.1) * nFace + foldRot;
      const offB = amp * (Math.sin(this.flapPhase - 0.7) * 0.5 - 0.1) * nFace + foldRot;
      this.wingBack.setPosition(ax, ay).setRotation(n.a + offB).setScale(kk).setFlipY(nFace < 0).setVisible(true);
      this.wingFront.setPosition(ax, ay).setRotation(n.a + offF).setScale(kk).setFlipY(nFace < 0).setVisible(true);
    } else {
      this.wingBack?.setVisible(false);
      this.wingFront?.setVisible(false);
    }
  }

  private updateExpression(now: number): void {
    let e: Expr = this.hintExpr;
    if (this.timedExpr && now < this.timedUntil) e = this.timedExpr;
    else this.timedExpr = null;
    if (e !== this.expr) {
      this.expr = e;
      this.faceImg.setFrame(`worm-${this.skin}-face-${e}`);
    }
  }

  destroy(): void {
    this.destroySprites();
  }
}

// размер холста крыла нужен подписчикам размеров (проверка в тестах)
export const WING_CANVAS_PX = WINGS_CANVAS;
