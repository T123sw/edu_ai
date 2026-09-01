export function decodeDisplayText(value: unknown): string {
  const raw = String(value ?? '');
  if (!raw) {
    return '';
  }

  let decoded = raw;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!/%[0-9A-Fa-f]{2}/.test(decoded)) {
      break;
    }

    try {
      const nextValue = decodeURIComponent(decoded);
      if (nextValue === decoded) {
        break;
      }
      decoded = nextValue;
    } catch {
      break;
    }
  }

  return decoded;
}
