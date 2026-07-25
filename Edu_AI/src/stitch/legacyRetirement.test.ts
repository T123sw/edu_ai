import assert from 'node:assert/strict';
import test from 'node:test';

import { routes } from './shared';

test('does not expose the AI lecturer video player route', () => {
  assert.equal('video' in routes, false);
});
