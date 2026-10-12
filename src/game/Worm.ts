import Phaser from 'phaser';
import rig from '../../design/worm/rig.json';
import { skinInfo, type SkinId } from '../data/skins';
import { JUMP_BONUS, SPEED_BONUS, WINGS_CANVAS, type Upgrades } from '../data/upgrades';
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
const SWIM_SPEED = 330;
const TURN_RATE = 5.0;
const GRAVITY = 2000;
const JUMP_HEIGHT = 300;
const AIR_CONTROL = 900;
const MAX_DEPTH = 1800;
const MOUTH_RADIUS = 46;
const HEAD_RADIUS = 70;
const TRAIL_STEP = 3;

const DEPTH = { wingBack: 0, tail: 10, bead: 100, wingFront: 150, crown: 190, head: 200 };

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

/**
 * Червь: голова ведёт, тело (сегменты и хвост) идёт по следу головы. Длина и толщина растут с тиром.
 * Устройство частей и порядок слоёв: design/README.md, раздел 3.
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
  /** Число сегментов тела (дробное: целая часть рисуется). */
  segs = 5;
  upgrades: Upgrades = { jump: 0, hp: 0, speed: 0 };
  onExit?: () => void;
  onEnter?: () => void;

  private skin: SkinId;
  private atlas = '';
  private head!: Phaser.GameObjects.Image;
  private crown: Phaser.GameObjects.Image | null = null;
  private tail!: Phaser.GameObjects.Image;
  private beads: Phaser.GameObjects.Image[] = [];
  private beadParity: number[] = [];
  private wingBack: Phaser.GameObjects.Image | null = null;
  private wingFront: Phaser.GameObjects.Image | null = null;
  private wingLevel = 0;
  private trail: Array<{ x: number; y: number }> = [];
  private expr: Expr = 'idle';
  private hintExpr: Expr = 'idle';
  private timedExpr: Expr | null = null;
  private timedUntil = 0;
  private face = 1;
  private flapPhase = 0;
  private wingOpen = 0;
  private nodes: Node[] = [];

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
    this.tail = img('tail', DEPTH.tail);
    this.head = img(`head-${this.expr}`, DEPTH.head);
    this.crown = info.crown ? img('crown', DEPTH.crown) : null;
    this.beads = [];
    this.beadParity = [];
    this.buildWings();
  }

  private destroySprites(): void {
    this.tail.destroy();
    this.head.destroy();
    this.crown?.destroy();
    this.beads.forEach((b) => b.destroy());
    this.wingBack?.destroy();
    this.wingFront?.destroy();
    this.crown = this.wingBack = this.wingFront = null;
    this.beads = [];
    this.beadParity = [];
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

  /** Точка рта в мире: сюда «кусает» червь. */
  mouth(): { x: number; y: number } {
    const S = this.scale;
    const ox = rig.anchors.mouth[0] * S;
    const oy = rig.anchors.mouth[1] * S * this.face;
    const c = Math.cos(this.heading);
    const s = Math.sin(this.heading);
    return { x: this.x + ox * c - oy * s, y: this.y + ox * s + oy * c };
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
    this.layout(dt);
    this.updateExpression(now);
  }

  private move(dt: number, steer: Steer): void {
    const S = this.scale;
    const swim = this.swimSpeed;
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

      const maxY = MAX_DEPTH * S;
      if (this.y > maxY) {
        this.y = maxY;
        if (Math.sin(this.heading) > 0) this.heading = Math.cos(this.heading) >= 0 ? 0 : Math.PI;
      }
      if (this.y < 0 && this.vy < 0) {
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
      this.heading = Math.atan2(this.vy, this.vx);
      if (this.y >= 0 && this.vy > 0) {
        this.inAir = false;
        this.speed = Math.hypot(this.vx, this.vy);
        this.onEnter?.();
      }
    }
    const cx = Math.cos(this.heading);
    if (cx > 0.2) this.face = 1;
    else if (cx < -0.2) this.face = -1;
  }

  private pushTrail(): void {
    const last = this.trail[this.trail.length - 1];
    if (!last || Math.hypot(this.x - last.x, this.y - last.y) >= TRAIL_STEP * this.scale) {
      this.trail.push({ x: this.x, y: this.y });
      const nb = Math.floor(this.segs);
      const maxPts = Math.ceil((rig.headToBead + nb * rig.beadStep + rig.beadToTail) / TRAIL_STEP) + 40;
      if (this.trail.length > maxPts) this.trail.splice(0, this.trail.length - maxPts);
    }
  }

  /** Узлы тела вдоль следа головы: голова, сегменты, хвост. */
  private computeNodes(total: number, S: number, sc: (i: number) => number): void {
    const dist: number[] = [];
    let acc = 0;
    for (let i = 1; i < total; i++) {
      const base = i === 1 ? rig.headToBead : i === total - 1 ? rig.beadToTail : rig.beadStep;
      acc += base * ((sc(i - 1) + sc(i)) / 2) * S;
      dist.push(acc);
    }
    const nodes = this.nodes;
    nodes.length = 0;
    nodes.push({ x: this.x, y: this.y, a: this.heading });
    let cur = { x: this.x, y: this.y };
    let walked = 0;
    let j = 0;
    let lastAngle = this.heading;
    for (let k = this.trail.length - 1; k >= 0 && j < dist.length; k--) {
      const p = this.trail[k];
      const segLen = Math.hypot(cur.x - p.x, cur.y - p.y);
      if (segLen < 1e-6) continue;
      const ang = Math.atan2(cur.y - p.y, cur.x - p.x);
      lastAngle = ang;
      while (j < dist.length && walked + segLen >= dist[j]) {
        const t = (dist[j] - walked) / segLen;
        nodes.push({ x: cur.x + (p.x - cur.x) * t, y: cur.y + (p.y - cur.y) * t, a: ang });
        j++;
      }
      walked += segLen;
      cur = p;
    }
    // следа не хватило (после резкого роста): продолжаем прямо назад
    while (j < dist.length) {
      const rest = dist[j] - walked;
      nodes.push({ x: cur.x - Math.cos(lastAngle) * rest, y: cur.y - Math.sin(lastAngle) * rest, a: lastAngle });
      j++;
    }
  }

  private layout(dt: number): void {
    const S = this.scale;
    const nb = Math.max(0, Math.floor(this.segs));
    const total = nb + 2;
    const sc = (i: number) => 1 - 0.45 * Math.pow(i / Math.max(1, total - 1), 1.25);
    this.computeNodes(total, S, sc);
    const nodes = this.nodes;

    // голова и макушка
    const h = nodes[0];
    this.head.setPosition(h.x, h.y).setRotation(this.heading).setScale(S).setFlipY(this.face < 0);
    this.crown?.setPosition(h.x, h.y).setRotation(this.heading).setScale(S).setFlipY(this.face < 0);

    // сегменты: создаём или убираем лишние
    while (this.beads.length < nb) {
      const idx = this.beads.length + 1;
      const parity = idx % 2;
      this.beads.push(this.scene.add.image(0, 0, this.atlas, `worm-${this.skin}-body-${parity ? 'a' : 'b'}`));
      this.beadParity.push(parity);
    }
    while (this.beads.length > nb) {
      this.beads.pop()?.destroy();
      this.beadParity.pop();
    }
    for (let i = 1; i <= nb; i++) {
      const n = nodes[i];
      this.beads[i - 1].setPosition(n.x, n.y).setRotation(n.a).setScale(sc(i) * S).setDepth(DEPTH.bead - i);
    }
    const t = nodes[total - 1];
    this.tail.setPosition(t.x, t.y).setRotation(t.a).setScale(sc(total - 1) * S);

    // крылья на 3-м сегменте (или на последнем, если тело короче)
    if (this.wingBack && this.wingFront && nb >= 1) {
      const wi = Math.min(rig.wingBead, nb);
      const n = nodes[wi];
      const ns = sc(wi) * S;
      const nFace = Math.cos(n.a) >= 0 ? 1 : -1;
      const ox = rig.anchors.wing[0] * ns;
      const oy = rig.anchors.wing[1] * ns * nFace;
      const c = Math.cos(n.a);
      const s = Math.sin(n.a);
      const ax = n.x + ox * c - oy * s;
      const ay = n.y + ox * s + oy * c;
      const k = ns / atlasScale('wings');
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
      this.head.setFrame(`worm-${this.skin}-head-${e}`);
    }
  }

  destroy(): void {
    this.destroySprites();
  }
}

// размер холста крыла нужен подписчикам размеров (проверка в тестах)
export const WING_CANVAS_PX = WINGS_CANVAS;
