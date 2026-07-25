import temml from 'temml';
import { mml2omml } from 'mathml2omml';

function stripUnsupportedMathMl(mathml: string): string {
  return mathml
    .replace(/<mpadded[^>]*>/g, '')
    .replace(/<\/mpadded>/g, '');
}

function mathRunProperties(sizeHundredths?: number): string {
  const size = sizeHundredths ? ` sz="${sizeHundredths}"` : '';
  return (
    `<a:rPr lang="en-US" i="1"${size}>` +
    '<a:latin typeface="Cambria Math" panose="02040503050406030204" charset="0"/>' +
    '<a:cs typeface="Cambria Math" panose="02040503050406030204" charset="0"/>' +
    '</a:rPr>'
  );
}

function makePowerPointCompatible(
  omml: string,
  sizeHundredths?: number,
): string {
  const runProperties = mathRunProperties(sizeHundredths);
  return omml
    .replace(/ xmlns:w="[^"]*"/g, '')
    .replace(/ xmlns:m="[^"]*"/g, '')
    .replace(
      /<m:r>(\s*)<m:t/g,
      `<m:r>$1${runProperties}$1<m:t`,
    )
    .replace(
      /<m:ctrlPr\/>/g,
      `<m:ctrlPr>${runProperties}</m:ctrlPr>`,
    )
    .replace(
      /<m:ctrlPr><\/m:ctrlPr>/g,
      `<m:ctrlPr>${runProperties}</m:ctrlPr>`,
    );
}

export function latexToOmml(
  latex: string,
  fontSize?: number,
): string | null {
  try {
    const mathml = temml.renderToString(latex, { throwOnError: true });
    const converted = mml2omml(stripUnsupportedMathMl(mathml));
    if (!converted) return null;
    const omml = String(converted);
    if (!omml.includes('<m:oMath')) return null;
    const sizeHundredths = fontSize
      ? Math.round(fontSize * 100)
      : undefined;
    return makePowerPointCompatible(omml, sizeHundredths);
  } catch {
    return null;
  }
}
