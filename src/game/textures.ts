import Phaser from 'phaser';

/**
 * Временные текстуры для прототипа, нарисованные кодом: почва, небо, трава и частицы.
 * Настоящие фоны и эффекты заменят их на этапе 3 (design/zone-1-underground/background, design/effects).
 */

function rng(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvasTex(scene: Phaser.Scene, key: string, w: number, h: number): CanvasRenderingContext2D {
  const tex = scene.textures.createCanvas(key, w, h);
  if (!tex) throw new Error('canvas texture: ' + key);
  return tex.getContext();
}

function refresh(scene: Phaser.Scene, key: string): void {
  (scene.textures.get(key) as Phaser.Textures.CanvasTexture).refresh();
}

export function makeTextures(scene: Phaser.Scene): void {
  // --- почва: бесшовный тайл 512×512 ---
  {
    const c = canvasTex(scene, 'bg-soil', 512, 512);
    c.fillStyle = '#6b4a32';
    c.fillRect(0, 0, 512, 512);
    const R = rng(7);
    const wrap = (fn: (dx: number, dy: number) => void) => {
      for (const dx of [-512, 0, 512]) for (const dy of [-512, 0, 512]) fn(dx, dy);
    };
    c.globalAlpha = 0.22;
    for (let i = 0; i < 260; i++) {
      const x = R() * 512, y = R() * 512, r = 14 + R() * 46;
      c.fillStyle = R() < 0.5 ? '#5b3a29' : '#7a5236';
      wrap((dx, dy) => {
        c.beginPath();
        c.arc(x + dx, y + dy, r, 0, Math.PI * 2);
        c.fill();
      });
    }
    c.globalAlpha = 0.35;
    for (let i = 0; i < 500; i++) {
      const x = R() * 512, y = R() * 512, r = 2 + R() * 7;
      c.fillStyle = R() < 0.5 ? '#4a2f1f' : '#8a6a4a';
      wrap((dx, dy) => {
        c.beginPath();
        c.arc(x + dx, y + dy, r, 0, Math.PI * 2);
        c.fill();
      });
    }
    c.globalAlpha = 1;
    c.lineWidth = 3;
    c.strokeStyle = '#3c2418';
    for (let i = 0; i < 70; i++) {
      const x = R() * 512, y = R() * 512, rx = 5 + R() * 12, ry = rx * (0.6 + R() * 0.3);
      c.fillStyle = R() < 0.5 ? '#8f6d4c' : '#7d5d40';
      wrap((dx, dy) => {
        c.beginPath();
        c.ellipse(x + dx, y + dy, rx, ry, R() * 3, 0, Math.PI * 2);
        c.fill();
        c.stroke();
      });
    }
    refresh(scene, 'bg-soil');
  }

  // --- градиент неба у горизонта ---
  {
    const c = canvasTex(scene, 'bg-horizon', 4, 256);
    const g = c.createLinearGradient(0, 0, 0, 256);
    g.addColorStop(0, '#3f9cff');
    g.addColorStop(1, '#d9f2ff');
    c.fillStyle = g;
    c.fillRect(0, 0, 4, 256);
    refresh(scene, 'bg-horizon');
  }

  // --- затемнение с глубиной ---
  {
    const c = canvasTex(scene, 'bg-depth', 4, 256);
    const g = c.createLinearGradient(0, 0, 0, 256);
    g.addColorStop(0, 'rgba(18,8,6,0)');
    g.addColorStop(1, 'rgba(18,8,6,0.9)');
    c.fillStyle = g;
    c.fillRect(0, 0, 4, 256);
    refresh(scene, 'bg-depth');
  }

  // --- полоса травы 256×48, бесшовная ---
  {
    const c = canvasTex(scene, 'bg-grass', 256, 48);
    const R = rng(21);
    const g = c.createLinearGradient(0, 24, 0, 48);
    g.addColorStop(0, '#3e8e2f');
    g.addColorStop(1, '#6b4a32');
    c.fillStyle = g;
    c.fillRect(0, 24, 256, 24);
    c.lineWidth = 2;
    c.strokeStyle = '#2b1b17';
    for (let x = -4; x < 262; x += 6 + Math.floor(R() * 4)) {
      const h = 12 + R() * 12;
      c.fillStyle = R() < 0.5 ? '#6cc24a' : '#4fa83f';
      for (const dx of [-256, 0, 256]) {
        c.beginPath();
        c.moveTo(x + dx - 5, 26);
        c.lineTo(x + dx + 1, 26 - h);
        c.lineTo(x + dx + 6, 26);
        c.closePath();
        c.fill();
        c.stroke();
      }
    }
    c.fillStyle = '#3e8e2f';
    c.fillRect(0, 24, 256, 6);
    refresh(scene, 'bg-grass');
  }

  // --- частицы ---
  {
    const c = canvasTex(scene, 'fx-star', 40, 40);
    c.translate(20, 20);
    c.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = (Math.PI / 5) * i - Math.PI / 2;
      const r = i % 2 === 0 ? 17 : 7.5;
      c.lineTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    c.closePath();
    c.fillStyle = '#ffffff';
    c.fill();
    c.lineWidth = 3;
    c.lineJoin = 'round';
    c.strokeStyle = '#2b1b17';
    c.stroke();
    refresh(scene, 'fx-star');
  }
  {
    const c = canvasTex(scene, 'fx-dot', 24, 24);
    c.beginPath();
    c.arc(12, 12, 9, 0, Math.PI * 2);
    c.fillStyle = '#ffffff';
    c.fill();
    c.lineWidth = 3;
    c.strokeStyle = '#2b1b17';
    c.stroke();
    refresh(scene, 'fx-dot');
  }
  {
    const c = canvasTex(scene, 'fx-ring', 160, 160);
    c.beginPath();
    c.arc(80, 80, 66, 0, Math.PI * 2);
    c.lineWidth = 16;
    c.strokeStyle = '#2b1b17';
    c.stroke();
    c.lineWidth = 9;
    c.strokeStyle = '#ffffff';
    c.stroke();
    refresh(scene, 'fx-ring');
  }
}
