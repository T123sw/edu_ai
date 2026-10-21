import { PracticeSelect } from './PracticeSelect';

const options = [
  { value: '自动设计', description: '根据主题安排探索方式' },
  { value: '观察参数变化', description: '调一调参数，观察结果怎样变化' },
  { value: '比较不同条件', description: '对比不同条件，发现结果的差异' },
  { value: '验证原理', description: '通过动手操作，理解背后的规律' },
];

export function PracticeFocusSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <PracticeSelect label="实验侧重" options={options} value={value} onChange={onChange} />;
}
