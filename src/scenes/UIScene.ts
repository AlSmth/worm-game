import Phaser from 'phaser';
import { state } from '../core/state';
import { controls } from '../core/controls';
import { sfx } from '../core/audio';
import { isCoarsePointer } from '../core/layout';
import { t, type TextKey } from '../core/i18n';
import { platform } from '../platform/platform';
import { save, TUTORIAL_EAT } from '../platform/save';

const FONT = "'Trebuchet MS', 'Segoe UI', Verdana, Arial, sans-serif";
const INK = 0x2b1b17;
const ORANGE = 0xffb020;
const BLUE = 0x4d8dff;
/** Для вернувшегося игрока подсказка показывается коротко, для нового держится до первой съеденной добычи. */
const HINT_RETURNING = 4;
const HINT_NEW = 1e9;

type Btn = { box: Phaser.GameObjects.Container; icon: Phaser.GameObjects.Graphics; bg: Phaser.GameObjects.Graphics };
type LabelBtn = { box: Phaser.GameObjects.Container; bg: Phaser.GameObjects.Graphics; text: Phaser.GameObjects.Text; key: TextKey; color: number };

/** Интерфейс поверх игры: шкала роста, монеты, кнопки паузы и звука, подсказка, сообщения, меню паузы. Кнопки не меньше 52 CSS-px. */
export class UIScene extends Phaser.Scene {
  private bar!: Phaser.GameObjects.Graphics;
  private tierText!: Phaser.GameObjects.Text;
  private coinPlate!: Phaser.GameObjects.Graphics;
  private coinIcon!: Phaser.GameObjects.Image;
  private coinText!: Phaser.GameObjects.Text;
  private shownCoins = -1;
  private pauseBtn!: Btn;
  private soundBtn!: Btn;
  private hint!: Phaser.GameObjects.Text;
  private toastText!: Phaser.GameObjects.Text;
  private toastKey: string | null = null;
  private hintLeft = HINT_RETURNING;
  private overlay!: Phaser.GameObjects.Container;
  private overlayDim!: Phaser.GameObjects.Rectangle;
  private overlayTitle!: Phaser.GameObjects.Text;
  private resumeBtn!: LabelBtn;
  private changeBtn!: LabelBtn;
  private last = { tier: -1, p: -1, w: -1 };

  constructor() {
    super('UI');
  }

  create(): void {
    this.bar = this.add.graphics().setDepth(10);
    this.tierText = this.add.text(0, 0, '1', this.textStyle(24, 5)).setOrigin(0.5).setDepth(12);
    this.coinPlate = this.add.graphics().setDepth(10);
    this.coinIcon = this.add.image(0, 0, 'treasure', 'treasure-coin').setDepth(12);
    this.coinText = this.add.text(0, 0, '0', { ...this.textStyle(22, 4.5), color: '#ffe27a' }).setOrigin(0, 0.5).setDepth(12);
    this.pauseBtn = this.makeButton(() => this.togglePause());
    this.soundBtn = this.makeButton(() => this.toggleSound());
    this.hint = this.add
      .text(0, 0, '', { ...this.textStyle(20, 4), align: 'center' })
      .setOrigin(0.5, 1)
      .setDepth(11);
    this.toastText = this.add
      .text(0, 0, '', { ...this.textStyle(22, 5), align: 'center' })
      .setOrigin(0.5, 0)
      .setDepth(13)
      .setAlpha(0);
    this.hintLeft = save.data.tutorial & TUTORIAL_EAT ? HINT_RETURNING : HINT_NEW;
    this.buildOverlay();
    this.layoutAll();
    this.scale.on('resize', () => this.layoutAll());

    controls.onKey('Escape', () => this.togglePause());
    controls.onKey('KeyP', () => this.togglePause());
    controls.onKey('KeyM', () => this.toggleSound());
    // персонаж выбран: если игра стояла на паузе (выбор открыт из меню), продолжаем
    this.game.events.on('skin-chosen', () => {
      if (state.paused) this.togglePause();
    });
  }

  // ---------- построение ----------
  private get u(): number {
    return state.layout.dpr;
  }

  private textStyle(sizeCss: number, strokeCss: number): Phaser.Types.GameObjects.Text.TextStyle {
    return {
      fontFamily: FONT,
      fontStyle: 'bold',
      fontSize: `${Math.round(sizeCss * this.u)}px`,
      color: '#ffffff',
      stroke: '#2b1b17',
      strokeThickness: Math.round(strokeCss * this.u),
    };
  }

  private makeButton(onClick: () => void): Btn {
    const bg = this.add.graphics();
    const icon = this.add.graphics();
    const box = this.add.container(0, 0, [bg, icon]).setDepth(15);
    box.on('pointerdown', () => {
      if (state.selecting) return;
      sfx.unlock();
      sfx.play('ui');
      onClick();
    });
    return { box, icon, bg };
  }

  private makeLabelButton(key: TextKey, color: number, onClick: () => void): LabelBtn {
    const bg = this.add.graphics();
    const text = this.add.text(0, 0, '', this.textStyle(26, 5)).setOrigin(0.5);
    const box = this.add.container(0, 0, [bg, text]);
    box.on('pointerdown', () => {
      if (state.selecting) return;
      sfx.unlock();
      sfx.play('ui');
      onClick();
    });
    return { box, bg, text, key, color };
  }

  private buildOverlay(): void {
    this.overlayDim = this.add.rectangle(0, 0, 10, 10, 0x000000, 0.58).setOrigin(0, 0).setInteractive();
    this.overlayTitle = this.add.text(0, 0, '', this.textStyle(46, 8)).setOrigin(0.5);
    this.resumeBtn = this.makeLabelButton('resume', ORANGE, () => this.togglePause());
    this.changeBtn = this.makeLabelButton('menu_change', BLUE, () => this.game.events.emit('open-select'));
    this.overlay = this.add
      .container(0, 0, [this.overlayDim, this.overlayTitle, this.resumeBtn.box, this.changeBtn.box])
      .setDepth(50)
      .setVisible(false);
  }

  // ---------- раскладка ----------
  private layoutAll(): void {
    const u = this.u;
    const W = this.scale.width;
    const H = this.scale.height;
    const m = 14 * u;
    const bs = 52 * u;

    // кнопки справа сверху
    const place = (b: Btn, x: number, y: number) => {
      b.box.setPosition(x + bs / 2, y + bs / 2);
      b.box.setSize(bs, bs);
      b.box.setInteractive(new Phaser.Geom.Rectangle(-bs / 2, -bs / 2, bs, bs), Phaser.Geom.Rectangle.Contains);
      this.drawButton(b.bg, bs);
    };
    const x1 = W - m - bs;
    const x2 = x1 - bs - 10 * u;
    place(this.pauseBtn, x1, m);
    place(this.soundBtn, x2, m);
    this.drawPauseIcon();
    this.drawSoundIcon();

    // плашка с монетами под шкалой роста
    const coinY = m + 2 * 24 * u + 12 * u + 16 * u;
    this.coinIcon.setScale((30 * u) / 64).setPosition(m + 16 * u, coinY);
    this.coinText.setStyle({ ...this.textStyle(22, 4.5), color: '#ffe27a' });
    this.coinText.setPosition(m + 38 * u, coinY + 1 * u);
    this.shownCoins = -1; // подпись и плашка перерисуются

    // область, занятая интерфейсом: игра не принимает там касания за управление
    state.uiRects = [
      { x: x2 - 4 * u, y: 0, w: W - x2 + 4 * u, h: m + bs + 8 * u },
      { x: 0, y: 0, w: this.barWidth() + 2 * 24 * u + 3 * m, h: m + 52 * u },
      { x: 0, y: coinY - 20 * u, w: 160 * u, h: 40 * u },
    ];

    // подсказка внизу по центру
    const touch = isCoarsePointer();
    this.hint.setStyle(this.textStyle(touch ? 20 : 19, 4));
    this.hint.setText(`${touch ? t('hint_move_touch') : t('hint_move_mouse')}\n${t('hint_eat')}`);
    this.hint.setWordWrapWidth(Math.max(240 * u, W * 0.86));
    this.hint.setPosition(W / 2, H - 18 * u);
    this.toastText.setStyle({ ...this.textStyle(22, 5), align: 'center' });
    this.toastText.setWordWrapWidth(Math.max(260 * u, W * 0.8));
    this.toastText.setPosition(W / 2, 84 * u);
    this.toastKey = null; // подпись перерисуется на новом языке и размере

    // меню паузы: заголовок и две кнопки друг под другом
    this.overlayDim.setSize(W, H);
    this.overlayTitle.setStyle(this.textStyle(46, 8));
    this.overlayTitle.setText(t('pause')).setPosition(W / 2, H / 2 - 92 * u);
    const bh = 62 * u;
    let y = H / 2 + 6 * u;
    for (const b of [this.resumeBtn, this.changeBtn]) {
      b.text.setStyle(this.textStyle(26, 5));
      b.text.setText(t(b.key));
      const bw = Math.max(240 * u, b.text.width + 60 * u);
      b.bg.clear();
      this.fillButton(b.bg, -bw / 2, -bh / 2, bw, bh, 16 * u, b.color);
      b.box.setPosition(W / 2, y);
      b.box.setSize(bw, bh);
      b.box.setInteractive(new Phaser.Geom.Rectangle(-bw / 2, -bh / 2, bw, bh), Phaser.Geom.Rectangle.Contains);
      y += bh + 14 * u;
    }

    this.last = { tier: -1, p: -1, w: -1 };
  }

  private barWidth(): number {
    return Math.min(300 * this.u, this.scale.width * 0.36);
  }

  private fillButton(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, r: number, color = ORANGE): void {
    const u = this.u;
    g.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r + 3 * u);
    g.fillStyle(color, 1).fillRoundedRect(x, y, w, h, r);
    g.fillStyle(0xffffff, 0.35).fillRoundedRect(x + 4 * u, y + 4 * u, w - 8 * u, h * 0.38, r * 0.7);
  }

  private drawButton(g: Phaser.GameObjects.Graphics, s: number): void {
    g.clear();
    this.fillButton(g, -s / 2, -s / 2, s, s, 14 * this.u);
  }

  private icon(g: Phaser.GameObjects.Graphics, draw: (fill: () => void) => void): void {
    g.clear();
    draw(() => {});
  }

  private drawPauseIcon(): void {
    const g = this.pauseBtn.icon;
    const s = 52 * this.u;
    this.icon(g, () => {
      g.fillStyle(0xffffff, 1).lineStyle(3 * this.u, INK, 1);
      if (state.paused) {
        // «играть»
        g.beginPath().moveTo(-0.14 * s, -0.24 * s).lineTo(0.26 * s, 0).lineTo(-0.14 * s, 0.24 * s).closePath().fillPath().strokePath();
      } else {
        for (const dx of [-0.15, 0.06]) {
          g.fillRoundedRect(dx * s, -0.22 * s, 0.11 * s, 0.44 * s, 0.03 * s);
          g.strokeRoundedRect(dx * s, -0.22 * s, 0.11 * s, 0.44 * s, 0.03 * s);
        }
      }
    });
  }

  private drawSoundIcon(): void {
    const g = this.soundBtn.icon;
    const s = 52 * this.u;
    this.icon(g, () => {
      g.fillStyle(0xffffff, 1).lineStyle(3 * this.u, INK, 1);
      g.beginPath()
        .moveTo(-0.26 * s, -0.1 * s)
        .lineTo(-0.1 * s, -0.1 * s)
        .lineTo(0.06 * s, -0.24 * s)
        .lineTo(0.06 * s, 0.24 * s)
        .lineTo(-0.1 * s, 0.1 * s)
        .lineTo(-0.26 * s, 0.1 * s)
        .closePath()
        .fillPath()
        .strokePath();
      if (sfx.isMuted) {
        g.lineStyle(4 * this.u, 0xd8261c, 1);
        g.beginPath().moveTo(0.14 * s, -0.14 * s).lineTo(0.3 * s, 0.14 * s).strokePath();
        g.beginPath().moveTo(0.3 * s, -0.14 * s).lineTo(0.14 * s, 0.14 * s).strokePath();
      } else {
        g.lineStyle(3 * this.u, INK, 1);
        g.beginPath().arc(0.06 * s, 0, 0.2 * s, -0.7, 0.7).strokePath();
        g.beginPath().arc(0.06 * s, 0, 0.32 * s, -0.7, 0.7).strokePath();
      }
    });
  }

  // ---------- действия ----------
  private togglePause(): void {
    if (state.selecting) return;
    state.paused = !state.paused;
    platform.gameplay(!state.paused);
    this.overlay.setVisible(state.paused);
    this.drawPauseIcon();
  }

  private toggleSound(): void {
    const muted = !sfx.isMuted;
    sfx.setMuted(muted);
    save.patch({ sound: !muted });
    this.drawSoundIcon();
  }

  // ---------- шаг ----------
  override update(_time: number, delta: number): void {
    // шкала роста перерисовывается только при изменении
    const u = this.u;
    const p = Math.max(0, Math.min(1, state.growth / state.need));
    const bw = this.barWidth();
    if (this.last.tier !== state.tier || Math.abs(this.last.p - p) > 0.002 || this.last.w !== bw) {
      this.last = { tier: state.tier, p, w: bw };
      this.drawBar(p, bw, u);
    }
    // монеты: число и плашка по ширине числа, при выигрыше «подпрыгивают»
    if (this.shownCoins !== state.coins) {
      const gained = this.shownCoins >= 0 && state.coins > this.shownCoins;
      this.shownCoins = state.coins;
      this.coinText.setText(String(state.coins));
      this.drawCoinPlate();
      if (gained) {
        this.tweens.killTweensOf([this.coinIcon, this.coinText]);
        const base = (30 * u) / 64;
        this.coinIcon.setScale(base * 1.45);
        this.tweens.add({ targets: this.coinIcon, scale: base, duration: 260, ease: 'Back.easeOut' });
        this.coinText.setScale(1.3);
        this.tweens.add({ targets: this.coinText, scale: 1, duration: 260, ease: 'Back.easeOut' });
      }
    }
    // подсказка: новому игроку висит до первой съеденной добычи, потом гаснет; не мешает окну выбора
    if (save.data.tutorial & TUTORIAL_EAT) this.hintLeft = Math.min(this.hintLeft, 2.5);
    if (this.hintLeft > 0 && !state.paused && !state.selecting) {
      this.hintLeft -= delta / 1000;
      this.hint.setAlpha(Math.max(0, Math.min(1, this.hintLeft / 1.5)));
    }
    this.hint.setVisible(!state.selecting);
    // короткое сообщение (выход на поверхность закрыт или открылся, обучение)
    const toast = state.toast;
    if (toast.key && toast.left > 0) {
      if (!state.paused && !state.selecting) toast.left -= delta / 1000;
      if (this.toastKey !== toast.key) {
        this.toastKey = toast.key;
        this.toastText.setText(t(toast.key));
      }
      this.toastText.setAlpha(Math.max(0, Math.min(1, toast.left / 0.6, (toast.total - toast.left) / 0.2)));
    } else if (this.toastText.alpha !== 0) {
      this.toastText.setAlpha(0);
      this.toastKey = null;
    }
  }

  private drawCoinPlate(): void {
    const u = this.u;
    const m = 14 * u;
    const y = m + 2 * 24 * u + 12 * u + 16 * u;
    const w = 52 * u + this.coinText.width;
    const g = this.coinPlate;
    g.clear();
    g.fillStyle(INK, 1).fillRoundedRect(m - 3 * u, y - 18 * u - 3 * u, w + 6 * u, 36 * u + 6 * u, 21 * u);
    g.fillStyle(0x4a2f1f, 1).fillRoundedRect(m, y - 18 * u, w, 36 * u, 18 * u);
    g.fillStyle(0xffffff, 0.14).fillRoundedRect(m + 4 * u, y - 15 * u, w - 8 * u, 11 * u, 6 * u);
  }

  private drawBar(p: number, bw: number, u: number): void {
    const m = 14 * u;
    const r = 24 * u;
    const cx = m + r;
    const cy = m + r;
    const bx = cx + r + 6 * u;
    const bh = 22 * u;
    const by = cy - bh / 2;
    const g = this.bar;
    g.clear();
    g.fillStyle(INK, 1).fillRoundedRect(bx - 3 * u, by - 3 * u, bw + 6 * u, bh + 6 * u, bh / 2 + 3 * u);
    g.fillStyle(0x4a2f1f, 1).fillRoundedRect(bx, by, bw, bh, bh / 2);
    if (p > 0.01) {
      const fw = Math.max(bh, bw * p);
      g.fillStyle(0xffb020, 1).fillRoundedRect(bx, by, fw, bh, bh / 2);
      g.fillStyle(0xffffff, 0.35).fillRoundedRect(bx + 3 * u, by + 3 * u, fw - 6 * u, bh * 0.35, bh * 0.2);
    }
    g.fillStyle(INK, 1).fillCircle(cx, cy, r + 3 * u);
    g.fillStyle(0x6bbf3a, 1).fillCircle(cx, cy, r);
    g.fillStyle(0xffffff, 0.3).fillCircle(cx - r * 0.3, cy - r * 0.35, r * 0.4);
    this.tierText.setStyle(this.textStyle(state.tier >= 10 ? 21 : 25, 5));
    this.tierText.setText(String(state.tier)).setPosition(cx, cy + 1 * u);
  }
}
