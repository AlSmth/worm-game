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
  select_title: 'Выберите червя',
  select_pick: 'Выбрать',
  select_chosen: 'Выбран',
  menu_change: 'Сменить червя',
  menu_back: 'Назад',
  'skin.peach.note': 'Милаха',
  'skin.salad.note': 'Хулиган',
  'skin.plum.note': 'Монстрик',
  story_intro: 'Вы маленький голодный червячок. Ешьте и растите!',
  tut_eat: 'Съешьте жука или червячка',
  tut_good: 'Отлично! Ешьте дальше, чтобы расти',
  tut_coin: 'Монеты и самоцветы пригодятся для улучшений',
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
  'armor.1': 'Мелкая чешуя',
  'armor.2': 'Крупная чешуя',
  'armor.3': 'Чешуя с бугорками',
  'armor.4': 'Острые рога',
  'armor.5': 'Драконьи рога',
  'fins.1': 'Спинной гребешок',
  'fins.2': 'Высокий гребень',
  'fins.3': 'Спинной плавник',
  'fins.4': 'Большой плавник',
  'fins.5': 'Золотой плавник',
  'line.jump': 'Прыжок',
  'line.hp': 'Здоровье',
  'line.speed': 'Скорость',
  'eff.jump': 'Высота прыжка +{n}%',
  'eff.hp': 'Запас здоровья +{n}%',
  'eff.speed': 'Скорость +{n}%',
  shop_title: 'Магазин',
  shop_tab_up: 'Улучшения',
  shop_tab_ch: 'Испытания',
  shop_max: 'Максимум',
  shop_need: 'Не хватает {n}',
  tut_shop: 'Хватает монет на улучшение! Откройте магазин',
  ch_eat: 'Съешьте добычу: {n}',
  ch_beetle: 'Съешьте жуков: {n}',
  ch_worm: 'Съешьте червячков: {n}',
  ch_coins: 'Соберите монеты: {n}',
  ch_gems: 'Найдите самоцветы: {n}',
  ch_chests: 'Найдите сундуки: {n}',
  ch_tier: 'Достигните уровня {n}',
  ch_jump: 'Выпрыгните из земли: {n}',
  ch_done: 'Испытание выполнено! +{n} монет',
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
  select_title: 'Choose your worm',
  select_pick: 'Choose',
  select_chosen: 'Chosen',
  menu_change: 'Change worm',
  menu_back: 'Back',
  'skin.peach.note': 'Sweetie',
  'skin.salad.note': 'Rascal',
  'skin.plum.note': 'Monster',
  story_intro: 'You are a tiny hungry worm. Eat and grow!',
  tut_eat: 'Eat a bug or a worm',
  tut_good: 'Great! Keep eating to grow',
  tut_coin: 'Coins and gems will buy upgrades',
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
  'armor.1': 'Small scales',
  'armor.2': 'Large scales',
  'armor.3': 'Scales with bumps',
  'armor.4': 'Sharp horns',
  'armor.5': 'Dragon horns',
  'fins.1': 'Dorsal crest',
  'fins.2': 'Tall crest',
  'fins.3': 'Dorsal fin',
  'fins.4': 'Big fin',
  'fins.5': 'Golden fin',
  'line.jump': 'Jump',
  'line.hp': 'Health',
  'line.speed': 'Speed',
  'eff.jump': 'Jump height +{n}%',
  'eff.hp': 'Health +{n}%',
  'eff.speed': 'Speed +{n}%',
  shop_title: 'Shop',
  shop_tab_up: 'Upgrades',
  shop_tab_ch: 'Challenges',
  shop_max: 'Maxed',
  shop_need: 'Need {n} more',
  tut_shop: 'Enough coins for an upgrade! Open the shop',
  ch_eat: 'Eat prey: {n}',
  ch_beetle: 'Eat beetles: {n}',
  ch_worm: 'Eat worms: {n}',
  ch_coins: 'Collect coins: {n}',
  ch_gems: 'Find gems: {n}',
  ch_chests: 'Find chests: {n}',
  ch_tier: 'Reach level {n}',
  ch_jump: 'Leap out of the ground: {n}',
  ch_done: 'Challenge complete! +{n} coins',
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

/** Текст по ключу; {n}, {name} и другие метки в строке заменяются значениями params. */
export function t(key: TextKey, params?: Record<string, number | string>): string {
  let s = dict[current][key];
  if (params) for (const k of Object.keys(params)) s = s.split(`{${k}}`).join(String(params[k]));
  return s;
}
