import test from 'node:test';
import assert from 'node:assert/strict';
import {createRecentOpenStore,recentFirst,recentKey,recentStorageKey,materialRecentKey} from './store';
const memory=()=>{const data=new Map<string,string>();return {getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>{data.set(key,value);}};};
test('点击顺序优先，刷新恢复，后台列表重排不覆盖访问顺序',()=>{
  const storage=memory(),key=recentStorageKey('alice'),store=createRecentOpenStore(storage,key,()=>100);
  store.mark('old');store.mark('new');store.mark('old');
  const restored=createRecentOpenStore(storage,key),items=['unopened','new','old'];
  assert.deepEqual(recentFirst(items,id=>id,restored.getSnapshot()),['old','new','unopened']);
  assert.deepEqual(items,['unopened','new','old']);
  assert.deepEqual(recentFirst(['new','old','unopened'],id=>id,restored.getSnapshot()),['old','new','unopened']);
});
test('账号、模块和资源身份隔离',()=>{
  const storage=memory(),alice=createRecentOpenStore(storage,recentStorageKey('alice')),bob=createRecentOpenStore(storage,recentStorageKey('bob'));
  alice.mark(recentKey('project','same'));
  assert.equal(alice.getSnapshot()[recentKey('practice','same')],undefined);assert.deepEqual(bob.getSnapshot(),{});
  assert.notEqual(materialRecentKey('report','same'),materialRecentKey('quiz','same'));
  assert.notEqual(materialRecentKey('report','same','course-a'),materialRecentKey('report','same','course-b'));
});
test('标签页合并记录，损坏和不可用存储不阻断点击',()=>{
  const storage=memory(),a=createRecentOpenStore(storage,'shared',()=>100),b=createRecentOpenStore(storage,'shared',()=>100);
  a.mark('a');b.mark('b');let updates=0;const off=a.subscribe(()=>updates++);a.sync();
  assert.equal(updates,1);assert.deepEqual(recentFirst(['a','b'],id=>id,a.getSnapshot()),['b','a']);off();
  storage.setItem('bad','invalid');const recovered=createRecentOpenStore(storage,'bad');recovered.mark('ok');assert.ok(recovered.getSnapshot().ok);
  const unavailable=createRecentOpenStore({getItem:()=>{throw Error('blocked');},setItem:()=>{throw Error('blocked');}},'private',()=>1);
  unavailable.mark('first');unavailable.mark('second');assert.deepEqual(recentFirst(['first','second'],id=>id,unavailable.getSnapshot()),['second','first']);
});
