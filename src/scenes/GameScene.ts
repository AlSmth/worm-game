import Phaser from 'phaser';
import { Worm, type Steer } from '../game/Worm';
import { PreySystem, type PreyItem, type View } from '../game/Prey';
import { WorldBackground } from '../game/Background';
import { Fx } from '../game/Fx';
import { controls } from '../core/controls';
import { sfx } from '../core/audio';
import { hideLoader } from '../core/loader';
import { state, hitsUi, showToast } from '../core/state';
import { platform } from '../platform/platform';
import { save } from '../platform/save';
import { MAX_TIER, growthFor, growthNeeded, segmentsAt, wormScale } from '../data/growth';
import { clampLevel, type Upgrades } from '../data/upgrades';
import { SURFACE_TIER, WORLD_WIDTH } from '../data/world';
import type { SkinId } from '../data/skins';
import { mountDevPanel, type DevApi } from '../dev/devPanel';

/** Сколько px мира видно при масштабе червя 1: не меньше, чем по высоте, и не меньше, чем по ширине (узкие окна). */
const BASE_VIEW_H = 900;
const BASE_VIEW_W = 1100;
const NO_STEER: Steer = { mode: 'none', tx: 0, ty: 0, dx: 0, dy: 0 };
const DIRT = [0x6b4a32, 0x8a5a3a, 0x4a2f1f];
const STARS = [0xffd23f, 0xffffff, 0xff9a2e];

export class GameScene extends Phaser.Scene {
  worm!: Worm;
  prey!: PreySystem;
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
    state.paused = false;

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
    this.updateCamera(0, true);
    this.prey.populate(0, this.worm.y, S0, this.view(), this.worm.canExit);

    this.setupInput();
    platform.onPause((p) => this.onPlatformPause(p));

    this.scene.launch('UI');
    // Игрок может начинать: сообщаем платформе (пп. 1.19.2, 1.19.3)
    platform.gameplay(true);
    platform.ready();
    hideLoader();
    if (import.meta.env.DEV) this.installDev();
  }

  // ---------- ввод ----------
  private setupInput(): void {
    this.input.addPointer(2);
    const onPointer = (p: Phaser.Input.Pointer, down: boolean) => {
      if (down) sfx.unlock();
      if (hitsUi(p.x, p.y)) return;
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

  /** Автопилот для проверки и показа: плывёт к ближайшей съедобной добыче. */
  private autoSteer(): Steer {
    const w = this.worm;
    let best: PreyItem | null = null;
    let bd = Infinity;
    for (const it of this.prey.items) {
      if (it.dying || !this.prey.isEdible(it, w.mouthRadius * 0.95)) continue;
      const dd = Math.hypot(it.x - w.x, it.y - w.y);
      if (dd < bd) {
        bd = dd;
        best = it;
      }
    }
    if (best) return { mode: 'target', tx: best.x, ty: best.y, dx: 0, dy: 0 };
    return { mode: 'target', tx: w.x + 400, ty: w.y + 60, dx: 0, dy: 0 };
  }

  // ---------- шаг ----------
  override update(time: number, delta: number): void {
    if (state.paused) return;
    const dt = Math.min(delta / 1000, 0.05);
    const w = this.worm;
    w.canExit = state.tier >= SURFACE_TIER;
    w.update(dt, this.readSteer(), time);
    this.prey.update(dt, time / 1000, w.x, w.y, w.scale, this.view(), w.canExit);
    this.checkEating(time);
    this.updateCamera(dt, false);
    this.bg.update(this.cameras.main, w.scale);
    this.fx.update(dt);
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
    const minC = -WORLD_WIDTH / 2 + visW * 0.42;
    const maxC = WORLD_WIDTH / 2 - visW * 0.42;
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
    for (const it of this.prey.items) {
      if (it.dying || !this.prey.isEdible(it, mr)) continue;
      const dx = it.x - m.x;
      const dy = it.y - m.y;
      const d2 = dx * dx + dy * dy;
      const reach = mr + it.r * 0.5;
      if (d2 < reach * reach) {
        this.eat(it, m, now);
        continue;
      }
      const look = mr * 3 + it.r;
      if (d2 < look * look && dx * hx + dy * hy > 0) near = true;
    }
    w.setHint(near ? 'open' : 'idle');
  }

  private eat(it: PreyItem, m: { x: number; y: number }, now: number): void {
    const w = this.worm;
    sfx.play('eat');
    w.flash('chomp', 150, now);
    this.fx.burst(m.x, m.y, w.scale, { count: 8, tex: 'fx-star', colors: STARS, speed: 380, life: 0.5, gravity: 900, size: 22 });
    this.prey.consume(it, m.x, m.y);
    this.eaten++;
    this.addGrowth(growthFor(it.r, w.scale));
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
    if (up) this.tierUp();
    // поверхность открывается при пересечении порога, даже если одним укусом перескочили через тир
    if (tierBefore < SURFACE_TIER && state.tier >= SURFACE_TIER) this.surfaceUnlocked();
  }

  /** Червь упёрся в «корку» под травой: подсказываем, что выход откроется с ростом (не чаще раза в несколько секунд). */
  private onBump(): void {
    const now = this.time.now;
    if (now - this.lastBump < 6000) return;
    this.lastBump = now;
    showToast('hint_locked', 3.5);
  }

  private tierUp(): void {
    const w = this.worm;
    sfx.play('grow');
    w.flash('happy', 900, this.time.now);
    this.fx.ring(w.x, w.y, w.scale);
    this.fx.burst(w.x, w.y, w.scale, { count: 18, tex: 'fx-star', colors: STARS, speed: 520, life: 0.8, gravity: 700, size: 26 });
  }

  /** Выход на поверхность открылся: сигнал, подсказка и заметный отъезд камеры. */
  private surfaceUnlocked(): void {
    const w = this.worm;
    showToast('hint_unlocked', 6);
    this.camKick = 0.16;
    this.time.delayedCall(260, () => sfx.play('grow'));
    this.fx.ring(w.x, w.y, w.scale * 1.4, 0x7bd957);
    this.fx.burst(w.x, w.y, w.scale, { count: 26, tex: 'fx-star', colors: STARS, speed: 640, life: 1.0, gravity: 600, size: 30 });
  }

  // ---------- поверхность ----------
  private onExit(): void {
    const w = this.worm;
    sfx.play('jump');
    this.fx.burst(w.x, 0, w.scale, { count: 12, tex: 'fx-dot', colors: DIRT, speed: 420, life: 0.7, gravity: 1500, size: 16 });
  }

  private onEnter(): void {
    const w = this.worm;
    sfx.play('splash');
    this.fx.burst(w.x, 0, w.scale, { count: 14, tex: 'fx-dot', colors: DIRT, speed: 360, life: 0.7, gravity: 1500, size: 16 });
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
        eaten: this.eaten,
        inAir: this.worm.inAir,
        x: Math.round(this.worm.x),
        y: Math.round(this.worm.y),
        prey: this.prey.items.length,
        fps: Math.round(this.game.loop.actualFps),
        paused: state.paused,
        zoom: Math.round(this.cameras.main.zoom * 1000) / 1000,
        canvasW: this.game.canvas.width,
        canvasH: this.game.canvas.height,
        audio: sfx.contextState,
        canExit: this.worm.canExit,
        toast: state.toast.left > 0 ? state.toast.key : null,
        jaw: Math.round(this.worm.jaw * 100) / 100,
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
      },
      autopilot: (on) => {
        this.autopilot = on;
      },
      setPos: (x, y) => {
        this.worm.reset(x, y, this.worm.heading);
        this.camReady = false;
      },
      world: () => ({ width: WORLD_WIDTH, surfaceTier: SURFACE_TIER }),
      resetSave: () => {
        save.reset();
        window.location.reload();
      },
    };
    (window as unknown as { __dev: DevApi & { scene: GameScene } }).__dev = Object.assign(api, { scene: this });
    mountDevPanel(api);
  }
}
