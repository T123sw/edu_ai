import React, { useState, useMemo, useEffect } from 'react';
import {
  Card,
  List,
  Button,
  Modal,
  Form,
  Input,
  Typography,
  Popconfirm,
  message,
  Empty,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CommentOutlined,
  FileTextOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  LeftOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useCourseStore, Course } from '../../store/course/useCourseStore';
import './CourseManagementPage.css';

const { Title, Text } = Typography;
const { TextArea } = Input;

// 图标映射
const iconMap: Record<string, React.ReactNode> = {
  CommentOutlined: <CommentOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  CloudServerOutlined: <CloudServerOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
};

const COURSES_PER_PAGE = 8; // 每页8个课程，2行4列

export default function CourseManagementPage() {
  const { courses, addCourse, updateCourse, deleteCourse, loadCoursesFromBackend } = useCourseStore();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCourse, setEditingCourse] = useState<Course | null>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState(0);

  useEffect(() => {
    loadCoursesFromBackend();
  }, [loadCoursesFromBackend]);

  // 计算总页数
  const totalPages = Math.ceil(courses.length / COURSES_PER_PAGE);
  
  // 获取当前页的课程
  const currentCourses = useMemo(() => {
    const start = currentPage * COURSES_PER_PAGE;
    const end = start + COURSES_PER_PAGE;
    return courses.slice(start, end);
  }, [currentPage, courses]);

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  const handleAdd = () => {
    setEditingCourse(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (course: Course) => {
    // 导航到课程详情页面
    navigate(`/course-management/${course.id}`);
  };

  const handleDelete = async (id: string) => {
    await deleteCourse(id);
    message.success('课程已删除');
  };

  const handleSubmit = () => {
    form.validateFields().then(async (values) => {
      const { title, description, objectives } = values as {
        title: string;
        description?: string;
        objectives?: string;
      };

      const parsedObjectives =
        objectives
          ?.split('\n')
          .map((line: string) => line.trim())
          .filter((line: string) => line.length > 0) || undefined;

      if (editingCourse) {
        await updateCourse(editingCourse.id, {
          title,
          description,
          objectives: parsedObjectives,
        });
        message.success('课程已更新');
      } else {
        await addCourse({
          id: '',
          title,
          description: description || '',
          icon: 'CommentOutlined',
          color: '#1890ff',
          objectives: parsedObjectives,
        });
        message.success('课程已创建');
      }
      setModalVisible(false);
      form.resetFields();
    });
  };

  const handleCancel = () => {
    setModalVisible(false);
    form.resetFields();
    setEditingCourse(null);
  };

  return (
    <div className="course-management-page">
      <div className="course-management-header">
        <Title level={2} style={{ marginBottom: 8 }}>
          课程管理
        </Title>
        <Text type="secondary">管理所有课程，新建、编辑或删除课程</Text>
      </div>

      <div className="course-management-actions">
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={handleAdd}
        >
          新建课程
        </Button>
      </div>

      <div className="course-list-container">
        {courses.length === 0 ? (
          <Empty description="暂无课程，点击上方按钮创建新课程" />
        ) : (
          <>
            <div className="courses-wrapper">
              <Button
                type="text"
                icon={<LeftOutlined />}
                onClick={handlePrevPage}
                disabled={currentPage === 0}
                className="page-nav-button page-nav-left"
                size="large"
              />
              <div className="courses-grid">
                {currentCourses.map((course) => (
                  <Card
                    key={course.id}
                    hoverable
                    className="course-card"
                    style={{ 
                      borderTop: `4px solid ${course.color}`,
                    }}
                    actions={[
                      <Button
                        key="edit"
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => handleEdit(course)}
                        block
                      >
                        编辑
                      </Button>,
                      <Popconfirm
                        key="delete"
                        title="确定要删除这门课程吗？"
                        onConfirm={() => handleDelete(course.id)}
                        okText="确定"
                        cancelText="取消"
                      >
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          block
                        >
                          删除
                        </Button>
                      </Popconfirm>,
                    ]}
                  >
                    <Card.Meta
                      avatar={
                        <div
                          style={{
                            fontSize: 32,
                            color: course.color,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 64,
                            height: 64,
                            background: `${course.color}15`,
                            borderRadius: 12,
                            flexShrink: 0,
                          }}
                        >
                          {iconMap[course.icon] || <CommentOutlined />}
                        </div>
                      }
                      title={
                        <Title 
                          level={4} 
                          style={{ 
                            margin: 0, 
                            marginBottom: 12,
                            fontSize: 18,
                            fontWeight: 600,
                            lineHeight: 1.5,
                          }}
                        >
                          {course.title}
                        </Title>
                      }
                      description={
                        <Text 
                          type="secondary" 
                          style={{ 
                            fontSize: 14,
                            lineHeight: 1.5,
                            display: 'block',
                          }}
                        >
                          {course.description}
                        </Text>
                      }
                    />
                  </Card>
                ))}
              </div>
              <Button
                type="text"
                icon={<RightOutlined />}
                onClick={handleNextPage}
                disabled={currentPage >= totalPages - 1}
                className="page-nav-button page-nav-right"
                size="large"
              />
            </div>
            {totalPages > 1 && (
              <div className="page-indicator">
                <Text type="secondary">
                  第 {currentPage + 1} 页 / 共 {totalPages} 页
                </Text>
              </div>
            )}
          </>
        )}
      </div>

      <Modal
        title={editingCourse ? '编辑课程' : '新建课程'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={handleCancel}
        okText={editingCourse ? '保存' : '创建'}
        cancelText="取消"
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 24 }}
        >
          <Form.Item
            label="课程名称"
            name="title"
            rules={[{ required: true, message: '请输入课程名称' }]}
          >
            <Input placeholder="请输入课程名称" size="large" />
          </Form.Item>

          <Form.Item
            label="课程简介（可选）"
            name="description"
          >
            <TextArea
              rows={4}
              placeholder="可选：简单介绍课程面向对象、主要内容等"
            />
          </Form.Item>

          <Form.Item
            label="教学目标（可选）"
            name="objectives"
          >
            <TextArea
              rows={4}
              placeholder="可选：每行填写一个教学目标，例如：&#10;掌握XXX的基本概念&#10;能够运用XXX解决简单问题"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

