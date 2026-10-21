import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import candidate from '../../backend/src/tests/pbl/fixtures/candidate.json';
function validate(patch:Record<string,unknown>={}) {
  const child=spawnSync(process.execPath,['--import','tsx','scripts/validate-pbl.mjs'],{input:JSON.stringify({candidate:{...candidate,...patch},templateVersion:'js-function-v1'}),encoding:'utf8',timeout:60000});
  assert.equal(child.status,0,child.stderr);return JSON.parse(child.stdout);
}
test('共享浏览器检查：参考通过、骨架待实现',()=>{const result=validate();assert.equal(result.passed,true);assert.ok(result.starterResults.every((r:{error:{code:string}})=>r.error.code==='NOT_IMPLEMENTED'));});
test('错误参考与预填答案不能发布',()=>{
  assert.equal(validate({referenceSolution:'export function quickSort(array) { return []; }'}).passed,false);
  assert.equal(validate({starterCode:candidate.referenceSolution}).issues[0].code,'STARTER_CONTAINS_IMPLEMENTATION');
});
test('结构化源码限制阻止模块访问',()=>{
  const result=validate({referenceSolution:'import x from "node:fs"; export function quickSort(a){return a}'});
  assert.equal(result.passed,false);assert.ok(result.issues.some((x:{code:string})=>x.code==='UNSUPPORTED_SOURCE'));
});
