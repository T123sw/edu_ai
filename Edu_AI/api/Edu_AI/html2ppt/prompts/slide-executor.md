# Task

Generate slide HTML fragment for the requested slide.

## Inputs

- Runtime content: `{{CONTENT_PATH}}`
- Content protocol: `{{CONTENT_PROTOCOL_PATH}}`
- Deck design plan: `{{DECK_DESIGN_PLAN_PATH}}`
- Layout catalog: `{{LAYOUT_CATALOG_PATH}}`
- Component catalog: `{{COMPONENT_CATALOG_PATH}}`
- HTML-to-PPTX restrictions: `{{HTML_RESTRICT_PATH}}`
- Agent workflow: `{{AGENT_WORKFLOW_PATH}}`
- Theme CSS: `{{THEME_CSS_PATH}}`
- Format directory: `{{FORMAT_DIR}}`
- Layout CSS: `{{LAYOUT_CSS_PATH}}`
- Brand config: `{{BRAND_CONFIG_PATH}}`
- Focused catalog summary: appended by the runtime prompt builder.
- Target output path: `{{OUTPUT_PATH}}`

## Execution Rules

- Follow `deck_design_plan.md`; do not redefine the deck strategy.
- Use the Focused catalog summary and target slide plan as the primary layout contract.
- Fill required slots from the selected recipe.
- If the selected layout is sparse-prone, fill its second-layer explanation/example slots or follow the declared fallback instead of emitting a thin shell.
- Respect min/max content units; use fallback or split guidance instead of overfilling.
- Keep HTML flexible inside slots, but use only registered classes and template structures.
- Use only registered layouts, components, classes, and template structures.
- Read the content protocol, catalogs, HTML-to-PPTX restrictions, and theme CSS before writing HTML.
- Read only the frame, preset, or component source files needed by the target slide.
- Output exactly one `<div class="slide ...">...</div>` when running in single-slide mode.
- Do not output a full HTML document.
- Do not output explanations.
