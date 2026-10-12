/**
 * Звук: все эффекты синтезируются в коде через Web Audio API (п. 1.6.1.6 / 1.6.2.5: без <audio> и <video>,
 * чтобы не появлялся системный плеер; заодно нет файлов и вопросов лицензии).
 */

export type SfxName = 'eat' | 'chomp' | 'grow' | 'jump' | 'splash' | 'ui' | 'coin';

type AudioCtor = typeof AudioContext;

function makeNoise(ctx: AudioContext): AudioBuffer {
  const len = Math.floor(ctx.sampleRate * 0.6);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  return buf;
}

class Sfx {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  private muted = false;
  private paused = false;

  /** Вызывать из обработчика жеста игрока (клик, касание, клавиша): иначе браузер не даёт запустить звук. */
  unlock(): void {
    if (!this.ctx) {
      const AC: AudioCtor | undefined = window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
      if (!AC) return;
      try {
        this.ctx = new AC();
      } catch {
        return;
      }
      this.master = this.ctx.createGain();
      this.master.connect(this.ctx.destination);
      this.noise = makeNoise(this.ctx);
    }
    this.apply();
  }

  setMuted(m: boolean): void {
    this.muted = m;
    this.apply();
  }

  /** Пауза платформы (реклама, смена вкладки): звук полностью останавливаем (пп. 1.3, 4.7). */
  setPaused(p: boolean): void {
    this.paused = p;
    this.apply();
  }

  get isMuted(): boolean {
    return this.muted;
  }

  /** Состояние звукового контекста: none (ещё не запускали), running, suspended. Для проверок. */
  get contextState(): string {
    return this.ctx ? this.ctx.state : 'none';
  }

  private apply(): void {
    if (!this.ctx || !this.master) return;
    const on = !this.muted && !this.paused;
    this.master.gain.value = on ? 0.55 : 0;
    if (on) void this.ctx.resume?.();
    else void this.ctx.suspend?.();
  }

  private tone(freq: number, dur: number, type: OscillatorType, vol: number, slideTo?: number, delay = 0): void {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime + delay;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t0);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g);
    g.connect(this.master!);
    o.start(t0);
    o.stop(t0 + dur + 0.03);
  }

  private burst(dur: number, lo: number, hi: number, vol: number, delay = 0): void {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime + delay;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    const f = ctx.createBiquadFilter();
    f.type = 'bandpass';
    f.Q.value = 1.2;
    f.frequency.setValueAtTime(lo, t0);
    f.frequency.exponentialRampToValueAtTime(hi, t0 + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(f);
    f.connect(g);
    g.connect(this.master!);
    src.start(t0);
    src.stop(t0 + dur + 0.03);
  }

  play(name: SfxName): void {
    if (!this.ctx || !this.master || this.muted || this.paused) return;
    switch (name) {
      case 'eat':
        this.tone(520, 0.1, 'sine', 0.5, 180);
        this.burst(0.08, 900, 300, 0.25);
        break;
      case 'chomp':
        this.burst(0.05, 1200, 600, 0.3);
        this.tone(220, 0.06, 'square', 0.1);
        break;
      case 'grow':
        [440, 554, 659, 880].forEach((f, i) => this.tone(f, 0.16, 'triangle', 0.35, undefined, i * 0.08));
        break;
      case 'jump':
        this.burst(0.28, 300, 1600, 0.3);
        break;
      case 'splash':
        this.burst(0.16, 600, 120, 0.35);
        this.tone(110, 0.14, 'sine', 0.25, 60);
        break;
      case 'ui':
        this.tone(740, 0.05, 'square', 0.14);
        break;
      case 'coin':
        this.tone(988, 0.07, 'square', 0.2);
        this.tone(1319, 0.14, 'square', 0.2, undefined, 0.07);
        break;
    }
  }
}

export const sfx = new Sfx();
