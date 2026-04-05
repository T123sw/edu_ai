import React, { useState } from 'react';
import {
  Card,
  Tabs,
  List,
  Button,
  Typography,
  Space,
  Dropdown,
  message,
  Empty,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  AudioOutlined,
  BookOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  MoreOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import type { GeneratedFile } from '../../store/teacher/useStore';
import './LearningRecordPage.css';

const { Title, Text } = Typography;

// 学习记录类型：保存生成式工厂生成的内容
const recordTypes: Array<{
  key: GeneratedFile['type'];
  label: string;
  icon: React.ReactNode;
  color: string;
}> = [
  { key: 'audio', label: '音频概览', icon: <AudioOutlined />, color: '#722ed1' },
  { key: 'graph', label: '思维导图', icon: <ApartmentOutlined />, color: '#eb2f96' },
  { key: 'report', label: '报告', icon: <FileTextOutlined />, color: '#faad14' },
  { key: 'quiz', label: '测验', icon: <QuestionCircleOutlined />, color: '#1890ff' },
  { key: 'flashcard', label: '闪卡', icon: <BookOutlined />, color: '#ff7875' },
];

const getFileIcon = (type: GeneratedFile['type'], size = 20) => {
  const typeConfig = recordTypes.find(t => t.key === type);
  if (typeConfig) {
    return React.cloneElement(typeConfig.icon as React.ReactElement, {
      style: { fontSize: size, color: typeConfig.color },
    });
  }
  return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
};

export default function LearningRecordPage() {
  const { generatedFiles, removeGeneratedFile } = useStore();
  const [activeTab, setActiveTab] = useState<GeneratedFile['type']>('audio');

  const handleDelete = (id: string) => {
    removeGeneratedFile(id);
    message.success('已删除');
  };

  const currentRecords = generatedFiles.filter(file => file.type === activeTab);

  const tabItems = recordTypes.map(type => ({
    key: type.key,
    label: (
      <Space>
        <span style={{ color: type.color }}>{type.icon}</span>
        <span>{type.label}</span>
        <span style={{ color: '#999', fontSize: 12 }}>
          ({generatedFiles.filter(f => f.type === type.key).length})
        </span>
      </Space>
    ),
  }));

  return (
    <div className="learning-record-page">
      <div className="learning-record-header">
        <Title level={2} style={{ marginBottom: 8 }}>
          学习资料
        </Title>
        <Text type="secondary">
          管理从生成式工厂保存下来的学习内容，按类型分类查看和管理
        </Text>
      </div>

      <Card className="learning-record-card">
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as GeneratedFile['type'])}
          items={tabItems}
        >
        </Tabs>

        <div style={{ marginTop: 24 }}>
          {currentRecords.length === 0 ? (
            <Empty
              description={
                <Text type="secondary">
                  暂无{recordTypes.find(t => t.key === activeTab)?.label}记录
                </Text>
              }
            />
          ) : (
            <List
              dataSource={currentRecords}
              renderItem={(item) => {
                const menuItems: MenuProps['items'] = [
                  {
                    key: 'view',
                    label: '查看',
                    icon: <EyeOutlined />,
                    onClick: () => {
                      // TODO: 实现查看功能
                      message.info('查看功能待实现');
                    },
                  },
                  {
                    key: 'delete',
                    label: '删除',
                    icon: <DeleteOutlined />,
                    danger: true,
                    onClick: () => {
                      handleDelete(item.id);
                    },
                  },
                ];

                return (
                  <List.Item
                    style={{
                      padding: '12px 0',
                      borderBottom: '1px solid #f0f0f0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <div style={{ marginRight: 12 }}>
                        {getFileIcon(item.type)}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Text strong style={{ display: 'block', marginBottom: 4 }}>
                          {item.name}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          创建时间：{new Date(parseInt(item.id)).toLocaleString('zh-CN')}
                        </Text>
                      </div>
                      <Space>
                        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                          <Button
                            type="text"
                            icon={<MoreOutlined />}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Dropdown>
                      </Space>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
        </div>
      </Card>
    </div>
  );
}

