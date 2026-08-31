import { MaterialIcon } from "../../shared";
import { StandardLearningResources } from "./StandardLearningResources";

type Props = {
  onClose: () => void;
};

export function LearningResourceGenerationPanel({ onClose }: Props) {
  return (
    <section
      className="course-kb-resource-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="course-kb-resource-panel-title"
    >
      <header className="course-kb-resource-panel__header">
        <div>
          <span>按叶子知识点组织</span>
          <h2 id="course-kb-resource-panel-title">学习资源生成</h2>
          <p>选择知识点，生成 AI 课堂、学习指南和练习。提交后可以离开当前页面，任务会在后台继续处理。</p>
        </div>
        <button type="button" onClick={onClose}>
          <MaterialIcon name="expand_less" />
          收起
        </button>
      </header>
      <StandardLearningResources />
    </section>
  );
}
