# Final review save recovery fixes

Both Important findings in `final-review-report.md` are addressed. No backend or production mutations and no commits were made.

## Changes

- `frontend/src/pbl/usePblWorkspace.ts`: replace the binary conflict guard with explicit `none`, `needs_read`, and `awaiting_choice` states. A failed server read remains protected from writes, while the existing visible **同步** action and browser `online` handler retry that read. The failure message explicitly names the action. A successful retry exposes the existing resolution controls without replacing either copy. Choosing a copy still retains the other as a recoverable backup.
- The same hook now rechecks both workspace and report queues after every operation. Edits made during a report POST therefore trigger a subsequent workspace PUT even if their debounce fired while the report was pending. `已保存` is emitted after the combined drain completes. Existing immutable pending mutations remain intact for uncertain-response replay. Dirty comparison includes the persisted active task as well as files/custom input.
- `frontend/tests/live-learning/pbl.spec.ts`: four targeted regressions reuse the fixture/editor helpers: conflict GET failure followed by manual recovery; the same failure followed by online recovery; deferred report POST plus editing beyond debounce and a gated follow-up PUT; accepted mutation with lost response followed by identical replay and a second mutation for newer edits. Existing tests were left unchanged apart from whitespace.

## Checks

All commands ran from `frontend/` with `PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH`. Browser tests used the default PBL dev server at port 5207, not production port 5208.

- `pnpm exec playwright test --config playwright.pbl.config.ts pbl.spec.ts --grep '延迟保存|离线草稿|冲突读取失败|报告上传期间'`: **5 passed (43.4 s)**. Covers both existing delayed-save/offline regressions and three new recovery/drain cases.
- `pnpm exec playwright test --config playwright.pbl.config.ts pbl.spec.ts --grep '保存响应丢失'`: **1 passed (8.1 s)**. The second PUT exactly matches the first mutation/payload; the third uses a new mutation ID at revision 1 and saves the newest code.
- `pnpm exec eslint src/pbl/usePblWorkspace.ts tests/live-learning/pbl.spec.ts`: **passed**.
- `pnpm exec tsc -p /tmp/pbl-save-fix-tsconfig.json`: **passed** with a temporary config extending the frontend tsconfig, an absolute `types` entry for `frontend/node_modules/vite/client`, and an include for the changed hook. Its imported production dependencies are checked as well.
- Plain `pnpm exec tsc --noEmit`: **blocked by existing broad repository errors**, including TS5097 test imports and unrelated generation/store test type errors. Initial temporary focused configs omitted Vite declarations and failed on `ImportMeta.env`; explicitly loading `vite/client` fixed that check configuration.

No backend suites were repeated. Production build/smoke remains with the root agent.
