import assert from 'node:assert/strict';

import { resolveSpeechInputError } from '../../src/services/teacher/speechInput.ts';

const missingDevice = resolveSpeechInputError({
  name: 'NotFoundError',
  message: 'Requested device not found',
});

assert.equal(missingDevice.fallback, 'none');
assert.match(missingDevice.message, /麦克风/);

const denied = resolveSpeechInputError({
  name: 'NotAllowedError',
  message: 'Permission denied',
});

assert.equal(denied.fallback, 'none');
assert.match(denied.message, /权限/);

console.log('speechInput.helpers tests passed');
