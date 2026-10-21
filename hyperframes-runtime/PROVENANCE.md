# Native HyperFrames runtime

The complete unmodified upstream source tree is pinned as a Git submodule at `vendor/hyperframes`.
Repository: https://github.com/heygen-com/hyperframes
Commit: `b18b3e958aa199529fa5fa06728e81b97d520021`
Codeload archive SHA256: `4d43c9d13add21436a222a386bea70b8a106a779c35372e47c350643d860f56b`
CLI and player: npm `hyperframes@0.8.168`, `@hyperframes/player@0.8.168`.
Upstream licenses remain in the vendored tree. Edu_AI adapters live outside it.

Initialize the pinned source with `git submodule update --init --depth 1 -- vendor/hyperframes` (also done by the install scripts). Upstream rendering-test media uses Git LFS; set `GIT_LFS_SKIP_SMUDGE=1` when initializing if only the teaching runtime is needed, and fetch that optional test media from the upstream submodule when running its media regressions.

Install with Node >=22: `npm ci --prefix hyperframes-runtime`.
Install Chromium using `npm --prefix hyperframes-runtime exec -- hyperframes browser ensure`; FFmpeg/ffprobe must be on PATH.
Configure HYPERFRAMES_RUNTIME_DIR if the runtime is outside this checkout.
COURSE_STORAGE_ROOT stores immutable projects and cached narration; use an isolated root in tests.

For updates, fetch the complete new commit archive, verify its hash, replace the upstream tree without local patches, pin matching CLI/player versions, regenerate the lockfile, run backend contract/generation tests and a real native check/render, and record the new commit and archive digest here. Never silently upgrade at generation time.

For existing Chromium installations set `HYPERFRAMES_BROWSER_PATH` to the executable (the native runtime recognizes this variable). The isolated smoke check used Playwright's Chromium headless shell 1234. Verification files record a one-second moving-box composition with synthetic sine-wave audio; this verifies real native browser checks and MP4 muxing, not a real teaching-model/TTS evaluation.
