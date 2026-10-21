// The host only parses source. All candidate execution happens in disposable browser Workers.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { parse } from 'acorn';
import sourceValidation from '../src/pbl/runtime/sourceValidation.ts';
const { validateSource } = sourceValidation;
const runtime = new URL('../src/pbl/runtime/', import.meta.url);
const TEMPLATE = 'js-function-v1';
let data = '';
for await (const part of process.stdin) data += part;
const {candidate, templateVersion} = JSON.parse(data);
const issues = [];
if (templateVersion !== TEMPLATE) issues.push({code:'TEMPLATE_MISMATCH',message:'运行模板版本不一致'});
for (const field of ['referenceSolution', 'starterCode']) {
  const check = validateSource(candidate[field]);
  if (!check.ok) issues.push(...check.issues.map(issue => ({...issue,field})));
}
try {
  const ast = parse(candidate.starterCode,{ecmaVersion:'latest',sourceType:'module'});
  const declaration = ast.body[0]?.declaration;
  const statement = declaration?.body?.body?.[0];
  if (ast.body.length !== 1 || declaration?.type !== 'FunctionDeclaration' || declaration.id?.name !== 'quickSort' ||
    declaration.body.body.length !== 1 || statement?.type !== 'ThrowStatement' || statement.argument.type !== 'NewExpression' ||
    statement.argument.callee?.name !== 'Error' || statement.argument.arguments?.length !== 1 || statement.argument.arguments[0].value !== 'NOT_IMPLEMENTED') {
    issues.push({code:'STARTER_CONTAINS_IMPLEMENTATION',message:'初始骨架仅允许 NOT_IMPLEMENTED 抛错'});
  }
} catch { /* Source validator already explains syntax failures. */ }
if (issues.length) {
  process.stdout.write(JSON.stringify({passed:false,templateVersion:TEMPLATE,issues,caseResults:[]}));
  process.exit(0);
}
let browser;
const allowed = new Set(['runner.js','worker-source.js']);
const server = createServer(async (req,res) => {
  const name = (req.url || '/').slice(1);
  if (name === '') {
    res.setHeader('Content-Type','text/html');
    res.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'self' blob:; worker-src blob:; connect-src 'none'");
    res.end('<!doctype html><html><head><title>PBL validation</title></head><body></body></html>');
  } else if (allowed.has(name)) {
    res.setHeader('Content-Type','text/javascript');
    res.end(await readFile(new URL(name,runtime)));
  } else { res.statusCode=404;res.end(); }
});
try {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
  const context = await browser.newContext({serviceWorkers:'block'});
  await context.route('**/*',route => route.request().url().startsWith(origin+'/') ? route.continue() : route.abort());
  const page = await context.newPage();
  await page.goto(origin);
  const execute = async code => page.evaluate(async ({code,cases}) => {
    const { createExecution } = await import('/runner.js');
    const request={runId:'validation',exerciseId:'validation',artifactVersion:1,templateVersion:'js-function-v1',taskId:'implement-sort',codeHash:'validation',mode:'check',code,cases};
    return createExecution(request).result;
  },{code,cases:candidate.testCases});
  const reference = await execute(candidate.referenceSolution);
  const starter = await execute(candidate.starterCode);
  if (reference.status !== 'passed') issues.push({code:'REFERENCE_FAILED',message:'参考实现未通过用例'});
  if (starter.results.length !== candidate.testCases.length || !starter.results.every(r => r.error?.code === 'NOT_IMPLEMENTED')) issues.push({code:'STARTER_INVALID',message:'初始骨架未按预期提示待实现'});
  process.stdout.write(JSON.stringify({passed:issues.length===0,templateVersion:TEMPLATE,issues,caseResults:reference.results,starterResults:starter.results}));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
