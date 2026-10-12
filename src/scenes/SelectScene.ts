import Phaser from 'phaser';
import { state } from '../core/state';
import { sfx } from '../core/audio';
import { t, type TextKey } from '../core/i18n';
import { save } from '../platform/save';
import { SKINS, type SkinId } from '../data/skins';
import { Worm } from '../game/Worm';

const FONT = "'Trebuchet MS', 'Segoe UI', Verdana, Arial, sans-serif";
const INK = 0x2b1b17;
const ORANGE = 0xffb020;
const GREEN = 0x6bbf3a;

interface Card {
  id: SkinId;
  bg: Phaser.GameObjects.Graphics;
  worm: Worm;
  name: Phaser.GameObjects.Text;
  note: Phaser.GameObjects.Text;
  btn: Phaser.GameObjects.Graphics;
  btnText: Phaser.GameObjects.Text;
  zone: Phaser.GameObjects.Zone;
  /** Прямоугольники карточки и её кнопки в px холста: x, y, ширина, высота. */
  rect: number[];
  btnRect: number[];
}

/**
 * Экран выбора персонажа: три карточки (Персик, Салат, Слива). Показывается при первом запуске и из меню паузы.
 * Выбор сохраняется с прогрессом. Кнопки не меньше 44 CSS-px (п. 1.8). Выбор мышью, пальцем и клавишами.
 */
export class SelectScene extends Phaser.Scene {
  private first = false;
  private sel = 0;
  private cards: Card[] = [];
  private dim!: Phaser.GameObjects.Rectangle;
  private title!: Phaser.GameObjects.Text;
  private backBtn!: Phaser.GameObjects.Container;
  private backBg!: Phaser.GameObjects.Graphics;
  private onKey = (e: KeyboardEvent): void => this.handleKey(e);
  private onResize = (): void => this.layout();

  constructor() {
    super('Select');
  }

  init(data: { first?: boolean }): void {
    this.first = !!data.first;
  }

  create(): void {
    state.selecting = true;
    this.cards = [];
    this.sel = Math.max(0, SKINS.findIndex((s) => s.id === save.data.skin));
    this.dim = this.add.rectangle(0, 0, 10, 10, 0x0b0d1a, 0.93).setOrigin(0, 0).setDepth(-100).setInteractive();
    this.title = this.add.text(0, 0, '', this.style(40, 8)).setOrigin(0.5, 0).setDepth(300);
    for (const s of SKINS) this.cards.push(this.makeCard(s.id));
    this.makeBack();
    this.layout();

    this.scale.on('resize', this.onResize);
    window.addEventListener('keydown', this.onKey);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.cleanup());
  }

  // ---------- построение ----------
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

  private makeCard(id: SkinId): Card {
    const i = this.cards.length;
    const bg = this.add.graphics().setDepth(-50);
    const worm = new Worm(this, id, 0, 0);
    worm.setHint('idle');
    const name = this.add.text(0, 0, '', this.style(26, 5)).setOrigin(0.5, 0).setDepth(300);
    const note = this.add.text(0, 0, '', this.style(16, 3, '#ffe9b8')).setOrigin(0.5, 0).setDepth(300);
    const btn = this.add.graphics().setDepth(250);
    const btnText = this.add.text(0, 0, '', this.style(22, 4)).setOrigin(0.5).setDepth(300);
    const zone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setInteractive({ useHandCursor: true });
    zone.on('pointerover', () => {
      this.sel = i;
      this.redraw();
    });
    zone.on('pointerdown', () => this.choose(i));
    return { id, bg, worm, name, note, btn, btnText, zone, rect: [0, 0, 10, 10], btnRect: [0, 0, 10, 10] };
  }

  private makeBack(): void {
    this.backBg = this.add.graphics();
    this.backBtn = this.add.container(0, 0, [this.backBg]).setDepth(310);
    this.backBtn.on('pointerdown', () => this.cancel());
    this.backBtn.setVisible(!this.first);
  }

  // ---------- раскладка ----------
  private layout(): void {
    const u = this.u;
    const W = this.scale.width;
    const H = this.scale.height;
    this.dim.setSize(W, H);
    const wide = W / u >= 560;
    const m = 16 * u;
    this.title.setStyle(this.style(Math.min(40, Math.max(26, (W / u) * 0.05)), 8));
    this.title.setText(t('select_title')).setPosition(W / 2, m);
    // под заголовком и кнопкой «назад» (она есть, когда экран открыт из меню)
    const top = m + Math.max(this.title.height, this.first ? 0 : 52 * u) + 14 * u;
    const gap = 14 * u;
    const n = this.cards.length;

    if (wide) {
      const cw = Math.min((W - 2 * m - (n - 1) * gap) / n, 290 * u);
      const ch = Math.min(H - top - m, 360 * u);
      const x0 = (W - (n * cw + (n - 1) * gap)) / 2;
      const y0 = top + Math.max(0, (H - top - m - ch) / 2);
      this.cards.forEach((c, i) => this.placeWide(c, x0 + i * (cw + gap), y0, cw, ch));
    } else {
      const ch = Math.min(130 * u, (H - top - m - (n - 1) * gap) / n);
      const cw = Math.min(W - 2 * m, 520 * u);
      const x0 = (W - cw) / 2;
      const y0 = top + Math.max(0, (H - top - m - (n * ch + (n - 1) * gap)) / 2);
      this.cards.forEach((c, i) => this.placeRow(c, x0, y0 + i * (ch + gap), cw, ch));
    }
    // кнопка «назад» в углу (только когда экран открыт из меню)
    const bs = 52 * u;
    this.backBtn.setPosition(m + bs / 2, m + bs / 2);
    this.backBtn.setSize(bs, bs);
    this.backBtn.setInteractive(new Phaser.Geom.Rectangle(-bs / 2, -bs / 2, bs, bs), Phaser.Geom.Rectangle.Contains);
    this.backBg.clear();
    this.candy(this.backBg, -bs / 2, -bs / 2, bs, bs, 14 * u, 0x4d8dff);
    this.backBg.lineStyle(5 * u, 0xffffff, 1);
    this.backBg.beginPath().moveTo(0.18 * bs, 0).lineTo(-0.2 * bs, 0).moveTo(-0.2 * bs, 0).lineTo(-0.02 * bs, -0.18 * bs).moveTo(-0.2 * bs, 0).lineTo(-0.02 * bs, 0.18 * bs).strokePath();
    this.redraw();
  }

  private portrait(c: Card, cx: number, cy: number, pw: number, ph: number): void {
    // голова с челюстями занимает ≈ 175×125 px дизайна, центр группы смещён вперёд на ≈ 31 px
    const k = Math.max(0.2, Math.min(pw / 205, ph / 142));
    c.worm.setSize(k, 0.25);
    c.worm.scale = k;
    c.worm.reset(cx - 31 * k, cy + 10 * k, 0);
  }

  private placeWide(c: Card, x: number, y: number, w: number, h: number): void {
    const u = this.u;
    const portraitH = h * 0.46;
    this.portrait(c, x + w / 2, y + 18 * u + portraitH / 2, w - 24 * u, portraitH);
    c.name.setPosition(x + w / 2, y + 22 * u + portraitH + 6 * u);
    c.note.setPosition(x + w / 2, c.name.y + c.name.height + 2 * u);
    c.zone.setPosition(x, y).setSize(w, h);
    c.zone.input?.hitArea.setTo(0, 0, w, h);
    c.rect = [x, y, w, h];
    c.btnRect = [x + 14 * u, y + h - 14 * u - 52 * u, w - 28 * u, 52 * u];
  }

  private placeRow(c: Card, x: number, y: number, w: number, h: number): void {
    const u = this.u;
    const pw = h - 16 * u;
    this.portrait(c, x + 10 * u + pw / 2, y + h / 2, pw, h - 20 * u);
    const tx = x + 20 * u + pw;
    const bw = w - (tx - x) - 12 * u;
    c.name.setOrigin(0, 0).setPosition(tx, y + 8 * u);
    c.note.setOrigin(0, 0).setPosition(tx, c.name.y + c.name.height);
    c.zone.setPosition(x, y).setSize(w, h);
    c.zone.input?.hitArea.setTo(0, 0, w, h);
    c.rect = [x, y, w, h];
    c.btnRect = [tx, y + h - 8 * u - 46 * u, bw, 46 * u];
  }

  private candy(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, r: number, color: number): void {
    const u = this.u;
    g.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r + 3 * u);
    g.fillStyle(color, 1).fillRoundedRect(x, y, w, h, r);
    g.fillStyle(0xffffff, 0.33).fillRoundedRect(x + 4 * u, y + 4 * u, w - 8 * u, h * 0.38, r * 0.7);
  }

  /** Перерисовать выбор: рамка и подпись выбранной карточки, выражение червя. */
  private redraw(): void {
    const u = this.u;
    this.cards.forEach((c, i) => {
      const on = i === this.sel;
      const chosen = c.id === save.data.skin && save.data.skinChosen;
      const [x, y, w, h] = c.rect;
      c.bg.clear();
      c.bg.fillStyle(INK, 1).fillRoundedRect(x - 4 * u, y - 4 * u, w + 8 * u, h + 8 * u, 24 * u);
      c.bg.fillStyle(on ? 0x3b3566 : 0x262a3f, 1).fillRoundedRect(x, y, w, h, 20 * u);
      if (on) c.bg.lineStyle(5 * u, ORANGE, 1).strokeRoundedRect(x, y, w, h, 20 * u);
      c.bg.fillStyle(0xffffff, on ? 0.1 : 0.05).fillRoundedRect(x + 6 * u, y + 6 * u, w - 12 * u, h * 0.2, 14 * u);
      const [bx, by, bw, bh] = c.btnRect;
      c.btn.clear();
      this.candy(c.btn, bx, by, bw, bh, 14 * u, chosen ? GREEN : ORANGE);
      c.btnText.setStyle(this.style(22, 4));
      c.btnText.setText(chosen ? `${t('select_chosen')} ✓` : t('select_pick')).setPosition(bx + bw / 2, by + bh / 2);
      c.name.setStyle(this.style(26, 5)).setText(t(`skin.${c.id}` as TextKey));
      c.note.setStyle(this.style(16, 3, '#ffe9b8')).setText(t(`skin.${c.id}.note` as TextKey));
      c.worm.setHint(on ? 'happy' : 'idle');
    });
  }

  // ---------- ввод ----------
  private handleKey(e: KeyboardEvent): void {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const n = this.cards.length;
    switch (e.code) {
      case 'ArrowLeft':
      case 'KeyA':
      case 'ArrowUp':
      case 'KeyW':
        this.sel = (this.sel + n - 1) % n;
        sfx.unlock();
        sfx.play('ui');
        this.redraw();
        e.preventDefault();
        break;
      case 'ArrowRight':
      case 'KeyD':
      case 'ArrowDown':
      case 'KeyS':
        this.sel = (this.sel + 1) % n;
        sfx.unlock();
        sfx.play('ui');
        this.redraw();
        e.preventDefault();
        break;
      case 'Enter':
      case 'Space':
        this.choose(this.sel);
        e.preventDefault();
        break;
      case 'Escape':
        this.cancel();
        break;
      default: {
        const d = /^Digit([1-9])$/.exec(e.code);
        if (d && Number(d[1]) <= n) this.choose(Number(d[1]) - 1);
      }
    }
  }

  private choose(i: number): void {
    const id = this.cards[i].id;
    sfx.unlock();
    sfx.play('select');
    save.patch({ skin: id, skinChosen: true });
    state.selecting = false; // до события: подписчики (пауза, обучение) проверяют это
    this.game.events.emit('skin-chosen', id);
    this.scene.stop();
  }

  private cancel(): void {
    if (this.first) return;
    sfx.play('ui');
    state.selecting = false;
    this.game.events.emit('select-closed');
    this.scene.stop();
  }

  override update(time: number, delta: number): void {
    const dt = Math.min(delta / 1000, 0.05);
    for (const c of this.cards) c.worm.hold(dt, time);
  }

  private cleanup(): void {
    this.scale.off('resize', this.onResize);
    window.removeEventListener('keydown', this.onKey);
    this.cards.forEach((c) => c.worm.destroy());
    this.cards = [];
    state.selecting = false;
  }
}
