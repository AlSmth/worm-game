import Phaser from 'phaser';

interface Particle {
  img: Phaser.GameObjects.Image;
  vx: number;
  vy: number;
  life: number;
  max: number;
  gravity: number;
  s0: number;
  spin: number;
}

export interface BurstOptions {
  count: number;
  /** Кадр из атласа `fx` (design/effects). */
  frame: string;
  colors: number[];
  speed: number;
  life: number;
  gravity: number;
  /** Ширина частицы в px мира при масштабе червя 1. */
  size: number;
}

const FONT = "'Trebuchet MS', 'Segoe UI', Verdana, Arial, sans-serif";

/** Частицы и вспышки из design/effects: звёздочки, комочки земли, блеск, кольцо роста, всплеск «ам», всплывающие числа. Масштабируются вместе с червём. */
export class Fx {
  private free: Particle[] = [];
  private live: Particle[] = [];
  private widths = new Map<string, number>();

  constructor(private scene: Phaser.Scene) {}

  private frameWidth(frame: string): number {
    let w = this.widths.get(frame);
    if (w === undefined) {
      w = this.scene.textures.getFrame('fx', frame)?.realWidth ?? 32;
      this.widths.set(frame, w);
    }
    return w;
  }

  burst(x: number, y: number, S: number, o: BurstOptions): void {
    const fw = this.frameWidth(o.frame);
    for (let i = 0; i < o.count; i++) {
      const p = this.free.pop() ?? this.make();
      const a = Math.random() * Math.PI * 2;
      const sp = o.speed * S * (0.4 + Math.random() * 0.8);
      p.vx = Math.cos(a) * sp;
      p.vy = Math.sin(a) * sp - o.speed * S * 0.25;
      p.life = p.max = o.life * (0.7 + Math.random() * 0.6);
      p.gravity = o.gravity * S;
      p.s0 = (o.size * S * (0.7 + Math.random() * 0.6)) / fw;
      p.spin = (Math.random() - 0.5) * 8;
      p.img
        .setTexture('fx', o.frame)
        .setPosition(x, y)
        .setTint(o.colors[Math.floor(Math.random() * o.colors.length)])
        .setScale(p.s0)
        .setAlpha(1)
        .setRotation(Math.random() * 6)
        .setVisible(true);
      this.live.push(p);
    }
  }

  /** Расходящееся кольцо: «тир вырос». */
  ring(x: number, y: number, S: number, color = 0xffd23f): void {
    const img = this.scene.add.image(x, y, 'fx', 'fx-tierup-ring').setDepth(500).setTint(color).setScale(0.3 * S).setAlpha(0.95);
    this.scene.tweens.add({
      targets: img,
      scale: 2.6 * S,
      alpha: 0,
      duration: 650,
      ease: 'Cubic.easeOut',
      onComplete: () => img.destroy(),
    });
  }

  /** Всплеск «ам» на месте укуса: короткая комикс-вспышка без текста. */
  pop(x: number, y: number, S: number, size = 150, color = 0xffffff): void {
    const k = (size * S) / this.frameWidth('fx-eat-pop');
    const img = this.scene.add
      .image(x, y, 'fx', 'fx-eat-pop')
      .setDepth(510)
      .setTint(color)
      .setScale(k * 0.35)
      .setRotation((Math.random() - 0.5) * 0.9);
    this.scene.tweens.add({
      targets: img,
      scale: k,
      alpha: 0,
      duration: 260,
      ease: 'Cubic.easeOut',
      onComplete: () => img.destroy(),
    });
  }

  /**
   * Взрыв ракеты: четыре кадра подряд (вспышка, огненный шар, шар с дымом, рассеивание), растёт и гаснет. size — диаметр шара в px мира.
   * Без текста и крови (п. 3.4.3). Не масштабируется червём: размер задаёт ракета.
   */
  boom(x: number, y: number, size: number): void {
    const k = size / this.frameWidth('fx-boom-1');
    const img = this.scene.add
      .image(x, y, 'fx', 'fx-boom-1')
      .setDepth(512)
      .setScale(k * 0.4)
      .setRotation((Math.random() - 0.5) * 0.8);
    const st = { p: 0 };
    this.scene.tweens.add({
      targets: st,
      p: 1,
      duration: 520,
      ease: 'Cubic.easeOut',
      onUpdate: () => {
        const f = Math.min(3, Math.floor(st.p * 4));
        img.setFrame(`fx-boom-${f + 1}`).setScale(k * (0.4 + 0.75 * st.p)).setAlpha(f === 3 ? 1 - (st.p * 4 - 3) * 0.9 : 1);
      },
      onComplete: () => img.destroy(),
    });
  }

  /** Линия скорости: тонкий штрих вдоль движения, остаётся на месте и гаснет (след за быстрым червём). */
  streak(x: number, y: number, angle: number, S: number, color = 0xffffff): void {
    const k = (150 * S) / this.frameWidth('fx-streak');
    const img = this.scene.add.image(x, y, 'fx', 'fx-streak').setDepth(499).setTint(color).setRotation(angle).setScale(k * 0.6, k).setAlpha(0.9);
    this.scene.tweens.add({
      targets: img,
      alpha: 0,
      scaleX: k * 1.15,
      scaleY: k * 0.5,
      duration: 380,
      ease: 'Quad.easeOut',
      onComplete: () => img.destroy(),
    });
  }

  /** Всплывающее число («+5» у монет): поднимается и гаснет. Размер растёт вместе с червём, чтобы читаться на любом отдалении. */
  floatText(x: number, y: number, S: number, text: string, color = '#ffd23f'): void {
    const t = this.scene.add
      .text(x, y, text, {
        fontFamily: FONT,
        fontStyle: 'bold',
        fontSize: '34px',
        color,
        stroke: '#2b1b17',
        strokeThickness: 7,
      })
      .setOrigin(0.5)
      .setDepth(520)
      .setScale(S * 1.1)
      .setResolution(2);
    this.scene.tweens.add({
      targets: t,
      y: y - 110 * S,
      alpha: 0,
      scale: S * 1.5,
      duration: 950,
      ease: 'Cubic.easeOut',
      onComplete: () => t.destroy(),
    });
  }

  update(dt: number): void {
    for (let i = this.live.length - 1; i >= 0; i--) {
      const p = this.live[i];
      p.life -= dt;
      if (p.life <= 0) {
        p.img.setVisible(false);
        this.live.splice(i, 1);
        this.free.push(p);
        continue;
      }
      p.vy += p.gravity * dt;
      const k = p.life / p.max;
      p.img.x += p.vx * dt;
      p.img.y += p.vy * dt;
      p.img.rotation += p.spin * dt;
      p.img.setScale(p.s0 * (0.3 + 0.7 * k)).setAlpha(Math.min(1, k * 2));
    }
  }

  private make(): Particle {
    const img = this.scene.add.image(0, 0, 'fx', 'fx-star').setDepth(500).setVisible(false);
    return { img, vx: 0, vy: 0, life: 0, max: 1, gravity: 0, s0: 1, spin: 0 };
  }
}
