import { workerSource } from './worker-source.js';

// Also serialized into the Worker: keep this function free of module closures.
export function inspectResult(fn, input, expected) {
  const argument = input.slice();
  const before = argument.slice();
  const result = fn(argument);
  const finiteArray = value => Array.isArray(value) && value.length <= 1000 &&
    Array.from({ length: value.length }, (_, i) => i).every(i =>
      Object.hasOwn(value, i) && typeof value[i] === 'number' && Number.isFinite(value[i]));
  const validArray = finiteArray(result);
  const unchanged = argument.length === before.length && before.every((value, i) =>
    Object.hasOwn(argument, i) && argument[i] === value);
  const matches = validArray && result.length === expected.length && expected.every((v, i) => result[i] === v);
  const errorCode = !validArray ? 'INVALID_RESULT' : !unchanged ? 'INPUT_MUTATED' :
    result === argument ? 'RETURNED_INPUT' : !matches ? 'OUTPUT_MISMATCH' : null;
  return {
    actual: validArray ? Array.from(result) : undefined,
    inputAfter: finiteArray(argument) ? Array.from(argument) : undefined,
    returnedSameReference: result === argument, passed: errorCode === null,
    error: errorCode ? { code: errorCode, message: errorCode } : undefined,
  };
}

export function createExecution(request, onCase = () => {}) {
  const started = performance.now();
  let stopped = false;
  let terminateCase = null;
  let batchTimedOut = false;
  const batchTimer = setTimeout(() => {
    batchTimedOut = true;
    if (terminateCase) terminateCase('TIMEOUT');
  }, request.batchTimeoutMs || 15000);
  const stop = () => {
    if (stopped) return;
    stopped = true;
    if (terminateCase) terminateCase('CANCELED');
  };
  const runCase = testCase => new Promise(resolve => {
    let settled = false;
    const completionToken = crypto.randomUUID();
    let worker;
    let url;
    let timer;
    const finish = value => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (worker) worker.terminate();
      if (url) URL.revokeObjectURL(url);
      terminateCase = null;
      resolve({ caseId: testCase.id, expected: testCase.expected, ...value });
    };
    const fail = code => finish({status: code === 'CANCELED' ? 'canceled' : code === 'TIMEOUT' ? 'timeout' : 'failed', error: {code, message: code}});
    terminateCase = fail;
    timer = setTimeout(() => fail('TIMEOUT'), request.caseTimeoutMs || 2000);
    try {
      url = URL.createObjectURL(new Blob([workerSource(inspectResult.toString())], {type:'text/javascript'}));
      worker = new Worker(url, {type:'module'});
      worker.onmessage = event => {
        const data = event.data;
        if (!data || data.completionToken !== completionToken) return;
        if (typeof data.passed !== 'boolean') return fail('INVALID_RESULT');
        finish({actual:data.actual,inputAfter:data.inputAfter,returnedSameReference:data.returnedSameReference,error:data.error,status:data.passed ? 'passed' : 'failed'});
      };
      worker.onerror = () => fail('RUNTIME_ERROR');
      worker.onmessageerror = () => fail('INVALID_RESULT');
      worker.postMessage({completionToken,code: request.code, input: testCase.input, expected: testCase.expected});
    } catch (error) { void error; fail('RUNTIME_UNAVAILABLE'); }
  });
  const result = (async () => {
    const results = [];
    try {
      for (const testCase of request.cases) {
        if (stopped || batchTimedOut) break;
        const item = await runCase(testCase);
        results.push(item);
        onCase(item);
      }
      return {exerciseId: request.exerciseId, artifactVersion: request.artifactVersion, templateVersion: request.templateVersion, taskId: request.taskId, mode: request.mode, runId: request.runId, codeHash: request.codeHash,
        status: stopped ? 'canceled' : batchTimedOut || results.some(r => r.status === 'timeout') ? 'timeout' :
          results.length > 0 && results.length === request.cases.length && results.every(r => r.status === 'passed') ? 'passed' : 'failed',
        results, durationMs: Math.round(performance.now() - started)};
    } finally { clearTimeout(batchTimer); }
  })();
  return {stop, result};
}
