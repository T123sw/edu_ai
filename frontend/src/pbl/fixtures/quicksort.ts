import type { TestCase } from '../types';
export const starterCode = "export function quickSort(array) {\n  // 请在这里实现快速排序\n  throw new Error('NOT_IMPLEMENTED');\n}\n";
export const referenceSolution = `export function quickSort(array) {
  if (array.length <= 1) return array.slice();
  const [pivot, ...rest] = array;
  const left = rest.filter(value => value < pivot);
  const right = rest.filter(value => value >= pivot);
  return [...quickSort(left), pivot, ...quickSort(right)];
}\n`;
export const testCases: TestCase[] = [
  {id:'mixed',label:'普通乱序',input:[4,1,3,2],expected:[1,2,3,4]},
  {id:'duplicates',label:'重复元素',input:[3,1,3,2],expected:[1,2,3,3]},
  {id:'negative',label:'负数与零',input:[0,-2,5,-1],expected:[-2,-1,0,5]},
  {id:'empty',label:'空数组',input:[],expected:[]},
  {id:'single',label:'单元素',input:[7],expected:[7]},
  {id:'sorted',label:'已排序',input:[1,2,3],expected:[1,2,3]},
  {id:'reversed',label:'逆序',input:[3,2,1],expected:[1,2,3]},
  {id:'numeric',label:'数值顺序',input:[10,2,1],expected:[1,2,10]},
  {id:'decimal',label:'小数',input:[1.5,-0.5,0],expected:[-0.5,0,1.5]},
];
