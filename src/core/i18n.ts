/** Локализация: RU и EN. Язык берём у платформы при старте (п. 2.14), всё остальное в игре переведено (п. 8.2.3). */

export type Lang = 'ru' | 'en';

const ru = {
  pause: 'Пауза',
  resume: 'Продолжить',
  hint_move_touch: 'Ведите пальцем, чтобы плыть и охотиться',
  hint_move_mouse: 'Двигайте мышью (или стрелками, WASD), чтобы плыть и охотиться',
  hint_eat: 'Ешьте жуков и червячков, чтобы расти. Добыча должна помещаться в челюсти',
  hint_locked: 'Подрастите, чтобы выбраться на поверхность',
  hint_unlocked: 'Вы выросли! Теперь можно выпрыгнуть на поверхность',
  sound_on: 'Звук включён',
  sound_off: 'Звук выключен',
  'skin.peach': 'Персик',
  'skin.salad': 'Салат',
  'skin.plum': 'Слива',
  'wings.1': 'Крылья жука',
  'wings.2': 'Птичьи крылья',
  'wings.3': 'Светлые крылья',
  'wings.4': 'Тёмные крылья',
  'wings.5': 'Крылья золотого дракона',
} as const;

export type TextKey = keyof typeof ru;

const en: Record<TextKey, string> = {
  pause: 'Paused',
  resume: 'Resume',
  hint_move_touch: 'Drag your finger to swim and hunt',
  hint_move_mouse: 'Move the mouse (or use arrows, WASD) to swim and hunt',
  hint_eat: 'Eat bugs and worms to grow. Prey must fit into your jaws',
  hint_locked: 'Grow bigger to break through to the surface',
  hint_unlocked: 'You have grown! Now you can leap out onto the surface',
  sound_on: 'Sound on',
  sound_off: 'Sound off',
  'skin.peach': 'Peach',
  'skin.salad': 'Salad',
  'skin.plum': 'Plum',
  'wings.1': 'Beetle wings',
  'wings.2': 'Bird wings',
  'wings.3': 'Light wings',
  'wings.4': 'Dark wings',
  'wings.5': 'Golden dragon wings',
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
