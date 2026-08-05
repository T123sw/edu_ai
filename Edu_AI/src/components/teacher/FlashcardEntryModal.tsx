import { Form, Input, InputNumber, Modal, Select, Switch, Typography } from 'antd';

const { Text } = Typography;

export type FlashcardEntryValue = {
  title?: string;
  count: number;
  difficulty: 'easy' | 'medium' | 'hard';
  category?: string;
  showSources: boolean;
};

type Props = {
  open: boolean;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (value: FlashcardEntryValue) => Promise<void>;
};

export default function FlashcardEntryModal({
  open,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [form] = Form.useForm<FlashcardEntryValue>();

  return (
    <Modal
      title="生成闪卡"
      open={open}
      okText="开始生成"
      cancelText="取消"
      confirmLoading={submitting}
      onCancel={onCancel}
      onOk={async () => onSubmit(await form.validateFields())}
      destroyOnHidden={false}
    >
      <Text type="secondary">
        闪卡会严格依据已勾选的课程资料生成，并在完成后保存到课程资源。
      </Text>
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          count: 10,
          difficulty: 'medium',
          category: '',
          showSources: true,
        }}
        style={{ marginTop: 20 }}
      >
        <Form.Item label="闪卡标题（可选）" name="title">
          <Input maxLength={80} placeholder="例如：变量与数据类型复习卡" />
        </Form.Item>
        <Form.Item
          label="卡片数量"
          name="count"
          rules={[{ required: true, message: '请选择卡片数量' }]}
        >
          <InputNumber min={3} max={30} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="难度" name="difficulty">
          <Select
            options={[
              { value: 'easy', label: '基础记忆' },
              { value: 'medium', label: '理解应用' },
              { value: 'hard', label: '综合辨析' },
            ]}
          />
        </Form.Item>
        <Form.Item label="分类偏好（可选）" name="category">
          <Input maxLength={40} placeholder="例如：核心概念、易错点" />
        </Form.Item>
        <Form.Item
          label="显示资料来源"
          name="showSources"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}

