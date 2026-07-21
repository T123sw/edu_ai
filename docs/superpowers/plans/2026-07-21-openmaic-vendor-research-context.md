# OpenMAIC Vendor Baseline and researchContext Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor the clean OpenMAIC `b516427d` snapshot into `openmaic-sidecar/` and add the three minimal seams that accept, forward, and merge an external `researchContext`.

**Architecture:** OpenMAIC remains an ordinary directory tracked by the edu_ai repository, with no nested Git metadata. The upstream snapshot is committed separately from the local seam; the seam adds one optional input field, route forwarding, and a deterministic Web-plus-external context merge before outline generation.

**Tech Stack:** Git archive, PowerShell, Node.js 22, pnpm 10, Next.js 16, TypeScript, Vitest.

---

### Task 1: Import the clean OpenMAIC baseline

**Files:**
- Create: `openmaic-sidecar/**` from upstream commit `b516427d272364f07cc54e5eb9c8a66278e827b3`

- [ ] **Step 1: Verify the source commit and destination boundary**

Run from the edu_ai worktree root:

```powershell
$upstream = 'D:\github\OpenMAIC'
$commit = 'b516427d272364f07cc54e5eb9c8a66278e827b3'
$destination = (Join-Path (git rev-parse --show-toplevel) 'openmaic-sidecar')

git -C $upstream cat-file -e "$commit^{commit}"
if ($destination -notlike "$(git rev-parse --show-toplevel)*") {
  throw "Destination escaped worktree: $destination"
}
if (Test-Path (Join-Path $destination '.git')) {
  throw 'Nested .git is forbidden'
}
```

Expected: `cat-file` exits 0, the destination resolves inside this worktree, and no nested `.git` exists.

- [ ] **Step 2: Export the exact committed snapshot**

```powershell
$archive = Join-Path $env:TEMP 'openmaic-b516427d.tar'
if (Test-Path $archive) { Remove-Item -LiteralPath $archive }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
git -C $upstream archive --format=tar --output=$archive $commit
tar -xf $archive -C $destination
Remove-Item -LiteralPath $archive
```

Expected: `openmaic-sidecar/package.json`, `.env.example`, `.github/`, `app/`, `lib/`, `packages/`, and `tests/` exist; `.git` does not.

- [ ] **Step 3: Verify the imported path set equals the upstream tree**

```powershell
$sourcePaths = @(git -C $upstream ls-tree -r --name-only $commit)
$vendorPaths = @(Get-ChildItem -LiteralPath $destination -Recurse -Force -File |
  ForEach-Object { $_.FullName.Substring($destination.Length + 1).Replace('\', '/') })
$delta = @(Compare-Object $sourcePaths $vendorPaths)

if ($sourcePaths.Count -ne 1419) { throw "Unexpected upstream count: $($sourcePaths.Count)" }
if ($delta.Count -ne 0) { $delta | Format-Table; throw 'Vendor path set differs from upstream' }
```

Expected: upstream count is `1419` and `$delta.Count` is `0`.

- [ ] **Step 4: Verify local secrets and generated files remain ignored**

```powershell
git check-ignore -v openmaic-sidecar/.env
git check-ignore -v openmaic-sidecar/node_modules/example
git check-ignore -v openmaic-sidecar/.next/example
git check-ignore -v openmaic-sidecar/dev.log
git check-ignore openmaic-sidecar/.env.example
```

Expected: the first four paths print matching ignore rules; the final `.env.example` check prints nothing and exits non-zero because the example must be trackable.

- [ ] **Step 5: Stage and verify all upstream files**

```powershell
git add -- openmaic-sidecar
$staged = @(git diff --cached --name-only -- openmaic-sidecar)
if ($staged.Count -ne 1419) { throw "Expected 1419 staged vendor files, got $($staged.Count)" }
git diff --cached --check
```

Expected: exactly `1419` vendor files are staged and `git diff --cached --check` is silent.

- [ ] **Step 6: Commit the immutable vendor baseline**

```powershell
git commit -m "chore: vendor OpenMAIC at b516427d"
git status --short
```

Expected: commit succeeds and the worktree is clean.

### Task 2: Install the vendored Node workspace and establish RED tests

**Files:**
- Create: `openmaic-sidecar/tests/server/classroom-research-context.test.ts`

- [ ] **Step 1: Install exactly the locked dependencies**

```powershell
conda run -n openmaic --no-capture-output pnpm install --frozen-lockfile
```

Run from `openmaic-sidecar/`.

Expected: install and postinstall complete; generated `node_modules/`, `.next/`, and `public/vendor/maic-importer/` stay ignored.

- [ ] **Step 2: Establish the clean upstream Vitest baseline**

```powershell
conda run -n openmaic --no-capture-output pnpm test
```

Expected: the complete upstream suite exits 0 before any local behavior test or production change is added. If it fails, stop and report the baseline failure before proceeding.

- [ ] **Step 3: Write the failing researchContext behavior tests**

Create `openmaic-sidecar/tests/server/classroom-research-context.test.ts` with:

```typescript
import { describe, expect, it } from 'vitest';
import { buildGenerateClassroomInput } from '@/app/api/generate-classroom/route';
import {
  mergeResearchContexts,
  type GenerateClassroomInput,
} from '@/lib/server/classroom-generation';

describe('generate-classroom researchContext route input', () => {
  it('forwards a non-empty external research context', () => {
    const rawBody = {
      requirement: 'Teach binary search',
      researchContext: 'RAG: binary search halves the interval.',
    } as Partial<GenerateClassroomInput> & { researchContext?: string };

    expect(buildGenerateClassroomInput(rawBody)).toMatchObject({
      requirement: 'Teach binary search',
      researchContext: 'RAG: binary search halves the interval.',
    });
  });

  it('omits an empty external research context', () => {
    const rawBody = {
      requirement: 'Teach binary search',
      researchContext: '',
    } as Partial<GenerateClassroomInput> & { researchContext?: string };

    expect(buildGenerateClassroomInput(rawBody)).not.toHaveProperty('researchContext');
  });
});

describe('generate-classroom research context merge', () => {
  it('appends injected context after web context', () => {
    expect(mergeResearchContexts('WEB: current source', 'RAG: course source')).toBe(
      'WEB: current source\n\nRAG: course source',
    );
  });

  it('keeps web context when injected context is absent', () => {
    expect(mergeResearchContexts('WEB: current source', undefined)).toBe('WEB: current source');
  });

  it('keeps injected context when web context is absent', () => {
    expect(mergeResearchContexts(undefined, 'RAG: course source')).toBe('RAG: course source');
  });

  it('returns undefined when both contexts are absent', () => {
    expect(mergeResearchContexts(undefined, undefined)).toBeUndefined();
  });
});
```

- [ ] **Step 4: Run the focused test and verify RED**

```powershell
conda run -n openmaic --no-capture-output pnpm test tests/server/classroom-research-context.test.ts
```

Expected: FAIL because `buildGenerateClassroomInput` and `mergeResearchContexts` are not exported. The failure must be about the missing seam, not dependency resolution or syntax.

- [ ] **Step 5: Confirm generated install artifacts did not enter Git status**

```powershell
git status --short
```

Expected: only `tests/server/classroom-research-context.test.ts` is untracked.

### Task 3: Implement the three minimal researchContext seams

**Files:**
- Modify: `openmaic-sidecar/lib/server/classroom-generation.ts`
- Modify: `openmaic-sidecar/app/api/generate-classroom/route.ts`
- Test: `openmaic-sidecar/tests/server/classroom-research-context.test.ts`

- [ ] **Step 1: Add the optional input field and pure merge function**

In `openmaic-sidecar/lib/server/classroom-generation.ts`, add the field immediately after `pdfContent`:

```typescript
  researchContext?: string;
```

Add this exported helper immediately after `GenerateClassroomInput`:

```typescript
export function mergeResearchContexts(
  webContext: string | undefined,
  injectedContext: string | undefined,
): string | undefined {
  const contexts = [webContext, injectedContext].filter(
    (context): context is string => typeof context === 'string' && context.length > 0,
  );
  return contexts.length > 0 ? contexts.join('\n\n') : undefined;
}
```

After the existing Web search block and before the `generating_outlines` progress event, add:

```typescript
  researchContext = mergeResearchContexts(researchContext, input.researchContext);
```

This location is required: it preserves Web-search graceful degradation and guarantees external context is still used if Web search is disabled or fails.

- [ ] **Step 2: Extract route input construction and forward the field**

In `openmaic-sidecar/app/api/generate-classroom/route.ts`, add this function after `maxDuration`:

```typescript
export function buildGenerateClassroomInput(
  rawBody: Partial<GenerateClassroomInput>,
): GenerateClassroomInput {
  return {
    requirement: rawBody.requirement || '',
    ...(rawBody.pdfContent ? { pdfContent: rawBody.pdfContent } : {}),
    ...(rawBody.researchContext ? { researchContext: rawBody.researchContext } : {}),
    ...(rawBody.enableWebSearch != null ? { enableWebSearch: rawBody.enableWebSearch } : {}),
    ...(rawBody.webSearchProviderId ? { webSearchProviderId: rawBody.webSearchProviderId } : {}),
    ...(rawBody.webSearchApiKey ? { webSearchApiKey: rawBody.webSearchApiKey } : {}),
    ...(rawBody.baiduSubSources ? { baiduSubSources: rawBody.baiduSubSources } : {}),
    ...(rawBody.enableImageGeneration != null
      ? { enableImageGeneration: rawBody.enableImageGeneration }
      : {}),
    ...(rawBody.enableVideoGeneration != null
      ? { enableVideoGeneration: rawBody.enableVideoGeneration }
      : {}),
    ...(rawBody.enableTTS != null ? { enableTTS: rawBody.enableTTS } : {}),
    ...(rawBody.agentMode ? { agentMode: rawBody.agentMode } : {}),
  };
}
```

Replace the current inline `const body: GenerateClassroomInput = { ... };` block in `POST` with:

```typescript
    const body = buildGenerateClassroomInput(rawBody);
```

- [ ] **Step 3: Run the focused test and verify GREEN**

```powershell
conda run -n openmaic --no-capture-output pnpm test tests/server/classroom-research-context.test.ts
```

Expected: `6 passed` and no test failures.

- [ ] **Step 4: Run the TypeScript checker**

```powershell
conda run -n openmaic --no-capture-output pnpm exec tsc --noEmit
```

Expected: exit 0 with no TypeScript errors.

- [ ] **Step 5: Check formatting of the touched TypeScript files**

```powershell
conda run -n openmaic --no-capture-output pnpm exec prettier --check `
  app/api/generate-classroom/route.ts `
  lib/server/classroom-generation.ts `
  tests/server/classroom-research-context.test.ts
```

Expected: all three files pass formatting. Do not add validation, truncation, provider behavior, or other files.

### Task 4: Archive the local seam and commit it separately

**Files:**
- Create: `docs/spec/patches/openmaic-research-context.md`
- Create: `docs/spec/patches/openmaic-research-context.patch`
- Modify: `openmaic-sidecar/lib/server/classroom-generation.ts`
- Modify: `openmaic-sidecar/app/api/generate-classroom/route.ts`
- Create: `openmaic-sidecar/tests/server/classroom-research-context.test.ts`

- [ ] **Step 1: Write the patch provenance document**

Create `docs/spec/patches/openmaic-research-context.md` with:

```markdown
# OpenMAIC external researchContext patch

- Upstream: `https://github.com/THU-MAIC/OpenMAIC.git`
- Base commit: `b516427d272364f07cc54e5eb9c8a66278e827b3`
- Local owner: edu_ai Phase 2

## Purpose

Accept an optional external `researchContext` in `/api/generate-classroom`, preserve it in `GenerateClassroomInput`, and append it after any OpenMAIC Web-search context before outline generation.

## Invariants

- Web context is first; injected context is second.
- Sources are separated by two newline characters.
- Either source works alone.
- Missing sources preserve upstream behavior.
- Web-search failure does not discard injected context.

## Changed production files

- `openmaic-sidecar/app/api/generate-classroom/route.ts`
- `openmaic-sidecar/lib/server/classroom-generation.ts`

## Verification

```powershell
conda run -n openmaic --no-capture-output pnpm test tests/server/classroom-research-context.test.ts
conda run -n openmaic --no-capture-output pnpm exec tsc --noEmit
conda run -n openmaic --no-capture-output pnpm test
```

Run these commands from `openmaic-sidecar/`.

## Upgrade procedure

1. Import the new clean OpenMAIC snapshot as a standalone vendor-baseline commit.
2. Apply `docs/spec/patches/openmaic-research-context.patch` from the edu_ai repository root.
3. Resolve conflicts by preserving the invariants above.
4. Run the focused test, TypeScript check, and complete Vitest suite.
5. If upstream supports external context natively, remove the duplicate local seam and retain behavioral coverage.
```

- [ ] **Step 2: Generate a replayable patch from only the local seam**

Run from the edu_ai root before staging the seam:

```powershell
$patchPath = 'docs/spec/patches/openmaic-research-context.patch'
git diff --output=$patchPath -- `
  openmaic-sidecar/app/api/generate-classroom/route.ts `
  openmaic-sidecar/lib/server/classroom-generation.ts
```

Expected: the patch contains only the two production files and three conceptual changes: input field, route forwarding, and context merge.

- [ ] **Step 3: Verify the patch can be checked against the vendor baseline**

```powershell
git diff --check
git apply --check --reverse docs/spec/patches/openmaic-research-context.patch
```

Expected: both commands exit 0. Reverse-check success proves the patch matches the currently modified tree and can return it to the baseline.

- [ ] **Step 4: Stage only the seam, tests, and patch documentation**

```powershell
git add -- `
  openmaic-sidecar/app/api/generate-classroom/route.ts `
  openmaic-sidecar/lib/server/classroom-generation.ts `
  openmaic-sidecar/tests/server/classroom-research-context.test.ts `
  docs/spec/patches/openmaic-research-context.md `
  docs/spec/patches/openmaic-research-context.patch
git diff --cached --check
git diff --cached --stat
```

Expected: only the five listed paths are staged and the diff check is silent.

- [ ] **Step 5: Commit the local seam**

```powershell
git commit -m "feat(openmaic): accept external research context"
```

Expected: commit succeeds and remains separate from the vendor-baseline commit.

### Task 5: Verify the completed scoped delivery

**Files:**
- Verify only; no source changes expected.

- [ ] **Step 1: Run the focused researchContext tests**

```powershell
conda run -n openmaic --no-capture-output pnpm test tests/server/classroom-research-context.test.ts
```

Expected: `6 passed`.

- [ ] **Step 2: Run the complete OpenMAIC Vitest suite**

```powershell
conda run -n openmaic --no-capture-output pnpm test
```

Expected: all tests pass with exit 0.

- [ ] **Step 3: Run the TypeScript checker and production build**

```powershell
conda run -n openmaic --no-capture-output pnpm exec tsc --noEmit
conda run -n openmaic --no-capture-output pnpm build
```

Expected: both commands exit 0.

- [ ] **Step 4: Start the worktree sidecar on an unused port**

In terminal A, from `openmaic-sidecar/`:

```powershell
conda run -n openmaic --no-capture-output pnpm exec next dev --port 3100
```

Expected: Next.js reports ready on `http://localhost:3100`.

- [ ] **Step 5: Verify health without using the local proxy**

In terminal B:

```powershell
curl.exe --noproxy localhost --fail --silent --show-error http://localhost:3100/api/health
```

Expected: HTTP 200 JSON with `"success":true` and `"status":"ok"`. Stop terminal A with Ctrl+C after the check.

- [ ] **Step 6: Verify provenance, repository shape, and final status**

```powershell
if (Test-Path openmaic-sidecar/.git) { throw 'Nested .git exists' }
git ls-files openmaic-sidecar/.env.example
git check-ignore -v openmaic-sidecar/.env
git log -3 --oneline
git status --short --branch
```

Expected: `.env.example` is tracked, `.env` is ignored, recent history shows separate design/vendor/seam commits, and the worktree is clean.
