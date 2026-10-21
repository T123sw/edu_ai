import { validatePractice } from './practice-validation.mjs';
import { validateExperiment } from './experiment-validation.mjs';
import { validateGuidance } from './guidance-validation.mjs';
import { validateStagePage } from './pages-validation.mjs';
import { mkdir, writeFile, readdir, stat, unlink } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
let input = ''; for await (const chunk of process.stdin) input += chunk;
const { html, native = false, guidance = null, experiment = null, stage_page = null } = JSON.parse(input);
// Keep private, bounded evidence even when the backend refuses to publish HTML.
const evidenceDirectory = fileURLToPath(new URL('../../.runtime/practice-validation/', import.meta.url));
const evidenceId = randomUUID();
let evidenceSaved = false;
try {
  await mkdir(evidenceDirectory, { recursive: true, mode: 0o700 });
  await writeFile(path.join(evidenceDirectory, `${evidenceId}.json`), JSON.stringify({ created_at: new Date().toISOString(), html, status: 'checking' }), { mode: 0o600 });
  evidenceSaved = true;
} catch { /* Evidence storage failure must not alter the check's verdict. */ }
const result = stage_page ? await validateStagePage(html, stage_page) : experiment ? await validateExperiment(html, experiment) : guidance ? await validateGuidance(html, guidance) : await validatePractice(html, { native });
if (evidenceSaved) {
  try {
    await writeFile(path.join(evidenceDirectory, `${evidenceId}.json`), JSON.stringify({ created_at: new Date().toISOString(), html, result }), { mode: 0o600 });
    result.diagnostics ||= {};
    result.diagnostics.evidence_id = evidenceId;
    const files = await readdir(evidenceDirectory);
    const entries = await Promise.all(files.filter(name => /^[\da-f-]{36}\.json$/.test(name)).map(async name => ({ name, mtime: (await stat(path.join(evidenceDirectory, name))).mtimeMs })));
    entries.sort((a, b) => b.mtime - a.mtime);
    await Promise.all(entries.filter((item, i) => item.name !== `${evidenceId}.json` && (i >= 100 || Date.now() - item.mtime > 7 * 86400000)).map(item => unlink(path.join(evidenceDirectory, item.name)).catch(() => {})));
  } catch { /* Preserve the original verdict if evidence rotation races another worker. */ }
}
process.stdout.write(JSON.stringify(result));
