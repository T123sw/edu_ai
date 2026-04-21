const fs = require('fs/promises');
const path = require('path');
const { repoRoot } = require('../config');
const { parseContentProtocol } = require('./content-protocol');
const { parsePlanEntryFields, splitPlanSections, splitSlideEntries } = require('./deck-plan-outline');

const deckPlannerPromptPath = path.join(repoRoot, 'prompts', 'deck-planner.md');
const deckPlanReferencePath = path.join(repoRoot, 'references', 'deck-design-plan.md');
const htmlRestrictPath = path.join(repoRoot, 'references', 'html-to-pptx-restrict.md');
const requiredSections = ['Metadata', 'Design Specification', 'Content Outline'];

function toPromptPath(filePath) {
  return String(filePath || '').replace(/\\/g, '/');
}

function applyPromptReplacements(template, replacements) {
  return Object.entries(replacements).reduce((output, [key, value]) => {
    return output.replaceAll(`{{${key}}}`, toPromptPath(value));
  }, String(template || ''));
}

async function buildDeckDesignPlanPrompt({
  contentPath,
  outputPath,
  plannerDigestPath,
}) {
  const template = await fs.readFile(deckPlannerPromptPath, 'utf8');
  return applyPromptReplacements(template, {
    CONTENT_PATH: contentPath,
    OUTPUT_PATH: outputPath,
    PLANNER_DIGEST_PATH: plannerDigestPath,
    DECK_PLAN_REFERENCE_PATH: deckPlanReferencePath,
  });
}

function hasMarkdownSection(markdown, sectionName) {
  const sectionPattern = new RegExp(`^##\\s+${sectionName}\\s*$`, 'm');
  return sectionPattern.test(markdown);
}

function validateDeckDesignPlan(markdown) {
  for (const section of requiredSections) {
    if (!hasMarkdownSection(markdown, section)) {
      throw new Error(`deck_design_plan.md is missing required section: ${section}`);
    }
  }
}

function validatePlannerPlanMatchesContent({ deckPlanMarkdown, contentMarkdown }) {
  const sections = splitPlanSections(deckPlanMarkdown);
  if (!sections) {
    throw new Error('deck_design_plan.md is missing ## Content Outline.');
  }

  const planEntries = splitSlideEntries(sections.outlineBody);
  const parsedContent = parseContentProtocol(contentMarkdown);
  const contentSlides = parsedContent.slides;

  if (planEntries.length !== contentSlides.length) {
    throw new Error(
      `Planner invented or dropped slides: plan has ${planEntries.length} entries but content has ${contentSlides.length} slides.`
    );
  }

  for (let index = 0; index < contentSlides.length; index += 1) {
    const contentSlide = contentSlides[index];
    const entry = planEntries[index] || '';
    const fields = parsePlanEntryFields(entry);
    const planTitle = String(fields.title?.value || '').trim();
    const planRole = String(fields.role?.value || '').trim();

    if (planTitle !== contentSlide.title) {
      throw new Error(
        `Planner invented or reordered slide ${index + 1}: "${planTitle || 'Untitled'}" is not present in content at this position; expected "${contentSlide.title}".`
      );
    }

    if (planRole && planRole !== contentSlide.role) {
      throw new Error(
        `Planner changed role for slide ${index + 1}: expected "${contentSlide.role}", got "${planRole}".`
      );
    }
  }
}

module.exports = {
  applyPromptReplacements,
  buildDeckDesignPlanPrompt,
  deckPlanReferencePath,
  deckPlannerPromptPath,
  htmlRestrictPath,
  validateDeckDesignPlan,
  validatePlannerPlanMatchesContent,
};
