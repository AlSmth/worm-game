#!/usr/bin/env node
/**
 * Конвейер графики: SVG из design/ -> обрезанные PNG-атласы для Phaser в public/assets/.
 *
 *   node tools/build-assets.mjs [--force]
 *
 * Для каждого атласа: растеризует SVG (resvg), обрезает прозрачные поля (смещение запоминается,
 * якоря остаются на месте), укладывает полками в одну текстуру степени двойки (≤ 2048) и пишет
 * <имя>.png и <имя>.json (формат JSON Hash, понятен Phaser).
 * Если исходники не менялись, атлас пропускается.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Resvg } from '@resvg/resvg-js';
import { PNG } from 'pngjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'public', 'assets');
const SELF = fileURLToPath(import.meta.url);
const FORCE = process.argv.includes('--force');
const MAX_PAGE = 2048;
const GAP = 2; // зазор между кадрами, px

/** scale: во сколько раз уменьшаем рисунок при растеризации (экономия памяти для крупных ассетов) */
const ATLASES = [
  { name: 'worm-peach', scale: 1, dir: 'design/worm/peach' },
  { name: 'worm-salad', scale: 1, dir: 'design/worm/salad' },
  { name: 'worm-plum', scale: 1, dir: 'design/worm/plum' },
  { name: 'wings', scale: 0.75, dir: 'design/upgrades/wings' },
  { name: 'props', scale: 1, dir: 'design/zone-1-underground/food' },
  { name: 'treasure', scale: 1, dir: 'design/treasure' },
  { name: 'fx', scale: 1, dir: 'design/effects' },
  // броня и гребень с плавниками: по атласу на персонажа (цвета пластин и плавников берутся от цвета червя)
  { name: 'gear-peach', scale: 1, dirs: ['design/upgrades/armor/peach', 'design/upgrades/fins/peach'] },
  { name: 'gear-salad', scale: 1, dirs: ['design/upgrades/armor/salad', 'design/upgrades/fins/salad'] },
  { name: 'gear-plum', scale: 1, dirs: ['design/upgrades/armor/plum', 'design/upgrades/fins/plum'] },
  // зона 2 «Поверхность»: люди, машины, техника охраны, декор, дома
  { name: 'z2', scale: 1, dirs: ['design/zone-2-surface/people', 'design/zone-2-surface/vehicles', 'design/zone-2-surface/military', 'design/zone-2-surface/decor', 'design/zone-2-surface/houses'] },
];

/** Одиночные картинки без обрезки и упаковки (фоны и повторяющиеся плитки): PNG целиком, размер степень двойки. */
const SINGLES = [
  { name: 'bg-z1-far', file: 'design/zone-1-underground/background/bg-z1-far.svg', scale: 1 },
  { name: 'bg-z1-mid', file: 'design/zone-1-underground/background/bg-z1-mid.svg', scale: 1 },
  { name: 'bg-z1-near', file: 'design/zone-1-underground/background/bg-z1-near.svg', scale: 1 },
  { name: 'bg-z1-edge', file: 'design/zone-1-underground/background/bg-z1-edge.svg', scale: 1 },
  { name: 'bg-z1-clouds', file: 'design/zone-1-underground/background/bg-z1-clouds.svg', scale: 0.5 },
  { name: 'bg-z2-skyline', file: 'design/zone-2-surface/background/bg-z2-skyline.svg', scale: 1 },
  { name: 'bg-z2-hills', file: 'design/zone-2-surface/background/bg-z2-hills.svg', scale: 1 },
];

const pot = (n) => 2 ** Math.ceil(Math.log2(Math.max(n, 1)));

function listSvgs(dir) {
  return readdirSync(join(ROOT, dir)).filter((f) => f.endsWith('.svg')).sort();
}

/** Все SVG атласа: одна папка (dir) или несколько (dirs). */
function atlasFiles(cfg) {
  return (cfg.dirs ?? [cfg.dir]).flatMap((d) => listSvgs(d).map((f) => join(ROOT, d, f)));
}

function newestMtime(paths) {
  return Math.max(...paths.map((p) => statSync(p).mtimeMs));
}

/** Кадр: растеризация + обрезка прозрачных полей */
function renderFrame(svgPath, scale) {
  const svg = readFileSync(svgPath, 'utf8');
  const resvg = new Resvg(svg, { fitTo: { mode: 'zoom', value: scale }, font: { loadSystemFonts: false } });
  const png = PNG.sync.read(resvg.render().asPng());
  const { width: sw, height: sh, data } = png;
  let minX = sw, minY = sh, maxX = -1, maxY = -1;
  for (let y = 0; y < sh; y++) {
    for (let x = 0; x < sw; x++) {
      if (data[(y * sw + x) * 4 + 3] > 2) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX < 0) throw new Error(`Пустой рисунок: ${svgPath}`);
  minX = Math.max(0, minX - 1); minY = Math.max(0, minY - 1);
  maxX = Math.min(sw - 1, maxX + 1); maxY = Math.min(sh - 1, maxY + 1);
  const w = maxX - minX + 1, h = maxY - minY + 1;
  const crop = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) {
    data.copy(crop, y * w * 4, ((minY + y) * sw + minX) * 4, ((minY + y) * sw + minX + w) * 4);
  }
  return { w, h, srcW: sw, srcH: sh, offX: minX, offY: minY, crop };
}

/** Укладка полками: возвращает позиции и размер страницы (степени двойки) */
function pack(frames) {
  const sorted = [...frames].sort((a, b) => b.h - a.h || b.w - a.w);
  let best = null;
  for (let pw = 128; pw <= MAX_PAGE; pw *= 2) {
    let x = 0, y = 0, rowH = 0, ok = true;
    const pos = new Map();
    for (const f of sorted) {
      if (f.w + GAP > pw) { ok = false; break; }
      if (x + f.w + GAP > pw) { x = 0; y += rowH + GAP; rowH = 0; }
      pos.set(f.name, { x, y });
      x += f.w + GAP;
      rowH = Math.max(rowH, f.h);
    }
    if (!ok) continue;
    const ph = pot(y + rowH + GAP);
    if (ph > MAX_PAGE) continue;
    // меньше площадь лучше; при равной площади предпочитаем квадратную текстуру
    const area = pw * ph * (1 + 0.1 * Math.abs(Math.log2(pw / ph)));
    if (!best || area < best.area) best = { pw, ph, area, pos };
  }
  if (!best) throw new Error('Кадры не помещаются в текстуру 2048×2048');
  return best;
}

function buildAtlas(cfg) {
  const files = atlasFiles(cfg);
  const pngPath = join(OUT, `${cfg.name}.png`);
  const jsonPath = join(OUT, `${cfg.name}.json`);
  if (!FORCE && existsSync(pngPath) && existsSync(jsonPath)) {
    const outTime = Math.min(statSync(pngPath).mtimeMs, statSync(jsonPath).mtimeMs);
    if (outTime > newestMtime([...files, SELF])) return { name: cfg.name, skipped: true };
  }
  const frames = files.map((p) => {
    const name = p.split(/[\\/]/).pop().replace(/\.svg$/, '');
    return { name, ...renderFrame(p, cfg.scale) };
  });
  const { pw, ph, pos } = pack(frames);
  const atlas = new PNG({ width: pw, height: ph });
  atlas.data.fill(0);
  const json = { frames: {}, meta: { app: 'tools/build-assets.mjs', version: '1', image: `${cfg.name}.png`, format: 'RGBA8888', size: { w: pw, h: ph }, scale: cfg.scale } };
  for (const f of frames) {
    const { x, y } = pos.get(f.name);
    for (let row = 0; row < f.h; row++) {
      f.crop.copy(atlas.data, ((y + row) * pw + x) * 4, row * f.w * 4, (row + 1) * f.w * 4);
    }
    json.frames[f.name] = {
      frame: { x, y, w: f.w, h: f.h },
      rotated: false,
      trimmed: true,
      spriteSourceSize: { x: f.offX, y: f.offY, w: f.w, h: f.h },
      sourceSize: { w: f.srcW, h: f.srcH },
    };
  }
  writeFileSync(pngPath, PNG.sync.write(atlas, { colorType: 6, deflateLevel: 9 }));
  writeFileSync(jsonPath, JSON.stringify(json));
  return { name: cfg.name, frames: frames.length, size: `${pw}x${ph}`, bytes: statSync(pngPath).size, scale: cfg.scale };
}

function buildSingle(cfg) {
  const src = join(ROOT, cfg.file);
  const pngPath = join(OUT, `${cfg.name}.png`);
  const render = () => {
    const resvg = new Resvg(readFileSync(src, 'utf8'), { fitTo: { mode: 'zoom', value: cfg.scale }, font: { loadSystemFonts: false } });
    return PNG.sync.read(resvg.render().asPng());
  };
  if (!FORCE && existsSync(pngPath) && statSync(pngPath).mtimeMs > newestMtime([src, SELF])) {
    const png = PNG.sync.read(readFileSync(pngPath));
    return { name: cfg.name, skipped: true, w: png.width, h: png.height };
  }
  const png = render();
  writeFileSync(pngPath, PNG.sync.write(png, { colorType: 6, deflateLevel: 9 }));
  return { name: cfg.name, w: png.width, h: png.height, bytes: statSync(pngPath).size };
}

mkdirSync(OUT, { recursive: true });
const info = {};
let total = 0;
for (const cfg of ATLASES) {
  const r = buildAtlas(cfg);
  if (r.skipped) console.log(`  ${cfg.name}: без изменений`);
  else console.log(`  ${cfg.name}: ${r.frames} кадров, ${r.size}, ${(r.bytes / 1024).toFixed(0)} КБ`);
  const jsonPath = join(OUT, `${cfg.name}.json`);
  const meta = JSON.parse(readFileSync(jsonPath, 'utf8')).meta;
  info[cfg.name] = { scale: meta.scale, w: meta.size.w, h: meta.size.h };
  total += statSync(join(OUT, `${cfg.name}.png`)).size;
}
for (const cfg of SINGLES) {
  const r = buildSingle(cfg);
  const isPot = (n) => (n & (n - 1)) === 0;
  if (!isPot(r.w) || !isPot(r.h)) throw new Error(`${cfg.name}: размер ${r.w}x${r.h} не степень двойки (нужно для повторяющейся плитки)`);
  if (r.skipped) console.log(`  ${cfg.name}: без изменений`);
  else console.log(`  ${cfg.name}: ${r.w}x${r.h}, ${(r.bytes / 1024).toFixed(0)} КБ`);
  info[cfg.name] = { scale: cfg.scale, w: r.w, h: r.h, single: true };
  total += statSync(join(OUT, `${cfg.name}.png`)).size;
}
writeFileSync(join(OUT, 'atlas-info.json'), JSON.stringify(info, null, 1));
console.log(`Атласы готовы: всего ${(total / 1024).toFixed(0)} КБ PNG`);
