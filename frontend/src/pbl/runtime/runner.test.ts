import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inspectResult } from './runner.js';
import { validateSource } from './sourceValidation';
import { referenceSolution, starterCode } from '../fixtures/quicksort';
test('结果检查拒绝稀疏、修改输入、同对象和非有限值',()=>{
  assert.equal(inspectResult(a=>a.slice(),[1,2],[1,2]).passed,true);
  for (const fn of [(a:number[])=>a, (a:number[])=>new Array(a.length),()=>[NaN],()=>[undefined],(a:number[])=>{delete a[0];return [1,2];}]) {
    assert.equal(inspectResult(fn,[1,2],[1,2]).passed,false);
  }
});
test('源码限制允许快速排序，拒绝模块副作用与异步',()=>{
  assert.equal(validateSource(referenceSolution).ok,true);
  assert.equal(validateSource(starterCode).ok,true);
  for(const source of ['export function quickSort(a){postMessage({passed:true});return []}', 'const {x=sideEffect()} = () => {}; export function quickSort(a){return a}', 'while(true){} export function quickSort(a) {return a}', 'import x from "x"; export function quickSort(a){return a}', 'export async function quickSort(a){return a}', 'export function quickSort(a){fetch("x"); return a}', 'const x = foo(); export function quickSort(a){return a}', 'export function quickSort(a){ return import("x") }']) assert.equal(validateSource(source).ok,false,source);
  assert.equal(validateSource('export function quickSort(a){return a.slice().sort()}').issues[0].code,'IMPLEMENTATION_HINT');
});
