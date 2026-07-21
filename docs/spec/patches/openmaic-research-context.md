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

The upstream baseline contains pre-existing trailing-whitespace warnings. Preserve the upstream bytes in the vendor-baseline commit and apply `git diff --check` only to local seam paths. On this Windows host, the complete Vitest suite can also exceed individual five-second test timeouts under full parallelism; rerun any timed-out baseline files with `--maxWorkers=1` to distinguish resource contention from a stable failure.

## Upgrade procedure

1. Import the new clean OpenMAIC snapshot as a standalone vendor-baseline commit.
2. Apply `docs/spec/patches/openmaic-research-context.patch` from the edu_ai repository root.
3. Resolve conflicts by preserving the invariants above.
4. Run the focused test, TypeScript check, and complete Vitest suite.
5. If upstream supports external context natively, remove the duplicate local seam and retain behavioral coverage.
