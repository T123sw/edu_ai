import type { ProjectCheck, JestCheck } from './projectTypes';
import { BUNDLER_URL } from './bridge';
import {projectSetup,type ProjectRuntime} from './projectRuntime';
import { nativeTestPrelude } from './nativeTestPrelude';

export const NATIVE_TEST_OPTIONS = { bundlerTimeOut:60000, bundlerURL: BUNDLER_URL, visibleFiles: ['/src/App.jsx', '/src/styles.css'], activeFile: '/src/App.jsx' };
export const NATIVE_TEST_SETUP = { dependencies: {
  react: '18.3.1', 'react-dom': '18.3.1', '@testing-library/react': '14.3.1', '@testing-library/dom': '9.3.4',
} };
export const isJestCheck = (check: ProjectCheck): check is JestCheck => 'engine' in check && check.engine === 'sandpack-jest';
export const testPath = (id: string) => `/__checks__/${id}.test.js`;

export function nativeTestFiles(files: Record<string,string>, checks: JestCheck[], runtime?:ProjectRuntime|null) {
  const result: Record<string, {code:string; hidden?:boolean; readOnly?:boolean}> = {};
  const setup=projectSetup(files,runtime);
  for(const [path,value] of Object.entries(setup.files))result[path]=typeof value==='string'?{code:value,readOnly:true}:value;
  // The test client has its own iframe; it must not mount the preview application.
  result['/__pbl__/test-entry.js']={code:'',hidden:true,readOnly:true};
  const deps={...setup.customSetup.dependencies,...NATIVE_TEST_SETUP.dependencies};
  result['/package.json']={code:JSON.stringify({main:'/__pbl__/test-entry.js',dependencies:deps}),hidden:true,readOnly:true};
  for (const check of checks) result[testPath(check.id)] = {
    code: nativeTestPrelude(check.id)+check.source, hidden:true,readOnly:true,
  };
  return result;
}

type TestError = {message?:string};
export type NativeSpec = {name?:string;error?:TestError;tests?:Record<string,{status?:string;name?:string;errors?:TestError[]}>;describes?:Record<string,NativeSpec>};
export function nativeTestResults(checks: JestCheck[], specs: Record<string,NativeSpec>) {
  return checks.map(check => {
    const spec = specs[testPath(check.id)];
    const tests: {status?:string;name?:string;errors?:TestError[]}[] = [];
    const errors: string[] = [];
    function visit(block:NativeSpec) {
      if(block.error) errors.push(block.error.message || '测试文件执行失败');
      tests.push(...Object.values(block.tests || {}));
      Object.values(block.describes || {}).forEach(visit);
    }
    if(spec) visit(spec);
    const passed = Boolean(spec && tests.length && !errors.length && tests.every(test=>test.status==='pass'&&!test.errors?.length));
    const message = !spec ? '测试文件未执行' : !tests.length ? errors.join('\n') || '未执行任何测试' : [
      ...errors,
      ...tests.map(test=>`${test.name || '测试'}：${test.status==='pass'?'通过':'未通过'}${test.errors?.length?'\n'+test.errors.map(error=>error.message || '断言失败').join('\n'):''}`),
    ].join('\n');
    return {caseId:check.id,status:passed?'passed' as const:'failed' as const,message:message.slice(0,2000)};
  });
}
