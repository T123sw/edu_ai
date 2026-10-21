export type Round = { remaining: number[]; known: number; attempts: number };
export const startRound = (count: number): Round => ({ remaining: Array.from({ length: count }, (_, i) => i), known: 0, attempts: 0 });
export function reviewCard(round: Round, known: boolean): Round {
  if (!round.remaining.length) return round;
  const [current, ...rest] = round.remaining;
  return { remaining: known ? rest : [...rest, current], known: round.known + Number(known), attempts: round.attempts + 1 };
}
export type StudyCard = { front: string; back: string; source_title?: string };
export function studyCards(value: unknown): StudyCard[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap(card => {
    if (!card || typeof card !== 'object') return [];
    const front = String(card.front || card.question || '').trim();
    const back = String(card.back || card.answer || '').trim();
    const source_title = String(card.source_title || "").trim();
    return front && back ? [{ front, back, ...(source_title ? { source_title } : {}) }] : [];
  });
}
