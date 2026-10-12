/** Локализация: RU и EN. Язык берём у платформы при старте (п. 2.14), всё остальное в игре переведено (п. 8.2.3). */

export type Lang = 'ru' | 'en';

const ru = {
  pause: 'Пауза',
  resume: 'Продолжить',
  hint_move_touch: 'Ведите пальцем, чтобы плыть и охотиться',
  hint_move_mouse: 'Двигайте мышью (или стрелками, WASD), чтобы плыть и охотиться',
  hint_jump: 'Выберитесь на поверхность, чтобы прыгнуть за добычей в воздухе',
  sound_on: 'Звук включён',
  sound_off: 'Звук выключен',
  'skin.peach': 'Персик',
  'skin.salad': 'Салат',
  'skin.plum': 'Слива',
  'wings.1': 'Крылышки дракончика',
  'wings.2': 'Кожистые крылья',
  'wings.3': 'Шипастые крылья',
  'wings.4': 'Раскалённые крылья',
  'wings.5': 'Пламенные крылья дракона',
} as const;

export type TextKey = keyof typeof ru;

const en: Record<TextKey, string> = {
  pause: 'Paused',
  resume: 'Resume',
  hint_move_touch: 'Drag your finger to swim and hunt',
  hint_move_mouse: 'Move the mouse (or use arrows, WASD) to swim and hunt',
  hint_jump: 'Break through the surface to leap after prey in the air',
  sound_on: 'Sound on',
  sound_off: 'Sound off',
  'skin.peach': 'Peach',
  'skin.salad': 'Salad',
  'skin.plum': 'Plum',
  'wings.1': 'Dragonling wings',
  'wings.2': 'Leathery wings',
  'wings.3': 'Spiked wings',
  'wings.4': 'Blazing wings',
  'wings.5': 'Flaming dragon wings',
};

const dict: Record<Lang, Record<TextKey, string>> = { ru, en };

/** Русский показываем для русского и языков соседних стран, где его обычно понимают; для остальных английский (резервный язык). */
const RU_LIKE = new Set(['ru', 'be', 'kk', 'uk', 'uz']);

export function detectLang(code: string | undefined): Lang {
  const c = (code ?? '').toLowerCase().slice(0, 2);
  return RU_LIKE.has(c) ? 'ru' : 'en';
}

let current: Lang = 'ru';

export function setLang(lang: Lang): void {
  current = lang;
  document.documentElement.lang = lang;
}

export function getLang(): Lang {
  return current;
}

export function t(key: TextKey): string {
  return dict[current][key];
}
