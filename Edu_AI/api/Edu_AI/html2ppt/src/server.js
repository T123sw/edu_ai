const express = require('express');
const path = require('path');
const { servicePort, workerConcurrency } = require('./config');
const { errorToResponse } = require('./domain/errors');
const { TaskQueue } = require('./queue/task-queue');
const { ClaudeCodeRunner } = require('./agents/claude-code-runner');
const { PptService } = require('./services/ppt-service');
const { ensurePreviewRuntimeBridge } = require('./lib/build-standalone-html');
const fs = require('fs/promises');

async function main() {
  const app = express();
  const queue = new TaskQueue({ concurrency: workerConcurrency });
  const runner = new ClaudeCodeRunner();
  const service = new PptService({ queue, runner });

  await service.init();

  app.use(express.json({ limit: '10mb' }));
  app.use('/assets', express.static(path.join(__dirname, '..', 'assets')));

  app.post('/ppt/jobs', async (req, res) => {
    try {
      const result = await service.createJob(req.body);
      res.status(202).json(result);
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.get('/ppt/jobs/:jobId', async (req, res) => {
    try {
      const result = await service.getJobStatus(req.params.jobId);
      res.json(result);
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.get('/ppt/jobs/:jobId/results', async (req, res) => {
    try {
      const result = await service.getResults(req.params.jobId);
      res.json(result);
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.post('/ppt/jobs/:jobId/revisions', async (req, res) => {
    try {
      const result = await service.createRevision(req.params.jobId, req.body);
      res.status(202).json(result);
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.get('/ppt/jobs/:jobId/revisions/:revisionId', async (req, res) => {
    try {
      const result = await service.getRevisionStatus(req.params.jobId, req.params.revisionId);
      res.json(result);
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.get('/ppt/artifacts/:jobId/:revisionId/:fileName', async (req, res) => {
    try {
      const artifactPath = await service.resolveArtifactPath(
        req.params.jobId,
        req.params.revisionId,
        req.params.fileName
      );
      if (req.params.fileName === 'deck.html') {
        const html = await fs.readFile(path.resolve(artifactPath), 'utf8');
        res.type('html').send(ensurePreviewRuntimeBridge(html));
        return;
      }
      res.sendFile(path.resolve(artifactPath));
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.get('/ppt/artifacts/:jobId/:revisionId/media/:fileName', async (req, res) => {
    try {
      const artifactPath = await service.resolveMediaArtifactPath(
        req.params.jobId,
        req.params.revisionId,
        req.params.fileName
      );
      res.sendFile(path.resolve(artifactPath));
    } catch (error) {
      const response = errorToResponse(error);
      res.status(response.statusCode).json(response.body);
    }
  });

  app.listen(servicePort, '127.0.0.1', () => {
    console.log(`PPT service listening on http://127.0.0.1:${servicePort}`);
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
