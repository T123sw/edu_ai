# HTML to PPTX Restrictions

These rules protect export stability for the browser-based HTML-to-PPTX pipeline.

## Agent Output

- Output slide fragments only, not full HTML documents.
- Each slide root must be `<div class="slide ...">`.
- Do not output `<style>`, `<script>`, inline `style`, or unregistered class names.
- Do not rely on pseudo-elements for critical visual elements.
- Use only classes registered by the layout and component catalogs.
- Footer chrome must only keep the bottom-right page number on normal content pages.
- 页脚只保留右下角页码.

## Media

- Prefer `Local-Path` and `Local-Poster-Path` when present in runtime content.
- Use real `<img>` for images and real `<video>` for videos.
- Videos only include `poster` when `Local-Poster-Path` exists; 没有 `Local-Poster-Path` 时不要输出 `poster` 属性.
- Preserve media aspect ratio unless the selected layout explicitly requires cover cropping.

## Deck Consistency

- Follow `deck_design_plan.md` for visual style and slide-level decisions.
- Do not invent new slides, remove slides, or merge slides.
- Keep source block markers visible when they carry titles, definitions, comparison sides, or process steps.

## Deterministic Decoration

- 全局装饰由系统后处理注入；不要手写 `slide-safe-decor`、`slide-top-rule`、`slide-header-hairline`、`slide-header-mark`、`slide-header-mark-accent`、`content-safe-accent` 或 `thanks-safe-decor`.
- 引言框装饰必须用真实 `quote-accent` 节点，不要改成 `border-left`.
- Brand slot and thanks logo must use real `<img>` elements.
- thanks 页不要再插入右上角 `slide-brand`.
- 不要输出 `contact-info` 或 `info-item`.
- Thanks pages must not output `contact-info`, `info-item`, or an extra top-right `slide-brand`; `thanks-note` is required and `Q&A` must stay on one line.
- If the thanks title is long, keep `title-main` short and move the summary sentence into `thanks-note` instead of stacking long Chinese and `Q&A` lines together.
