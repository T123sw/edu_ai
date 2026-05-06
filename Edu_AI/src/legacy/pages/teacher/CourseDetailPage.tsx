import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Space,
  Tabs,
  Tree,
  Typography,
  Upload,
  message,
} from 'antd';
import type { TreeDataNode } from 'antd';
import {
  DeleteOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FolderOutlined,
  GlobalOutlined,
  LeftOutlined,
  PlusOutlined,
  SaveOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useCourseStore, type KnowledgeBaseItem } from '../../store/course/useCourseStore';
import './CourseDetailPage.css';

const { Title, Text, Paragraph } = Typography;

const COURSE_COVER_PRESETS = [
  'https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1509228627152-72ae9ae6848d?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1530026405186-ed1f139313f8?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80',
];

function getFileIcon(item: KnowledgeBaseItem) {
  if (item.type === 'folder') {
    return <FolderOutlined style={{ color: '#f59e0b' }} />;
  }
  if (item.type === 'web') {
    return <GlobalOutlined style={{ color: '#2563eb' }} />;
  }
  if (item.fileType === 'doc' || item.fileType === 'docx') {
    return <FileWordOutlined style={{ color: '#2563eb' }} />;
  }
  return <FilePdfOutlined style={{ color: '#dc2626' }} />;
}

function convertToTreeNodes(items: KnowledgeBaseItem[]): TreeDataNode[] {
  return items.map((item) => ({
    key: item.id,
    title: item.name,
    icon: getFileIcon(item),
    isLeaf: item.type !== 'folder',
    children: item.children ? convertToTreeNodes(item.children) : undefined,
  }));
}

export default function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const coverInputRef = useRef<HTMLInputElement | null>(null);
  const {
    courses,
    loadCoursesFromBackend,
    updateCourse,
    addKnowledgeBaseItem,
    removeKnowledgeBaseItem,
  } = useCourseStore();
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('basic');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!courses.length) {
      void loadCoursesFromBackend();
    }
  }, [courses.length, loadCoursesFromBackend]);

  const course = useMemo(() => courses.find((item) => item.id === courseId), [courseId, courses]);
  const coverImage = Form.useWatch('image', form) || course?.image || COURSE_COVER_PRESETS[0];

  useEffect(() => {
    if (!course) return;
    form.setFieldsValue({
      title: course.title,
      description: course.description,
      objectives: course.objectives?.join('\n') || '',
      knowledgeGraph: course.knowledgeGraph || '',
      image: course.image || COURSE_COVER_PRESETS[0],
    });
  }, [course, form]);

  const handleSave = async () => {
    if (!courseId) return;

    try {
      const values = await form.validateFields();
      setSaving(true);
      await updateCourse(courseId, {
        title: values.title?.trim(),
        description: values.description?.trim(),
        objectives: String(values.objectives || '')
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean),
        knowledgeGraph: String(values.knowledgeGraph || '').trim(),
        image: values.image?.trim(),
      });
      message.success('课程信息已保存');
    } catch (error) {
      if (error instanceof Error) {
        console.error(error);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleCoverImageUpload = (fileList: FileList | null) => {
    const file = fileList?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      message.error('请选择图片文件作为课程封面');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      form.setFieldValue('image', String(reader.result || ''));
      message.success('课程封面已载入，保存后生效');
    };
    reader.onerror = () => message.error('封面图片读取失败，请重试');
    reader.readAsDataURL(file);
  };

  const handleFileUpload = (file: File, parentId?: string) => {
    if (!courseId) return false;

    const nextItem: KnowledgeBaseItem = {
      id: `kb-${Date.now()}`,
      name: file.name,
      type: 'file',
      fileType: file.name.split('.').pop()?.toLowerCase(),
      size: file.size,
      uploadedAt: new Date().toISOString(),
    };

    addKnowledgeBaseItem(courseId, nextItem, parentId);
    message.success(`已添加文件：${file.name}`);
    return false;
  };

  const handleCreateFolder = () => {
    if (!courseId) return;
    const folderName = window.prompt('请输入新建文件夹名称');
    if (!folderName?.trim()) return;

    addKnowledgeBaseItem(courseId, {
      id: `folder-${Date.now()}`,
      name: folderName.trim(),
      type: 'folder',
      children: [],
    });
    message.success('文件夹已创建');
  };

  const handleDeleteKnowledgeItem = (itemId: string) => {
    if (!courseId) return;
    removeKnowledgeBaseItem(courseId, itemId);
    message.success('知识库条目已删除');
  };

  if (!course) {
    return (
      <div className="course-detail-page">
        <Card className="course-detail-card">
          <Empty description="未找到对应课程" />
          <div className="course-detail-empty-actions">
            <Button type="primary" onClick={() => navigate('/course-management')}>
              返回课程管理
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const knowledgeBaseCount = course.masterKnowledgeBase?.length || 0;

  return (
    <div className="course-detail-page">
      <section className="course-edit-hero">
        <div className="course-edit-hero-copy">
          <div className="course-edit-kicker">Course Edit</div>
          <Title level={1} className="course-edit-title">
            {course.title}
          </Title>
          <Paragraph className="course-edit-text">
            新版课程详情编辑页完整接入课程封面、基础信息和课程知识库编辑。课程保存仍走现有
            updateCourse 流程，封面作为前端扩展字段持久化，不破坏后端课程接口。
          </Paragraph>
          <Space wrap className="course-edit-actions">
            <Button size="large" icon={<LeftOutlined />} onClick={() => navigate('/course-management')}>
              返回课程管理
            </Button>
            <Button type="primary" size="large" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>
              保存课程
            </Button>
          </Space>
        </div>

        <div className="course-edit-summary">
          <div className="course-cover-preview">
            <img src={coverImage} alt={`${course.title} cover`} />
            <span>课程封面预览</span>
          </div>
          <div className="course-edit-summary-grid">
            <div>
              <span>课程 ID</span>
              <strong>{course.id}</strong>
            </div>
            <div>
              <span>学习目标</span>
              <strong>{course.objectives?.length || 0}</strong>
            </div>
            <div>
              <span>知识库条目</span>
              <strong>{knowledgeBaseCount}</strong>
            </div>
            <div>
              <span>当前标签页</span>
              <strong>{activeTab === 'basic' ? '基础信息' : '课程知识库'}</strong>
            </div>
          </div>
        </div>
      </section>

      <Card className="course-detail-card">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'basic',
              label: '基础信息',
              children: (
                <div className="course-edit-panel">
                  <div className="course-edit-panel-head">
                    <div>
                      <span className="course-edit-panel-kicker">Basic Profile</span>
                      <Title level={3}>课程信息设置</Title>
                    </div>
                  </div>

                  <Form form={form} layout="vertical">
                    <div className="course-edit-form-grid">
                      <Form.Item
                        label="课程名称"
                        name="title"
                        rules={[{ required: true, message: '请输入课程名称' }]}
                      >
                        <Input size="large" placeholder="请输入课程名称" />
                      </Form.Item>

                      <Form.Item label="知识图谱引用" name="knowledgeGraph">
                        <Input size="large" placeholder="可填写 JSON 或 URL" />
                      </Form.Item>
                    </div>

                    <Form.Item
                      label="课程封面图"
                      name="image"
                      extra="支持图片 URL，也可以上传本地图片。保存后会在前端持久化，不改变现有后端课程接口。"
                    >
                      <Input size="large" placeholder="输入课程封面图片 URL" />
                    </Form.Item>

                    <div className="course-cover-tools">
                      <Button icon={<UploadOutlined />} onClick={() => coverInputRef.current?.click()}>
                        上传本地封面
                      </Button>
                      <Button onClick={() => form.setFieldValue('image', COURSE_COVER_PRESETS[0])}>
                        恢复默认封面
                      </Button>
                      <input
                        ref={coverInputRef}
                        type="file"
                        accept="image/*"
                        className="course-cover-hidden-input"
                        onChange={(event) => handleCoverImageUpload(event.target.files)}
                      />
                    </div>

                    <div className="course-cover-presets">
                      {COURSE_COVER_PRESETS.map((image) => (
                        <button
                          key={image}
                          type="button"
                          className={coverImage === image ? 'is-active' : ''}
                          onClick={() => form.setFieldValue('image', image)}
                        >
                          <img src={image} alt="课程封面候选" />
                        </button>
                      ))}
                    </div>

                    <Form.Item
                      label="课程简介"
                      name="description"
                      rules={[{ required: true, message: '请输入课程简介' }]}
                    >
                      <Input.TextArea rows={4} placeholder="介绍课程内容、适用对象和教学目标" />
                    </Form.Item>

                    <Form.Item
                      label="学习目标"
                      name="objectives"
                      rules={[{ required: true, message: '请输入学习目标' }]}
                      extra="每行一个学习目标"
                    >
                      <Input.TextArea rows={6} placeholder={'理解课程核心概念\n掌握实践方法\n完成阶段任务'} />
                    </Form.Item>
                  </Form>
                </div>
              ),
            },
            {
              key: 'knowledge-base',
              label: '课程知识库',
              children: (
                <div className="course-edit-panel">
                  <div className="course-edit-panel-head is-knowledge">
                    <div>
                      <span className="course-edit-panel-kicker">Knowledge Base</span>
                      <Title level={3}>课程资料树</Title>
                      <Text type="secondary">保留原有课程知识库树编辑行为，替换为新版结构与样式。</Text>
                    </div>
                    <Space wrap>
                      <Upload beforeUpload={(file) => handleFileUpload(file)} showUploadList={false}>
                        <Button icon={<UploadOutlined />} type="primary">
                          上传文件
                        </Button>
                      </Upload>
                      <Button icon={<PlusOutlined />} onClick={handleCreateFolder}>
                        新建文件夹
                      </Button>
                    </Space>
                  </div>

                  {course.masterKnowledgeBase && course.masterKnowledgeBase.length > 0 ? (
                    <Card className="course-kb-tree-card">
                      <Tree
                        showIcon
                        defaultExpandAll
                        treeData={convertToTreeNodes(course.masterKnowledgeBase)}
                        titleRender={(node) => (
                          <div className="course-kb-tree-node">
                            <span className="course-kb-tree-title">{node.title}</span>
                            <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              size="small"
                              onClick={() => handleDeleteKnowledgeItem(String(node.key))}
                            />
                          </div>
                        )}
                      />
                    </Card>
                  ) : (
                    <div className="course-kb-empty">
                      <Empty description="当前还没有课程知识库内容" />
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
