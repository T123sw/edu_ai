import React, { useState } from 'react';
import { Button, Divider, Dropdown, Space, Tooltip, Typography, Modal, Form, Input, Select, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileMarkdownOutlined,
  FileTextOutlined,
  LeftOutlined,
  MoreOutlined,
  QuestionCircleOutlined,
  RightOutlined,
  AudioOutlined,
  BookOutlined,
  EditOutlined,
  PlayCircleOutlined,
  VideoCameraOutlined,
  FilePdfOutlined,
  TableOutlined,
  FilePptOutlined,
  InfoCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import type { GeneratedFile } from '../../store/teacher/useStore';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';

const { Title, Text, Paragraph } = Typography;

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

const getGeneratedFileIcon = (file: GeneratedFile, size = 20) => {
  switch (file.type) {
    case 'report':
      return <FileMarkdownOutlined style={{ fontSize: size, color: '#555' }} />;
    case 'quiz':
      return <QuestionCircleOutlined style={{ fontSize: size, color: '#f7b731' }} />;
    case 'blog':
      return <FileTextOutlined style={{ fontSize: size, color: '#1890ff' }} />;
    case 'lesson_plan':
      return <BookOutlined style={{ fontSize: size, color: '#52c41a' }} />;
    case 'audio':
      return <AudioOutlined style={{ fontSize: size, color: '#722ed1' }} />;
    case 'video':
      return <VideoCameraOutlined style={{ fontSize: size, color: '#52c41a' }} />;
    case 'graph':
      return <ApartmentOutlined style={{ fontSize: size, color: '#4caf50' }} />;
    case 'flashcard':
      return <BookOutlined style={{ fontSize: size, color: '#ff7875' }} />;
    default:
      return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
  }
};

// 生成功能卡片组件
interface GenerativeCardProps {
  icon: React.ReactNode;
  title: string;
  color: string;
  onGenerate: () => void;
  onConfigure: () => void;
}

const GenerativeCard: React.FC<GenerativeCardProps> = ({ icon, title, color, onGenerate, onConfigure }) => {
  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: `linear-gradient(135deg, ${color}15 0%, ${color}08 100%)`,
        borderRadius: '24px',
        border: `1px solid ${color}30`,
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        minHeight: 56,
      }}
      onClick={onGenerate}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${color}25 0%, ${color}15 100%)`;
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = `0 4px 12px ${color}30`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${color}15 0%, ${color}08 100%)`;
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
        <div style={{ fontSize: 20, color: color }}>
          {icon}
        </div>
        <Text strong style={{ fontSize: 14, color: '#1e293b' }}>
          {title}
        </Text>
      </div>
      <Button
        type="text"
        icon={<EditOutlined />}
        size="small"
        onClick={(e) => {
          e.stopPropagation();
          onConfigure();
        }}
        style={{
          color: color,
          padding: '4px 8px',
          minWidth: 'auto',
        }}
      />
    </div>
  );
};

const StudioPanel: React.FC<Props> = ({ collapsed, onToggleCollapsed }) => {
  const { generatedFiles, viewingFile, addGeneratedFile, removeGeneratedFile, setViewingFile } = useStore();
  const { addMaterial } = useCourseMaterialsStore();
  const [configModalVisible, setConfigModalVisible] = useState(false);
  const [configType, setConfigType] = useState<string>('');
  const [configForm] = Form.useForm();

  const handleGenerate = (type: GeneratedFile['type'] | string) => {
    const typeNames: Record<string, string> = {
      report: '报告',
      quiz: '测验',
      blog: '博客',
      lesson_plan: '教案',
      audio: '音频概览',
      video: '视频概览',
      graph: '思维导图',
      flashcard: '闪卡',
    };
    
    const newFile: GeneratedFile = {
      id: Date.now().toString(),
      name: `新${typeNames[type] || '文件'}-${generatedFiles.length + 1}`,
      type: type as GeneratedFile['type'],
    };
    addGeneratedFile(newFile);
    // TODO: 调用后端生成API
    console.log('生成类型:', type);
  };

  const handleConfigure = (type: string) => {
    setConfigType(type);
    setConfigModalVisible(true);
    // TODO: 加载该类型的配置参数
    configForm.setFieldsValue({});
  };

  const handleConfigSubmit = () => {
    configForm.validateFields().then((values) => {
      console.log('配置参数:', values);
      // TODO: 保存配置参数
      setConfigModalVisible(false);
      configForm.resetFields();
    });
  };

  const handleAddToCourseMaterials = (file: GeneratedFile) => {
    const material = {
      ...file,
      addedAt: new Date().toISOString(),
    };
    addMaterial(material);
    message.success('已增加到学习资料');
  };

  // Collapsed view: 显示功能模块logo和文档列表
  if (collapsed) {
    // 功能类型定义
    const functionTypes = [
      { type: 'audio' as const, icon: <AudioOutlined />, color: '#722ed1' },
      { type: 'graph' as const, icon: <ApartmentOutlined />, color: '#eb2f96' },
      { type: 'report' as const, icon: <FileTextOutlined />, color: '#faad14' },
      { type: 'quiz' as const, icon: <QuestionCircleOutlined />, color: '#1890ff' },
      { type: 'flashcard' as const, icon: <BookOutlined />, color: '#ff7875' },
    ];

    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          background: '#ffffff',
          borderRadius: 12,
          padding: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <Button 
            type="text" 
            icon={<LeftOutlined />} 
            onClick={onToggleCollapsed} 
            aria-label="展开工作室"
            style={{ padding: '4px 8px' }}
          />
        </div>
        
        {/* 功能模块logo - 一字排开 */}
        <div style={{ 
          display: 'flex',
          flexDirection: 'column',
          gap: 8, 
          marginBottom: 16,
          paddingBottom: 16,
          borderBottom: '1px solid #f0f0f0'
        }}>
          {functionTypes.map((func) => (
            <div
              key={func.type}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '10px',
                background: `${func.color}10`,
                borderRadius: 8,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = `${func.color}20`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = `${func.color}10`;
              }}
              onClick={() => handleGenerate(func.type)}
            >
              <div style={{ fontSize: 18, color: func.color }}>
                {func.icon}
              </div>
            </div>
          ))}
        </div>

        {/* 生成的文档列表 */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {generatedFiles.length > 0 ? (
            generatedFiles.map((f) => (
              <div
                key={f.id}
                style={{ 
                  height: 40, 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  marginBottom: 4,
                  cursor: 'pointer',
                  borderRadius: 4,
                  transition: 'background 0.2s',
                }}
                onClick={() => setViewingFile(f)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
                title={f.name}
              >
                {getGeneratedFileIcon(f, 18)}
              </div>
            ))
          ) : (
            <Text type="secondary" style={{ fontSize: 12, textAlign: 'center', display: 'block' }}>
              暂无生成文件
            </Text>
          )}
        </div>
      </div>
    );
  }

  // Detail view
  if (viewingFile) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          background: '#ffffff',
          borderRadius: 12,
          padding: 24,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => setViewingFile(null)}
            style={{ marginLeft: -12 }}
          >
            返回
          </Button>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
        </div>

        <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
          {viewingFile.name}
        </Title>
        <Divider style={{ flexShrink: 0 }} />
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <Paragraph>这里是【{viewingFile.name}】的内容预览。TODO: 集成实际内容显示。</Paragraph>
        </div>
      </div>
    );
  }

  // List view
  return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          background: '#ffffff',
          borderRadius: 12,
          padding: 24,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexShrink: 0 }}>
        <Title level={5} style={{ margin: 0, fontWeight: 600 }}>
          生成式工场
        </Title>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>

      <Text type="secondary" style={{ flexShrink: 0, marginBottom: 16, display: 'block' }}>点击生成</Text>
      
      {/* 五个功能：两行布局 */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(3, 1fr)', 
        gap: 12, 
        marginBottom: 16,
        flexShrink: 0 
      }}>
        {/* 第一行 */}
        <GenerativeCard
          icon={<AudioOutlined />}
          title="音频概览"
          color="#722ed1"
          onGenerate={() => handleGenerate('audio')}
          onConfigure={() => handleConfigure('audio')}
        />
        <GenerativeCard
          icon={<ApartmentOutlined />}
          title="思维导图"
          color="#eb2f96"
          onGenerate={() => handleGenerate('graph')}
          onConfigure={() => handleConfigure('graph')}
        />
        <GenerativeCard
          icon={<FileTextOutlined />}
          title="报告"
          color="#faad14"
          onGenerate={() => handleGenerate('report')}
          onConfigure={() => handleConfigure('report')}
        />
        
        {/* 第二行 */}
        <GenerativeCard
          icon={<QuestionCircleOutlined />}
          title="测验"
          color="#1890ff"
          onGenerate={() => handleGenerate('quiz')}
          onConfigure={() => handleConfigure('quiz')}
        />
        <GenerativeCard
          icon={<BookOutlined />}
          title="闪卡"
          color="#ff7875"
          onGenerate={() => handleGenerate('flashcard')}
          onConfigure={() => handleConfigure('flashcard')}
        />
      </div>
      <Divider style={{ margin: '12px 0', flexShrink: 0 }} />

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {generatedFiles.map((item) => {
          const menuItems: MenuProps['items'] = [
            {
              key: 'add-to-course',
              label: '增加到学习资料',
              icon: <PlusOutlined />,
              onClick: (info) => {
                info.domEvent.stopPropagation();
                handleAddToCourseMaterials(item);
              },
            },
            {
              key: 'delete',
              label: '删除',
              icon: <DeleteOutlined />,
              danger: true,
              onClick: (info) => {
                info.domEvent.stopPropagation();
                removeGeneratedFile(item.id);
              },
            },
          ];

          return (
            <div key={item.id} style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '8px 0' }}>
              <div
                style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, cursor: 'pointer' }}
                onClick={() => setViewingFile(item)}
              >
                {getGeneratedFileIcon(item)}
                <Text ellipsis={{ tooltip: item.name }} style={{ marginLeft: 12 }}>
                  {item.name}
                </Text>
              </div>

              <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                <Button type="text" icon={<MoreOutlined />} onClick={(e) => e.stopPropagation()} />
              </Dropdown>

              <Tooltip title="查看">
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setViewingFile(item);
                  }}
                />
              </Tooltip>
            </div>
          );
        })}
      </div>

      {/* 配置参数模态框 */}
      <Modal
        title={`配置${configType === 'audio' ? '音频概览' : configType === 'graph' ? '思维导图' : configType === 'report' ? '报告' : configType === 'quiz' ? '测验' : configType === 'flashcard' ? '闪卡' : '未知'}参数`}
        open={configModalVisible}
        onOk={handleConfigSubmit}
        onCancel={() => {
          setConfigModalVisible(false);
          configForm.resetFields();
        }}
        okText="保存配置"
        cancelText="取消"
        width={600}
      >
        <Form
          form={configForm}
          layout="vertical"
          style={{ marginTop: 24 }}
        >
          <Form.Item
            label="生成主题"
            name="topic"
            rules={[{ required: true, message: '请输入生成主题' }]}
          >
            <Input placeholder="请输入要生成的内容主题" />
          </Form.Item>
          
          <Form.Item
            label="详细描述"
            name="description"
          >
            <Input.TextArea 
              rows={4} 
              placeholder="请描述生成内容的详细要求（可选）"
            />
          </Form.Item>

          {configType === 'quiz' && (
            <>
              <Form.Item
                label="题目数量"
                name="count"
                initialValue={10}
              >
                <Input type="number" min={1} max={50} />
              </Form.Item>
              <Form.Item
                label="难度等级"
                name="difficulty"
                initialValue="medium"
              >
                <Select>
                  <Select.Option value="easy">简单</Select.Option>
                  <Select.Option value="medium">中等</Select.Option>
                  <Select.Option value="hard">困难</Select.Option>
                </Select>
              </Form.Item>
            </>
          )}

          {configType === 'audio' && (
            <Form.Item
              label="音频时长（分钟）"
              name="duration"
              initialValue={5}
            >
              <Input type="number" min={1} max={30} />
            </Form.Item>
          )}

          {configType === 'graph' && (
            <Form.Item
              label="导图层级"
              name="levels"
              initialValue={3}
            >
              <Input type="number" min={2} max={5} />
            </Form.Item>
          )}

          {configType === 'flashcard' && (
            <>
              <Form.Item
                label="闪卡数量"
                name="count"
                initialValue={10}
              >
                <Input type="number" min={1} max={100} />
              </Form.Item>
              <Form.Item
                label="难度等级"
                name="difficulty"
                initialValue="medium"
              >
                <Select>
                  <Select.Option value="easy">简单</Select.Option>
                  <Select.Option value="medium">中等</Select.Option>
                  <Select.Option value="hard">困难</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item
                label="分类标签"
                name="category"
              >
                <Input placeholder="输入闪卡分类（可选）" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default StudioPanel;

