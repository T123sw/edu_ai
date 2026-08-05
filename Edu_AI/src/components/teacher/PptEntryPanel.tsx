import { useEffect, useState } from 'react';
import { Alert, Button, Form, Input, Modal, Select, Space, Typography } from 'antd';
import type { ChatDirectPptOutlineResponseV2 } from '../../services/teacher/chatV2';

const { Text } = Typography;

export type PptEntryConfig = {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: 'short' | 'medium' | 'long';
  keyPointsText?: string;
  styleHint?: string;
  specialRequirements?: string;
};

type Props = {
  open: boolean;
  submitting?: boolean;
  onCancel: () => void;
  onBuildOutline: (config: PptEntryConfig) => Promise<ChatDirectPptOutlineResponseV2>;
  onGenerate: (draftId: string, outline: Record<string, unknown>) => Promise<void>;
};

function extractOutline(response: ChatDirectPptOutlineResponseV2): Record<string, unknown> {
  const artifact = response.artifacts.find(
    (item) => String(item.artifact_type || '') === 'ppt_outline',
  );
  const content = artifact?.content;
  return content && typeof content === 'object'
    ? content as Record<string, unknown>
    : {};
}

export default function PptEntryPanel({
  open,
  submitting = false,
  onCancel,
  onBuildOutline,
  onGenerate,
}: Props) {
  const [form] = Form.useForm<PptEntryConfig>();
  const [draftId, setDraftId] = useState('');
  const [outlineText, setOutlineText] = useState('');
  const [buildingOutline, setBuildingOutline] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) {
      setDraftId('');
      setOutlineText('');
      setError('');
      form.resetFields();
    }
  }, [form, open]);

  const buildOutline = async () => {
    try {
      const config = await form.validateFields();
      setBuildingOutline(true);
      setError('');
      const response = await onBuildOutline(config);
      setDraftId(response.draft.draft_id);
      setOutlineText(JSON.stringify(extractOutline(response), null, 2));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'PPT 大纲生成失败');
    } finally {
      setBuildingOutline(false);
    }
  };

  const generate = async () => {
    try {
      const outline = JSON.parse(outlineText);
      if (!outline || typeof outline !== 'object') {
        throw new Error('大纲格式不正确');
      }
      setError('');
      await onGenerate(draftId, outline);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'PPT 任务提交失败');
    }
  };

  return (
    <Modal
      title="生成 PPT"
      open={open}
      width={820}
      onCancel={onCancel}
      footer={
        <Space>
          <Button onClick={onCancel}>取消</Button>
          {!draftId ? (
            <Button type="primary" loading={buildingOutline} onClick={() => void buildOutline()}>
              生成大纲
            </Button>
          ) : (
            <>
              <Button loading={buildingOutline} onClick={() => void buildOutline()}>
                重新生成大纲
              </Button>
              <Button type="primary" loading={submitting} onClick={() => void generate()}>
                确认大纲并生成 PPT
              </Button>
            </>
          )}
        </Space>
      }
      destroyOnHidden={false}
    >
      <Text type="secondary">
        先根据所选资料生成逐页大纲。确认或修改大纲后，再提交后台生成和 PPTX 导出。
      </Text>
      {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 16 }} /> : null}
      {!draftId ? (
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            themeId: 'heu_academic_elegant',
            lengthOption: 'medium',
          }}
          style={{ marginTop: 20 }}
        >
          <Form.Item
            label="PPT 标题"
            name="deckTitle"
            rules={[{ required: true, message: '请输入 PPT 标题' }]}
          >
            <Input maxLength={100} placeholder="例如：变量与数据类型" />
          </Form.Item>
          <Form.Item label="副标题（可选）" name="deckSubtitle">
            <Input maxLength={120} />
          </Form.Item>
          <Space align="start" size={16} style={{ width: '100%' }}>
            <Form.Item label="适用对象" name="audience" style={{ minWidth: 220 }}>
              <Input placeholder="例如：高中信息技术学生" />
            </Form.Item>
            <Form.Item label="篇幅" name="lengthOption" style={{ minWidth: 160 }}>
              <Select
                options={[
                  { value: 'short', label: '精简 · 约 8 页' },
                  { value: 'medium', label: '标准 · 约 12 页' },
                  { value: 'long', label: '详细 · 约 18 页' },
                ]}
              />
            </Form.Item>
            <Form.Item label="模板" name="themeId" style={{ minWidth: 190 }}>
              <Select
                options={[
                  { value: 'heu_academic_elegant', label: '学术雅致' },
                  { value: 'heu_academic_basic', label: '学术简洁' },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item label="教学目标（可选）" name="objective">
            <Input placeholder="例如：理解变量的定义、赋值与变化过程" />
          </Form.Item>
          <Form.Item label="重点内容（每行一项）" name="keyPointsText">
            <Input.TextArea rows={4} placeholder={'变量定义\n命名规则\n赋值与更新'} />
          </Form.Item>
          <Form.Item label="风格与特殊要求（可选）" name="specialRequirements">
            <Input.TextArea rows={3} placeholder="例如：图文均衡，包含课堂提问和总结页" />
          </Form.Item>
        </Form>
      ) : (
        <div style={{ marginTop: 20 }}>
          <Alert
            type="success"
            showIcon
            message="大纲已生成"
            description="可以直接修改下面的逐页结构；提交前会再次校验格式。"
          />
          <Input.TextArea
            aria-label="PPT 大纲"
            value={outlineText}
            onChange={(event) => setOutlineText(event.target.value)}
            rows={18}
            style={{ marginTop: 16, fontFamily: 'Consolas, monospace' }}
          />
        </div>
      )}
    </Modal>
  );
}

