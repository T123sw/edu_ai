import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeTestFiles,nativeTestResults,testPath} from './nativeTests';
import type {JestCheck} from './projectTypes';

const checks:JestCheck[]=[{id:'behavior',engine:'sandpack-jest',label:'行为',source:'test("行为",()=>expect(1).toBe(1));'}];
test('原生结果需要完整执行，空文件、跳过、错误、缺失都不能通过',()=>{
  for(const spec of [undefined,{}, {tests:{a:{status:'skip'}}}, {tests:{a:{status:'idle'}}}, {error:{message:'编译失败'}}, {tests:{a:{status:'pass'}},error:{message:'加载失败'}}]){
    assert.equal(nativeTestResults(checks,spec?{[testPath('behavior')]:spec}:{})[0].status,'failed');
  }
  const result=nativeTestResults(checks,{[testPath('behavior')]:{describes:{group:{tests:{a:{status:'pass'},b:{status:'fail',errors:[{message:'Expected 2; Received 1'}]}}}}}})[0];
  assert.equal(result.status,'failed');assert.match(result.message,/Expected 2/);
  assert.equal(nativeTestResults(checks,{[testPath('behavior')]:{describes:{group:{tests:{a:{status:'pass'}}}}}})[0].status,'passed');
});
test('测试不修改学生源码，宿主加入独立准备和实际断言要求',()=>{
  const files={'/src/App.jsx':'export default function App(){}','/src/styles.css':''};
  const copy={...files};const assembled=nativeTestFiles(files,checks);
  assert.deepEqual(files,copy);assert.equal(assembled['/__pbl__/test-entry.js'].code,'');assert.equal(JSON.parse(assembled['/package.json'].code).main,'/__pbl__/test-entry.js');
  assert.equal(assembled[testPath('behavior')].readOnly,true);
  assert.match(assembled[testPath('behavior')].code,/assertionCalls/);
  assert.equal(Object.keys(files).length,2);
});
