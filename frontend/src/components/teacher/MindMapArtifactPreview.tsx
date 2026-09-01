import { ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Empty, Typography } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';

const { Text, Title } = Typography;

type Node = { title: string; summary?: string | null; children?: Node[] };

function MindNode({ node, depth = 0 }: { node: Node; depth?: number }) {
  return (
    <li className={`mind-map-preview__node depth-${Math.min(depth, 4)}`}>
      <div className="mind-map-preview__node-card">
        <Text strong>{node.title}</Text>
        {node.summary ? <Text type="secondary">{node.summary}</Text> : null}
      </div>
      {node.children?.length ? (
        <ul>{node.children.map((child, index) => <MindNode key={`${child.title}-${index}`} node={child} depth={depth + 1} />)}</ul>
      ) : null}
    </li>
  );
}

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
  const root = payload.root && typeof payload.root === 'object' ? payload.root as Node : null;
  return (
    <div className="mind-map-preview edu-rich-preview">
      <div className="mind-map-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>返回</Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>
      <Title level={4}>{file.name}</Title>
      <Text type="secondary">按知识层级检查概念关系；资源会随课程长期保存。</Text>
      <div className="mind-map-preview__canvas">
        {root ? <ul><MindNode node={root} /></ul> : <Empty description="暂无可用导图内容" />}
      </div>
    </div>
  );
}

