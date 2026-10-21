import { PracticeSelect } from './PracticeSelect';
export type PracticeMode = 'simulation' | 'code';
const options = [
  { value: 'simulation', label: '模拟实验', description: '调整参数、观察变化，动手探索原理' },
  { value: 'code', label: '编程练习（PBL）', description: '亲手编写代码，通过运行和检查完成项目' },
];
export function PracticeModeSelect({ value, onChange }: { value: PracticeMode; onChange: (value: PracticeMode) => void }) {
  return <PracticeSelect label="实践方式" options={options} value={value} onChange={value => onChange(value as PracticeMode)} />;
}
