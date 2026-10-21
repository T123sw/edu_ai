import assert from 'node:assert/strict';
import test from 'node:test';
import {algorithmExample} from './problemStatement';
import type {ExerciseTask,TestCase} from './types';

test('首个空数组或已排序示例不掩盖后续有代表性的模型示例',()=>{
  const task={examples:[{input:[],expected:[]},{input:[1,2,3],expected:[1,2,3]},{input:[4,-1,4,2],expected:[-1,2,4,4]}]} as ExerciseTask;
  assert.deepEqual(algorithmExample(task,[]),{input:'[4,-1,4,2]',output:'[-1,2,4,4]'});
});
test('旧题只有边界示例时可选公开用例，不自行计算或编造输出',()=>{
  const task={examples:[{input:[],expected:[]}]} as ExerciseTask;
  const cases=[{id:'mixed',label:'乱序',input:[3,1,2],expected:[1,2,3]}] as TestCase[];
  assert.deepEqual(algorithmExample(task,cases),{input:'[3,1,2]',output:'[1,2,3]'});
  assert.deepEqual(algorithmExample(task,[]),{input:'[]',output:'[]'});
});
