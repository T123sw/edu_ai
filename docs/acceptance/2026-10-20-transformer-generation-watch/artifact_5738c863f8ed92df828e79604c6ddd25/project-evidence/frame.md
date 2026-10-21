# frame.md — design truth

**Concept angle:** 把计算图摊在讲台上——一条被串起来的依赖链，和一张全连接的网，用同一套图示语言并排对比。整支片子的说服力来自「同一批方格，两种连接方式」的视觉反差，而不是术语卡片。

Course visual contract (`teaching-readable-v1`) is binding. Canvas 1920×1080. No photo, video, icon-font or external image assets: every visual is authored HTML/SVG.

## Canvas & palette

| Token | Value | Use |
| --- | --- | --- |
| `--hf-canvas` | `#0f172a` | full-bleed background of every frame |
| `--hf-ink` | `#f8fafc` | body text, diagram cell labels |
| `--hf-accent` | `#38bdf8` | parallel / direct-connection / structure semantics, eyebrow, rules |
| `--hf-wait` | `#fbbf24` | serial wait, cost, "must add" obligations |
| `--hf-muted` | `#94a3b8` | secondary notes, inactive cells, captions of diagrams |
| `--hf-line` | `rgba(148,163,184,0.30)` | hairline rules, inactive borders |
| `--hf-surface` | `rgba(248,250,252,0.045)` | panels, cards |
| `--hf-accent-soft` | `rgba(56,189,248,0.16)` | active accent fills, glow cores |

Semantics are fixed: **cyan = the new path (parallel, direct, structural); amber = the old path (serial, waiting, cost).** Never use amber for praise or cyan for a cost.

## Typography

Single family — the staged variable font covers both Chinese and Latin:

```css
@font-face{font-family:"Noto Sans SC";font-style:normal;font-weight:100 900;font-display:block;src:url("assets/fonts/NotoSansSC-Variable.ttf") format("truetype");}
```

This exact `@font-face` block must be declared **inside every frame's template**. `font-family: "Noto Sans SC", sans-serif;` — no other named family anywhere (no `Inter`, no CJK system names, no monospace families).

| Role | Size | Weight | Notes |
| --- | --- | --- | --- |
| Hero statement | 88–120px | 700 | max 2 lines, ≤ 14 chars/line |
| Scene title | 60–72px | 700 | one line |
| Diagram label | 30–34px | 500 | never below 28px |
| Formula | 44–56px | 500 | `h` with `<sub>` subscripts; letter-spacing 0.01em |
| Big number | 120–168px | 700 | `font-variant-numeric: tabular-nums` |
| Eyebrow / meta | 28px | 600 | letter-spacing 0.16em |
| Note | 30–32px | 400 | `--hf-muted` |

Line height 1.35 for body, 1.12 for display. Body text never goes below 32px; diagram labels never below 28px.

## Layout

- Frame padding: `88px` left/right, `72px` top. Content region: y `160–880`. **Nothing below y = 900** (caption keep-out; holds even without captions).
- Every frame opens with the same chrome, drawn inside the frame: eyebrow at top-left (`0N · <module name>`), and a hairline rule across `88 → 1832` at y ≈ 132 running `--hf-accent` 55% → transparent.
- Anchor to the left edge or split the frame (diagram left / reading right). Never centre-and-float a single cluster.
- Full-bleed ground: a `class="clip"` `<div>` at `inset:0` on track 0 holds `--hf-canvas` + the 48px grid + a radial accent glow + one ghost glyph. **Never paint the background on `#root`.**
- Two focal points minimum per frame: the diagram is one, the reading text the other.

## Background treatment (each frame owns its own)

1. Base fill `--hf-canvas`.
2. 48px grid: `repeating-linear-gradient` both axes, `rgba(148,163,184,0.075)`, masked with a radial fade so it dies toward the edges.
3. One radial glow (accent or amber, 0.10–0.22 peak) positioned off-centre, ambient breathing.
4. One ghost glyph (e.g. `h`, `O(n)`, `N×`) at 5–8% opacity, 380–460px, weight 800, slow drift.

## Components

- `.panel` — `--hf-surface`, `2px solid rgba(56,189,248,0.22)`, radius 20px, padding 32–40px.
- `.cell` — 96×96 (serial chain) or 84×84 (compact), radius 16px, `2px` border, label 32px, weight 600. Inactive: `--hf-line` border, `--hf-ink` at 70%. Active-serial: amber border + `rgba(251,191,36,0.12)` fill + soft amber shadow. Active-parallel: `--hf-accent` border + `--hf-accent-soft` fill.
- `.chip` — pill, padding `10px 24px`, radius 999px, `2px` border, 30px label, weight 500.
- `.tag` — small square/uppercase-ish label for `t = 1…n`, 28px, `--hf-muted`.
- `.link` — SVG hairline, `3px` stroke, `vector-effect: non-scaling-stroke`, arrowhead marker; amber = serial dependency, cyan = direct attention path.
- Every connector is honest SVG geometry with authored coordinates — no CSS borders pretending to be arrows.

## Motion

- Entrance only (`fromTo`), 0.35–0.6s, overlapping: `power3.out`, `power2.inOut`, `back.out(1.6)` used on different elements in the same scene. No exit tweens (non-final frames are unmounted by the timeline).
- Reveals are paced to the narration: the scene's diagram arrives first, then each named result lands as the voice reaches it. Never dump the whole canvas in the first 25%.
- Ambient motion on background only: glow breathe and ghost drift, finite repeat counts (`repeat: Math.max(0, Math.floor(duration / cycle) - 1)`), `yoyo: true`.
- No CSS `transition`, no `display`/`visibility` tweens, no `autoAlpha` on `.clip`, no `Math.random`, no `Date.now`.
- Animate transforms and opacity: `x`, `y`, `scale`, `rotation`, `opacity`, `strokeDashoffset`, `clipPath`, `filter: blur()`.

## Frame-specific art direction

| Frame | Diagram idea |
| --- | --- |
| 01 | Title statement, then three question chips land in sequence: 串行的代价 / 架构决策 / 需要补什么 |
| 02 | One row of six position cells with `x₁…x₆` underneath; curved amber arrows `h₁→h₂→h₃…`; formula card `h_t = f(h_{t−1}, x_t)` |
| 03 | Same row becomes a time axis: a playhead steps cell by cell, each arrow draws only when its predecessor completes; a step counter counts `1 / n` |
| 04 | Split comparison: left serial staircase (amber, `O(n)` steps), right all-to-all fan (cyan, `1` step); step counts count up |
| 05 | The decision: `循环` and `卷积` chips get struck through, `注意力` + `逐位置前馈` chips lift into place at the centre |
| 06 | Three numbered result tiles assemble (消除串行瓶颈 / 建立直接连接 / 统一计算模式), each with a 3-element micro-diagram |
| 07 | Bag-of-positions demo: two orderings of the same three word cells collapse into one identical pile; then position codes re-attach and the orders separate again |
| 08 | A layer stack (6 stacked bands) with a residual bypass arc on the right and LayerNorm bars; a degraded signal line without them vs a stable one with them |
| 09 | Proof + close: `8 × P100`, `12h`, then the two-line takeaway; the whole dependency chain from frame 03 re-draws small and turns cyan |

## Do / Don't

- **Do** keep one background language across all frames so cuts read as one lecture.
- **Do** keep diagram labels ≥ 28px and split a dense diagram across reveals instead of shrinking it.
- **Don't** put a narration sentence on screen; visible text is keywords, formulas, labels and numerals only.
- **Don't** use gradient text, left accent stripes on cards, or a uniform card grid with identical weights.
- **Don't** name a font that has no file in `assets/fonts/`.
