import Phaser from 'phaser';

/**
 * Текстуры, нарисованные кодом: только плавные градиенты неба у горизонта и затемнения с глубиной.
 * Почва, трава, облака, частицы и сокровища берутся из design/ (атласы и картинки, tools/build-assets.mjs).
 */

function canvasTex(scene: Phaser.Scene, key: string, w: number, h: number): CanvasRenderingContext2D {
  const tex = scene.textures.createCanvas(key, w, h);
  if (!tex) throw new Error('canvas texture: ' + key);
  return tex.getContext();
}

function refresh(scene: Phaser.Scene, key: string): void {
  (scene.textures.get(key) as Phaser.Textures.CanvasTexture).refresh();
}

export function makeTextures(scene: Phaser.Scene): void {
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
}
