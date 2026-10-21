import { test } from 'node:test';
import assert from 'node:assert/strict';
import vectors from './fixtures/code-hash.json';
import { hashCode, isCurrentReport } from './protocol';
import type { ExerciseArtifact, RunReport } from './types';
import { deriveTaskStatus } from './runState';
const artifact = {exerciseId:'a',artifactVersion:1,templateVersion:'js-function-v1',tasks:[{id:'implement-sort',testCaseIds:['one','two']}]} as ExerciseArtifact;
const report = {exerciseId:'a',artifactVersion:1,templateVersion:'js-function-v1',taskId:'implement-sort',codeHash:'hash',mode:'check',status:'passed',results:[{caseId:'one',status:'passed'},{caseId:'two',status:'passed'}]} as RunReport;
test('UTF8 source hashes agree with Python', async () => { for (const item of vectors) assert.equal(await hashCode(item.code),item.hash); });
test('only full current checks count', () => {
  assert.ok(isCurrentReport(report,artifact,'hash'));
  for (const patch of [{mode:'sample'}, {status:'canceled'}, {exerciseId:'other'}, {templateVersion:'old'}, {artifactVersion:2}, {taskId:'other'}, {codeHash:'old'}, {results:report.results.slice(0,1)}, {results:[report.results[0],report.results[0]]}]) {
    assert.equal(isCurrentReport({...report,...patch} as RunReport,artifact,'hash'),false);
  }
});
test('editing invalidates a prior check', () => {
  assert.equal(deriveTaskStatus({hasEdits:true,currentCodeHash:'new',artifact,latestCheck:report}),'needs_recheck');
  assert.equal(deriveTaskStatus({hasEdits:false,currentCodeHash:'hash',artifact,latestCheck:null}),'not_started');
});
