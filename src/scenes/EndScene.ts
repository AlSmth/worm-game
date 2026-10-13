import Phaser from 'phaser';
import { state } from '../core/state';
import { sfx } from '../core/audio';
import { t } from '../core/i18n';

const FONT = "'Trebuchet MS', 'Segoe UI', Verdana, Arial, sans-serif";
const INK = 0x2b1b17;
const ORANGE = 0xffb020;
const GREEN = 0x6bbf3a;
const STAR_COLORS = [0xffd23f, 0xffffff, 0xff9a2e];

interface Btn {
  bg: Phaser.GameObjects.Graphics;
  text: Phaser.GameObjects.Text;
  zone: Phaser.GameObjects.Zone;
  /** Прямоугольник кнопки в px холста: x, y, ширина, высота. */
  rect: number[];
}

/**
 * Концовка: Земля съедена. Затемнение поверх игры, заголовок, короткий рассказ, титры и две кнопки: «Играть дальше» (червь остаётся в космосе)
 * и «Заново, с улучшениями» (рост и испытания с нуля, улучшения и монеты остаются). Кнопки не меньше 44 CSS-px (п. 1.8), Enter и пробел — «Играть дальше».
 */
export class EndScene extends Phaser.Scene {
  private dim!: Phaser.GameObjects.Rectangle;
  private title!: Phaser.GameObjects.Text;
  private story!: Phaser.GameObjects.Text;
  private credits!: Phaser.GameObjects.Text;
  private confetti: Array<{ img: Phaser.GameObjects.Image; vx: number; vy: number; spin: number }> = [];
  private btns: Btn[] = [];
  private onKey = (e: KeyboardEvent): void => this.handleKey(e);
  private onResize = (): void => this.layout();

  constructor() {
    super('End');
  }

  create(): void {
    state.ending = true;
    this.btns = [];
    this.confetti = [];
    this.dim = this.add.rectangle(0, 0, 10, 10, 0x0b0d1a, 0.88).setOrigin(0, 0).setDepth(-100).setInteractive();
    this.title = this.add.text(0, 0, '', this.style(44, 8)).setOrigin(0.5, 0).setDepth(300);
    this.story = this.add.text(0, 0, '', this.style(22, 4)).setOrigin(0.5, 0).setDepth(300).setAlign('center');
    this.credits = this.add.text(0, 0, '', this.style(18, 3, '#ffe9b8')).setOrigin(0.5, 0).setDepth(300).setAlign('center');
    this.btns.push(this.makeBtn('end_continue', () => this.choose('end-continue')));
    this.btns.push(this.makeBtn('end_restart', () => this.choose('end-restart')));
    for (let i = 0; i < 26; i++) {
      const img = this.add.image(0, 0, 'fx', 'fx-star').setDepth(200).setTint(STAR_COLORS[i % STAR_COLORS.length]).setAlpha(0.85);
      this.confetti.push({ img, vx: 0, vy: 0, spin: (Math.random() - 0.5) * 4 });
    }
    this.layout();
    this.scatter();
    this.scale.on('resize', this.onResize);
    window.addEventListener('keydown', this.onKey);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.cleanup());
    sfx.play('quest');
  }

  private get u(): number {
    return state.layout.dpr;
  }

  private style(sizeCss: number, strokeCss: number, color = '#ffffff'): Phaser.Types.GameObjects.Text.TextStyle {
    return {
      fontFamily: FONT,
      fontStyle: 'bold',
      fontSize: `${Math.round(sizeCss * this.u)}px`,
      color,
      stroke: '#2b1b17',
      strokeThickness: Math.round(strokeCss * this.u),
    };
  }

  private makeBtn(key: 'end_continue' | 'end_restart', onClick: () => void): Btn {
    const bg = this.add.graphics().setDepth(250);
    const text = this.add.text(0, 0, t(key), this.style(22, 4)).setOrigin(0.5).setDepth(300);
    const zone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setInteractive({ useHandCursor: true });
    zone.on('pointerdown', onClick);
    return { bg, text, zone, rect: [0, 0, 10, 10] };
  }

  private choose(ev: 'end-continue' | 'end-restart'): void {
    sfx.play('select');
    this.scene.stop();
    state.ending = false;
    this.game.events.emit(ev);
  }

  private handleKey(e: KeyboardEvent): void {
    if (e.code === 'Enter' || e.code === 'Space' || e.code === 'Escape') {
      e.preventDefault();
      this.choose('end-continue');
    }
  }

  /** Подгоняет текст под ширину и высоту: размер шрифта уменьшается, пока всё не поместится. */
  private fit(txt: Phaser.GameObjects.Text, s: string, maxW: number, maxH: number, size: number, min: number, stroke: number, color: string): void {
    for (let sz = size; sz >= min; sz -= 1) {
      txt.setStyle({ ...this.style(sz, stroke, color), wordWrap: { width: maxW, useAdvancedWrap: true } });
      txt.setText(s);
      if (txt.height <= maxH) return;
    }
  }

  private layout(): void {
    const u = this.u;
    const W = this.scale.width;
    const H = this.scale.height;
    this.dim.setSize(W, H);
    const m = 16 * u;
    const maxW = Math.min(W - 2 * m, 640 * u);
    this.title.setStyle({ ...this.style(Math.min(44, Math.max(24, (W / u) * 0.05)), 8), wordWrap: { width: W - 2 * m } });
    this.title.setText(t('end_title')).setPosition(W / 2, m);
    // кнопки внизу: рядом на широком окне, друг под другом на узком
    const bh = Math.max(46 * u, Math.min(60 * u, H * 0.1));
    const wide = W / u >= 620;
    const gap = 12 * u;
    const bw = wide ? Math.min((W - 2 * m - gap) / 2, 300 * u) : Math.min(W - 2 * m, 360 * u);
    const bottom = H - m;
    const btnsH = wide ? bh : bh * 2 + gap;
    const by0 = bottom - btnsH;
    this.btns.forEach((b, i) => {
      const x = wide ? W / 2 - (2 * bw + gap) / 2 + i * (bw + gap) : (W - bw) / 2;
      const y = wide ? by0 : by0 + i * (bh + gap);
      b.rect = [x, y, bw, bh];
      b.zone.setPosition(x, y).setSize(bw, bh);
      b.zone.input?.hitArea.setTo(0, 0, bw, bh);
      b.text.setStyle(this.style(Math.min(22, Math.max(15, bh / u / 2.6)), 4));
      b.text.setText(t(i === 0 ? 'end_continue' : 'end_restart')).setPosition(x + bw / 2, y + bh / 2);
      if (b.text.width > bw - 16 * u) b.text.setScale((bw - 16 * u) / b.text.width);
      else b.text.setScale(1);
      this.drawBtn(b, i === 0);
    });
    const top = m + this.title.height + 14 * u;
    const free = by0 - 14 * u - top;
    this.fit(this.story, t('end_story'), maxW, free * 0.62, 22, 12, 4, '#ffffff');
    this.story.setPosition(W / 2, top);
    const top2 = top + this.story.height + 12 * u;
    this.fit(this.credits, t('end_credits'), maxW, Math.max(10 * u, by0 - 14 * u - top2), 18, 11, 3, '#ffe9b8');
    this.credits.setPosition(W / 2, top2);
  }

  private drawBtn(b: Btn, main: boolean): void {
    const u = this.u;
    const [x, y, w, h] = b.rect;
    const r = 14 * u;
    b.bg.clear();
    b.bg.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r + 3 * u);
    b.bg.fillStyle(main ? GREEN : ORANGE, 1).fillRoundedRect(x, y, w, h, r);
    b.bg.fillStyle(0xffffff, 0.3).fillRoundedRect(x + 5 * u, y + 5 * u, w - 10 * u, h * 0.3, r * 0.6);
  }

  /** Звёздочки по всему экрану: праздничный фон, медленно падают. */
  private scatter(): void {
    const W = this.scale.width;
    const H = this.scale.height;
    for (const c of this.confetti) {
      c.img.setPosition(Math.random() * W, Math.random() * H).setScale((18 * this.u + Math.random() * 18 * this.u) / 40);
      c.vx = (Math.random() - 0.5) * 20 * this.u;
      c.vy = (30 + Math.random() * 50) * this.u;
    }
  }

  override update(_time: number, delta: number): void {
    const dt = Math.min(delta / 1000, 0.05);
    const W = this.scale.width;
    const H = this.scale.height;
    for (const c of this.confetti) {
      c.img.x += c.vx * dt;
      c.img.y += c.vy * dt;
      c.img.rotation += c.spin * dt;
      if (c.img.y > H + 40) {
        c.img.y = -30;
        c.img.x = Math.random() * W;
      }
    }
  }

  private cleanup(): void {
    this.scale.off('resize', this.onResize);
    window.removeEventListener('keydown', this.onKey);
  }
}
