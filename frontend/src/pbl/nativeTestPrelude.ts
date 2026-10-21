// Sandpack's jest-lite reports test bodies but drops hook failures and does not
// await beforeAll/afterAll. Keep its runner/matchers and adapt those omissions.
// This code executes only inside the test iframe, never in the application host.
export function nativeTestPrelude(checkId:string) {
  return `import {cleanup as __pblCleanup} from '@testing-library/react';
const __pblNative = {test:globalThis.test, beforeEach:globalThis.beforeEach, afterEach:globalThis.afterEach, beforeAll:globalThis.beforeAll, afterAll:globalThis.afterAll};
const __pblBeforeAll = [];
const __pblSend = (event,message) => globalThis.parent.postMessage({channel:'pbl-jest-hooks-v1',checkId:${JSON.stringify(checkId)},event,message}, '*');
const __pblCall = (fn,args=[]) => fn.length>args.length ? new Promise((resolve,reject)=>fn(...args,error=>error?reject(error):resolve())) : Promise.resolve().then(()=>fn(...args));
function __pblHook(fn, timeout, prepare=false) {
  return function() {
    __pblSend('start');
    let timer;
    const work = Promise.race([
      (prepare?Promise.resolve():Promise.all(__pblBeforeAll)).then(()=>__pblCall(fn)),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('测试准备或清理超时')),timeout || 5000)})
    ]).catch(error=>{__pblSend('error',String((error && error.message) || error));throw error;}).finally(()=>{clearTimeout(timer);__pblSend('end');});
    if(prepare) __pblBeforeAll.push(work);
    return work;
  };
}
const beforeAll = (fn,timeout) => __pblNative.beforeAll(__pblHook(fn,timeout,true),timeout);
const afterAll = (fn,timeout) => __pblNative.afterAll(__pblHook(fn,timeout),timeout);
const beforeEach = (fn,timeout) => __pblNative.beforeEach(__pblHook(fn,timeout),timeout);
const afterEach = (fn,timeout) => __pblNative.afterEach(__pblHook(fn,timeout),timeout);
__pblNative.beforeEach(async()=>{await Promise.all(__pblBeforeAll);__pblCleanup();document.body.innerHTML='';localStorage.clear();sessionStorage.clear();expect.setState({assertionCalls:0});});
__pblNative.afterEach(()=>__pblCleanup());
function __pblWrapTest(native) {
  return new Proxy(native, {
    apply(target,receiver,args) {
      const [name,body,...rest]=args;
      if(typeof body!=='function') return Reflect.apply(target,receiver,args);
      return Reflect.apply(target,receiver,[name,async function(...testArgs){
        await Promise.all(__pblBeforeAll);
        await __pblCall(body,testArgs);
        if(expect.getState().assertionCalls<1) throw new Error('本项测试没有执行断言');
      },...rest]);
    },
    get(target,key) {
      if(key==='only'||key==='skip') return __pblWrapTest(target[key]);
      if(key==='each') return (...table)=>__pblWrapTest(target.each(...table));
      return target[key];
    }
  });
}
const test=__pblWrapTest(__pblNative.test);
const it=test;
`;
}
