export function normalizeCourseCodeInput(value: string): string {
  return value.toUpperCase().replace(/[\s-]+/g, "").slice(0, 8);
}

export function isCompleteCourseCode(value: string): boolean {
  return /^[A-HJ-KM-NP-Z2-9]{8}$/.test(normalizeCourseCodeInput(value));
}
