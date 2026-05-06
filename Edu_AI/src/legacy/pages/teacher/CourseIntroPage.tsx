import React, { useEffect, useState } from 'react';
import { Typography, Button, Tag, Spin } from 'antd';
import {
  RocketOutlined,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  DeploymentUnitOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useCourseStore } from '../../store/course/useCourseStore';
import './CourseIntroPage.css';

const { Title, Paragraph, Text } = Typography;

const CourseIntroPage: React.FC = () => {
  const navigate = useNavigate();
  const { courseId } = useParams<{ courseId: string }>();
  const { courses, loadCoursesFromBackend, setCurrentCourse, currentCourse } = useCourseStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      if (courses.length === 0) {
        await loadCoursesFromBackend();
      }
      if (courseId) {
        setCurrentCourse(courseId);
      }
      setLoading(false);
    };
    loadData();
  }, [courseId, courses.length, loadCoursesFromBackend, setCurrentCourse]);

  const handleStartTeaching = () => {
    if (courseId) {
      navigate(`/course/${courseId}/studio`);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          height: '100vh',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          background: '#f8fafc',
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (!currentCourse) {
    return null;
  }

  const descriptionText =
    currentCourse.description ||
    '本课程是基于计算机核心体系建设的智慧慕课，人工智能是引领科技革命和产业变革的战略性技术和重要驱动力量。课程内容涵盖了从基础理论到前沿应用的完整知识体系。';

  return (
    <div className="course-intro-page">
      <div className="main-card">
        <div className="left-section">
          <div className="course-category">{'计算机科学 / AI'}</div>

          <Title className="teacher-course-title">{currentCourse.title}</Title>

          <div className="course-tags">
            <Tag icon={<ClockCircleOutlined />} color="blue" style={{ padding: '4px 10px', borderRadius: '12px' }}>
              {currentCourse.duration || '32 学时'}
            </Tag>
            <Tag
              icon={<SafetyCertificateOutlined />}
              color="cyan"
              style={{ padding: '4px 10px', borderRadius: '12px' }}
            >
              {currentCourse.difficulty || '进阶课程'}
            </Tag>
            <Tag color="purple" style={{ padding: '4px 10px', borderRadius: '12px' }}>
              精品慕课
            </Tag>
          </div>

          <div className="course-description-box">
            <Text strong style={{ display: 'block', marginBottom: 8, color: '#334155' }}>
              课程简介
            </Text>
            <Paragraph className="course-description">{descriptionText}</Paragraph>
          </div>

          <div className="action-area">
            <Button type="primary" size="large" icon={<RocketOutlined />} className="start-btn" onClick={handleStartTeaching}>
              进入课程学习
            </Button>
            <Button type="link" style={{ marginLeft: 16, color: '#64748b' }}>
              查看教学大纲 &gt;
            </Button>
          </div>
        </div>

        <div className="right-section">
          <div className="graph-container">
            <div className="graph-label">
              <DeploymentUnitOutlined style={{ color: '#3b82f6' }} /> 知识图谱概览
            </div>

            <div className="node-group">
              <div className="center-node">AI Core</div>

              <div className="satellite s1">机器学习</div>
              <div className="satellite s2">深度神经网络</div>
              <div className="satellite s3">自然语言处理</div>
              <div className="satellite s4">计算机视觉</div>

              <svg
                style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: -1 }}
              >
                <line x1="50%" y1="50%" x2="20%" y2="25%" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4" />
                <line x1="50%" y1="50%" x2="80%" y2="20%" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4" />
                <line x1="50%" y1="50%" x2="20%" y2="80%" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4" />
                <line x1="50%" y1="50%" x2="85%" y2="75%" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CourseIntroPage;
