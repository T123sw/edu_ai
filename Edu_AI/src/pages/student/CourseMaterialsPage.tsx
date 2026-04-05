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
  Popconfirm,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  AudioOutlined,
  BookOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  EditOutlined,
  QuestionCircleOutlined,
  MoreOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';
import type { GeneratedFile } from '../../store/teacher/useStore';
import './CourseMaterialsPage.css';

const { Title, Text } = Typography;

// 学生端课程资料类型：只保留技术博客和测验（承接自教师端）
const materialTypes: Array<{
  key: GeneratedFile['type'];
  label: string;
  icon: React.ReactNode;
  color: string;
}> = [
  { key: 'blog', label: '技术博客', icon: <EditOutlined />, color: '#ff7875' },
  { key: 'quiz', label: '测验', icon: <QuestionCircleOutlined />, color: '#1890ff' },
];

const getFileIcon = (type: GeneratedFile['type'], size = 20) => {
  const typeConfig = materialTypes.find(t => t.key === type);
  if (typeConfig) {
    return React.cloneElement(typeConfig.icon as React.ReactElement, {
      style: { fontSize: size, color: typeConfig.color },
    });
  }
  return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
};

export default function CourseMaterialsPage() {
  const { materials, removeMaterial, getMaterialsByType } = useCourseMaterialsStore();
  const [activeTab, setActiveTab] = useState<GeneratedFile['type']>('blog');

  const handleDelete = (id: string) => {
    removeMaterial(id);
    message.success('已删除');
  };

  const currentMaterials = getMaterialsByType(activeTab);

  const tabItems = materialTypes.map(type => ({
    key: type.key,
    label: (
      <Space>
        <span style={{ color: type.color }}>{type.icon}</span>
        <span>{type.label}</span>
        <span style={{ color: '#999', fontSize: 12 }}>
          ({getMaterialsByType(type.key).length})
        </span>
      </Space>
    ),
  }));

  return (
    <div className="course-materials-page">
      <div className="course-materials-header">
        <Title level={2} style={{ marginBottom: 8 }}>
          课程资料
        </Title>
        <Text type="secondary">
          查看教师端传下来的技术博客和测验资料
        </Text>
      </div>

      <Card className="course-materials-card">
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as GeneratedFile['type'])}
          items={tabItems}
        >
        </Tabs>

        <div style={{ marginTop: 24 }}>
          {currentMaterials.length === 0 ? (
            <Empty
              description={
                <Text type="secondary">
                  暂无{materialTypes.find(t => t.key === activeTab)?.label}资料
                </Text>
              }
            />
          ) : (
            <List
              dataSource={currentMaterials}
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
                          添加时间：{new Date(item.addedAt).toLocaleString('zh-CN')}
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

