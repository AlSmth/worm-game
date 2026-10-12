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
  tex: 'fx-star' | 'fx-dot';
  colors: number[];
  speed: number;
  life: number;
  gravity: number;
  size: number;
}

/** Простые эффекты без крови: звёздочки, комочки земли, кольцо при росте. Масштабируются вместе с червём. */
export class Fx {
  private free: Particle[] = [];
  private live: Particle[] = [];

  constructor(private scene: Phaser.Scene) {}

  burst(x: number, y: number, S: number, o: BurstOptions): void {
    for (let i = 0; i < o.count; i++) {
      const p = this.free.pop() ?? this.make();
      const a = Math.random() * Math.PI * 2;
      const sp = o.speed * S * (0.4 + Math.random() * 0.8);
      p.vx = Math.cos(a) * sp;
      p.vy = Math.sin(a) * sp - o.speed * S * 0.25;
      p.life = p.max = o.life * (0.7 + Math.random() * 0.6);
      p.gravity = o.gravity * S;
      p.s0 = (o.size * S * (0.7 + Math.random() * 0.6)) / 24;
      p.spin = (Math.random() - 0.5) * 8;
      p.img
        .setTexture(o.tex)
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
    const img = this.scene.add.image(x, y, 'fx-ring').setDepth(500).setTint(color).setScale(0.3 * S).setAlpha(0.95);
    this.scene.tweens.add({
      targets: img,
      scale: 2.6 * S,
      alpha: 0,
      duration: 650,
      ease: 'Cubic.easeOut',
      onComplete: () => img.destroy(),
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
    const img = this.scene.add.image(0, 0, 'fx-star').setDepth(500).setVisible(false);
    return { img, vx: 0, vy: 0, life: 0, max: 1, gravity: 0, s0: 1, spin: 0 };
  }
}
