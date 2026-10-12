import Phaser from 'phaser';
import { state } from '../core/state';
import { sfx } from '../core/audio';
import { t, type TextKey } from '../core/i18n';
import { save, TUTORIAL_CH_SEEN, TUTORIAL_SHOP_OPENED } from '../platform/save';
import { LINES, MAX_UPGRADE, WING_LENGTH, bonusPercent, levelNameKey, priceFor, type LineId } from '../data/upgrades';
import { challengeKey } from '../data/challenges';
import { Worm } from '../game/Worm';
import { Fx } from '../game/Fx';

const FONT = "'Trebuchet MS', 'Segoe UI', Verdana, Arial, sans-serif";
const INK = 0x2b1b17;
const ORANGE = 0xffb020;
const GREEN = 0x6bbf3a;
const GREY = 0x7d84a8;
const NAVY = 0x1e2a5a;
const ROW = 0x2b3a78;
const ROW_ON = 0x3b50a8;
const SOIL = 0x5b3a29;
const STAR_COLORS = [0xffd23f, 0xffffff, 0xff9a2e];

/** Ширина и высота червя-витрины в px дизайна (тело 5 звеньев, хвостовой плавник, голова, крылья над спиной): по ним считается масштаб. */
const SHOW_W = 650;
const SHOW_H = 400;
const SHOW_SEGS = 5;

interface UpRow {
  line: LineId;
  bg: Phaser.GameObjects.Graphics;
  thumbBg: Phaser.GameObjects.Graphics;
  thumb: Phaser.GameObjects.Image;
  label: Phaser.GameObjects.Text;
  name: Phaser.GameObjects.Text;
  eff: Phaser.GameObjects.Text;
  pips: Phaser.GameObjects.Graphics;
  btn: Phaser.GameObjects.Graphics;
  btnText: Phaser.GameObjects.Text;
  btnIcon: Phaser.GameObjects.Image;
  zone: Phaser.GameObjects.Zone;
  btnZone: Phaser.GameObjects.Zone;
  /** Прямоугольники строки и кнопки в px холста: x, y, ширина, высота. */
  rect: number[];
  btnRect: number[];
  thumbRect: number[];
  /** Где лежат подписи: x, y, ширина, высота. */
  textRect: number[];
}

interface ChRow {
  bg: Phaser.GameObjects.Graphics;
  text: Phaser.GameObjects.Text;
  bar: Phaser.GameObjects.Graphics;
  prog: Phaser.GameObjects.Text;
  chip: Phaser.GameObjects.Graphics;
  reward: Phaser.GameObjects.Text;
  icon: Phaser.GameObjects.Image;
  rect: number[];
}

interface Tab {
  bg: Phaser.GameObjects.Graphics;
  text: Phaser.GameObjects.Text;
  zone: Phaser.GameObjects.Zone;
  rect: number[];
}

/**
 * Магазин: три линии улучшений (прыжок/крылья, здоровье/броня, скорость/гребень) по пять ступеней и вкладка испытаний.
 * Игра стоит на паузе. Слева или сверху витрина: ваш червь со всеми купленными деталями, покупка меняет его сразу.
 * Кнопки не меньше 44 CSS-px (п. 1.8), всё помещается в любое окно (п. 1.10), управление мышью, пальцем и клавишами.
 * Покупка сохраняется сразу (п. 1.9).
 */
export class ShopScene extends Phaser.Scene {
  private tab = 0;
  private sel = 0;
  private bought = false;
  private dim!: Phaser.GameObjects.Rectangle;
  private panel!: Phaser.GameObjects.Graphics;
  private stage!: Phaser.GameObjects.Graphics;
  private title!: Phaser.GameObjects.Text;
  private coinPlate!: Phaser.GameObjects.Graphics;
  private coinIcon!: Phaser.GameObjects.Image;
  private coinText!: Phaser.GameObjects.Text;
  private closeBg!: Phaser.GameObjects.Graphics;
  private closeZone!: Phaser.GameObjects.Zone;
  private tabs: Tab[] = [];
  private ups: UpRow[] = [];
  private chs: ChRow[] = [];
  private worm!: Worm;
  private fx!: Fx;
  private stageRect = [0, 0, 0, 0];
  private showWorm = true;
  private wormK = 1;
  private shownCoins = -1;
  private closing = false;
  /** Правый край плашки монет: от него плашка растёт влево. */
  private coinRight = 0;
  private onKey = (e: KeyboardEvent): void => this.handleKey(e);
  private onResize = (): void => this.layout();

  constructor() {
    super('Shop');
  }

  create(): void {
    state.shopOpen = true;
    this.tab = 0;
    this.bought = false;
    this.closing = false;
    this.ups = [];
    this.chs = [];
    this.tabs = [];
    this.shownCoins = -1;
    this.sel = this.firstWanted();

    this.dim = this.add.rectangle(0, 0, 10, 10, 0x0b0d1a, 0.84).setOrigin(0, 0).setDepth(-100).setInteractive();
    this.panel = this.add.graphics().setDepth(-90);
    this.stage = this.add.graphics().setDepth(-80);
    this.title = this.add.text(0, 0, '', this.style(34, 7)).setOrigin(0, 0.5).setDepth(300);
    this.coinPlate = this.add.graphics().setDepth(250);
    this.coinIcon = this.add.image(0, 0, 'treasure', 'treasure-coin').setDepth(300);
    this.coinText = this.add.text(0, 0, '0', { ...this.style(24, 5), color: '#ffe27a' }).setOrigin(0, 0.5).setDepth(300);
    this.closeBg = this.add.graphics().setDepth(250);
    this.closeZone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setDepth(400).setInteractive({ useHandCursor: true });
    this.closeZone.on('pointerdown', () => this.close(false));
    for (let i = 0; i < 2; i++) this.tabs.push(this.makeTab(i));
    for (const line of LINES) this.ups.push(this.makeUpRow(line));
    for (let i = 0; i < 3; i++) this.chs.push(this.makeChRow());

    this.worm = new Worm(this, save.data.skin, -9999, -9999);
    this.worm.setUpgrades(save.data.up);
    this.worm.showOff = true;
    this.worm.setHint('idle');
    this.fx = new Fx(this);

    this.layout();
    this.scale.on('resize', this.onResize);
    window.addEventListener('keydown', this.onKey);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.cleanup());
    if (!(save.data.tutorial & TUTORIAL_SHOP_OPENED)) save.patch({ tutorial: save.data.tutorial | TUTORIAL_SHOP_OPENED });
    sfx.unlock();
    sfx.play('ui');
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

  private makeTab(i: number): Tab {
    const bg = this.add.graphics().setDepth(250);
    const text = this.add.text(0, 0, '', this.style(20, 4)).setOrigin(0.5).setDepth(300);
    const zone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setDepth(400).setInteractive({ useHandCursor: true });
    zone.on('pointerdown', () => this.setTab(i));
    return { bg, text, zone, rect: [0, 0, 10, 10] };
  }

  private makeUpRow(line: LineId): UpRow {
    const i = this.ups.length;
    const bg = this.add.graphics().setDepth(-70);
    const thumbBg = this.add.graphics().setDepth(-60);
    const thumb = this.add.image(0, 0, 'wings', 'wings-t1-front').setDepth(10);
    const label = this.add.text(0, 0, '', this.style(13, 3, '#ffe9b8')).setOrigin(0, 0).setDepth(300);
    const name = this.add.text(0, 0, '', this.style(20, 4)).setOrigin(0, 0).setDepth(300);
    const eff = this.add.text(0, 0, '', this.style(14, 3, '#cfe3ff')).setOrigin(0, 0).setDepth(300);
    const pips = this.add.graphics().setDepth(300);
    const btn = this.add.graphics().setDepth(250);
    const btnText = this.add.text(0, 0, '', this.style(24, 5)).setOrigin(0.5).setDepth(300);
    const btnIcon = this.add.image(0, 0, 'treasure', 'treasure-coin').setDepth(300);
    const zone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setDepth(100).setInteractive({ useHandCursor: true });
    zone.on('pointerover', () => this.select(i));
    zone.on('pointerdown', () => this.select(i));
    const btnZone = this.add.zone(0, 0, 10, 10).setOrigin(0, 0).setDepth(400).setInteractive({ useHandCursor: true });
    btnZone.on('pointerdown', () => {
      this.select(i);
      this.buy(i);
    });
    return { line, bg, thumbBg, thumb, label, name, eff, pips, btn, btnText, btnIcon, zone, btnZone, rect: [0, 0, 10, 10], btnRect: [0, 0, 10, 10], thumbRect: [0, 0, 10, 10], textRect: [0, 0, 10, 10] };
  }

  private makeChRow(): ChRow {
    const bg = this.add.graphics().setDepth(-70);
    const text = this.add.text(0, 0, '', this.style(19, 4)).setOrigin(0, 0).setDepth(300);
    const bar = this.add.graphics().setDepth(250);
    const prog = this.add.text(0, 0, '', this.style(14, 3, '#cfe3ff')).setOrigin(0, 0.5).setDepth(300);
    const chip = this.add.graphics().setDepth(250);
    const reward = this.add.text(0, 0, '', { ...this.style(22, 4.5), color: '#ffe27a' }).setOrigin(0, 0.5).setDepth(300);
    const icon = this.add.image(0, 0, 'treasure', 'treasure-coin').setDepth(300);
    return { bg, text, bar, prog, chip, reward, icon, rect: [0, 0, 10, 10] };
  }

  // ---------- раскладка ----------
  /** Подгоняет текст под ширину: сначала уменьшает шрифт до минимума, потом переносит по словам. */
  private fit(txt: Phaser.GameObjects.Text, s: string, maxWidth: number, maxCss: number, minCss: number, strokeCss: number, color = '#ffffff'): void {
    const maxW = Math.max(40 * this.u, maxWidth);
    let px = maxCss;
    txt.setWordWrapWidth(0);
    txt.setStyle(this.style(px, strokeCss, color));
    txt.setText(s);
    while (txt.width > maxW && px > minCss) {
      px -= 1;
      txt.setStyle(this.style(px, strokeCss, color));
    }
    if (txt.width > maxW) txt.setWordWrapWidth(maxW, true);
  }

  private candy(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, r: number, color: number): void {
    const u = this.u;
    g.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r + 3 * u);
    g.fillStyle(color, 1).fillRoundedRect(x, y, w, h, r);
    g.fillStyle(0xffffff, 0.33).fillRoundedRect(x + 4 * u, y + 4 * u, w - 8 * u, h * 0.38, r * 0.7);
  }

  private layout(): void {
    const u = this.u;
    const W = this.scale.width;
    const H = this.scale.height;
    const cssW = W / u;
    const cssH = H / u;
    this.dim.setSize(W, H);
    const compact = cssH < 440;
    const narrow = cssW < 480;
    const m = (narrow || compact ? 6 : 14) * u;
    const pw = Math.min(W - 2 * m, 1120 * u);
    const ph = Math.min(H - 2 * m, 700 * u);
    const X = (W - pw) / 2;
    const Y = (H - ph) / 2;
    const pad = (compact ? 6 : 14) * u;
    const gap = (compact ? 4 : 10) * u;

    this.panel.clear();
    this.panel.fillStyle(INK, 1).fillRoundedRect(X - 4 * u, Y - 4 * u, pw + 8 * u, ph + 8 * u, 26 * u);
    this.panel.fillStyle(NAVY, 1).fillRoundedRect(X, Y, pw, ph, 22 * u);
    this.panel.fillStyle(0xffffff, 0.06).fillRoundedRect(X + 6 * u, Y + 6 * u, pw - 12 * u, ph * 0.12, 16 * u);

    // шапка: заголовок, монеты, закрыть
    const cb = (compact ? 46 : 52) * u;
    const hh = cb;
    const cbx = X + pw - pad - cb;
    const cby = Y + pad;
    this.closeBg.clear();
    this.candy(this.closeBg, cbx, cby, cb, cb, 14 * u, 0xe8523f);
    this.closeBg.lineStyle(5 * u, 0xffffff, 1);
    const q = cb * 0.26;
    const cx0 = cbx + cb / 2;
    const cy0 = cby + cb / 2;
    this.closeBg.beginPath().moveTo(cx0 - q, cy0 - q).lineTo(cx0 + q, cy0 + q).moveTo(cx0 + q, cy0 - q).lineTo(cx0 - q, cy0 + q).strokePath();
    this.closeZone.setPosition(cbx, cby).setSize(cb, cb);
    this.closeZone.input?.hitArea.setTo(0, 0, cb, cb);
    this.title.setStyle(this.style(compact ? 26 : narrow ? 28 : 34, 7));
    this.title.setText(t('shop_title')).setPosition(X + pad, cby + cb / 2);
    this.shownCoins = -1;
    this.coinRight = cbx - gap;
    this.drawCoins(this.coinRight);

    // вкладки
    const tabY = Y + pad + hh + gap;
    const tb = 46 * u;
    const labels: TextKey[] = ['shop_tab_up', 'shop_tab_ch'];
    let tx = X + pad;
    const tabW = narrow ? (pw - 2 * pad - gap) / 2 : 0;
    this.tabs.forEach((tab, i) => {
      tab.text.setStyle(this.style(compact ? 17 : 20, 4));
      tab.text.setText(t(labels[i]));
      const w = narrow ? tabW : Math.max(120 * u, tab.text.width + 40 * u);
      tab.rect = [tx, tabY, w, tb];
      tab.text.setPosition(tx + w / 2, tabY + tb / 2);
      tab.zone.setPosition(tx, tabY).setSize(w, tb);
      tab.zone.input?.hitArea.setTo(0, 0, w, tb);
      tx += w + gap;
    });

    // область содержимого
    const top = tabY + tb + gap;
    const left = X + pad;
    const right = X + pw - pad;
    const bottom = Y + ph - pad;
    const cw = right - left;
    const chh = bottom - top;
    const minRow = 60 * u;
    const wide = cw >= 640 * u && chh >= 250 * u;
    let rowsX = left;
    let rowsW = cw;
    let rowsY = top;
    this.stageRect = [0, 0, 0, 0];
    if (wide) {
      const sw = Math.max(240 * u, Math.min(cw * 0.42, 480 * u));
      this.stageRect = [left, top, sw, chh];
      rowsX = left + sw + gap * 1.5;
      rowsW = cw - sw - gap * 1.5;
    }
    // узкая строка (телефон стоя): кнопка цены под подписями на всю ширину, иначе справа
    const stackRows = rowsW < 430 * u;
    const stackH = 116 * u;
    let rowH = 0;
    if (wide) {
      rowH = Math.min(stackRows ? stackH : 124 * u, (chh - 2 * gap) / 3);
      rowsY = top + Math.max(0, (chh - (3 * Math.max(minRow, rowH) + 2 * gap)) / 2);
    } else {
      const rowNeed = stackRows ? stackH : minRow;
      const stageH = chh - (3 * rowNeed + 2 * gap) - gap;
      if (stageH >= 96 * u) {
        const sh = Math.min(stageH, 230 * u, cw * 0.5);
        this.stageRect = [left, top, cw, sh];
        rowsY = top + sh + gap;
        rowH = Math.min(stackRows ? stackH : 106 * u, (bottom - rowsY - 2 * gap) / 3);
      } else {
        rowH = Math.min(stackRows ? stackH : 106 * u, (chh - 2 * gap) / 3);
      }
    }
    rowH = Math.max(stackRows ? 100 * u : minRow, rowH);
    this.showWorm = this.stageRect[2] > 0;

    this.stage.clear();
    if (this.showWorm) {
      const [sx, sy, sw, sh] = this.stageRect;
      this.stage.fillStyle(INK, 1).fillRoundedRect(sx - 3 * u, sy - 3 * u, sw + 6 * u, sh + 6 * u, 20 * u);
      this.stage.fillStyle(SOIL, 1).fillRoundedRect(sx, sy, sw, sh, 17 * u);
      this.stage.fillStyle(0x7a5236, 1).fillRoundedRect(sx, sy + sh * 0.55, sw, sh * 0.45, { tl: 0, tr: 0, bl: 17 * u, br: 17 * u });
      this.stage.fillStyle(0xffffff, 0.08).fillRoundedRect(sx + 6 * u, sy + 6 * u, sw - 12 * u, sh * 0.14, 12 * u);
      // камешки в земле: одни и те же при любой раскладке
      let seed = 7;
      const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      for (let i = 0; i < 16; i++) {
        const px = sx + 14 * u + rnd() * (sw - 28 * u);
        const py = sy + sh * 0.3 + rnd() * (sh * 0.64);
        const pr = (5 + rnd() * 9) * u;
        this.stage.fillStyle(0x3a2417, 0.55).fillEllipse(px, py + 2 * u, pr * 2.2, pr * 1.5);
        this.stage.fillStyle(0xa57852, 0.75).fillEllipse(px, py, pr * 2.1, pr * 1.4);
        this.stage.fillStyle(0xffffff, 0.18).fillEllipse(px - pr * 0.3, py - pr * 0.3, pr * 0.9, pr * 0.5);
      }
      this.placeWorm();
    } else {
      this.worm.reset(-9999, -9999, 0);
    }

    this.ups.forEach((r, i) => {
      const y = rowsY + i * (rowH + gap);
      r.rect = [rowsX, y, rowsW, rowH];
      const r10 = Math.min(10 * u, rowH * 0.12);
      if (stackRows) {
        const bh = 46 * u;
        const ts = Math.min(52 * u, rowH - 2 * r10 - bh - 6 * u);
        r.thumbRect = [rowsX + r10, y + r10, ts, ts];
        r.btnRect = [rowsX + r10, y + rowH - r10 - bh, rowsW - 2 * r10, bh];
        r.textRect = [rowsX + r10 + ts + 10 * u, y + r10, rowsW - 2 * r10 - ts - 10 * u, ts];
      } else {
        const ts = Math.min(rowH - 2 * r10, 84 * u);
        r.thumbRect = [rowsX + r10, y + (rowH - ts) / 2, ts, ts];
        const bw = Math.max(108 * u, Math.min(rowsW * 0.27, 170 * u));
        const bh = Math.max(46 * u, Math.min(54 * u, rowH - 2 * r10));
        r.btnRect = [rowsX + rowsW - r10 - bw, y + (rowH - bh) / 2, bw, bh];
        const tx = rowsX + r10 + ts + 12 * u;
        r.textRect = [tx, y + 4 * u, Math.max(60 * u, r.btnRect[0] - 10 * u - tx), rowH - 8 * u];
      }
      r.zone.setPosition(rowsX, y).setSize(rowsW, rowH);
      r.zone.input?.hitArea.setTo(0, 0, rowsW, rowH);
      r.btnZone.setPosition(r.btnRect[0], r.btnRect[1]).setSize(r.btnRect[2], r.btnRect[3]);
      r.btnZone.input?.hitArea.setTo(0, 0, r.btnRect[2], r.btnRect[3]);
    });
    this.chs.forEach((r, i) => {
      r.rect = [rowsX, rowsY + i * (rowH + gap), rowsW, rowH];
    });
    this.redraw();
  }

  /** Витрина: червь целиком с текущими улучшениями, масштаб по размеру площадки. */
  private placeWorm(): void {
    const [sx, sy, sw, sh] = this.stageRect;
    const u = this.u;
    const k = Math.max(0.16, Math.min(1.05, Math.min((sw * 0.94) / SHOW_W, (sh * 0.92) / SHOW_H)));
    this.wormK = k;
    const L = SHOW_SEGS * 72;
    const hx = sx + sw / 2 + ((L - 10) / 2) * k;
    // над спиной крылья, рога и плавник: тело опускается ровно настолько, чтобы всё вместе стояло по центру площадки
    const up = Math.max(110, (WING_LENGTH[save.data.up.jump] ?? 0) * 0.95 + 40);
    const hy = Math.min(sy + sh - 62 * k - 14 * u, sy + sh / 2 + ((up - 70) / 2) * k);
    this.worm.setSize(k, SHOW_SEGS);
    this.worm.scale = k;
    this.worm.reset(hx, hy, 0);
  }

  private drawCoins(rightEdge: number): void {
    const u = this.u;
    const cy = this.title.y;
    this.coinText.setStyle({ ...this.style(compactSize(this.scale.height / u, 22, 26), 5), color: '#ffe27a' });
    this.coinText.setText(String(state.coins));
    const h = 38 * u;
    const w = 56 * u + this.coinText.width;
    const x = rightEdge - w;
    this.coinPlate.clear();
    this.coinPlate.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, cy - h / 2 - 3 * u, w + 6 * u, h + 6 * u, h / 2 + 3 * u);
    this.coinPlate.fillStyle(0x4a2f1f, 1).fillRoundedRect(x, cy - h / 2, w, h, h / 2);
    this.coinPlate.fillStyle(0xffffff, 0.14).fillRoundedRect(x + 4 * u, cy - h / 2 + 3 * u, w - 8 * u, 11 * u, 6 * u);
    this.coinIcon.setScale((32 * u) / 64).setPosition(x + 22 * u, cy);
    this.coinText.setPosition(x + 42 * u, cy + 1 * u);
    this.shownCoins = state.coins;
  }

  // ---------- рисование ----------
  private firstWanted(): number {
    const i = LINES.findIndex((l) => {
      const p = priceFor(save.data.up[l]);
      return p !== null && state.coins >= p;
    });
    if (i >= 0) return i;
    const j = LINES.findIndex((l) => save.data.up[l] < MAX_UPGRADE);
    return j >= 0 ? j : 0;
  }

  private thumbFrame(line: LineId, n: number): { atlas: string; frame: string } {
    const skin = save.data.skin;
    if (line === 'jump') return { atlas: 'wings', frame: `wings-t${n}-front` };
    if (line === 'hp') return { atlas: `gear-${skin}`, frame: `armor-${skin}-t${n}-plate` };
    return { atlas: `gear-${skin}`, frame: `fin-${skin}-t${n}-seg` };
  }

  /** Перерисовать содержимое выбранной вкладки. */
  private redraw(): void {
    const u = this.u;
    // вкладки
    this.tabs.forEach((tab, i) => {
      const [x, y, w, h] = tab.rect;
      tab.bg.clear();
      this.candy(tab.bg, x, y, w, h, 13 * u, i === this.tab ? ORANGE : 0x4a5698);
      // красная точка на вкладке испытаний, пока её ни разу не открывали
      if (i === 1 && !(save.data.tutorial & TUTORIAL_CH_SEEN)) {
        tab.bg.fillStyle(0xffffff, 1).fillCircle(x + w - 8 * u, y + 8 * u, 10 * u);
        tab.bg.fillStyle(0xe8352a, 1).fillCircle(x + w - 8 * u, y + 8 * u, 7.5 * u);
      }
    });
    const up = this.tab === 0;
    this.ups.forEach((r, i) => {
      const on = up;
      for (const o of [r.bg, r.thumbBg, r.thumb, r.label, r.name, r.eff, r.pips, r.btn, r.btnText, r.btnIcon]) o.setVisible(on);
      this.setZone(r.zone, on);
      this.setZone(r.btnZone, on);
      if (on) this.redrawUpRow(r, i);
    });
    this.chs.forEach((r, i) => {
      const on = !up;
      for (const o of [r.bg, r.text, r.bar, r.prog, r.chip, r.reward, r.icon]) o.setVisible(on);
      if (on) this.redrawChRow(r, i);
    });
  }

  private setZone(z: Phaser.GameObjects.Zone, on: boolean): void {
    if (z.input) z.input.enabled = on;
  }

  private redrawUpRow(r: UpRow, i: number): void {
    const u = this.u;
    const lvl = save.data.up[r.line];
    const maxed = lvl >= MAX_UPGRADE;
    const next = Math.min(MAX_UPGRADE, lvl + 1);
    const price = priceFor(lvl);
    const can = price !== null && state.coins >= price;
    const on = i === this.sel;
    const [x, y, w, h] = r.rect;
    const r12 = Math.min(14 * u, h * 0.16);
    r.bg.clear();
    r.bg.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r12 + 3 * u);
    r.bg.fillStyle(on ? ROW_ON : ROW, 1).fillRoundedRect(x, y, w, h, r12);
    if (on) r.bg.lineStyle(4 * u, ORANGE, 1).strokeRoundedRect(x, y, w, h, r12);
    r.bg.fillStyle(0xffffff, on ? 0.1 : 0.06).fillRoundedRect(x + 5 * u, y + 5 * u, w - 10 * u, h * 0.2, 9 * u);

    // значок следующей ступени (или последней, если куплено всё)
    const [tx, ty, ts] = r.thumbRect;
    r.thumbBg.clear();
    r.thumbBg.fillStyle(INK, 1).fillRoundedRect(tx - 2 * u, ty - 2 * u, ts + 4 * u, ts + 4 * u, 12 * u);
    r.thumbBg.fillStyle(SOIL, 1).fillRoundedRect(tx, ty, ts, ts, 10 * u);
    const { atlas, frame } = this.thumbFrame(r.line, maxed ? MAX_UPGRADE : next);
    r.thumb.setTexture(atlas, frame);
    // кадр обрезан по прозрачным полям: масштаб берём по видимой части и сдвигаем её в центр плитки
    const fr = r.thumb.frame;
    const sc = (ts * 0.84) / Math.max(fr.width, fr.height);
    const dx = (fr.realWidth / 2 - (fr.x + fr.width / 2)) * sc;
    const dy = (fr.realHeight / 2 - (fr.y + fr.height / 2)) * sc;
    r.thumb.setScale(sc).setPosition(tx + ts / 2 + dx, ty + ts / 2 + dy);
    if (this.tab === 0) r.thumb.setVisible(true);

    // подписи: блок из названия линии со ступенями, названия ступени и эффекта, по центру области текста по вертикали
    const [textX, textY, textW, textH] = r.textRect;
    const tall = textH >= 78 * u || (r.btnRect[1] > y + h * 0.4 && textH >= 52 * u);
    r.label.setVisible(tall);
    if (tall) this.fit(r.label, t(`line.${r.line}` as TextKey).toUpperCase(), textW - 90 * u, 13, 11, 3, '#ffe9b8');
    const nameKey = levelNameKey(r.line, maxed ? lvl : next);
    this.fit(r.name, t(nameKey), textW, tall ? 20 : 17, 12, 4);
    const cur = bonusPercent(r.line, lvl);
    let effText = maxed
      ? t(`eff.${r.line}` as TextKey, { n: cur })
      : lvl === 0
        ? t(`eff.${r.line}` as TextKey, { n: bonusPercent(r.line, next) })
        : `${t(`eff.${r.line}` as TextKey, { n: cur })} → +${bonusPercent(r.line, next)}%`;
    // крылья: к высоте прыжка добавляется умение лететь (парить, зависать, набирать высоту)
    if (r.line === 'jump') effText = `${t(`fly.${maxed ? lvl : next}` as TextKey)} · ${t('eff.jump', { n: bonusPercent('jump', maxed ? lvl : next) })}`;
    this.fit(r.eff, effText, textW, tall ? 14 : 13, 10, 3, maxed ? '#9be15d' : '#cfe3ff');
    const labelH = tall ? r.label.height + 2 * u : 0;
    const blockH = labelH + r.name.height + 1 * u + r.eff.height;
    let yy = textY + Math.max(0, (textH - blockH) / 2);
    if (tall) {
      r.label.setPosition(textX, yy);
      this.drawPips(r, textX + r.label.width + 8 * u, yy + r.label.height / 2, lvl);
      yy += labelH;
    } else {
      r.pips.clear();
    }
    r.name.setPosition(textX, yy);
    yy += r.name.height + 1 * u;
    r.eff.setPosition(textX, yy);
    if (!tall) this.drawPips(r, textX + Math.min(textW - 70 * u, Math.max(r.name.width, r.eff.width) + 14 * u), textY + textH / 2, lvl);

    // кнопка цены
    const [bx, by, bw, bh] = r.btnRect;
    r.btn.clear();
    this.candy(r.btn, bx, by, bw, bh, 14 * u, maxed ? 0x5a607d : can ? GREEN : GREY);
    if (maxed) {
      r.btnIcon.setVisible(false);
      this.fit(r.btnText, t('shop_max'), bw - 14 * u, 18, 12, 4);
      r.btnText.setPosition(bx + bw / 2, by + bh / 2);
    } else {
      r.btnText.setStyle(this.style(bh >= 50 * u ? 24 : 22, 5, can ? '#ffffff' : '#e3e6f5'));
      r.btnText.setWordWrapWidth(0);
      r.btnText.setText(String(price));
      const iw = 30 * u;
      const total = iw + 6 * u + r.btnText.width;
      const sx = bx + (bw - total) / 2;
      r.btnIcon.setVisible(this.tab === 0).setScale(iw / 64).setPosition(sx + iw / 2, by + bh / 2).setAlpha(can ? 1 : 0.6);
      r.btnText.setPosition(sx + iw + 6 * u + r.btnText.width / 2, by + bh / 2 + 1 * u);
    }
  }

  private drawPips(r: UpRow, x: number, cy: number, lvl: number): void {
    const u = this.u;
    const g = r.pips;
    g.clear();
    const d = 11 * u;
    for (let k = 0; k < MAX_UPGRADE; k++) {
      const px = x + k * (d + 3 * u) + d / 2;
      g.fillStyle(INK, 1).fillCircle(px, cy, d / 2 + 1.5 * u);
      g.fillStyle(k < lvl ? ORANGE : 0x3a4272, 1).fillCircle(px, cy, d / 2);
      if (k < lvl) g.fillStyle(0xffffff, 0.45).fillCircle(px - 1.5 * u, cy - 1.5 * u, d * 0.18);
    }
  }

  private redrawChRow(r: ChRow, i: number): void {
    const u = this.u;
    const c = save.data.ch[i];
    const [x, y, w, h] = r.rect;
    const r12 = Math.min(14 * u, h * 0.16);
    r.bg.clear();
    r.bg.fillStyle(INK, 1).fillRoundedRect(x - 3 * u, y - 3 * u, w + 6 * u, h + 6 * u, r12 + 3 * u);
    r.bg.fillStyle(ROW, 1).fillRoundedRect(x, y, w, h, r12);
    r.bg.fillStyle(0xffffff, 0.06).fillRoundedRect(x + 5 * u, y + 5 * u, w - 10 * u, h * 0.2, 9 * u);
    r.bar.clear();
    r.chip.clear();
    if (!c) {
      for (const o of [r.text, r.prog, r.reward, r.icon]) o.setVisible(false);
      return;
    }
    const pad = Math.min(14 * u, h * 0.2);
    const chipH = Math.min(44 * u, h - 2 * pad);
    r.reward.setStyle({ ...this.style(22, 4.5), color: '#ffe27a' });
    r.reward.setText(`+${c.r}`);
    const iw = 28 * u;
    const chipW = iw + 10 * u + r.reward.width + 20 * u;
    const chipX = x + w - pad - chipW;
    const chipY = y + (h - chipH) / 2;
    r.chip.fillStyle(INK, 1).fillRoundedRect(chipX - 2 * u, chipY - 2 * u, chipW + 4 * u, chipH + 4 * u, chipH / 2 + 2 * u);
    r.chip.fillStyle(0x4a2f1f, 1).fillRoundedRect(chipX, chipY, chipW, chipH, chipH / 2);
    r.icon.setVisible(true).setScale(iw / 64).setPosition(chipX + 10 * u + iw / 2, chipY + chipH / 2);
    r.reward.setVisible(true).setPosition(chipX + 18 * u + iw, chipY + chipH / 2 + 1 * u);
    const textW = Math.max(80 * u, chipX - 12 * u - (x + pad));
    this.fit(r.text, t(challengeKey(c.k), { n: c.n }), textW, h >= 84 * u ? 20 : 17, 12, 4);
    const barH = Math.min(14 * u, h * 0.2);
    const blockH = r.text.height + 6 * u + barH;
    const ty = y + (h - blockH) / 2;
    r.text.setPosition(x + pad, ty);
    const by = ty + r.text.height + 6 * u;
    const progW = 70 * u;
    const bw = Math.max(50 * u, textW - progW - 6 * u);
    const ratio = Math.max(0, Math.min(1, c.p / c.n));
    r.bar.fillStyle(INK, 1).fillRoundedRect(x + pad - 2 * u, by - 2 * u, bw + 4 * u, barH + 4 * u, barH / 2 + 2 * u);
    r.bar.fillStyle(0x3a4272, 1).fillRoundedRect(x + pad, by, bw, barH, barH / 2);
    if (ratio > 0.01) {
      const fw = Math.max(barH, bw * ratio);
      r.bar.fillStyle(ORANGE, 1).fillRoundedRect(x + pad, by, fw, barH, barH / 2);
      r.bar.fillStyle(0xffffff, 0.35).fillRoundedRect(x + pad + 2 * u, by + 2 * u, fw - 4 * u, barH * 0.35, barH * 0.2);
    }
    r.prog.setStyle(this.style(14, 3, '#cfe3ff'));
    r.prog.setText(`${c.p} / ${c.n}`).setVisible(true).setPosition(x + pad + bw + 8 * u, by + barH / 2);
  }

  // ---------- действия ----------
  private select(i: number): void {
    if (this.sel === i || this.tab !== 0) return;
    this.sel = i;
    this.redraw();
  }

  private setTab(i: number): void {
    if (this.tab === i) return;
    this.tab = i;
    if (i === 1 && !(save.data.tutorial & TUTORIAL_CH_SEEN)) save.patch({ tutorial: save.data.tutorial | TUTORIAL_CH_SEEN });
    sfx.play('ui');
    this.redraw();
  }

  private buy(i: number): void {
    const line = LINES[i];
    const lvl = save.data.up[line];
    const price = priceFor(lvl);
    const row = this.ups[i];
    if (price === null) {
      sfx.play('bump');
      return;
    }
    if (state.coins < price) {
      sfx.play('bump');
      this.denied(row, price - state.coins);
      return;
    }
    state.coins -= price;
    this.bought = true;
    save.patch({ coins: state.coins, up: { [line]: lvl + 1 } });
    this.game.events.emit('upgrade-bought', line, lvl + 1);
    sfx.play('buy');
    this.worm.setUpgrades(save.data.up);
    if (this.showWorm) this.placeWorm();
    this.celebrate(row);
    this.redraw();
    this.drawCoins(this.coinRight);
  }

  /** Не хватает монет: плашка монет вздрагивает, у кнопки всплывает «Не хватает N». */
  private denied(row: UpRow, need: number): void {
    const u = this.u;
    this.tweens.killTweensOf([this.coinText, this.coinIcon]);
    this.coinText.setTint(0xff6a5a);
    this.time.delayedCall(350, () => this.coinText.clearTint());
    this.tweens.add({ targets: [this.coinText, this.coinIcon], x: '+=6', duration: 50, yoyo: true, repeat: 3 });
    const [bx, by, bw] = row.btnRect;
    const tx = this.add
      .text(bx + bw / 2, by - 4 * u, t('shop_need', { n: need }), this.style(16, 4, '#ffb4a8'))
      .setOrigin(0.5, 1)
      .setDepth(500);
    this.tweens.add({ targets: tx, y: by - 26 * u, alpha: 0, duration: 900, ease: 'Cubic.easeOut', onComplete: () => tx.destroy() });
  }

  /** Покупка: звёздочки и кольцо на витрине, вспышка, «-цена» над счётом. */
  private celebrate(row: UpRow): void {
    const u = this.u;
    const [sx, sy, sw, sh] = this.stageRect;
    if (this.showWorm) {
      const cx = sx + sw / 2;
      const cy = sy + sh * 0.55;
      this.fx.burst(cx, cy, u, { count: 22, frame: 'fx-star', colors: STAR_COLORS, speed: 520, life: 0.9, gravity: 500, size: 30 });
      this.fx.ring(cx, cy, u * Math.max(0.8, this.wormK * 1.4), 0xffd23f);
      const flash = this.add.rectangle(sx, sy, sw, sh, 0xffffff, 0.55).setOrigin(0, 0).setDepth(200);
      this.tweens.add({ targets: flash, alpha: 0, duration: 380, onComplete: () => flash.destroy() });
    }
    const [bx, by, bw, bh] = row.btnRect;
    this.fx.burst(bx + bw / 2, by + bh / 2, u, { count: 10, frame: 'fx-coin-sparkle', colors: [0xffd23f, 0xffffff], speed: 320, life: 0.6, gravity: 300, size: 28 });
  }

  private close(viaKey: boolean): void {
    if (this.closing) return;
    this.closing = true;
    sfx.play('ui');
    const finish = () => {
      state.shopOpen = false;
      this.game.events.emit('shop-closed', this.bought);
      this.scene.stop();
    };
    // с клавиши закрываем на следующем такте: обработчики других сцен на ту же клавишу должны увидеть открытый магазин
    if (viaKey) window.setTimeout(finish, 0);
    else finish();
  }

  // ---------- ввод ----------
  private handleKey(e: KeyboardEvent): void {
    if (e.ctrlKey || e.metaKey || e.altKey || this.closing) return;
    switch (e.code) {
      case 'Escape':
      case 'KeyB':
        this.close(true);
        e.preventDefault();
        break;
      case 'ArrowUp':
      case 'KeyW':
        if (this.tab === 0) this.select((this.sel + LINES.length - 1) % LINES.length);
        e.preventDefault();
        break;
      case 'ArrowDown':
      case 'KeyS':
        if (this.tab === 0) this.select((this.sel + 1) % LINES.length);
        e.preventDefault();
        break;
      case 'ArrowLeft':
      case 'KeyA':
        this.setTab(0);
        e.preventDefault();
        break;
      case 'ArrowRight':
      case 'KeyD':
        this.setTab(1);
        e.preventDefault();
        break;
      case 'Enter':
      case 'Space':
        if (this.tab === 0) this.buy(this.sel);
        e.preventDefault();
        break;
      default: {
        const d = /^Digit([1-3])$/.exec(e.code);
        if (d && this.tab === 0) {
          this.select(Number(d[1]) - 1);
          this.buy(Number(d[1]) - 1);
        }
      }
    }
  }

  override update(time: number, delta: number): void {
    const dt = Math.min(delta / 1000, 0.05);
    if (this.showWorm) this.worm.hold(dt, time);
    this.fx.update(dt);
    if (this.shownCoins !== state.coins) this.drawCoins(this.coinRight);
  }

  private cleanup(): void {
    this.scale.off('resize', this.onResize);
    window.removeEventListener('keydown', this.onKey);
    this.worm.destroy();
    state.shopOpen = false;
  }
}

function compactSize(cssH: number, small: number, big: number): number {
  return cssH < 440 ? small : big;
}
