# New Frontend Src Merge Design

## Goal

Merge the new frontend source snapshot from remote branch `origin/New_frontend` into the current project frontend path `frontend/src`.

## Source And Target

- Remote branch: `origin/New_frontend`
- Source path in remote branch: `edu_ai-main/frontend/src`
- Target path in this repository: `frontend/src`

The remote branch does not contain `frontend/src` at the repository root. The source path must be remapped from `edu_ai-main/frontend/src` to `frontend/src`.

## Current Constraints

The current `main` worktree has many uncommitted changes. The frontend overlap that needs special care is:

- `frontend/src/components/teacher/StudioPanel.tsx`
- `frontend/src/services/teacher/chatV2.ts`

Both files have local uncommitted changes and are also changed in the new frontend snapshot.

## Approach

Use an isolated `.worktrees` branch to validate the new frontend source before changing the dirty `main` worktree. In that branch:

1. Copy the remote tree `origin/New_frontend:edu_ai-main/frontend/src`.
2. Place it at `frontend/src`.
3. Compare the two overlapping local files against the current dirty worktree before applying changes back to `main`.
4. Run frontend verification from `Edu_AI`, starting with `npm run build`.

## Success Criteria

- `frontend/src` in the isolated branch matches the remote new frontend source after path remapping.
- The `stitch/` frontend module from the remote branch is present under `frontend/src/stitch`.
- Build verification is attempted from `Edu_AI`.
- Any build or type failures are reported with concrete file references.
- No uncommitted changes in the current `main` worktree are overwritten during validation.
