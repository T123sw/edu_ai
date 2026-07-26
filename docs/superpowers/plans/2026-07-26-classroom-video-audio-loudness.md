# AI Classroom Video Audio Loudness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent FFmpeg from attenuating AI classroom narration according to clip count and normalize exported MP4 speech to a stable web-video loudness.

**Architecture:** Keep the existing Playwright scene recorder and timeline-driven narration inputs unchanged. Update the single FFmpeg audio filter graph so delayed, non-overlapping narration streams are summed without `amix` input-count normalization, then pass the result through `loudnorm`; explicitly constrain the final AAC sample rate and bitrate.

**Tech Stack:** TypeScript, Node.js test runner, Playwright, FFmpeg, Vite

---

## File structure

- Modify `Edu_AI/scripts/videoPipeline.test.ts`: define the expected FFmpeg filter graph and output parameters, including a 47-clip regression case.
- Modify `Edu_AI/scripts/videoPipeline.ts`: build the corrected `amix`/`loudnorm` graph and AAC output options.
- No API, frontend route, database, classroom schema, or OpenMAIC source file changes are required.

### Task 1: Add the narration-count attenuation regression test

**Files:**

- Modify: `Edu_AI/scripts/videoPipeline.test.ts:121-148`
- Test: `Edu_AI/scripts/videoPipeline.test.ts`

- [ ] **Step 1: Update the existing exact-arguments test**

Replace the expected filter and append the expected audio output options:

```ts
      '-filter_complex',
      '[1:a]adelay=0|0,volume=0.8[n0];[2:a]adelay=1250|1250,volume=0.8[n1];[n0][n1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]',
      '-map',
      '0:v:0',
      '-map',
      '[aout]',
      '-c:v',
      'copy',
      '-c:a',
      'aac',
      '-ar',
      '48000',
      '-b:a',
      '128k',
```

- [ ] **Step 2: Add a many-clip regression test**

Add this test immediately after the exact-arguments test:

```ts
test('buildAudioMixArguments does not attenuate narration according to clip count', () => {
  const audio = Array.from({ length: 47 }, (_, index) => ({
    path: `speech-${index}.wav`,
    startMs: index * 1000,
  }));
  const args = buildAudioMixArguments(audio, 1);
  const filterIndex = args.indexOf('-filter_complex');
  const filter = args[filterIndex + 1];

  assert.match(
    filter,
    /amix=inputs=47:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1\.5:LRA=11\[aout\]$/,
  );
  assert.equal(filter.match(/loudnorm=/g)?.length, 1);
  assert.doesNotMatch(filter, /normalize=1/);
});
```

- [ ] **Step 3: Run the focused test and verify RED**

Run from `Edu_AI`:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts
```

Expected: the exact-arguments test fails because `normalize=0`, `loudnorm`, `-ar 48000`, and `-b:a 128k` are absent; the 47-clip regression test also fails.

### Task 2: Implement count-independent mixing and loudness normalization

**Files:**

- Modify: `Edu_AI/scripts/videoPipeline.ts:152-180`
- Test: `Edu_AI/scripts/videoPipeline.test.ts`

- [ ] **Step 1: Update the filter graph**

Replace the current `filters.push` call with:

```ts
  filters.push(
    `${mixInputs}amix=inputs=${audio.length}:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]`,
  );
```

The existing timeline validator rejects overlapping narration. Therefore `normalize=0` preserves each active clip's configured gain instead of dividing it by the total number of delayed inputs.

- [ ] **Step 2: Set deterministic AAC output parameters**

Append these values after `'aac'` in the returned argument list:

```ts
    '-ar',
    '48000',
    '-b:a',
    '128k',
```

- [ ] **Step 3: Run the focused test and verify GREEN**

Run from `Edu_AI`:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts
```

Expected: all tests in `scripts/videoPipeline.test.ts` pass.

- [ ] **Step 4: Check formatting and review the exact patch**

Run from the repository root:

```powershell
git diff --check
git diff -- Edu_AI/scripts/videoPipeline.ts Edu_AI/scripts/videoPipeline.test.ts
```

Expected: `git diff --check` prints no errors; the diff contains only the intended filter, AAC options, and regression tests.

- [ ] **Step 5: Commit the tested implementation**

Run from the repository root:

```powershell
git add -- Edu_AI/scripts/videoPipeline.ts Edu_AI/scripts/videoPipeline.test.ts
git commit -m "fix(video): normalize classroom narration loudness"
```

Expected: one commit containing the passing regression test and minimal implementation.

### Task 3: Run repository regression checks

**Files:**

- Verify only; no source change expected.

- [ ] **Step 1: Run the complete test suite**

Run from `Edu_AI`:

```powershell
npm test
```

Expected: all repository tests pass.

- [ ] **Step 2: Run the production build**

Run from `Edu_AI`:

```powershell
npm run build
```

Expected: Vite exits successfully and writes the production bundle.

- [ ] **Step 3: Confirm the worktree is clean**

Run from the repository root:

```powershell
git status --short
```

Expected: no output.

### Task 4: Verify the real FFmpeg audio result

**Files:**

- Verify only; create artifacts beneath a new temporary directory outside the repository.

- [ ] **Step 1: Resolve FFmpeg and create isolated media inputs**

Use the same FFmpeg executable selected by the video pipeline. Create a two-second black H.264 video and two non-overlapping mono narration-like tone files at `-24 dB`, each 0.7 seconds long.

```powershell
$audioCheckDir = Join-Path $env:TEMP 'edu-ai-audio-loudness-check'
New-Item -ItemType Directory -Force -Path $audioCheckDir | Out-Null
ffmpeg -y -f lavfi -i "color=c=black:s=640x360:r=30:d=2" -an -c:v libx264 -pix_fmt yuv420p (Join-Path $audioCheckDir 'silent.mp4')
ffmpeg -y -f lavfi -i "sine=frequency=440:duration=0.7:sample_rate=48000" -af "volume=-24dB" (Join-Path $audioCheckDir 'speech-0.wav')
ffmpeg -y -f lavfi -i "sine=frequency=660:duration=0.7:sample_rate=48000" -af "volume=-24dB" (Join-Path $audioCheckDir 'speech-1.wav')
```

Expected: all three commands exit successfully.

- [ ] **Step 2: Apply the production filter graph**

```powershell
ffmpeg -y `
  -i (Join-Path $audioCheckDir 'silent.mp4') `
  -i (Join-Path $audioCheckDir 'speech-0.wav') `
  -i (Join-Path $audioCheckDir 'speech-1.wav') `
  -filter_complex "[1:a]adelay=0|0,volume=1[n0];[2:a]adelay=1000|1000,volume=1[n1];[n0][n1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]" `
  -map 0:v:0 -map "[aout]" -c:v copy -c:a aac -ar 48000 -b:a 128k `
  (Join-Path $audioCheckDir 'classroom.mp4')
```

Expected: the output MP4 contains H.264 video and AAC audio and FFmpeg reports no clipping error.

- [ ] **Step 3: Measure output loudness**

```powershell
ffmpeg -hide_banner -i (Join-Path $audioCheckDir 'classroom.mp4') -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null NUL 2>&1
```

Expected:

- `input_i` is between `-18.0` and `-14.0`;
- `input_tp` is no higher than `-1.0`;
- the second tone is not quieter solely because it is the second delayed input.

### Task 5: Integrate the verified fix into main

**Files:**

- Git integration only; preserve unrelated user changes in the primary worktree.

- [ ] **Step 1: Inspect both worktrees**

Run:

```powershell
git -C C:\Users\Tang\.config\superpowers\worktrees\edu_ai\fix-classroom-audio-loudness status --short
git -C D:\github\edu_ai status --short
```

Expected: the feature worktree is clean. The main worktree may still contain the user's pre-existing `Edu_AI/package.json` change, which must not be staged or overwritten.

- [ ] **Step 2: Merge the feature branch into main without touching the user change**

Run from `D:\github\edu_ai`:

```powershell
git merge --no-ff fix/classroom-audio-loudness -m "merge: fix classroom video narration loudness"
```

Expected: the design, plan, tests, and implementation merge cleanly; `Edu_AI/package.json` remains an unrelated unstaged user modification.

- [ ] **Step 3: Re-run the focused test on main**

Run from `D:\github\edu_ai\Edu_AI`:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts
```

Expected: all focused tests pass on `main`.

- [ ] **Step 4: Report the measured outcome**

Record in the task handoff:

- feature and merge commit identifiers;
- focused/full test and build results;
- synthetic MP4 measured LUFS and true peak;
- confirmation that the user's unrelated `Edu_AI/package.json` change was preserved.
