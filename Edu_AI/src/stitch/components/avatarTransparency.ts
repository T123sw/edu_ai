export type WhiteColorKeyOptions = {
  similarity?: number;
  blend?: number;
};

const DEFAULT_SIMILARITY = 0.1;
const DEFAULT_BLEND = 0.1;

function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function getWhiteColorKeyAlpha(
  red: number,
  green: number,
  blue: number,
  options: WhiteColorKeyOptions = {},
) {
  const similarity = clamp01(options.similarity ?? DEFAULT_SIMILARITY);
  const blend = clamp01(options.blend ?? DEFAULT_BLEND);
  const whiteDistance = Math.max(255 - red, 255 - green, 255 - blue) / 255;

  if (whiteDistance <= similarity) return 0;
  if (blend <= 0) return 255;

  const feather = (whiteDistance - similarity) / blend;
  return Math.round(clamp01(feather) * 255);
}

export function applyWhiteColorKeyTransparency(
  data: Uint8ClampedArray,
  options: WhiteColorKeyOptions = {},
) {
  for (let index = 0; index < data.length; index += 4) {
    const keyAlpha = getWhiteColorKeyAlpha(data[index], data[index + 1], data[index + 2], options);
    data[index + 3] = Math.min(data[index + 3], keyAlpha);
  }
}
