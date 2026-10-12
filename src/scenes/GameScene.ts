import Phaser from 'phaser';
import { Worm, type Steer } from '../game/Worm';
import { PreySystem, type PreyItem, type View } from '../game/Prey';
import { TreasureSystem, type TreasureItem } from '../game/Treasure';
import { SurfaceSystem, type SurfaceItem, type WormInfo, type BodyCircle } from '../game/Surface';
import { Challenges, type ChallengeDone } from '../game/Challenges';
import type { ChallengeKind } from '../data/challenges';
import { WorldBackground } from '../game/Background';
import { Fx } from '../game/Fx';
import { controls } from '../core/controls';
import { sfx } from '../core/audio';
import { hideLoader } from '../core/loader';
import { state, hitsUi, showToast } from '../core/state';
import { platform } from '../platform/platform';
import { save, TUTORIAL_COIN, TUTORIAL_EAT, TUTORIAL_GUARD, TUTORIAL_SURFACE, TUTORIAL_WINGS } from '../platform/save';
import { MAX_TIER, econScale, growthFor, growthNeeded, segmentsAt, wormScale } from '../data/growth';
import { clampLevel, type LineId, type Upgrades } from '../data/upgrades';
import { SURFACE_TIER, WORLD_WIDTH, worldHalf } from '../data/world';
import { HIT_GRACE, HP_REGEN, RESPAWN_GRACE, SOIL_GROWTH_FACTOR, maxHp, type SurfaceKind } from '../data/surface';
import type { SkinId } from '../data/skins';
import { mountDevPanel, type DevApi } from '../dev/devPanel';

/** Сколько px мира видно при масштабе червя 1: не меньше, чем по высоте, и не меньше, чем по ширине (узкие окна). */
const BASE_VIEW_H = 900;
const BASE_VIEW_W = 1100;
const NO_STEER: Steer = { mode: 'none', tx: 0, ty: 0, dx: 0, dy: 0 };
const DIRT = [0x6b4a32, 0x8a5a3a, 0x4a2f1f, 0xa07048];
const STARS = [0xffd23f, 0xffffff, 0xff9a2e];
const GOLD = [0xffd23f, 0xffffff, 0xffe27a];

export class GameScene extends Phaser.Scene {
  worm!: Worm;
  prey!: PreySystem;
  treasure!: TreasureSystem;
  surface!: SurfaceSystem;
  private bg!: WorldBackground;
  private fx!: Fx;
  private pointerActive = false;
  private pointer = { x: 0, y: 0 };
  private eaten = 0;
  private autopilot = false;
  private camReady = false;
  /** Кратковременный отъезд камеры при открытии поверхности (доля, плавно спадает). */
  private camKick = 0;
  private lastBump = -1e9;
  /** Первый запуск: сначала экран выбора персонажа, потом игра. */
  private firstRun = false;
  private digT = 0;
  private tutArrow!: Phaser.GameObjects.Image;
  private coinHinted = false;
  /** Испытания (концепт, раздел 10): прогресс копится здесь, в сохранении лежит список. */
  quests = new Challenges();
  /** Самая большая высота над землёй за текущий прыжок, px мира. */
  private maxHeight = 0;
  private tailT = 0;
  /** Неуязвимость после попадания и возрождения, с. */
  private hpGrace = 0;
  private stars: Phaser.GameObjects.Image[] = [];
  private circles: BodyCircle[] = [];
  /** Для проверок: червь стоит на месте (как оглушённый), но игра идёт. */
  private freeze = false;

  constructor() {
    super('Game');
  }

  create(): void {
    const d = save.data;
    this.cameras.main.setBackgroundColor(0x3f9cff);
    this.bg = new WorldBackground(this);
    this.fx = new Fx(this);

    state.tier = d.tier;
    state.growth = d.growth;
    state.need = growthNeeded(d.tier);
    state.coins = d.coins;
    state.paused = false;
    state.selecting = false;
    state.shopOpen = false;
    state.hpMax = maxHp(d.up.hp);
    state.hp = state.hpMax;
    state.hpFlash = 0;
    state.stunned = false;
    state.stunShown = false;
    if (this.quests.load(d.ch, d.tier)) save.patch({ ch: this.quests.list });

    const tf = this.fractionalTier();
    const S0 = wormScale(tf);
    this.worm = new Worm(this, d.skin, 0, 260 * S0);
    this.worm.setUpgrades(d.up);
    this.worm.setSize(S0, segmentsAt(tf));
    this.worm.scale = S0;
    this.worm.reset(0, 260 * S0, 0);
    this.worm.onExit = () => this.onExit();
    this.worm.onEnter = () => this.onEnter();
    this.worm.onBump = () => this.onBump();
    this.worm.canExit = state.tier >= SURFACE_TIER;

    this.prey = new PreySystem(this);
    this.treasure = new TreasureSystem(this, (x, y) => this.glint(x, y));
    this.tutArrow = this.add.image(0, 0, 'fx', 'fx-arrow').setDepth(600).setVisible(false);
    this.updateCamera(0, true);
    this.surface = new SurfaceSystem(this, {
      onShoot: (x, y, len, ang) => this.onRocketLaunch(x, y, len, ang),
      onTrail: (x, y, len) => this.onRocketTrail(x, y, len),
      onExplode: (x, y, len, dmg, direct) => this.onRocketBoom(x, y, len, dmg, direct),
    });
    this.prey.populate(0, this.worm.y, S0, this.view(), state.tier);
    this.treasure.populate(0, this.worm.y, S0, this.view());
    this.surface.populate(0, S0, this.view(), state.tier);

    this.setupInput();
    platform.onPause((p) => this.onPlatformPause(p));
    this.game.events.on('skin-chosen', (id: SkinId) => this.onSkinChosen(id));
    this.game.events.on('open-select', () => this.openSelect(false));
    this.game.events.on('open-shop', () => this.openShop());
    this.game.events.on('upgrade-bought', (line: LineId, level: number) => {
      this.worm.setUpgrades(save.data.up);
      if (line === 'hp') {
        // броня прибавляет запас здоровья и сразу лечит на прибавку
        const old = state.hpMax;
        state.hpMax = maxHp(level);
        state.hp = Math.min(state.hpMax, state.hp + (state.hpMax - old));
      }
    });
    this.game.events.on('respawn', () => this.respawn());
    this.game.events.on('shop-closed', (bought: boolean) => this.onShopClosed(bought));

    this.scene.launch('UI');
    // Игрок может начинать: сообщаем платформе (пп. 1.19.2, 1.19.3). При первом запуске это экран выбора персонажа.
    this.firstRun = !d.skinChosen;
    if (this.firstRun) this.openSelect(true);
    else platform.gameplay(true);
    platform.ready();
    hideLoader();
    if (import.meta.env.DEV) this.installDev();
  }

  // ---------- выбор персонажа ----------
  private openSelect(first: boolean): void {
    if (state.selecting) return;
    state.selecting = true;
    platform.gameplay(false);
    this.scene.launch('Select', { first });
    this.scene.bringToTop('Select');
  }

  // ---------- магазин ----------
  private openShop(): void {
    if (state.selecting || state.shopOpen || state.paused || state.stunned) return;
    state.shopOpen = true;
    platform.gameplay(false);
    this.scene.launch('Shop');
    this.scene.bringToTop('Shop');
  }

  /** Магазин закрыт: игра продолжается; после покупки червь «вспыхивает» новой деталью. */
  private onShopClosed(bought: boolean): void {
    platform.gameplay(true);
    if (!bought) return;
    const w = this.worm;
    this.fx.ring(w.x, w.y, w.scale * 1.3, 0xffd23f);
    this.fx.burst(w.x, w.y, w.scale, { count: 20, frame: 'fx-star', colors: STARS, speed: 520, life: 0.9, gravity: 600, size: 28 });
    w.flash('happy', 900, this.time.now);
    sfx.play('grow');
  }

  private onSkinChosen(id: SkinId): void {
    this.worm.setSkin(id);
    if (this.firstRun) {
      this.firstRun = false;
      platform.gameplay(true);
      showToast('story_intro', 5);
    }
  }

  // ---------- ввод ----------
  private setupInput(): void {
    this.input.addPointer(2);
    const onPointer = (p: Phaser.Input.Pointer, down: boolean) => {
      if (down) sfx.unlock();
      if (state.selecting || state.shopOpen || hitsUi(p.x, p.y)) return;
      if (p.wasTouch && !p.isDown) return;
      this.pointerActive = true;
      this.pointer.x = p.x;
      this.pointer.y = p.y;
    };
    this.input.on('pointerdown', (p: Phaser.Input.Pointer) => onPointer(p, true));
    this.input.on('pointermove', (p: Phaser.Input.Pointer) => onPointer(p, false));
    const release = (p: Phaser.Input.Pointer) => {
      if (p.wasTouch) this.pointerActive = false;
    };
    this.input.on('pointerup', release);
    this.input.on('pointerupoutside', release);
    // первое нажатие клавиши тоже «открывает» звук
    window.addEventListener('keydown', () => sfx.unlock(), { once: true });
  }

  private readSteer(): Steer {
    const k = controls.dir;
    if (k) return { mode: 'dir', dx: k.x, dy: k.y, tx: 0, ty: 0 };
    if (this.autopilot) return this.autoSteer();
    if (this.pointerActive) {
      const w = this.cameras.main.getWorldPoint(this.pointer.x, this.pointer.y);
      return { mode: 'target', tx: w.x, ty: w.y, dx: 0, dy: 0 };
    }
    return NO_STEER;
  }

  /** Автопилот для проверки и показа: плывёт к ближайшей съедобной добыче, на поверхности прыгает за людьми; при малом здоровье ныряет. */
  private autoSteer(): Steer {
    const w = this.worm;
    // здоровье на исходе: прочь под землю, там оно восстанавливается
    if (w.canExit && state.hp < state.hpMax * 0.45) return { mode: 'target', tx: w.x + 300, ty: w.y + 900 * w.scale, dx: 0, dy: 0 };
    let tx = w.x + 400;
    let ty = w.y + 60;
    let bd = Infinity;
    for (const it of this.prey.items) {
      if (it.dying || !this.prey.isEdible(it, w.mouthRadius * 0.95)) continue;
      const dd = Math.hypot(it.x - w.x, it.y - w.y);
      if (dd < bd) {
        bd = dd;
        tx = it.x;
        ty = it.y;
      }
    }
    if (w.canExit) {
      // добычу на поверхности предпочитаем: с неё идёт рост
      for (const it of this.surface.items) {
        if (it.dying || !this.surface.isEdible(it, w.mouthRadius * 0.95)) continue;
        const dd = Math.hypot(it.x - w.x, it.cy - w.y) * 0.5;
        if (dd < bd) {
          bd = dd;
          tx = it.x;
          ty = it.cy;
        }
      }
    }
    return { mode: 'target', tx, ty, dx: 0, dy: 0 };
  }

  // ---------- шаг ----------
  override update(time: number, delta: number): void {
    if (state.paused || state.selecting || state.shopOpen) return;
    if (state.stunShown) {
      // окно «Заново» открыто: игра стоит, звёздочки над головой продолжают кружить
      this.updateStars(time);
      return;
    }
    const dt = Math.min(delta / 1000, 0.05);
    const w = this.worm;
    w.canExit = state.tier >= SURFACE_TIER;
    w.stunned = state.stunned || this.freeze;
    w.update(dt, w.stunned ? NO_STEER : this.readSteer(), time);
    const view = this.view();
    this.prey.update(dt, time / 1000, w.x, w.y, w.scale, view, state.tier, w.mouthRadius);
    this.treasure.econ = econScale(state.tier);
    this.treasure.update(dt, time / 1000, w.x, w.y, w.scale, view, w.mouthRadius);
    this.updateSurface(dt, time, view);
    if (!state.stunned) this.checkEating(time);
    this.dig(dt);
    this.updateTutorial(time);
    this.updateTrail(dt);
    this.trackJump();
    this.updateCamera(dt, false);
    this.bg.update(this.cameras.main, w.scale);
    this.fx.update(dt);
    this.updateStars(time);
  }

  private view(): View {
    const c = this.cameras.main;
    return { w: c.width / c.zoom, h: c.height / c.zoom };
  }

  private updateCamera(dt: number, snap: boolean): void {
    const cam = this.cameras.main;
    const w = this.worm;
    const S = w.scale;
    const viewH = BASE_VIEW_H * Math.pow(S, 0.85);
    const viewW = BASE_VIEW_W * Math.pow(S, 0.85);
    this.camKick = Math.max(0, this.camKick - dt * 0.12);
    const targetZoom = Math.min(cam.height / viewH, cam.width / viewW) * (1 - this.camKick);
    if (snap || !this.camReady) cam.setZoom(targetZoom);
    else cam.setZoom(cam.zoom + (targetZoom - cam.zoom) * Math.min(1, 3 * dt));
    // камера не показывает пустоту за стенами карты: у края останавливается, оставляя видимой полосу стены
    const visW = cam.width / cam.zoom;
    const half = worldHalf(S);
    const minC = -half + visW * 0.42;
    const maxC = half - visW * 0.42;
    const rawX = w.x + w.vx * 0.22;
    const cx = minC < maxC ? Math.max(minC, Math.min(maxC, rawX)) : 0;
    const cy = w.y + w.vy * 0.12 - viewH * 0.06;
    const tx = cx - cam.width / 2;
    const ty = cy - cam.height / 2;
    if (snap || !this.camReady) {
      cam.scrollX = tx;
      cam.scrollY = ty;
    } else {
      const k = Math.min(1, 7 * dt);
      cam.scrollX += (tx - cam.scrollX) * k;
      cam.scrollY += (ty - cam.scrollY) * k;
    }
    this.camReady = true;
  }

  // ---------- охота ----------
  private checkEating(now: number): void {
    const w = this.worm;
    const m = w.mouth();
    const mr = w.mouthRadius;
    const hx = Math.cos(w.heading);
    const hy = Math.sin(w.heading);
    let near = false;
    const consider = (x: number, y: number, r: number): 'eat' | 'near' | null => {
      const dx = x - m.x;
      const dy = y - m.y;
      const d2 = dx * dx + dy * dy;
      const reach = mr + r * 0.5;
      if (d2 < reach * reach) return 'eat';
      const look = mr * 3 + r;
      return d2 < look * look && dx * hx + dy * hy > 0 ? 'near' : null;
    };
    for (const it of this.prey.items) {
      if (it.dying || !this.prey.isEdible(it, mr)) continue;
      const c = consider(it.x, it.y, it.r);
      if (c === 'eat') this.eat(it, m, now);
      else if (c === 'near') near = true;
    }
    for (const tr of this.treasure.items) {
      if (tr.dying || !this.treasure.isEdible(tr, mr)) continue;
      const c = consider(tr.x, tr.y, tr.r);
      if (c === 'eat') this.eatTreasure(tr, m, now);
      else if (c === 'near') near = true;
    }
    // добыча над землёй: кусать можно, только когда пасть над землёй (под землёй червь её не достаёт)
    if (w.canExit && m.y < -8) {
      for (const it of this.surface.items) {
        if (it.dying || !this.surface.isEdible(it, mr)) continue;
        const c = consider(it.x, it.cy, it.r);
        if (c === 'eat') this.eatSurface(it, m, now);
        else if (c === 'near') near = true;
      }
    }
    w.setHint(near ? 'open' : 'idle');
  }

  private eat(it: PreyItem, m: { x: number; y: number }, now: number): void {
    const w = this.worm;
    sfx.play('eat');
    w.flash('chomp', 150, now);
    w.gulp(0.09 + Math.min(0.12, it.r / (w.mouthRadius * 9)));
    this.fx.pop(m.x, m.y, 1, Math.max(110, it.r * 2.4));
    this.fx.burst(m.x, m.y, w.scale, { count: 7, frame: 'fx-star', colors: STARS, speed: 380, life: 0.5, gravity: 900, size: 22 });
    this.prey.consume(it, m.x, m.y);
    this.eaten++;
    this.quest('eat', 1);
    this.quest(it.species, 1);
    this.addGrowth(growthFor(it.r) * (state.tier >= SURFACE_TIER ? SOIL_GROWTH_FACTOR : 1));
    this.markEaten();
  }

  private markEaten(): void {
    if (!(save.data.tutorial & TUTORIAL_EAT)) {
      save.patch({ tutorial: save.data.tutorial | TUTORIAL_EAT });
      showToast('tut_good', 3.5);
    }
  }

  /** Добыча над землёй съедена: люди, машины, дома, техника охраны. Большое сопровождается облаком пыли. */
  private eatSurface(it: SurfaceItem, m: { x: number; y: number }, now: number): void {
    const w = this.worm;
    const big = it.r > w.mouthRadius * 0.45;
    sfx.play(big ? 'chest' : 'eat');
    w.flash('chomp', 180, now);
    w.gulp(0.1 + Math.min(0.14, it.r / (w.mouthRadius * 7)));
    this.fx.pop(m.x, m.y, 1, Math.max(120 * w.scale, Math.min(it.r * 1.8, w.mouthRadius * 2.6)));
    this.fx.burst(m.x, m.y, w.scale, { count: big ? 12 : 7, frame: 'fx-star', colors: STARS, speed: 420, life: 0.6, gravity: 900, size: big ? 28 : 22 });
    this.fx.burst(it.x, it.cy, 1, { count: big ? 5 : 2, frame: 'fx-dust-poof', colors: [0xf0d9b5], speed: 220, life: 0.8, gravity: 0, size: Math.max(70, it.w * 0.45) });
    this.surface.consume(it, m.x, m.y);
    this.eaten++;
    this.quest('eat', 1);
    const k = it.spec.kind;
    if (k === 'person') this.quest('people', 1);
    else if (k === 'car' || k === 'truck' || k === 'bus') this.quest('cars', 1);
    else if (k === 'patrol' || k === 'heavy') this.quest('guards', 1);
    else this.quest('buildings', 1);
    this.addGrowth(it.spec.points);
    this.markEaten();
    // крупная добыча приносит монеты (люди нет): ценность растёт с тиром, как у сокровищ
    const coins = Math.round(it.spec.coins * econScale(state.tier));
    if (coins > 0) {
      state.coins += coins;
      save.patch({ coins: state.coins });
      this.quest('coins', coins);
      this.fx.floatText(m.x, m.y - 40 * w.scale, w.scale, `+${coins}`);
    }
  }

  /** Сокровище съедено: монеты на счёт, искры, всплывающее число. */
  private eatTreasure(tr: TreasureItem, m: { x: number; y: number }, now: number): void {
    const w = this.worm;
    sfx.play(tr.spec.kind === 'coin' ? 'coin' : tr.spec.kind === 'gem' ? 'gem' : 'chest');
    w.flash('happy', 380, now);
    w.gulp(0.08);
    this.fx.pop(m.x, m.y, 1, Math.max(100, tr.r * 2.6), 0xffe27a);
    this.fx.burst(m.x, m.y, w.scale, {
      count: tr.spec.kind === 'coin' ? 6 : 14,
      frame: 'fx-coin-sparkle',
      colors: GOLD,
      speed: 460,
      life: 0.7,
      gravity: 500,
      size: 34,
    });
    this.fx.floatText(m.x, m.y - 40 * w.scale, w.scale, `+${tr.value}`);
    this.treasure.consume(tr, m.x, m.y);
    state.coins += tr.value;
    save.patch({ coins: state.coins });
    if (!(save.data.tutorial & TUTORIAL_COIN)) save.patch({ tutorial: save.data.tutorial | TUTORIAL_COIN });
    this.quest('coins', tr.value);
    if (tr.spec.kind === 'gem') this.quest('gems', 1);
    else if (tr.spec.kind === 'chestSmall' || tr.spec.kind === 'chestBig') this.quest('chests', 1);
  }

  /** Блеск на сокровище: крохотная искра, чтобы оно привлекало взгляд. */
  private glint(x: number, y: number): void {
    this.fx.burst(x, y, 1, { count: 1, frame: 'fx-coin-sparkle', colors: [0xffffff, 0xffe27a], speed: 6, life: 0.55, gravity: 0, size: 30 });
  }

  /** Комочки земли из-под головы, пока червь роет: ощущение подземного движения. */
  private dig(dt: number): void {
    const w = this.worm;
    this.digT -= dt;
    if (this.digT > 0 || w.inAir || w.y < 50 * w.scale || w.speed < 0.3 * w.swimSpeed) return;
    this.digT = 0.07 + Math.random() * 0.06;
    const m = w.mouth();
    this.fx.burst(m.x, m.y, w.scale, { count: 1, frame: 'fx-dirt-chunk', colors: DIRT, speed: 200, life: 0.55, gravity: 1000, size: 16 });
  }

  private fractionalTier(): number {
    return state.tier + Math.min(1, state.growth / state.need);
  }

  private applySize(): void {
    const tf = this.fractionalTier();
    this.worm.setSize(wormScale(tf), segmentsAt(tf));
  }

  private addGrowth(points: number): void {
    state.growth += points;
    const tierBefore = state.tier;
    let up = false;
    while (state.growth >= state.need && state.tier < MAX_TIER) {
      state.growth -= state.need;
      state.tier++;
      state.need = growthNeeded(state.tier);
      up = true;
    }
    if (state.tier >= MAX_TIER) state.growth = Math.min(state.growth, state.need);
    save.patch({ tier: state.tier, growth: state.growth });
    this.applySize();
    if (up) {
      this.tierUp();
      this.finishChallenges(this.quests.reportTier(state.tier));
    }
    // поверхность открывается при пересечении порога, даже если одним укусом перескочили через тир
    if (tierBefore < SURFACE_TIER && state.tier >= SURFACE_TIER) this.surfaceUnlocked();
  }

  /** Червь упёрся в «корку» под травой: подсказываем, что выход откроется с ростом (не чаще раза в несколько секунд). */
  private onBump(): void {
    const now = this.time.now;
    if (now - this.lastBump < 6000) return;
    this.lastBump = now;
    sfx.play('bump');
    showToast('hint_locked', 3.5);
  }

  private tierUp(): void {
    const w = this.worm;
    sfx.play('grow');
    w.flash('happy', 900, this.time.now);
    this.fx.ring(w.x, w.y, w.scale);
    this.fx.burst(w.x, w.y, w.scale, { count: 18, frame: 'fx-star', colors: STARS, speed: 520, life: 0.8, gravity: 700, size: 26 });
  }

  /** Выход на поверхность открылся: сигнал, подсказка и заметный отъезд камеры. */
  private surfaceUnlocked(): void {
    const w = this.worm;
    showToast('hint_unlocked', 6);
    this.camKick = 0.16;
    this.time.delayedCall(260, () => sfx.play('grow'));
    this.fx.ring(w.x, w.y, w.scale * 1.4, 0x7bd957);
    this.fx.burst(w.x, w.y, w.scale, { count: 26, frame: 'fx-star', colors: STARS, speed: 640, life: 1.0, gravity: 600, size: 30 });
  }

  // ---------- обучение ----------
  /** Стрелка над целью: сначала ближайшая съедобная добыча, после первой съеденной ближайшее съедобное сокровище. */
  private updateTutorial(now: number): void {
    const t = save.data.tutorial;
    const w = this.worm;
    const view = this.view();
    let target: { x: number; y: number; r: number } | null = null;
    let best = Infinity;
    const pick = (x: number, y: number, r: number) => {
      const d = Math.hypot(x - w.x, y - w.y);
      if (d < best && Math.abs(x - w.x) < view.w * 0.46 && Math.abs(y - w.y) < view.h * 0.42) {
        best = d;
        target = { x, y, r };
      }
    };
    if (!(t & TUTORIAL_EAT)) {
      for (const it of this.prey.items) if (!it.dying && this.prey.isEdible(it, w.mouthRadius)) pick(it.x, it.y, it.r);
    } else if (!(t & TUTORIAL_COIN)) {
      for (const tr of this.treasure.items) if (!tr.dying && this.treasure.isEdible(tr, w.mouthRadius)) pick(tr.x, tr.y, tr.r);
      // подсказку про монеты показываем, когда предыдущее сообщение (например «Отлично!») уже закончилось
      if (target && !this.coinHinted && state.toast.left <= 0) {
        this.coinHinted = true;
        showToast('tut_coin', 4.5);
      }
    }
    const tg = target as { x: number; y: number; r: number } | null;
    if (!tg) {
      if (this.tutArrow.visible) this.tutArrow.setVisible(false);
      return;
    }
    const cam = this.cameras.main;
    const k = 74 / cam.zoom / 64;
    const bob = Math.sin(now / 160) * 10 * k * 2;
    // цель ниже червя: стрелка снизу и смотрит вверх, чтобы не ложиться на его тело
    const below = tg.y > w.y + 60 * w.scale;
    const off = tg.r * 1.35 + 34 * k + bob;
    this.tutArrow.setVisible(true).setScale(k).setRotation(below ? Math.PI : 0).setPosition(tg.x, below ? tg.y + off : tg.y - off);
  }

  // ---------- испытания ----------
  /** Сообщить об событии: прогресс копится, выполненное даёт монеты. */
  private quest(kind: ChallengeKind, amount: number): void {
    this.finishChallenges(this.quests.report(kind, amount, state.tier));
  }

  private finishChallenges(done: ChallengeDone[]): void {
    if (!done.length) {
      save.patch({ ch: this.quests.list });
      return;
    }
    let sum = 0;
    for (const d of done) sum += d.reward;
    state.coins += sum;
    save.patch({ coins: state.coins, ch: this.quests.list });
    sfx.play('quest');
    showToast('ch_done', 4, { n: sum });
    const w = this.worm;
    this.fx.floatText(w.x, w.y - 90 * w.scale, w.scale, `+${sum}`);
    this.fx.burst(w.x, w.y, w.scale, { count: 14, frame: 'fx-coin-sparkle', colors: GOLD, speed: 460, life: 0.8, gravity: 400, size: 32 });
  }

  /** Высота прыжка над землёй: «выпрыгнуть» засчитывается при выходе, тут запоминается наибольшая высота (для проверок). */
  private trackJump(): void {
    const w = this.worm;
    if (w.inAir) this.maxHeight = Math.max(this.maxHeight, -w.y);
    else this.maxHeight = 0;
  }

  /** Линии скорости и золотые искры за хвостом на старших ступенях гребня. */
  private updateTrail(dt: number): void {
    const w = this.worm;
    const lvl = w.upgrades.speed;
    if (lvl < 4 || w.speed < 0.55 * w.swimSpeed) return;
    this.tailT -= dt;
    if (this.tailT > 0) return;
    this.tailT = lvl >= 5 ? 0.05 : 0.07;
    const tp = w.tailPoint();
    const back = tp.a + Math.PI;
    const k = w.scale;
    const spread = (Math.random() - 0.5) * 70 * k;
    const bx = tp.x + Math.cos(back) * 150 * k - Math.sin(back) * spread;
    const by = tp.y + Math.sin(back) * 150 * k + Math.cos(back) * spread;
    this.fx.streak(bx, by, tp.a, k, lvl >= 5 ? 0xffe27a : 0xbdeaff);
    if (lvl >= 5) this.fx.burst(bx, by, k, { count: 1, frame: 'fx-coin-sparkle', colors: GOLD, speed: 90, life: 0.8, gravity: 0, size: 34 });
  }

  // ---------- опасности и здоровье ----------
  /** Шаг поверхности: люди, машины, охрана и снаряды; попадания по червю; лечение под землёй. */
  private updateSurface(dt: number, time: number, view: View): void {
    const w = this.worm;
    this.hpGrace = Math.max(0, this.hpGrace - dt);
    state.hpFlash = Math.max(0, state.hpFlash - dt);
    // круги тела нужны для попаданий ракет: считаем, только пока ракеты в воздухе и червь у поверхности
    const near = this.surface.shots.length > 0 && w.y < w.headRadius * 2 + w.scale * 200;
    const circles: BodyCircle[] = near ? w.hitCircles(this.circles) : [];
    const info: WormInfo = {
      x: w.x, y: w.y, vx: w.vx, vy: w.vy, scale: w.scale,
      exposed: w.y < w.headRadius * 0.7 && !state.stunned,
      scary: w.y < w.headRadius * 2.5,
      circles,
    };
    this.surface.update(dt, info, view, state.tier, w.canExit);
    this.surface.highlight(w.mouthRadius, w.canExit, time / 1000);
    // под землёй червь лечится
    if (!state.stunned && state.hp < state.hpMax && w.y > w.headRadius * 1.1) state.hp = Math.min(state.hpMax, state.hp + HP_REGEN * dt);
    // первая встреча с охраной: предупреждение (один раз, когда нет другого сообщения)
    if (w.canExit && !(save.data.tutorial & TUTORIAL_GUARD) && state.toast.left <= 0) {
      const seen = this.surface.items.some((it) => !it.dying && it.spec.behavior === 'guard' && Math.abs(it.x - w.x) < view.w * 0.6);
      if (seen) {
        save.patch({ tutorial: save.data.tutorial | TUTORIAL_GUARD });
        showToast('hint_guard', 5);
      }
    }
  }

  /** Пуск ракеты: вспышка и облачко у ствола, звук пуска. */
  private onRocketLaunch(x: number, y: number, len: number, ang: number): void {
    sfx.play('launch');
    this.fx.pop(x, y, 1, len * 0.9, 0xffd27a);
    this.fx.burst(x, y, 1, { count: 3, frame: 'fx-dust-poof', colors: [0xf2eee8, 0xd8d2cb], speed: len * 0.9, life: 0.7, gravity: 0, size: len * 0.45 });
    void ang;
  }

  /** Дымный след за ракетой: серые облачка, расползаются и гаснут. */
  private onRocketTrail(x: number, y: number, len: number): void {
    this.fx.burst(x, y, 1, { count: 1, frame: 'fx-dust-poof', colors: [0xeeeae4, 0xcfc9c2], speed: len * 0.1, life: 0.8, gravity: -len * 0.08, size: len * 0.28 });
  }

  /**
   * Взрыв ракеты: огненный шар с дымом и камнями (о землю), встряска. Урон червю: прямое попадание бьёт полностью,
   * а рядом (в радиусе взрыва) наполовину, если червь над землёй или у самой поверхности.
   */
  private onRocketBoom(x: number, y: number, len: number, dmg: number, direct: boolean): void {
    const w = this.worm;
    sfx.play('boom');
    const size = len * 1.5;
    this.fx.boom(x, y - size * 0.12, size);
    this.fx.burst(x, y, 1, { count: 6, frame: 'fx-dirt-chunk', colors: DIRT, speed: len * 1.1, life: 0.8, gravity: len * 2.2, size: len * 0.2 });
    this.fx.burst(x, y - size * 0.2, 1, { count: 3, frame: 'fx-dust-poof', colors: [0x8d857d, 0xb7aea5], speed: len * 0.5, life: 1.0, gravity: -len * 0.2, size: len * 0.7 });
    // чем ближе взрыв к червю, тем сильнее встряска
    const d = Math.hypot(x - w.x, y - w.y);
    if (d < len * 14 + w.scale * 1500) this.cameras.main.shake(180, 0.005);
    if (direct) {
      this.hurt(dmg, x, y);
      return;
    }
    // осколки по ближнему червю: взрыв у самого тела (радиус взрыва ≈ длина ракеты)
    if (w.y < w.headRadius * 2 + w.scale * 200) {
      const cs = w.hitCircles(this.circles);
      const rr = size * 0.5;
      for (const c of cs) {
        if (Math.hypot(x - c.x, y - c.y) < c.r + rr) {
          this.hurt(dmg * 0.5, x, y);
          break;
        }
      }
    }
  }

  /** Попадание снаряда: урон, вспышка, неуязвимость на секунду; здоровье кончилось — червь оглушён. */
  private hurt(dmg: number, x: number, y: number): void {
    if (state.stunned || this.hpGrace > 0) return;
    const w = this.worm;
    state.hp = Math.max(0, state.hp - dmg);
    state.hpFlash = 0.4;
    this.hpGrace = HIT_GRACE;
    sfx.play('hit');
    w.flash('hurt', 700, this.time.now);
    this.cameras.main.shake(150, 0.006);
    this.fx.burst(x, y, w.scale, { count: 9, frame: 'fx-star', colors: [0xffffff, 0xffb347, 0xffd23f], speed: 420, life: 0.5, gravity: 600, size: 22 });
    this.fx.floatText(w.x, w.y - 110 * w.scale, w.scale, `-${Math.round(dmg)}`, '#ff9a8a');
    if (state.hp <= 0) this.stun();
  }

  /** Здоровье кончилось: червь оглушён (звёздочки над головой, без крови), через секунду окно «Заново» (п. 3.4.3). */
  private stun(): void {
    state.stunned = true;
    sfx.play('stun');
    this.worm.flash('hurt', 1e9, this.time.now);
    for (let i = 0; i < 5; i++) {
      this.stars.push(this.add.image(0, 0, 'fx', 'fx-star').setDepth(520).setTint(STARS[i % STARS.length]));
    }
    this.time.delayedCall(1100, () => {
      if (!state.stunned) return;
      state.stunShown = true;
      platform.gameplay(false);
    });
  }

  private updateStars(time: number): void {
    if (!this.stars.length) return;
    const w = this.worm;
    const k = w.scale;
    this.stars.forEach((st, i) => {
      const a = time / 380 + (i * Math.PI * 2) / this.stars.length;
      st.setPosition(w.x + Math.cos(a) * 70 * k, w.y - 105 * k + Math.sin(a) * 18 * k)
        .setScale((34 * k) / 40)
        .setRotation(a)
        .setDepth(Math.sin(a) > 0 ? 520 : 5);
    });
  }

  /** «Заново»: червь возвращается под землю на месте оглушения с полным здоровьем и недолгой неуязвимостью. */
  private respawn(): void {
    if (!state.stunned) return;
    const w = this.worm;
    state.stunned = false;
    state.stunShown = false;
    w.stunned = false;
    this.stars.forEach((st) => st.destroy());
    this.stars = [];
    state.hp = state.hpMax;
    this.hpGrace = RESPAWN_GRACE;
    w.flash('happy', 600, this.time.now);
    w.reset(w.x, 300 * w.scale, 0);
    this.camReady = false;
    this.surface.clearRockets();
    platform.gameplay(true);
    sfx.play('grow');
  }

  // ---------- поверхность ----------
  private onExit(): void {
    const w = this.worm;
    sfx.play('jump');
    this.quest('jump', 1);
    if (!(save.data.tutorial & TUTORIAL_SURFACE)) {
      save.patch({ tutorial: save.data.tutorial | TUTORIAL_SURFACE });
      showToast('hint_surface', 6);
    } else if (w.upgrades.jump > 0 && !(save.data.tutorial & TUTORIAL_WINGS)) {
      save.patch({ tutorial: save.data.tutorial | TUTORIAL_WINGS });
      showToast('hint_wings', 6);
    }
    this.fx.burst(w.x, 0, w.scale, { count: 12, frame: 'fx-dirt-chunk', colors: DIRT, speed: 420, life: 0.7, gravity: 1500, size: 20 });
    this.fx.burst(w.x, 0, w.scale, { count: 3, frame: 'fx-dust-poof', colors: [0xf0d9b5], speed: 200, life: 0.7, gravity: 0, size: 70 });
  }

  private onEnter(): void {
    const w = this.worm;
    sfx.play('splash');
    this.fx.burst(w.x, 0, w.scale, { count: 14, frame: 'fx-dirt-chunk', colors: DIRT, speed: 360, life: 0.7, gravity: 1500, size: 20 });
    this.fx.burst(w.x, 0, w.scale, { count: 3, frame: 'fx-dust-poof', colors: [0xf0d9b5], speed: 200, life: 0.7, gravity: 0, size: 70 });
  }

  // ---------- пауза платформы ----------
  private onPlatformPause(p: boolean): void {
    sfx.setPaused(p);
    if (p) this.scene.pause();
    else this.scene.resume();
  }

  // ---------- dev ----------
  private setUpgrade(line: keyof Upgrades, level: number): void {
    save.patch({ up: { [line]: clampLevel(level) } });
    this.worm.setUpgrades(save.data.up);
    if (line === 'hp') {
      state.hpMax = maxHp(save.data.up.hp);
      state.hp = Math.min(state.hp, state.hpMax);
    }
  }

  private installDev(): void {
    const api: DevApi = {
      state: () => ({
        tier: state.tier,
        growth: Math.round(state.growth * 100) / 100,
        need: state.need,
        scale: Math.round(this.worm.scale * 1000) / 1000,
        segs: Math.floor(this.worm.segs),
        skin: this.worm.getSkin(),
        wings: this.worm.upgrades.jump,
        armor: this.worm.upgrades.hp,
        fins: this.worm.upgrades.speed,
        up: { ...save.data.up },
        hp: Math.round(state.hp * 10) / 10,
        hpMax: state.hpMax,
        stunned: state.stunned,
        stunShown: state.stunShown,
        hpGrace: Math.round(this.hpGrace * 100) / 100,
        surface: this.surface.items.filter((it) => !it.dying).map((it) => it.spec.kind),
        shots: this.surface.shots.length,
        gear: this.worm.gearInfo(),
        shopOpen: state.shopOpen,
        challenges: this.quests.list.map((c) => ({ ...c })),
        maxHeight: Math.round(this.maxHeight),
        eaten: this.eaten,
        inAir: this.worm.inAir,
        x: Math.round(this.worm.x),
        y: Math.round(this.worm.y),
        vx: Math.round(this.worm.vx),
        vy: Math.round(this.worm.vy),
        lift: Math.round(this.worm.lift * 100) / 100,
        prey: this.prey.items.length,
        treasures: this.treasure.items.length,
        coins: state.coins,
        fps: Math.round(this.game.loop.actualFps),
        paused: state.paused,
        selecting: state.selecting,
        zoom: Math.round(this.cameras.main.zoom * 1000) / 1000,
        canvasW: this.game.canvas.width,
        canvasH: this.game.canvas.height,
        audio: sfx.contextState,
        canExit: this.worm.canExit,
        toast: state.toast.left > 0 ? state.toast.key : null,
        jaw: Math.round(this.worm.jaw * 100) / 100,
        tutorial: save.data.tutorial,
      }),
      setSkin: (id: SkinId) => {
        this.worm.setSkin(id);
        save.patch({ skin: id });
      },
      setUpgrade: (line, level) => this.setUpgrade(line, level),
      addGrowth: (n) => this.addGrowth(n),
      setTier: (n) => {
        state.tier = Math.max(1, Math.min(MAX_TIER, Math.round(n)));
        state.growth = 0;
        state.need = growthNeeded(state.tier);
        save.patch({ tier: state.tier, growth: 0 });
        this.applySize();
        // для проверок размер меняется сразу, а не плавно
        this.worm.scale = this.worm.targetScale;
        this.camReady = false;
      },
      autopilot: (on) => {
        this.autopilot = on;
      },
      setPos: (x, y) => {
        this.worm.reset(x, y, this.worm.heading);
        this.camReady = false;
      },
      world: () => ({ width: WORLD_WIDTH, surfaceTier: SURFACE_TIER, half: worldHalf(this.worm.scale) }),
      addCoins: (n) => {
        state.coins = Math.max(0, state.coins + n);
        save.patch({ coins: state.coins });
      },
      openSelect: () => this.openSelect(false),
      openShop: () => this.openShop(),
      placeSurface: (kind: SurfaceKind, x: number) => {
        const it = this.surface.place(kind, x, this.worm.scale);
        (window as unknown as { __test_it?: SurfaceItem }).__test_it = it;
        return { r: it.r, cy: it.cy, w: it.w, h: it.h };
      },
      setHp: (n: number) => {
        state.hp = Math.max(0, Math.min(state.hpMax, n));
      },
      // hit уважает неуязвимость после попадания, hurt её сбрасывает (проверки оглушения)
      hit: (n: number) => this.hurt(n, this.worm.x, this.worm.y),
      hurt: (n: number) => {
        this.hpGrace = 0;
        this.hurt(n, this.worm.x, this.worm.y);
      },
      respawn: () => this.respawn(),
      freeze: (on: boolean) => {
        this.freeze = on;
      },
      reportChallenge: (kind: ChallengeKind, amount: number) => this.quest(kind, amount),
      resetTutorial: () => {
        save.patch({ tutorial: 0 });
        this.coinHinted = false;
      },
      resetSave: () => {
        save.reset();
        window.location.reload();
      },
    };
    (window as unknown as { __dev: DevApi & { scene: GameScene } }).__dev = Object.assign(api, { scene: this });
    mountDevPanel(api);
  }
}
