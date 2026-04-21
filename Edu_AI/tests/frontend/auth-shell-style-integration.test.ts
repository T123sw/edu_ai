import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const stitchApp = readFileSync(new URL('../../src/stitch/App.tsx', import.meta.url), 'utf8');
const stitchLoginPage = readFileSync(new URL('../../src/stitch/pages/LoginPage.tsx', import.meta.url), 'utf8');
const stitchHomeDashboard = readFileSync(new URL('../../src/stitch/pages/HomeDashboard.tsx', import.meta.url), 'utf8');
const routeLoginPage = readFileSync(new URL('../../src/pages/LoginPage.tsx', import.meta.url), 'utf8');
const routeWelcomePage = readFileSync(new URL('../../src/pages/WelcomePage.tsx', import.meta.url), 'utf8');

assert.match(
  stitchApp,
  /import\s+\{\s*LoginPage\s*\}\s+from\s+"\.\/pages\/LoginPage"/,
  'Stitch App should render the dedicated login page component instead of an inline auth screen',
);

assert.doesNotMatch(
  stitchApp,
  /function\s+AuthScreen\s*\(/,
  'Stitch App should remove the old inline AuthScreen after the visual replacement',
);

assert.match(
  stitchLoginPage,
  /login-feature-item/,
  'Stitch login page should expose the richer marketing feature strip classes',
);

assert.match(
  stitchHomeDashboard,
  /import\s+"\.\/HomeDashboard\.css"/,
  'Stitch home dashboard should load the dedicated welcome page stylesheet',
);

assert.match(
  stitchHomeDashboard,
  /welcome-topbar/,
  'Stitch home dashboard should render the new welcome top bar shell',
);

assert.match(
  routeLoginPage,
  /login-feature-item/,
  'Route-based login page should adopt the same richer login layout classes',
);

assert.match(
  routeLoginPage,
  /navigate\('\/welcome',\s*\{\s*replace:\s*true\s*\}\)/,
  'Route-based login page should still navigate to /welcome after successful login',
);

assert.match(
  routeWelcomePage,
  /welcome-user-pill/,
  'Route-based welcome page should render the stitched welcome account pill',
);

assert.match(
  routeWelcomePage,
  /navigate\(`\/course\/\$\{courseId\}\/intro`\)/,
  'Route-based welcome page should keep opening the selected course intro route',
);

console.log('auth-shell-style-integration tests passed');
