const CONTENT_OUTLINE_HEADING = '## Content Outline';
const SLIDE_HEADING_PATTERN = /^###\s+Slide\s+(\d+)\b/i;
const PLAN_FIELD_PATTERN = /^-\s+(\*\*[^:]+?\*\*|[^:]+?)\s*:\s*(.*)$/;
const BOLD_PLAN_FIELD_PATTERN = /^-\s+\*\*([^*]+?)\s*:\*\*\s*(.*)$/;

function normalizePlanFieldName(value) {
  return String(value || '')
    .replace(/\*/g, '')
    .trim()
    .toLowerCase();
}

function normalizePlanFieldValue(value) {
  return String(value || '')
    .trim()
    .replace(/^\*\*\s*/, '')
    .replace(/\s*\*\*$/, '')
    .trim();
}

function splitPlanSections(markdown) {
  const source = String(markdown || '');
  const outlineIndex = source.indexOf(CONTENT_OUTLINE_HEADING);
  if (outlineIndex === -1) {
    return null;
  }

  const outlineBodyIndex = outlineIndex + CONTENT_OUTLINE_HEADING.length;
  return {
    beforeOutline: source.slice(0, outlineBodyIndex),
    outlineBody: source.slice(outlineBodyIndex),
  };
}

function splitSlideEntries(outlineBody) {
  const entries = [];
  const lines = String(outlineBody || '').split(/\r?\n/);
  let current = [];

  for (const line of lines) {
    if (SLIDE_HEADING_PATTERN.test(line) && current.length) {
      entries.push(current.join('\n').trimEnd());
      current = [];
    }
    current.push(line);
  }

  if (current.length) {
    entries.push(current.join('\n').trimEnd());
  }

  return entries.filter((entry) => entry.trim());
}

function extractSlideIndex(entry) {
  const match = String(entry || '').match(SLIDE_HEADING_PATTERN);
  return match ? Number.parseInt(match[1], 10) : null;
}

function parsePlanEntryFields(entry) {
  const fields = {};

  for (const line of String(entry || '').split(/\r?\n/)) {
    const match = line.match(BOLD_PLAN_FIELD_PATTERN) || line.match(PLAN_FIELD_PATTERN);
    if (!match) {
      continue;
    }

    fields[normalizePlanFieldName(match[1])] = {
      rawKey: match[1].trim(),
      value: normalizePlanFieldValue(match[2]),
    };
  }

  return fields;
}

function getPlanField(entry, fieldName) {
  const fields = parsePlanEntryFields(entry);
  return fields[normalizePlanFieldName(fieldName)]?.value || '';
}

function setPlanField(entry, fieldName, value) {
  const normalizedValue = String(value || '').trim();
  const targetFieldName = normalizePlanFieldName(fieldName);
  const lines = String(entry || '').split(/\r?\n/);
  let updated = false;

  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(PLAN_FIELD_PATTERN);
    if (!match || normalizePlanFieldName(match[1]) !== targetFieldName) {
      continue;
    }

    lines[index] = `- ${match[1].trim()}: ${normalizedValue}`;
    updated = true;
    break;
  }

  if (!updated) {
    lines.push(`- ${fieldName}: ${normalizedValue}`);
  }

  return lines.join('\n').trimEnd();
}

module.exports = {
  extractSlideIndex,
  getPlanField,
  normalizePlanFieldName,
  normalizePlanFieldValue,
  parsePlanEntryFields,
  setPlanField,
  splitPlanSections,
  splitSlideEntries,
};
