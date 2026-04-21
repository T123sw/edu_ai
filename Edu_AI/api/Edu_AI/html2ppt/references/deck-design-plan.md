# deck_design_plan.md Reference

The deck design plan is the planning artifact generated before slide HTML. It must be concise, structured, and directly useful to slide executors.

## Required Sections

### Metadata

- Deck name.
- Visual style.
- Page count.
- Language.
- Theme or template pack.

### Design Specification

State the visual direction, typography, color use, brand rules, and CRAP principles:

- Contrast: make hierarchy and key claims obvious.
- Repetition: reuse title, spacing, component, and page chrome rhythm.
- Alignment: keep all content anchored to a consistent grid.
- Proximity: group related text, metrics, and visuals together.

### Content Outline

Use one subsection per slide. Each slide must include:

- `Slide`: page number.
- `Role`: cover, toc, section, content, or thanks.
- `Title`: main slide title.
- `Visible Content`: source content that must appear on the slide.
- Teaching Objective: one sentence about what the teacher should explain.
- Teaching Recipe: definition, example, comparison, process, chart, misconception, classroom prompt.
- Layout Level: component, preset_slide, or frame.
- Layout: catalog key.
- Components: comma-separated component keys or none.
- Density: light, standard, full, or split-needed.
- Fallback: split page or safer layout when the content exceeds capacity.

Planner invariants:

- Keep exactly the same slide count and slide order as the runtime content.
- Do not add, remove, merge, split, or reorder slides.
- If source Notes request a game page, animation page, appendix, companion page, or any extra slide, ignore that request and still plan only the original slides.

Do not invent factual statistics, dates, or external claims. If source content has no data, use conceptual charts or matrices.

Density routing rules:

- Reserve `light` mainly for `cover`, `toc`, `section`, `thanks`, and clearly media-led slides.
- Ordinary `content` slides should usually plan as `standard` or `full`.
- If a page would render as two short comparison cards, three short process nodes, or three definition-only cards, route to the declared fallback instead of preserving a sparse layout.
