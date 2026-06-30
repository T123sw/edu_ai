const { parseContentProtocol } = require('./content-protocol');
const {
  extractSlideIndex,
  getPlanField,
  setPlanField,
  splitPlanSections,
  splitSlideEntries,
} = require('./deck-plan-outline');

const ROUTABLE_BULLET_LAYOUTS = new Set([
  'standard_text',
  'standard_text_structured',
  'thesis_evidence_grid',
  'card_layout',
]);

function applyEntryUpdates(entry, updates) {
  return Object.entries(updates).reduce((current, [fieldName, value]) => {
    if (value == null) {
      return current;
    }
    return setPlanField(current, fieldName, value);
  }, String(entry || ''));
}

function serializePlan({ beforeOutline, entries }) {
  const outlineBody = entries.join('\n\n').trim();
  return `${beforeOutline.trimEnd()}\n\n${outlineBody}\n`;
}

function extractBlockItems(rawLines, blockName) {
  const items = [];
  const lines = Array.isArray(rawLines) ? rawLines : [];
  let inBlocks = false;
  let activeBlock = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^###\s+Blocks\b/i.test(trimmed)) {
      inBlocks = true;
      activeBlock = null;
      continue;
    }
    if (/^###\s+Notes\b/i.test(trimmed)) {
      break;
    }
    if (!inBlocks) {
      continue;
    }

    const blockMatch = line.match(/^- ([A-Za-z-]+):(.*)$/);
    if (blockMatch) {
      activeBlock = blockMatch[1];
      continue;
    }

    if (activeBlock !== blockName) {
      continue;
    }

    const itemMatch = line.match(/^\s+- (.+)$/);
    if (itemMatch) {
      items.push(itemMatch[1].trim());
    }
  }

  return items;
}

function extractBulletItems(rawLines) {
  return extractBlockItems(rawLines, 'Bullets');
}

function extractBulletLabel(item) {
  const text = String(item || '').trim();
  const match = text.match(/^([^：:]{1,16})[：:]/);
  return match ? match[1].trim() : '';
}

function buildSlideProfile(slide) {
  const bulletItems = extractBulletItems(slide?.rawLines);
  const bulletLabels = bulletItems.map(extractBulletLabel).filter(Boolean);
  const semanticText = [slide?.title || '', ...bulletItems].join(' ');
  const allBulletsLabeled = bulletItems.length > 0 && bulletLabels.length === bulletItems.length;

  return {
    bulletItems,
    bulletLabels,
    bulletCount: bulletItems.length,
    semanticText,
    allBulletsLabeled,
  };
}

function buildRoute(layout, components, teachingRecipe, fallback) {
  return {
    'Layout Level': 'frame',
    Layout: layout,
    Components: components,
    Density: 'full',
    'Teaching Recipe': teachingRecipe,
    Fallback: fallback,
  };
}

function chooseBulletRoute(profile) {
  if (profile.bulletCount < 4) {
    return null;
  }

  const semanticText = profile.semanticText;
  const labels = new Set(profile.bulletLabels.map((label) => String(label || '').toLowerCase()));
  const hasAnyLabel = (candidates) => candidates.some((candidate) => labels.has(String(candidate).toLowerCase()));

  if (
    /(架构|pipeline|链路|编码侧|解码侧|llm核心|llm\s*核心|核心层|处理核心|创新点|设计哲学)/i.test(semanticText) &&
    hasAnyLabel(['编码侧', '解码侧', 'LLM核心', '创新点'])
  ) {
    return buildRoute(
      'architecture_pipeline_spotlight',
      'none',
      '总判断 + 三段主链 + 创新点',
      'standard_text_process_grid'
    );
  }

  if (
    /(语义|声学|双核|解耦|机制|优势|结果|收益)/.test(semanticText) &&
    profile.allBulletsLabeled &&
    profile.bulletCount === 4
  ) {
    return buildRoute(
      'dual_core_support',
      'none',
      '总判断 + 两个主概念 + 机制与结果',
      'standard_text_dual_panel'
    );
  }

  if (/(为何|为什么|必须|原因|挑战|关键|支撑|论据|基础)/.test(semanticText)) {
    return buildRoute(
      'thesis_evidence_grid',
      'none',
      '先结论后论据',
      'standard_text'
    );
  }

  return null;
}

function rebalanceDeckDesignPlan({ deckPlanMarkdown, contentMarkdown }) {
  const sections = splitPlanSections(deckPlanMarkdown);
  if (!sections) {
    return String(deckPlanMarkdown || '');
  }

  const parsedContent = parseContentProtocol(contentMarkdown, { allowLoose: true });
  const slideByIndex = new Map(parsedContent.slides.map((slide) => [slide.slide_number, slide]));
  const entries = splitSlideEntries(sections.outlineBody);
  const updatedEntries = [...entries];
  let changed = false;

  for (let entryIndex = 0; entryIndex < entries.length; entryIndex += 1) {
    const entry = entries[entryIndex];
    const slideIndex = extractSlideIndex(entry);
    const slide = slideByIndex.get(slideIndex);
    if (!slide) {
      continue;
    }

    const updates = {};
    const currentLayout = getPlanField(entry, 'Layout');
    const isRouteableBulletSlide =
      slide.role === 'content' &&
      slide.blockTypes.length === 1 &&
      slide.blockTypes[0] === 'Bullets' &&
      ROUTABLE_BULLET_LAYOUTS.has(currentLayout);

    if (isRouteableBulletSlide) {
      const route = chooseBulletRoute(buildSlideProfile(slide));
      if (route) {
        Object.assign(updates, route);
      }
    }

    if (Object.keys(updates).length === 0) {
      continue;
    }

    const nextEntry = applyEntryUpdates(entry, updates);
    if (nextEntry !== entry) {
      updatedEntries[entryIndex] = nextEntry;
      changed = true;
    }
  }

  if (!changed) {
    return String(deckPlanMarkdown || '');
  }

  return serializePlan({
    beforeOutline: sections.beforeOutline,
    entries: updatedEntries,
  });
}

module.exports = {
  rebalanceDeckDesignPlan,
};
