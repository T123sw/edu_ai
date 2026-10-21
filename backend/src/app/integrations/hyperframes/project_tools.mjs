// Fixed host utilities; the complete upstream authoring workflow stays intact.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const runtime = process.env.EDU_HF_RUNTIME;
const project = path.resolve(process.argv[3] || '.');
const policy = 'playback-first-v1';

function save(file, body) {
  fs.mkdirSync(path.dirname(file), {recursive: true});
  if (!fs.existsSync(file) || !fs.readFileSync(file).equals(Buffer.from(body))) fs.writeFileSync(file, body);
}

function prepare() {
  const font = 'NotoSansSC-Variable.ttf';
  const source = path.join(runtime, 'assets/fonts', font);
  if (!fs.existsSync(source)) throw Error('Run scripts/prepare-hyperframes-runtime.py once on the host; do not install fonts inside a video task.');
  for (const name of [font, 'OFL-NotoSansSC.txt']) {
    save(path.join(project, 'assets/fonts', name), fs.readFileSync(path.join(runtime, 'assets/fonts', name)));
  }
  save(path.join(project, 'assets/gsap.min.js'), fs.readFileSync(path.join(runtime, 'node_modules/gsap/dist/gsap.min.js')));
  const css = '@font-face{font-family:"Noto Sans SC";font-style:normal;font-weight:100 900;font-display:block;src:url("assets/fonts/NotoSansSC-Variable.ttf") format("truetype");}';
  const result = {font_family: 'Noto Sans SC', font_face: css,
    gsap: 'assets/gsap.min.js', weights: '100–900',
    usage: 'Use the supplied font-face inside each native template; paths are relative to the assembled project. Keep native design tokens, using this font for Chinese text. Do not download fonts or inspect glyph coverage per scene.'};
  save(path.join(project, '.hyperframes/host-assets.json'), JSON.stringify(result, null, 2));
  // Re-run after upstream assembly to localize its known GSAP CDN include.
  const index = path.join(project, 'index.html');
  if (fs.existsSync(index)) {
    const html = fs.readFileSync(index, 'utf8');
    save(index, html.replace(/(<script\b[^>]*\bsrc=["'])https:\/\/(?:cdn\.jsdelivr\.net\/npm\/gsap(?:@[^/"']+)?\/dist\/gsap\.min\.js|cdnjs\.cloudflare\.com\/ajax\/libs\/gsap\/[^/"']+\/gsap\.min\.js)(["'])/g, '$1assets/gsap.min.js$2'));
  }
  return result;
}

function fingerprint() {
  const hash = createHash('sha256').update(policy).update(fs.readFileSync(fileURLToPath(import.meta.url)));
  hash.update(fs.readFileSync(path.join(runtime, 'node_modules/hyperframes/package.json')));
  const excluded = new Set(['.git', '.host', '.hyperframes', 'node_modules', 'renders', 'exports', 'boards']);
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes: true}).sort((a,b) => a.name.localeCompare(b.name))) {
      if (excluded.has(entry.name)) continue;
      const file = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) throw Error('Project input must be a local file: '+file);
      if (entry.isDirectory()) walk(file);
      else if (entry.isFile()) hash.update(path.relative(project, file)).update('\0').update(fs.readFileSync(file));
    }
  }
  walk(project);
  return hash.digest('hex');
}

function check() {
  const digest = fingerprint();
  const receipt = path.join(project, '.hyperframes/host-check.json');
  let previous;
  try { previous = JSON.parse(fs.readFileSync(receipt, 'utf8')); } catch (e) { if (e.code !== 'ENOENT' && !(e instanceof SyntaxError)) throw e; }
  if (previous?.digest === digest) return {...previous, cached: true};
  const cli = path.join(runtime, 'node_modules/hyperframes/dist/cli.js');
  const command = spawnSync(process.execPath, [cli, 'check', project, '--json'], {cwd: project, encoding: 'utf8', maxBuffer: 16*1024*1024});
  if (command.error || ![0, 1].includes(command.status)) throw Error(command.error?.message || command.stderr || command.stdout || 'Native check process failed');
  const report = JSON.parse(command.stdout);
  if (report.browserSkipped !== false || !report.layout?.samples?.length ||
      ['lint','runtime','motion','layout','contrast'].some(k => typeof report[k]?.ok !== 'boolean')) throw Error('Native browser check incomplete; no successful receipt saved');
  const blocking = ['lint','runtime','motion'].filter(k => !report[k].ok);
  if (report.ok === false && ['lint','runtime','motion','layout','contrast'].every(k => report[k].ok)) throw Error('Unclassified native check failure');
  const result = {policy, digest, cached: false, passed: blocking.length === 0,
    blocking: blocking.map(section => ({section, findings: report[section].findings})),
    advisory_count: ['layout','contrast'].reduce((n,k) => n+(report[k].findings?.length || 0), 0),
    report_file: path.join(project, '.hyperframes/host-check-native.json'),
    next: blocking.length ? 'Repair only the reported blocking failures, then check the changed project.' : 'Proceed to render. Do not rerun lint/check, add per-scene previews, or polish advisory layout/contrast findings.'};
  save(result.report_file, JSON.stringify(report, null, 2));
  save(receipt, JSON.stringify(result, null, 2));
  return result;
}

try {
  if (!runtime) throw Error('EDU_HF_RUNTIME is required');
  const action = process.argv[2];
  const result = action === 'prepare' ? prepare() : action === 'check' ? check() : null;
  if (!result) throw Error('Expected prepare or check');
  console.log(JSON.stringify(result));
  if (result.passed === false) process.exitCode = 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
