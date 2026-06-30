# Task

Create `deck_design_plan.md` for the PPT generation job.

## Inputs

- Runtime content: `{{CONTENT_PATH}}`
- Deck design plan reference: `{{DECK_PLAN_REFERENCE_PATH}}`
- Planner digest: `{{PLANNER_DIGEST_PATH}}`
- Target output path: `{{OUTPUT_PATH}}`

## Workflow

1. Read the runtime content.
2. Read the deck design plan reference.
3. Read the planner digest.
4. Write a concise Markdown deck design plan to the target output path.

## Output Rules

- Write only the target Markdown file.
- Include Metadata, Design Specification, and Content Outline.
- Every slide in runtime content must appear exactly once in the Content Outline.
- Never add, remove, merge, split, or reorder slides.
- Use only layout keys and component keys that appear in the planner digest.
- For every slide, write Teaching Objective, Teaching Recipe, Layout Level, Layout, Components, Density, and Fallback.
- If Notes mention appending a game page, animation page, companion page, appendix, or any extra slide, ignore that request and keep the original slide count unchanged.
- Do not write file paths, JSON payloads, HTML, or insertion mechanics.
- Reserve `light` mainly for `cover`, `toc`, `section`, `thanks`, or clearly media-led pages; ordinary `content` pages should usually be `standard` or `full`.
- Prefer the declared fallback over sparse layout variety when a page would otherwise become a thin shell.
- Enrich teaching material with examples, classroom prompts, common misconceptions, conceptual charts, or matrices when useful.
- Do not invent unsupported factual data. Use conceptual charts when no numeric data is provided.
- Prefer compact recipes from the planner digest over long custom instructions.
