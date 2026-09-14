import { ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Empty, Typography } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';
import { MindMapCanvas, type MindMapNode } from '../mindmap/MindMapCanvas';

const { Text, Title } = Typography;

export default function MindMapArtifactPreview({
  file,
  onBack,
  onToggleCollapsed,
}: {
  file: GeneratedFile;
  onBack: () => void;
  onToggleCollapsed: () => void;
}) {
  const payload = file.content && typeof file.content === 'object'
    ? file.content as Record<string, unknown>
    : {};
  const root = payload.root && typeof payload.root === 'object' ? payload.root as MindMapNode : null;
  return (
    <div className="mind-map-preview edu-rich-preview">
      <div className="mind-map-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>返回</Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>
      <Title level={4}>{file.name}</Title>
      <Text type="secondary">按知识层级检查概念关系；资源会随课程长期保存。</Text>
      <div className="mind-map-preview__canvas">
        {root ? <MindMapCanvas root={root} label={file.name} /> : <Empty description="暂无可用导图内容" />}
      </div>
    </div>
  );
}
