import { Card, Typography, Button, Space, Avatar } from 'antd';
import {
  CommentOutlined,
  FileTextOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  RocketOutlined,
  ArrowRightOutlined,
  LeftOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useState, useMemo, useEffect } from 'react';
import { useCourseStore } from '../store/course/useCourseStore';
import './WelcomePage.css';

const { Title, Paragraph, Text } = Typography;

const iconMap: Record<string, React.ReactNode> = {
  CommentOutlined: <CommentOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  CloudServerOutlined: <CloudServerOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
};

const COURSES_PER_PAGE = 4;

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 6) return '凌晨好';
  if (hour < 9) return '早上好';
  if (hour < 12) return '上午好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  if (hour < 22) return '晚上好';
  return '夜深了';
}

export default function WelcomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { courses, loadCoursesFromBackend, loading } = useCourseStore();
  const [currentPage, setCurrentPage] = useState(0);

  useEffect(() => {
    void loadCoursesFromBackend();
  }, [loadCoursesFromBackend]);

  const totalPages = Math.ceil(courses.length / COURSES_PER_PAGE);

  useEffect(() => {
    if (totalPages <= 0) {
      setCurrentPage(0);
      return;
    }
    setCurrentPage((prev) => Math.min(prev, totalPages - 1));
  }, [totalPages]);

  const currentCourses = useMemo(() => {
    const start = currentPage * COURSES_PER_PAGE;
    const end = start + COURSES_PER_PAGE;
    return courses.slice(start, end);
  }, [currentPage, courses]);

  const handleCourseClick = (courseId: string) => {
    navigate(`/course/${courseId}/intro`);
  };

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  if (!loading && courses.length === 0) {
    return (
      <div className="welcome-page welcome-page-empty">
        <div className="welcome-topbar">
          <div className="welcome-brand">Edu AI</div>
          <div className="welcome-topbar-actions">
            <a href="/settings" className="welcome-user-pill">
              <span className="welcome-user-avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</span>
              <span className="welcome-user-name">{user?.username || '用户'}</span>
            </a>
          </div>
        </div>
        <div className="welcome-empty-card">
          <Title level={3}>暂无课程</Title>
          <Text type="secondary">请先前往课程管理创建课程。</Text>
        </div>
      </div>
    );
  }

  return (
    <div className="welcome-page">
      <div className="welcome-topbar">
        <div className="welcome-brand">Edu AI</div>
        <div className="welcome-topbar-actions">
          <a href="/settings" className="welcome-user-pill">
            <span className="welcome-user-avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</span>
            <span className="welcome-user-name">{user?.username || '用户'}</span>
          </a>
        </div>
      </div>

      <div className="welcome-hero">
        <div className="welcome-content">
          <Space direction="vertical" size="large" align="center" style={{ width: '100%' }}>
            <Avatar
              size={80}
              style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                fontSize: 32,
                marginBottom: 16,
                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
              }}
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </Avatar>
            <Title level={1} className="welcome-title">
              {getGreeting()}，{user?.username || '用户'}
            </Title>
            <Paragraph className="welcome-subtitle">欢迎使用 Edu-AI 智能教学平台</Paragraph>
            <Text type="secondary" className="welcome-description">
              从这里进入课程、知识图谱、资源和工作台，保持现在的业务逻辑不变，只把界面切到新的视觉风格。
            </Text>
          </Space>
        </div>
      </div>

      <div className="welcome-features">
        <Title level={2} className="features-title">
          <RocketOutlined style={{ marginRight: 12, color: '#1890ff' }} />
          我的课程
        </Title>

        {loading ? (
          <div className="welcome-status-card">
            <Text type="secondary">正在加载课程...</Text>
          </div>
        ) : (
          <>
            <div className="courses-container">
              <Button
                type="text"
                icon={<LeftOutlined />}
                onClick={handlePrevPage}
                disabled={currentPage === 0}
                className="page-nav-button page-nav-left"
                size="large"
              />
              <div className="courses-row">
                {currentCourses.map((course) => (
                  <div className="course-col" key={course.id}>
                    <Card
                      className="course-card"
                      hoverable
                      onClick={() => handleCourseClick(course.id)}
                      style={{
                        borderTop: `4px solid ${course.color}`,
                        height: '100%',
                        transition: 'all 0.3s ease',
                      }}
                    >
                      <div className="course-icon" style={{ color: course.color }}>
                        {iconMap[course.icon] || <CommentOutlined />}
                      </div>
                      <Title level={4} className="course-title">
                        {course.title}
                      </Title>
                      <Paragraph className="course-description" type="secondary">
                        {course.description}
                      </Paragraph>
                      <Button
                        type="link"
                        className="course-link"
                        style={{ color: course.color, padding: 0 }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCourseClick(course.id);
                        }}
                      >
                        进入课程 <ArrowRightOutlined />
                      </Button>
                    </Card>
                  </div>
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

      <div className="welcome-footer">
        <Text type="secondary">问答工作台页保持不动，其它页面样式会继续按这套风格收敛。</Text>
      </div>
    </div>
  );
}
