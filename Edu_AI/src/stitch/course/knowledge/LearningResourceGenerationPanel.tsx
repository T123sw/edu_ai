import { Modal } from "antd";

import { StandardLearningResources } from "./StandardLearningResources";

type Props = {
  onClose: () => void;
};

export function LearningResourceGenerationPanel({ onClose }: Props) {
  return (
    <Modal
      className="learning-resource-modal"
      title="学习资源生成"
      open
      centered
      width={1080}
      footer={null}
      destroyOnHidden
      onCancel={onClose}
    >
      <p className="learning-resource-modal__intro">
        选择知识点，批量生成 AI 课堂、学习指南和练习。提交后可关闭窗口，任务会在后台继续处理。
      </p>
      <StandardLearningResources compact onCancel={onClose} />
    </Modal>
  );
}
