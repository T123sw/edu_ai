const PHASE_PROGRESS = {
  accepted: 0,
  preprocessing: 10,
  generating_slides: 40,
  building_full_html: 70,
  exporting_pptx: 90,
  storing_artifacts: 95,
  completed: 100,
  failed: 0,
};

function progressForPhase(phase, fallback = 0) {
  return Object.prototype.hasOwnProperty.call(PHASE_PROGRESS, phase)
    ? PHASE_PROGRESS[phase]
    : fallback;
}

function nowIso() {
  return new Date().toISOString();
}

function withLifecycleFields(target, patch) {
  return {
    ...target,
    ...patch,
    progress: patch.progress ?? progressForPhase(patch.phase, target.progress ?? 0),
    updated_time: nowIso(),
  };
}

module.exports = {
  PHASE_PROGRESS,
  nowIso,
  progressForPhase,
  withLifecycleFields,
};
