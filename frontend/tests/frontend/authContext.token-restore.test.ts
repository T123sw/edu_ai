import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const authContext = readFileSync(new URL('../../src/context/AuthContext.tsx', import.meta.url), 'utf8');

assert.match(
  authContext,
  /import\s+\{\s*login\s+as\s+loginService,\s*verifyToken\s*\}\s+from\s+'..\/services\/auth'/,
  'AuthContext should import verifyToken so restored localStorage sessions are checked before reuse',
);

assert.match(
  authContext,
  /const\s+result\s*=\s*await\s+verifyToken\(parsed\.token\)/,
  'AuthContext should verify the persisted token while restoring auth state',
);

assert.match(
  authContext,
  /if\s*\(\s*result\.valid\s*\)\s*\{[\s\S]*setUser\(result\.user\)[\s\S]*setToken\(parsed\.token\)[\s\S]*\}\s*else\s*\{[\s\S]*window\.localStorage\.removeItem\(STORAGE_KEY\)/,
  'AuthContext should restore only valid tokens and remove expired or invalid persisted sessions',
);

assert.match(
  authContext,
  /catch\s*\{[\s\S]*window\.localStorage\.removeItem\(STORAGE_KEY\)/,
  'AuthContext should clear persisted auth when token verification fails',
);

console.log('authContext.token-restore tests passed');
