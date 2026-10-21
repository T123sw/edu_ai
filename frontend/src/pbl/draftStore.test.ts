import {test} from 'node:test';
import assert from 'node:assert/strict';
import {draftKey} from './draftStore';
test('草稿键同时隔离账号、练习和产物版本',()=>{
  assert.notEqual(draftKey('alice','exercise',1),draftKey('bob','exercise',1));
  assert.notEqual(draftKey('alice','exercise',1),draftKey('alice','exercise',2));
  assert.notEqual(draftKey('alice/a','b',1),draftKey('alice','a/b',1));
});
