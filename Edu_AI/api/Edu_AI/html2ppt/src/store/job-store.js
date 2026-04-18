const fs = require('fs/promises');
const path = require('path');
const { dataDir } = require('../config');
const { AppError } = require('../domain/errors');
const { nowIso } = require('../domain/status');
const { ensureDir, fileExists, hashRequestForIdempotency, readJson, writeJson } = require('../lib/file-utils');

const jobsRootDir = path.join(dataDir, 'jobs');
const idempotencyIndexPath = path.join(dataDir, 'idempotency-index.json');

function getJobDir(jobId) {
  return path.join(jobsRootDir, jobId);
}

function getRevisionDir(jobId, revisionId) {
  return path.join(getJobDir(jobId), 'revisions', revisionId);
}

function getJobPaths(jobId) {
  const jobDir = getJobDir(jobId);
  return {
    jobDir,
    requestPath: path.join(jobDir, 'request.json'),
    jobStatePath: path.join(jobDir, 'job.json'),
    revisionsDir: path.join(jobDir, 'revisions'),
  };
}

function getRevisionPaths(jobId, revisionId) {
  const revisionDir = getRevisionDir(jobId, revisionId);
  return {
    revisionDir,
    mediaDir: path.join(revisionDir, 'media'),
    revisionStatePath: path.join(revisionDir, 'revision.json'),
    fragmentPath: path.join(revisionDir, 'deck.fragment.html'),
    fullHtmlPath: path.join(revisionDir, 'deck.html'),
    pptxPath: path.join(revisionDir, 'deck.pptx'),
    manifestPath: path.join(revisionDir, 'manifest.json'),
    qualityReportPath: path.join(revisionDir, 'layout-quality-report.json'),
    contentPath: path.join(revisionDir, 'content.md'),
    promptPath: path.join(revisionDir, 'agent-prompt.txt'),
  };
}

async function initStore() {
  await ensureDir(jobsRootDir);
  if (!(await fileExists(idempotencyIndexPath))) {
    await writeJson(idempotencyIndexPath, {});
  }
}

async function readIdempotencyIndex() {
  await initStore();
  return readJson(idempotencyIndexPath);
}

async function writeIdempotencyIndex(index) {
  await writeJson(idempotencyIndexPath, index);
}

function buildIdempotencyKey(tenantId, idempotencyKey) {
  return `${tenantId || 'default'}::${idempotencyKey}`;
}

async function findByIdempotency(tenantId, idempotencyKey) {
  const index = await readIdempotencyIndex();
  return index[buildIdempotencyKey(tenantId, idempotencyKey)] || null;
}

async function registerIdempotency(tenantId, idempotencyKey, payload) {
  const index = await readIdempotencyIndex();
  index[buildIdempotencyKey(tenantId, idempotencyKey)] = payload;
  await writeIdempotencyIndex(index);
}

async function createJob({ jobId, request }) {
  const timestamp = nowIso();
  const paths = getJobPaths(jobId);
  const tenantId = request.metadata?.tenant_id || 'default';
  const requestHash = hashRequestForIdempotency(request);

  await ensureDir(paths.revisionsDir);
  await writeJson(paths.requestPath, request);
  await writeJson(paths.jobStatePath, {
    job_id: jobId,
    status: 'queued',
    phase: 'accepted',
    progress: 0,
    message: '任务已排队',
    create_time: timestamp,
    updated_time: timestamp,
    finished_time: null,
    latest_revision_id: null,
    latest_success_revision_id: null,
    active_revision_id: null,
    theme_id: request.theme_id,
    metadata: request.metadata,
    request_hash: requestHash,
    error: null,
  });

  await registerIdempotency(tenantId, request.metadata.idempotency_key, {
    job_id: jobId,
    request_hash: requestHash,
  });

  return {
    jobId,
    requestHash,
  };
}

async function getJob(jobId) {
  const paths = getJobPaths(jobId);
  if (!(await fileExists(paths.jobStatePath))) {
    throw new AppError('JOB_NOT_FOUND', `Job not found: ${jobId}`, 404);
  }
  return readJson(paths.jobStatePath);
}

async function getRequest(jobId) {
  const paths = getJobPaths(jobId);
  if (!(await fileExists(paths.requestPath))) {
    throw new AppError('JOB_NOT_FOUND', `Request for job not found: ${jobId}`, 404);
  }
  return readJson(paths.requestPath);
}

async function updateJob(jobId, updater) {
  const paths = getJobPaths(jobId);
  const current = await getJob(jobId);
  const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
  await writeJson(paths.jobStatePath, next);
  return next;
}

async function listJobIds() {
  await initStore();
  const entries = await fs.readdir(jobsRootDir, { withFileTypes: true });
  return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
}

async function ensureRevisionCounter(jobId) {
  const job = await getJob(jobId);
  return job;
}

async function listRevisionIds(jobId) {
  const paths = getJobPaths(jobId);
  if (!(await fileExists(paths.revisionsDir))) {
    return [];
  }
  const entries = await fs.readdir(paths.revisionsDir, { withFileTypes: true });
  return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
}

async function allocateRevisionId(jobId) {
  await ensureRevisionCounter(jobId);
  const revisionIds = await listRevisionIds(jobId);
  const nextIndex = revisionIds.length;
  return `rev_${String(nextIndex).padStart(4, '0')}`;
}

async function createRevision(jobId, payload) {
  const revisionId = await allocateRevisionId(jobId);
  const paths = getRevisionPaths(jobId, revisionId);
  const timestamp = nowIso();
  await ensureDir(paths.revisionDir);
  await writeJson(paths.revisionStatePath, {
    revision_id: revisionId,
    job_id: jobId,
    status: 'queued',
    phase: 'accepted',
    progress: 0,
    message: payload.kind === 'initial' ? '生成任务已排队' : '修订任务已排队',
    create_time: timestamp,
    updated_time: timestamp,
    finished_time: null,
    error: null,
    kind: payload.kind,
    mode: payload.mode || null,
    target_slides: payload.target_slides || [],
    updated_content: payload.updated_content || null,
    user_instruction: payload.user_instruction || null,
    artifacts: {
      fragment_path: paths.fragmentPath,
      full_html_path: paths.fullHtmlPath,
      pptx_path: paths.pptxPath,
      manifest_path: paths.manifestPath,
      quality_report_path: paths.qualityReportPath,
      media_dir: paths.mediaDir,
    },
  });
  return revisionId;
}

async function getRevision(jobId, revisionId) {
  const paths = getRevisionPaths(jobId, revisionId);
  if (!(await fileExists(paths.revisionStatePath))) {
    throw new AppError('REVISION_NOT_FOUND', `Revision not found: ${revisionId}`, 404);
  }
  return readJson(paths.revisionStatePath);
}

async function updateRevision(jobId, revisionId, updater) {
  const paths = getRevisionPaths(jobId, revisionId);
  const current = await getRevision(jobId, revisionId);
  const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
  await writeJson(paths.revisionStatePath, next);
  return next;
}

module.exports = {
  createJob,
  createRevision,
  findByIdempotency,
  getJob,
  getJobDir,
  getJobPaths,
  getRequest,
  getRevision,
  getRevisionDir,
  getRevisionPaths,
  initStore,
  listJobIds,
  listRevisionIds,
  readIdempotencyIndex,
  updateJob,
  updateRevision,
};
