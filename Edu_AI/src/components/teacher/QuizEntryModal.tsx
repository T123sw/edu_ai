import React, { useEffect, useState } from 'react';
import { Alert, Button, Form, Input, InputNumber, Modal, Select, Skeleton, Space, Switch, Typography, message } from 'antd';

import {
  fetchQuizEntryPrefillV2,
  type DirectQuizConfigV2,
  type QuizQuestionTypeV2,
} from '../../services/teacher/chatV2';
import { DEFAULT_QUIZ_CONFIG } from '../../services/teacher/quizEntry.helpers';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';

const { Text } = Typography;

type Props = {
  open: boolean;
  selectedDocIds: string[];
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { config: DirectQuizConfigV2 }) => Promise<void> | void;
};

const QUESTION_TYPE_OPTIONS: Array<{ value: QuizQuestionTypeV2; label: string }> = [
  { value: 'choice', label: '选择题' },
  { value: 'judge', label: '判断题' },
  { value: 'blank', label: '填空题' },
  { value: 'short', label: '简答题' },
];

export default function QuizEntryModal({
  open,
  selectedDocIds,
  courseId,
  workspaceScope,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [form] = Form.useForm<DirectQuizConfigV2>();
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!open) {
      form.resetFields();
      setLoading(false);
      setLoadError('');
      return;
    }

    if (!selectedDocIds.length) {
      setLoadError('请先选择至少一份文档。');
      form.setFieldsValue(DEFAULT_QUIZ_CONFIG);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadError('');
    fetchQuizEntryPrefillV2({
      course_id: courseId,
      scope_type: workspaceScope?.scopeType,
      scope_id: workspaceScope?.scopeId,
      selected_doc_ids: selectedDocIds,
    })
      .then((response) => {
        if (cancelled) return;
        form.setFieldsValue({
          ...DEFAULT_QUIZ_CONFIG,
          topic: response.topic || DEFAULT_QUIZ_CONFIG.topic,
          hard_points: Array.isArray(response.hard_points) ? response.hard_points : [],
        });
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setLoadError(error.message || '习题配置预填失败');
        form.setFieldsValue(DEFAULT_QUIZ_CONFIG);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [courseId, form, open, selectedDocIds, workspaceScope]);

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (!values.question_types?.length) {
      message.warning('请至少选择一种题型');
      return;
    }
    await onSubmit({
      config: {
        ...DEFAULT_QUIZ_CONFIG,
        ...values,
        hard_points: Array.isArray(values.hard_points) ? values.hard_points : [],
        question_types: Array.isArray(values.question_types) ? values.question_types : DEFAULT_QUIZ_CONFIG.question_types,
      },
    });
  };

  return (
    <Modal
      title="创建习题"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={720}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {loading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
        {loadError ? <Alert type="warning" showIcon message={loadError} /> : null}

        {!loading && (
          <Form
            form={form}
            layout="vertical"
            initialValues={DEFAULT_QUIZ_CONFIG}
          >
            <Form.Item
              label="主题"
              name="topic"
              rules={[{ required: true, message: '请输入习题主题' }]}
            >
              <Input placeholder="根据已选文档自动预填，可手动修改" />
            </Form.Item>

            <Form.Item
              label="重点难点"
              name="hard_points"
              tooltip="已根据勾选文档自动预填，可继续补充或删除"
            >
              <Select
                mode="tags"
                placeholder="输入重点难点，按回车添加"
                tokenSeparators={[',', '，']}
              />
            </Form.Item>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 12,
              }}
            >
              <Form.Item
                label="难度"
                name="difficulty"
                rules={[{ required: true, message: '请选择难度' }]}
              >
                <Select
                  options={[
                    { value: 'easy', label: '简单' },
                    { value: 'medium', label: '中等' },
                    { value: 'hard', label: '困难' },
                  ]}
                />
              </Form.Item>

              <Form.Item
                label="数量"
                name="question_count"
                rules={[{ required: true, message: '请输入题目数量' }]}
              >
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
            </div>

            <Form.Item
              label="题型"
              name="question_types"
              rules={[{ required: true, message: '请至少选择一种题型' }]}
            >
              <Select
                mode="multiple"
                placeholder="可勾选多个题型"
                options={QUESTION_TYPE_OPTIONS}
              />
            </Form.Item>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
              <Form.Item label="附答案" name="include_answers" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="附解析" name="include_explanations" valuePropName="checked">
                <Switch />
              </Form.Item>
            </div>

            <div style={{ padding: 12, borderRadius: 10, background: '#f7f9fc', marginBottom: 12 }}>
              <Text type="secondary">
                已选文档 {selectedDocIds.length} 份。提交后会把勾选文档内容、上面的配置项，以及固定的习题生成提示一起交给大模型直接生成。
              </Text>
            </div>

            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button onClick={onCancel} disabled={submitting}>
                取消
              </Button>
              <Button type="primary" onClick={handleSubmit} loading={submitting}>
                生成习题
              </Button>
            </Space>
          </Form>
        )}
      </Space>
    </Modal>
  );
}
