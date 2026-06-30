# Task

Rewrite one existing slide fragment.

## Inputs

- Deck design plan: `{{DECK_DESIGN_PLAN_PATH}}`
- Layout catalog: `{{LAYOUT_CATALOG_PATH}}`
- Component catalog: `{{COMPONENT_CATALOG_PATH}}`
- HTML-to-PPTX restrictions: `{{HTML_RESTRICT_PATH}}`
- Theme CSS: `{{THEME_CSS_PATH}}`
- Format directory: `{{FORMAT_DIR}}`
- Brand config: `{{BRAND_CONFIG_PATH}}`
- Target output path: `{{OUTPUT_PATH}}`

## Execution Rules

- Rewrite only the target slide.
- Preserve deck-level visual decisions from `deck_design_plan.md`.
- Use the original slide HTML and neighboring slide context supplied in the runtime prompt.
- Output exactly one slide fragment.
- Do not output explanations.
