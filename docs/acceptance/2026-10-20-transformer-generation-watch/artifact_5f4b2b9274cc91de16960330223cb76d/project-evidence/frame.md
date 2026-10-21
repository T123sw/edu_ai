---
version: alpha
name: 自注意力课堂帧 — 深色矩阵画布 (Teaching Matrix)
description: >
  Course visual contract for a Chinese Transformer teaching video. The unit is the frame (1920×1080).
  A dark navy ground carries one faint lattice; information is always drawn as MATRIX CELLS, arrows and
  weight bars — never stock photos. Cyan is the primary accent and means "the thing being computed now";
  Q is cyan, K is green, V is violet and those three role colours never change across scenes. Numbers are
  tabular and always set in the accent-warm tone so a viewer can check the arithmetic by eye.
unit: the frame — 1920×1080 landscape
principle: one idea per step · split dense diagrams into steps · never shrink type to fit a diagram
concept angle: 课堂投影幕 —— 在黑板上一步步写公式，每一步只增加一层信息
---

# Design truth

This file is brand truth for colour, type, spacing and component geometry. The storyboard block owns
content. When they disagree on content the block wins; on style this file wins.

## Canvas & ground

- Canvas 1920×1080 (`data-width="1920" data-height="1080"`). Every frame paints its own full-bleed
  background `clip` layer (`position:absolute; inset:0`) — never rely on the root for the ground.
- Ground: flat `#0f172a`, plus ONE faint lattice: 60px grid lines at `rgba(148,163,184,0.06)` and a single
  soft radial glow `rgba(56,189,248,0.10)` behind the focal region. No photographic texture, no noise, no
  second glow.
- Safe margins: 96px left/right, 72px top, 84px bottom. Nothing important enters 40px of any edge.

## Colours

```yaml
colors:
  bg: "#0f172a"          # canvas ground
  surface: "#16213a"     # panel / card
  surface-2: "#1e293b"   # matrix cell, bar track
  ink: "#f8fafc"         # primary text
  muted: "#94a3b8"       # secondary text, captions, axis labels
  line: "rgba(248,250,252,0.14)"   # hairlines only
  accent: "#38bdf8"      # PRIMARY accent — and the Q colour, always
  key: "#34d399"         # K colour only
  value: "#a78bfa"       # V colour only
  warm: "#fbbf24"        # numbers / the value being read right now
  danger: "#f87171"      # only for "梯度接近 0" warnings
```

Never recolour Q/K/V per scene: Q is always `accent`, K always `key`, V always `value`. Heat cells use the
accent at 8–70% alpha to encode magnitude (four or five discrete steps, no random values).

## Typography

Local shipped font — put this exact face inside each frame's `<template>` `<style>`:

```css
@font-face{font-family:"Noto Sans SC";font-style:normal;font-weight:100 900;font-display:block;src:url("assets/fonts/NotoSansSC-Variable.ttf") format("truetype");}
```

`font-family: "Noto Sans SC", system-ui, sans-serif` everywhere. Numbers and formulas add
`font-variant-numeric: tabular-nums`. Do not name any other font family (no other family is bundled).

| role          | px  | weight | line-height | notes                                            |
| ------------- | --- | ------ | ----------- | ------------------------------------------------ |
| display       | 96  | 700    | 1.10        | opening / closing title only                     |
| title         | 64  | 700    | 1.20        | scene title, top of every frame                  |
| headline      | 48  | 600    | 1.25        | formula line, section statement (≥ 48px rule)    |
| body          | 36  | 400    | 1.55        | explanation text                                 |
| label         | 28  | 500    | 1.35        | diagram labels, axis text, role tags (≥ 28px)    |
| numeral       | 32  | 600    | 1.20        | matrix cell values, tabular                      |
| footer-rail   | 28  | 400    | 1.20        | "3 · Q/K/V 为什么" style scene index, muted      |

Hard minimums: body/text 32px, diagram labels 28px, titles 48px. If a diagram does not fit at those sizes,
split it into two frames — never shrink below the minimum. No `<br>` in body text; use block spans.

## Layout grammar

- **Title band** — top-left at `(96, 72)`: scene title (64px) and, 12px beneath, a muted 28px kicker naming
  the step ("步骤 2 / 4 · 除以 √dk"). A 2px accent underline 96px wide sits under the kicker.
- **Stage** — the content region is `y = 220 … 940`, full width inside the margins. One focal group only.
- **Footer rail** — bottom-left `(96, 992)`: `第 N 节 · <scene slug>` in muted 28px; bottom-right: the video
  chapter label `自注意力与多头注意力` in muted 28px. Keep both subtle; they are orientation, not content.
- **Step ladder** — when a frame shows a 3–4 step computation, put a step badge row above the stage:
  56px circles, 1px `line` border, the active one filled `accent` with `bg` numerals. Steps already done show
  a muted check, steps not yet reached stay at 35% opacity.
- **Two-zone split** — for a "before → after" matrix step, left zone = input matrix, right zone = result
  matrix, a 64px arrow (`accent`, 3px stroke, arrowhead marker) between them. Left zone starts at x=140,
  right zone right-aligned to x=1780.

## Components (reuse these, do not invent new chrome)

- `matrix-block` — label (28px, muted, above) + rows of cells. Cell: 76×76 (4 cols) or 96×96 (3 cols),
  `border-radius: 8px`, `background: #1e293b`, `border: 1px solid rgba(248,250,252,0.10)`, value centred in
  32px `numeral`/tabular. Row labels (token names) sit 24px left of the first cell in 28px muted text; column
  labels sit 12px above in 28px muted text. A matrix's shape caption (`3 × 4`) sits beneath it in 28px muted.
- `heat-cell` — the same cell with `background: rgba(56,189,248,0.10…0.62)` and value in `ink`; the
  most-attended cell in a row may add a 2px `accent` outline.
- `role-tag` — pill, 28px, 8px/18px padding, `border-radius: 999px`, tinted background at 16% of its role
  colour, text in the role colour, 600 weight. Role tags read `Q · 发问`, `K · 被匹配`, `V · 内容`.
- `formula` — 48px `headline`, `ink`; the operator that is being executed on this frame is the only part in
  `accent`; a `warm` box may underline the numeric result. No LaTeX — plain spans and superscripts.
- `arrow` — inline SVG, 3px `accent` stroke, small arrowhead, `pathLength` dash-drawn where it animates.
- `weight-bars` — horizontal bars, 40px tall, 12px gap, `surface-2` track with an `accent` fill scaled by
  `scaleX` (never tween width), 28px label to the left, 32px tabular value to the right.
- `callout` — `surface` panel, `border-left: 4px solid accent` (or `danger` for a warning), 24px padding,
  36px `body`. Used once per frame at most.

## Motion posture (doctrine)

- Calm, legible, teacher-paced. Reveals follow the narration clause-by-clause; nothing arrives before it is
  mentioned and nothing freezes for more than ~4s without a small read-in (a subtle 0→1 opacity, a scaleX
  bar settle, a colour tick on a cell).
- One paused GSAP timeline per frame, `fromTo` with explicit from-states, `power2.out` / `power3.out`
  entrances at 0.45–0.7s, group staggers capped at 0.5s total. No `Math.random`, no CSS transitions on
  animated nodes, no `autoAlpha`/`visibility` on `.clip`.
- Entrances: cells/rows appear a row at a time (stagger 0.08–0.12s); arrows draw on (`stroke-dashoffset`);
  bars grow with `scaleX` from a left origin; the executing number pulses to `warm` once, then holds.
- No scene-exit animation — the orchestrator owns seams. End each frame settled and readable.

## What this design forbids

- Photographic or stock imagery, decorative icons unrelated to the maths, drop shadows, glassmorphism.
- Font sizes below the minimums above, dense formula walls, or three focal groups in one frame.
- Any hidden dependency on network fonts, remote images or audio.
