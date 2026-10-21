// NODE_OPTIONS preloader covers native CLI launches via node, npx and shims.
const path = require('path');
if (process.env.EDU_RENDER_PERMIT !== '1' && process.argv[1] &&
    path.resolve(process.argv[1]) === path.join(process.env.EDU_HF_RUNTIME || '', 'node_modules/hyperframes/dist/cli.js') &&
    process.argv.slice(2).includes('render')) {
  const result = require('child_process').spawnSync('/usr/bin/python3',
    [path.join(__dirname, 'render_gate.py'), process.execPath, ...process.argv.slice(1)], {stdio: 'inherit'});
  process.exit(result.status ?? 1);
}
