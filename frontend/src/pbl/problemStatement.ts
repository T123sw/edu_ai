import type { ExerciseTask, TestCase } from './types';

export interface StatementExample {input:string;output:string}

// Choose existing, validated public data; never manufacture an expected result.
export function algorithmExample(step:ExerciseTask,cases:TestCase[]):StatementExample|undefined {
  const examples=[...step.examples,...cases];
  const illustratesSorting=(example:{input:number[];expected:number[]})=>example.input.length>=3&&example.input.length<=8&&example.input.some((value,index)=>value!==example.expected[index]);
  const example=examples.find(illustratesSorting)
    || examples.find(item=>item.input.length>1&&item.input.some((value,index)=>value!==item.expected[index]))
    || examples.find(item=>item.input.length>0)
    || examples[0];
  return example?{input:JSON.stringify(example.input),output:JSON.stringify(example.expected)}:undefined;
}
