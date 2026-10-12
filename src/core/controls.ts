/**
 * Клавиатура: читаем физический код клавиши (event.code), поэтому раскладка не важна (п. 1.6.2.4).
 * Системные сочетания (Ctrl, Alt, Cmd) не перехватываем (п. 1.6.2.6).
 */
const PREVENT = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space']);

type KeyHandler = () => void;

class Controls {
  private down = new Set<string>();
  private handlers = new Map<string, KeyHandler[]>();

  constructor() {
    window.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (PREVENT.has(e.code)) e.preventDefault();
      if (!this.down.has(e.code)) this.handlers.get(e.code)?.forEach((h) => h());
      this.down.add(e.code);
    });
    window.addEventListener('keyup', (e) => this.down.delete(e.code));
    window.addEventListener('blur', () => this.down.clear());
    document.addEventListener('visibilitychange', () => this.down.clear());
  }

  /** Однократное нажатие клавиши. */
  onKey(code: string, handler: KeyHandler): void {
    const list = this.handlers.get(code) ?? [];
    list.push(handler);
    this.handlers.set(code, list);
  }

  /** Направление со стрелок и WASD или null, если ничего не нажато. */
  get dir(): { x: number; y: number } | null {
    const d = this.down;
    const x = (d.has('ArrowRight') || d.has('KeyD') ? 1 : 0) - (d.has('ArrowLeft') || d.has('KeyA') ? 1 : 0);
    const y = (d.has('ArrowDown') || d.has('KeyS') ? 1 : 0) - (d.has('ArrowUp') || d.has('KeyW') ? 1 : 0);
    return x || y ? { x, y } : null;
  }
}

export const controls = new Controls();
