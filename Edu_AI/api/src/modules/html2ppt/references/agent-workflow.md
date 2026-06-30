# Agent Workflow

## Planner

The planner reads runtime content, catalogs, and references, then writes `deck_design_plan.md`.

The planner decides:

- Deck metadata.
- Design specification.
- Slide-by-slide layout and component plan.

## Slide Executor

The slide executor reads the deck plan, source content, catalogs, theme CSS, and restrictions. In parallel generation mode it writes exactly one slide fragment.

The slide executor executes the plan; it does not redefine the deck strategy. Keep prompt rules short. Use catalog teaching recipes, the focused catalog summary, and the selected template as the detailed contract. If a page exceeds capacity, follow the declared fallback or split guidance instead of forcing all content into one slide.

Slide display text must be compressed into short phrases, labels, short actions, or keywords. 教学表达的显示文案和显示层必须压缩成短句、标签、短动作或关键词。Notes/讲稿 are used for understanding and should not be pasted into the visible slide. Every input Block needs a visible carrier, especially Definition（定义）, Compare（对比）, Process（流程）, Analogy（类比）, and Takeaway（结论） content.
Sparse-prone layouts must not emit hollow shells: if `standard_text`, `standard_text_process_track`, `card_layout`, or other conditional layouts cannot fill their second-layer explanation/example slots, the executor should follow the declared fallback.

## Revision Executor

The revision executor rewrites exactly one slide using the latest successful deck, original slide HTML, neighboring manifest entries, deck plan, catalogs, and user revision input.
