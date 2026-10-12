import { CHALLENGE_COUNT, makeChallenge, pickKind, type ChallengeKind, type ChallengeState } from '../data/challenges';

export interface ChallengeDone {
  kind: ChallengeKind;
  /** Награда в монетах (уже посчитана, начислить должна сцена). */
  reward: number;
}

/**
 * Три активных испытания (концепт, раздел 10). Сцена сообщает о событиях (съели жука, нашли сундук, выросли),
 * тут копится прогресс; выполненное заменяется новым, награду начисляет сцена. Без Phaser: проверяется отдельно.
 */
export class Challenges {
  list: ChallengeState[] = [];

  /** Сохранённые испытания плюс новые до нужного числа. Возвращает true, если пришлось добавлять. */
  load(saved: ChallengeState[], tier: number): boolean {
    this.list = saved.slice(0, CHALLENGE_COUNT).map((c) => ({ ...c }));
    let added = false;
    while (this.list.length < CHALLENGE_COUNT) {
      this.list.push(makeChallenge(pickKind(tier, this.list.map((c) => c.k)), tier));
      added = true;
    }
    return added;
  }

  /** Прибавить прогресс всем испытаниям этого вида; вернуть выполненные (они уже заменены новыми). */
  report(kind: ChallengeKind, amount: number, tier: number): ChallengeDone[] {
    const done: ChallengeDone[] = [];
    for (let i = 0; i < this.list.length; i++) {
      const c = this.list[i];
      if (c.k !== kind) continue;
      c.p = Math.min(c.n, c.p + amount);
      if (c.p >= c.n) done.push(this.finish(i, tier));
    }
    return done;
  }

  /** «Достигните уровня N»: прогресс равен текущему тиру. */
  reportTier(tier: number): ChallengeDone[] {
    const done: ChallengeDone[] = [];
    for (let i = 0; i < this.list.length; i++) {
      const c = this.list[i];
      if (c.k !== 'tier') continue;
      c.p = Math.min(c.n, Math.max(c.p, tier));
      if (c.p >= c.n) done.push(this.finish(i, tier));
    }
    return done;
  }

  private finish(i: number, tier: number): ChallengeDone {
    const old = this.list[i];
    const taken = this.list.filter((_, j) => j !== i).map((c) => c.k);
    this.list[i] = makeChallenge(pickKind(tier, [...taken, old.k]), tier);
    return { kind: old.k, reward: old.r };
  }
}
