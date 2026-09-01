# Teacher Chat Main Area Beautification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beautify the teacher workspace middle chat area so it reads as the primary teacher Q&A work area, with a lighter top control layer, a cleaner message stage, and a clearer bottom action/input zone without changing the underlying chat workflows.

**Architecture:** Keep `ChatPanel.tsx` as the single behavior owner for chat sending, streaming updates, history loading, workflow polling, and attachment input, but shift its presentation away from inline-heavy shell styling toward a clearer three-part structure: light controls, message stage, and stable composer. Implementation must explicitly use the frontend beautification skills in sequence: `frontend-design` for the overall tone, `arrange` for the three-layer visual hierarchy, `colorize` for restrained neutral/accent tuning, and `polish` for the final spacing/alignment/detail pass. If `npx openskills` cannot load those skills in this environment, read the local `SKILL.md` files directly before implementation.

**Tech Stack:** React 18, TypeScript, Ant Design, component-scoped CSS, Vite, `node:test`

---

## File Structure

- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
  - Remove the top status card from the render tree, introduce semantic wrappers for the top controls, message-stage shell, and composer shell, and preserve all existing chat/workflow behaviors.
- Create: `frontend/src/components/teacher/ChatPanel.css`
  - Hold the dedicated middle-panel visual language: top control strip, message rhythm, avatar tone, bubble hierarchy, and the stable bottom composer shell.
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`
  - Keep coverage for readable user-facing chat copy after the middle-panel refactor.
- Create: `frontend/tests/frontend/chatPanel.layout.test.ts`
  - Add source-level regression checks for the new middle-area shell and the removal of the status-card render.

## Skill Execution Notes

Before editing implementation files, the worker must explicitly load and follow these skills:

1. `frontend-design`
   - Lock the middle panel to a calm, professional, teacher-workspace tone rather than social-chat styling.
2. `arrange`
   - Shape the three-part rhythm: light top controls, dominant message stage, stable composer.
3. `colorize`
   - Keep the palette restrained while clarifying hierarchy between AI replies, user replies, and controls.
4. `polish`
   - Run a final pass on message spacing, avatar weight, composer presence, and button alignment.

If `npx openskills read <skill>` fails for these design skills, load the local skill files instead:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\frontend-design\SKILL.md -TotalCount 200
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\arrange\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\colorize\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\polish\SKILL.md -TotalCount 180
```

Do not rewrite chat business logic, conversation history behavior, workflow polling, or attachment upload logic during this plan.

### Task 1: Add failing regressions for the new middle-area shell

**Files:**
- Create: `frontend/tests/frontend/chatPanel.layout.test.ts`
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`

- [ ] **Step 1: Write the failing layout regression**

Create `frontend/tests/frontend/chatPanel.layout.test.ts`:

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanel = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanel,
  /chat-panel/,
  'ChatPanel should render the dedicated chat-panel root class for the beautified middle area',
);

assert.match(
  chatPanel,
  /chat-panel__controls/,
  'ChatPanel should render a dedicated light control layer above the message stage',
);

assert.match(
  chatPanel,
  /chat-panel__messages/,
  'ChatPanel should render a dedicated message-stage shell',
);

assert.match(
  chatPanel,
  /chat-panel__composer/,
  'ChatPanel should render a dedicated bottom composer shell',
);

assert.doesNotMatch(
  chatPanel,
  /<StatusCard\s/,
  'ChatPanel should remove the top status card from the middle conversation area',
);

console.log('chatPanel.layout tests passed');
```

- [ ] **Step 2: Extend text-safety coverage for the middle panel**

Keep `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts` aligned with the current readable chat copy by ensuring it still checks the visible composer placeholder:

```ts
assert.match(
  chatPanelFile,
  /\u5f00\u59cb\u8f93\u5165\u95ee\u9898\u2026\uff08Shift \+ Enter \u6362\u884c\uff09/,
  'ChatPanel should render readable composer placeholder copy',
);
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
node --test tests/frontend/chatPanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts
```

Expected: FAIL because the current middle-area shell does not yet contain the new structural classes and still carries the previous inline-heavy shell.

- [ ] **Step 4: Commit the red test checkpoint**

```bash
git add frontend/tests/frontend/chatPanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "test: cover beautified teacher chat main area"
```

### Task 2: Remove the status-card shell and introduce semantic middle-area structure

**Files:**
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`

- [ ] **Step 1: Load the required beautification skills**

Run one of these paths:

```bash
npx openskills read frontend-design
npx openskills read arrange
npx openskills read colorize
```

If those commands fail, run:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\frontend-design\SKILL.md -TotalCount 200
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\arrange\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\colorize\SKILL.md -TotalCount 160
```

Expected: the design guidance is available before editing the component.

- [ ] **Step 2: Import the dedicated stylesheet**

Add this import near the top of `frontend/src/components/teacher/ChatPanel.tsx`:

```ts
import './ChatPanel.css';
```

- [ ] **Step 3: Remove the status-card render from the middle area**

Delete the status-card import and render call:

```tsx
// remove:
import StatusCard from './StatusCardV2';

// remove:
<StatusCard statusCard={statusCard} onActionSelect={handleSuggestedAction} />
```

Do not remove `statusCard` store wiring in this task if other flows still write to it; this task only removes the middle-area visual card.

- [ ] **Step 4: Wrap the top control strip in a semantic shell**

Refactor the top toolbar wrapper into a semantic light-control layer:

```tsx
<div className="chat-panel__controls">
  <div className="chat-panel__controls-main">
    <Space size="middle" wrap>
      {/* existing RAG / Web switches and conversation controls */}
    </Space>
  </div>
</div>
```

Keep the existing `Switch`, `Button`, and `Popover` behaviors unchanged.

- [ ] **Step 5: Wrap the message list in a dedicated message-stage shell**

Replace the inline message scroll wrapper with:

```tsx
<div className="chat-panel__messages">
  <div className="chat-panel__messages-scroll">
    <List
      dataSource={messages}
      renderItem={(item, index) => (
        <List.Item
          key={index}
          className={`chat-panel__message-row chat-panel__message-row--${item.user === 'You' ? 'user' : 'ai'}`}
        >
          {/* existing avatar + message content structure, now with class names */}
        </List.Item>
      )}
    />
    <div ref={chatEndRef} />
  </div>
</div>
```

- [ ] **Step 6: Wrap the composer in a dedicated bottom shell**

Refactor the existing bottom input area into:

```tsx
<div className="chat-panel__composer">
  <div className="chat-panel__composer-inner">
    {/* existing text area, attachment buttons, voice button, send button */}
  </div>
</div>
```

Preserve the existing handlers and button actions.

- [ ] **Step 7: Run the focused layout and text tests**

Run:

```bash
node --test tests/frontend/chatPanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit the structural refactor**

```bash
git add frontend/src/components/teacher/ChatPanel.tsx frontend/tests/frontend/chatPanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "feat: restructure teacher chat main area shell"
```

### Task 3: Implement the middle-area visual language in a dedicated stylesheet

**Files:**
- Create: `frontend/src/components/teacher/ChatPanel.css`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`

- [ ] **Step 1: Create the stylesheet shell**

Create `frontend/src/components/teacher/ChatPanel.css` with the core layers:

```css
.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
}

.chat-panel__controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 8px 12px 12px;
}

.chat-panel__messages {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-panel__messages-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 12px 20px;
}

.chat-panel__composer {
  padding: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.84);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(250, 251, 253, 0.98) 100%);
}
```

- [ ] **Step 2: Add message-row, avatar, and bubble classes to the JSX**

Update the message render block so the avatar and bubble wrappers carry semantic classes:

```tsx
<div className={`chat-panel__message-shell chat-panel__message-shell--${item.user === 'You' ? 'user' : 'ai'}`}>
  <div className={`chat-panel__avatar chat-panel__avatar--${item.user === 'You' ? 'user' : 'ai'}`}>
    {item.user === 'You' ? '?' : 'AI'}
  </div>
  <div className="chat-panel__message-content">
    {item.user === 'AI' && item.statusText && (
      <div className="chat-panel__status-text">{item.statusText}</div>
    )}
    {item.text ? (
      <div className={`chat-panel__bubble chat-panel__bubble--${item.user === 'You' ? 'user' : 'ai'}`}>
        {/* existing markdown / text rendering */}
      </div>
    ) : null}
  </div>
</div>
```

- [ ] **Step 3: Implement the calmer message-stage styling**

Extend `frontend/src/components/teacher/ChatPanel.css` with:

```css
.chat-panel__message-row {
  border: none !important;
  padding: 0 !important;
  margin-bottom: 18px;
}

.chat-panel__message-shell {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  max-width: 100%;
}

.chat-panel__message-shell--user {
  flex-direction: row-reverse;
}

.chat-panel__avatar {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
}

.chat-panel__avatar--user {
  background: #dbeafe;
  color: #1d4ed8;
}

.chat-panel__avatar--ai {
  background: #ede9fe;
  color: #6d28d9;
}

.chat-panel__bubble {
  width: fit-content;
  max-width: min(80vw, 720px);
  padding: 12px 16px;
  border-radius: 14px;
  line-height: 1.72;
  word-break: break-word;
}

.chat-panel__bubble--user {
  background: #2563eb;
  color: #ffffff;
}

.chat-panel__bubble--ai {
  background: #f8fafc;
  color: #0f172a;
  border: 1px solid rgba(226, 232, 240, 0.86);
}
```

- [ ] **Step 4: Style the lighter top control layer**

Add control-strip styling:

```css
.chat-panel__controls .ant-space {
  gap: 10px !important;
}

.chat-panel__controls .ant-btn,
.chat-panel__controls .ant-switch {
  box-shadow: none;
}

.chat-panel__controls .ant-btn {
  border-radius: 8px;
  border-color: rgba(203, 213, 225, 0.82);
  background: rgba(255, 255, 255, 0.86);
}
```

- [ ] **Step 5: Style the stable bottom composer shell**

Add composer styling:

```css
.chat-panel__composer-inner {
  border: 1px solid rgba(203, 213, 225, 0.86);
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.04);
}

.chat-panel__composer .ant-input,
.chat-panel__composer .ant-input-affix-wrapper,
.chat-panel__composer textarea {
  border: none !important;
  box-shadow: none !important;
}
```

- [ ] **Step 6: Run the targeted layout, text, and conversation regressions**

Run:

```bash
node --test tests/frontend/chatPanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts tests/frontend/chatPanel.conversation-reference.test.ts tests/frontend/chatPanel.workflow-polling.test.ts
```

Expected: PASS. If `chatPanel.workflow-polling.test.ts` still fails due to a stale source-level regex unrelated to the beautification, update only that test’s assertion pattern to match the current existing polling logic without changing behavior.

- [ ] **Step 7: Commit the visual-language pass**

```bash
git add frontend/src/components/teacher/ChatPanel.tsx frontend/src/components/teacher/ChatPanel.css frontend/tests/frontend/chatPanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts frontend/tests/frontend/chatPanel.workflow-polling.test.ts
git commit -m "style: beautify teacher chat main area"
```

### Task 4: Polish spacing, input emphasis, and remaining regression edges

**Files:**
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Modify: `frontend/src/components/teacher/ChatPanel.css`
- Modify: `frontend/tests/frontend/chatPanel.workflow-polling.test.ts` (only if needed)

- [ ] **Step 1: Load the final polish guidance**

Run one of these:

```bash
npx openskills read polish
```

If that fails, run:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\polish\SKILL.md -TotalCount 180
```

- [ ] **Step 2: Tighten the final spacing and alignment details**

Apply final polish to:

```css
.chat-panel__messages-scroll {
  padding-top: 2px;
  padding-bottom: 18px;
}

.chat-panel__message-row:last-child {
  margin-bottom: 8px;
}

.chat-panel__status-text {
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
}
```

And ensure the composer controls align cleanly with the send button and attachment buttons after the shell refactor.

- [ ] **Step 3: Update the workflow polling source-level test only if it is stale**

If `frontend/tests/frontend/chatPanel.workflow-polling.test.ts` still fails despite unchanged behavior, update only the assertion regex to match the current code shape, for example:

```ts
assert.match(
  chatPanelFile,
  /if \(!currentConversationId \|\| workflowType !== 'ppt' \|\| workflowStatus !== 'running'\)/,
  'ChatPanel should track running PPT workflows before polling conversation detail',
);
```

Do not change runtime polling behavior in this step unless there is an actual product bug.

- [ ] **Step 4: Run the full middle-area verification**

Run:

```bash
node --test tests/frontend/chatPanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts tests/frontend/chatPanel.conversation-reference.test.ts tests/frontend/chatPanel.workflow-polling.test.ts tests/frontend/chatPanel.image-input.test.ts tests/frontend/chatPanel.video-input.test.ts
npm run build
```

Expected:

- all listed tests PASS
- Vite build PASS

- [ ] **Step 5: Commit the polish pass**

```bash
git add frontend/src/components/teacher/ChatPanel.tsx frontend/src/components/teacher/ChatPanel.css frontend/tests/frontend/chatPanel.layout.test.ts frontend/tests/frontend/chatPanel.workflow-polling.test.ts
git commit -m "style: polish teacher chat main area"
```

## Self-Review

Spec coverage check:

- Remove the top status card: covered in Task 2.
- Light top control layer: covered in Tasks 2 and 3.
- Message stage as the dominant area: covered in Tasks 2 and 3.
- Stable bottom input zone: covered in Tasks 2 and 3.
- Keep business logic untouched: enforced across all tasks and validated in Task 4.

Placeholder scan:

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-changing step includes concrete code or explicit commands.

Type consistency:

- The new semantic classes referenced in tests (`chat-panel`, `chat-panel__controls`, `chat-panel__messages`, `chat-panel__composer`) are defined in the implementation tasks.
- The polling test adjustment only targets assertion shape, not production logic names.
