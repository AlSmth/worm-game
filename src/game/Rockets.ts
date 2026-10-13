import Phaser from 'phaser';

const DEPTH_ROCKET = -40;
/** Длина ракеты на рисунке (px), по ней считается масштаб. */
const ROCKET_DRAW_LEN = 98;
const ROCKET_LIFE = 7;
/** Цель скрылась под землёй дольше этого: ракета подрывается в воздухе. */
const ROCKET_LOST = 0.9;
/** Ракета не меньше этой доли высоты вида: при большом отъезде камеры она остаётся хорошо видной. */
const ROCKET_MIN_VIEW = 0.06;

/** Ракета охраны, истребителя или вертолёта: летит к червю с самонаведением, оставляет дым, взрывается у цели или на земле. */
export interface Rocket {
  img: Phaser.GameObjects.Image;
  flame: Phaser.GameObjects.Image;
  x: number;
  y: number;
  ang: number;
  v: number;
  vmax: number;
  turn: number;
  damage: number;
  len: number;
  age: number;
  trail: number;
  /** Сколько секунд цели нет над землёй: потерявшая цель ракета подрывается в воздухе. */
  lost: number;
  flameT: number;
  flameFrame: number;
}

export interface BodyCircle {
  x: number;
  y: number;
  r: number;
}

/** Что ракетам нужно знать о черве: где он, куда летит, виден ли над землёй и его круги для попаданий. */
export interface WormInfo {
  x: number;
  y: number;
  vx: number;
  vy: number;
  scale: number;
  /** Червь над землёй (в небе и космосе всегда): охрана видит и стреляет только в такого. */
  exposed: boolean;
  /** Червь над землёй или у самой поверхности пугает людей. */
  scary: boolean;
  /** Круги тела для попаданий ракет (пусто, когда червь глубоко под землёй). */
  circles: BodyCircle[];
}

export interface RocketEvents {
  /** Ракета ушла из дульного среза (x, y) под углом ang; len — длина ракеты. */
  onShoot: (x: number, y: number, len: number, ang: number) => void;
  /** След дыма за ракетой. */
  onTrail: (x: number, y: number, len: number) => void;
  /** Взрыв ракеты: прямое попадание в червя (direct) или о землю; damage — урон при близости червя. */
  onExplode: (x: number, y: number, len: number, damage: number, direct: boolean) => void;
}

/** Ракеты: общая система для охраны на земле (Surface) и истребителей и вертолётов в небе (Air). */
export class RocketSystem {
  shots: Rocket[] = [];
  /** Высота вида, px мира: от неё зависит наименьшая длина ракеты (её ставит сцена). */
  viewH = 0;

  constructor(private scene: Phaser.Scene, private ev: RocketEvents) {}

  /** Пуск: из точки (x, y) под углом ang; len — длина ракеты по данным (будет не меньше 6 % высоты вида), vmax — наибольшая скорость, px/с. */
  launch(x: number, y: number, ang: number, len: number, vmax: number, turn: number, damage: number): void {
    const L = Math.max(len, this.viewH * ROCKET_MIN_VIEW);
    const sc = L / ROCKET_DRAW_LEN;
    const img = this.scene.add.image(x, y, 'z2', 'z2-rocket').setScale(sc).setRotation(ang).setDepth(DEPTH_ROCKET);
    const flame = this.scene.add.image(x, y, 'z2', 'z2-flame-1').setOrigin(1, 0.5).setScale(sc * 1.05).setRotation(ang).setDepth(DEPTH_ROCKET - 0.1);
    this.shots.push({ img, flame, x, y, ang, v: vmax * 0.35, vmax, turn, damage, len: L, age: 0, trail: 0, lost: 0, flameT: 0, flameFrame: 0 });
    this.ev.onShoot(x, y, L, ang);
  }

  update(dt: number, worm: WormInfo): void {
    for (let i = this.shots.length - 1; i >= 0; i--) {
      const r = this.shots[i];
      r.age += dt;
      // разгон и самонаведение (первые 0,3 с летит прямо, потом доворачивает на червя, если он над землёй)
      r.v = r.vmax * (0.35 + 0.65 * Math.min(1, r.age / 0.7));
      r.lost = worm.exposed ? 0 : r.lost + dt;
      if (r.age > 0.3 && worm.exposed) {
        const tx = worm.x + worm.vx * 0.2;
        const ty = worm.y + worm.vy * 0.2;
        let d = Math.atan2(ty - r.y, tx - r.x) - r.ang;
        while (d > Math.PI) d -= Math.PI * 2;
        while (d < -Math.PI) d += Math.PI * 2;
        r.ang += Math.max(-r.turn * dt, Math.min(r.turn * dt, d));
      }
      r.x += Math.cos(r.ang) * r.v * dt;
      r.y += Math.sin(r.ang) * r.v * dt;
      r.img.setPosition(r.x, r.y).setRotation(r.ang);
      // пламя мерцает тремя кадрами, прижато к хвосту
      r.flameT += dt;
      if (r.flameT > 0.06) {
        r.flameT = 0;
        r.flameFrame = (r.flameFrame + 1) % 3;
        r.flame.setFrame(`z2-flame-${r.flameFrame + 1}`);
      }
      const sc = r.len / ROCKET_DRAW_LEN;
      const tail = (64 - 24) * sc;
      const tx0 = r.x - Math.cos(r.ang) * tail;
      const ty0 = r.y - Math.sin(r.ang) * tail;
      r.flame.setPosition(tx0, ty0).setRotation(r.ang);
      // дымный след
      r.trail -= dt;
      if (r.trail <= 0) {
        r.trail = 0.04;
        this.ev.onTrail(tx0 - Math.cos(r.ang) * r.len * 0.35, ty0 - Math.sin(r.ang) * r.len * 0.35, r.len);
      }
      // попадание в червя
      let hit = false;
      for (const c of worm.circles) {
        const dx = r.x - c.x;
        const dy = r.y - c.y;
        const rr = c.r + r.len * 0.18;
        if (dx * dx + dy * dy < rr * rr) {
          hit = true;
          break;
        }
      }
      if (hit) this.detonate(i, true);
      else if (r.y >= 0) this.detonate(i, false);
      else if (r.age > ROCKET_LIFE || r.lost > ROCKET_LOST) this.detonate(i, false);
    }
  }

  private detonate(i: number, direct: boolean): void {
    const r = this.shots[i];
    this.shots.splice(i, 1);
    const y = Math.min(r.y, 0);
    r.img.destroy();
    r.flame.destroy();
    this.ev.onExplode(r.x, y, r.len, r.damage, direct);
  }

  clear(): void {
    this.shots.forEach((r) => {
      r.img.destroy();
      r.flame.destroy();
    });
    this.shots = [];
  }
}
