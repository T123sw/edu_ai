import React, { useState } from 'react';
import {
  Card,
  Button,
  Form,
  Input,
  Space,
  Typography,
  Tabs,
  Tree,
  Upload,
  message,
  Divider,
} from 'antd';
import type { TreeDataNode } from 'antd';
import {
  LeftOutlined,
  SaveOutlined,
  UploadOutlined,
  DeleteOutlined,
  FolderOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  GlobalOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useCourseStore, KnowledgeBaseItem } from '../../store/course/useCourseStore';
import './CourseDetailPage.css';

const { Title, Text } = Typography;

const getFileIcon = (item: KnowledgeBaseItem) => {
  if (item.type === 'folder') {
    return <FolderOutlined style={{ color: '#faad14' }} />;
  }
  if (item.type === 'web') {
    return <GlobalOutlined style={{ color: '#1890ff' }} />;
  }
  if (item.fileType === 'pdf') {
    return <FilePdfOutlined style={{ color: '#D93025' }} />;
  }
  if (item.fileType === 'docx' || item.fileType === 'doc') {
    return <FileWordOutlined style={{ color: '#2A5699' }} />;
  }
  return <FilePdfOutlined style={{ color: '#555' }} />;
};

export default function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { courses, updateCourse, addKnowledgeBaseItem, removeKnowledgeBaseItem } = useCourseStore();
  const [form] = Form.useForm();

  const course = courses.find(c => c.id === courseId);

  if (!course) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Title level={3}>课程不存在</Title>
        <Button onClick={() => navigate('/student/course-management')}>返回课程管理</Button>
      </div>
    );
  }

  const [activeTab, setActiveTab] = useState('basic');

  // 转换知识库数据为树形结构
  const convertToTreeNodes = (items: KnowledgeBaseItem[]): TreeDataNode[] => {
    return items.map(item => ({
      key: item.id,
      title: item.name,
      icon: getFileIcon(item),
      isLeaf: item.type !== 'folder',
      children: item.children ? convertToTreeNodes(item.children) : undefined,
    }));
  };

  const handleSave = () => {
    form.validateFields().then((values) => {
      // 处理教学目标：如果是字符串，转换为数组
      if (values.objectives && typeof values.objectives === 'string') {
        values.objectives = values.objectives
          .split('\n')
          .map(obj => obj.trim())
          .filter(obj => obj.length > 0);
      }
      updateCourse(courseId!, values);
      message.success('课程信息已保存');
    });
  };

  const handleFileUpload = (file: File, parentId?: string) => {
    const newItem: KnowledgeBaseItem = {
      id: `kb-${Date.now()}`,
      name: file.name,
      type: 'file',
      fileType: file.name.split('.').pop()?.toLowerCase(),
      size: file.size,
      uploadedAt: new Date().toISOString(),
    };
    addKnowledgeBaseItem(courseId!, newItem, parentId);
    message.success('文档已添加');
  };

  const handleCreateFolder = () => {
    const folderName = prompt('请输入文件夹名称：');
    if (folderName && folderName.trim()) {
      const newFolder: KnowledgeBaseItem = {
        id: `folder-${Date.now()}`,
        name: folderName.trim(),
        type: 'folder',
        children: [],
      };
      addKnowledgeBaseItem(courseId!, newFolder);
      message.success('文件夹已创建');
    }
  };

  const handleDeleteKnowledgeItem = (itemId: string) => {
    removeKnowledgeBaseItem(courseId!, itemId);
    message.success('文档已删除');
  };

  return (
    <div className="course-detail-page">
      <div className="course-detail-header">
        <Button
          icon={<LeftOutlined />}
          onClick={() => navigate('/student/course-management')}
          style={{ marginBottom: 16 }}
        >
          返回课程管理
        </Button>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={2} style={{ margin: 0 }}>
            编辑课程：{course.title}
          </Title>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            size="large"
            onClick={handleSave}
          >
            保存更改
          </Button>
        </div>
      </div>

      <Card className="course-detail-card">
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'basic',
            label: '基本信息',
            children: (
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                title: course.title,
                description: course.description,
                objectives: course.objectives ? course.objectives.join('\n') : '',
                knowledgeGraph: course.knowledgeGraph || '',
              }}
            >
              <Form.Item
                label="课程名称"
                name="title"
                rules={[{ required: true, message: '请输入课程名称' }]}
              >
                <Input placeholder="请输入课程名称" size="large" />
              </Form.Item>

              <Form.Item
                label="课程简介"
                name="description"
                rules={[{ required: true, message: '请输入课程简介' }]}
              >
                <Input.TextArea
                  rows={3}
                  placeholder="请输入课程简介"
                  size="large"
                />
              </Form.Item>

              <Form.Item
                label="教学目标"
                name="objectives"
                rules={[{ required: true, message: '请输入教学目标' }]}
                extra="每行一个教学目标，支持多个目标"
              >
                <Input.TextArea
                  rows={4}
                  placeholder="请输入教学目标，每行一个&#10;例如：&#10;理解计算思维的核心概念和方法&#10;掌握问题分解和模式识别的技巧"
                  size="large"
                />
              </Form.Item>

              <Form.Item
                label="课程知识图谱"
                name="knowledgeGraph"
                extra="可以输入知识图谱的JSON数据或URL链接"
              >
                <Input.TextArea
                  rows={6}
                  placeholder="请输入课程知识图谱（JSON格式）或URL链接"
                  size="large"
                />
              </Form.Item>
            </Form>
            ),
          },
          {
            key: 'knowledge-base',
            label: '主知识库 (L1)',
            children: (
            <div className="knowledge-base-section">
              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Title level={4} style={{ margin: 0 }}>
                    主知识库管理
                  </Title>
                  <Text type="secondary">
                    教师主知识库是课程的权威资料集，学生拥有只读权限。所有文档将用于RAG检索。
                  </Text>
                </div>
                <Space>
                  <Upload
                    beforeUpload={(file) => {
                      handleFileUpload(file);
                      return false;
                    }}
                    showUploadList={false}
                  >
                    <Button icon={<UploadOutlined />} type="primary">
                      上传文档
                    </Button>
                  </Upload>
                  <Button icon={<PlusOutlined />} onClick={handleCreateFolder}>
                    新建文件夹
                  </Button>
                </Space>
              </div>

              <Divider />

              <Card>
                {course.masterKnowledgeBase && course.masterKnowledgeBase.length > 0 ? (
                  <Tree
                    showIcon
                    defaultExpandAll
                    treeData={convertToTreeNodes(course.masterKnowledgeBase)}
                    titleRender={(node) => (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <span>{node.title}</span>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          size="small"
                          onClick={() => handleDeleteKnowledgeItem(node.key as string)}
                        />
                      </div>
                    )}
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: 48 }}>
                    <Text type="secondary">暂无知识库文档，点击上方按钮上传文档</Text>
                  </div>
                )}
              </Card>
            </div>
            ),
          },
        ]} />
      </Card>
    </div>
  );
}

