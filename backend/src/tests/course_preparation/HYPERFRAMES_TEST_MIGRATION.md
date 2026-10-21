# Classroom test migration (2026-10-17)

The active classroom adapter now generates HyperFrames projects. Tests must not
reintroduce the deleted storyboard/OpenMAIC writer merely to satisfy old mocks.
This mapping records the replacement coverage and retained history.

| Previous coverage | Current coverage |
| --- | --- |
| `_generate_storyboard_draft` context, source evidence, original body and revision feedback transport | `test_hyperframes_preparation.py::test_native_entry_preserves_sources_revision_context_and_full_project` inspects both native authoring requests and the published sub-composition. |
| Storyboard writer/reviewer phases, audit identity, estimated duration | `test_no_extra_model_review_and_measured_duration_not_target_estimate` checks only native writing, an explicit skipped model-review receipt, digest invalidation and duration measured from synthesized narration. An independent classroom semantic review is deliberately no longer required. |
| Sidecar pending-scene / storyboard-review recovery | `test_render_resume_does_not_rewrite_or_resynthesize_successful_stages`; native `tests/hyperframes/test_generation.py` also tests the actual immutable project export and resumed audio checkpoints. |
| Stale storyboard review digest | `test_checkpoint_identity_changes_regenerate_for_new_authorized_request` covers changed spec, evidence, feedback and teaching context. The new policy regenerates a distinct request instead of interpreting old review state as a native project. |
| Slow writer cancellation and provider timeout | `test_cancellation_after_slow_writer_cannot_save_candidate` and `test_provider_timeout_does_not_publish_or_create_fake_audio`. |
| Reviewer-mutated slides, binding review and repair mocks | `test_runtime_repair_receives_actual_findings_without_semantic_review`; native generation tests separately reject and repair invalid semantic event bounds and unreachable narration. Model-based classroom review/repair is intentionally retired. |
| Missing required narration/media could silently degrade | Native tests in `tests/hyperframes/test_generation.py` check required audio presence, duplication, global timing, hidden/template placement and local-reference containment. Sandbox tests cover browser IO boundaries. |
| Old page caps and estimated target duration | `test_long_narration_and_more_than_24_segments_are_not_truncated` plus measured-duration assertions; existing `test_unlimited_content_policy.py` remains active. |
| Per-page model mapping and cross-page locator repair | `test_classroom_page_mapping.py` now verifies authored source/objective IDs without a mapping model, and rejects/repairs scene-local events that would point into a different global segment. |
| Private checkpoint and parent lease fencing | Retained in `test_openmaic_native_integration.py::test_native_generation_checkpoint_is_private_and_lease_fenced`; it tests the generic artifact checkpoint store, not the retired generator. |
| Existing saved OpenMAIC resources | `legacy_classroom_fixtures.py` constructs historical records for existing reader, validator, receipt and revision tests. It is test-only. Historical storyboard/quiz/interactive validators remain tested. |

No test skips were introduced. PostgreSQL variants retain their existing
requirement for `PREPARATION_TEST_DATABASE_URL`; live model opt-in tests retain
their existing provider configuration requirement. Native unit runtime fixtures
do not claim to verify real MP4/audio bytes; the native runtime/browser smoke
and recorded acceptance artifact supply that integration evidence separately.

Verification: the 12 affected modules and shared-fixture consumers completed
with **148 passed, 34 pre-existing skips** (66.42 seconds). Skips cover optional
PostgreSQL/live-provider cases and the existing SQLite-only subprocess smoke
variant. Full `course_preparation` collection succeeds: **848 tests collected**.
After removing unused legacy fixture helpers, the two historical fixture
modules were rerun: **14 passed, 1 existing skip**. No production source was
changed by this test migration.
