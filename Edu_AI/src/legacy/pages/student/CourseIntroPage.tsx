import { useParams, useNavigate } from 'react-router-dom';
import { Card, Typography, Button, Space } from 'antd';
import { 
  ArrowRightOutlined,
  LeftOutlined
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';
import { useCourseStore } from '../../store/course/useCourseStore';
import './CourseIntroPage.css';

const { Title, Paragraph, Text } = Typography;

export default function CourseIntroPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { courses } = useCourseStore();
  const userRole = user?.role || 'student';

  const course = courses.find(c => c.id === courseId);

  if (!course) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Title level={2}>课程不存在</Title>
        <Button onClick={() => navigate('/welcome')}>返回课程列表</Button>
      </div>
    );
  }

  const handleEnterCourse = () => {
    // 跳转到三栏式交互界面
    navigate(`/${userRole}/course/${courseId}/studio`);
  };

  const handleBack = () => {
    navigate('/welcome');
  };

  return (
    <div className="course-intro-page">
      <div className="course-intro-wrapper">
        <Button
          type="text"
          icon={<LeftOutlined />}
          onClick={handleBack}
          className="course-intro-back"
        >
          返回课程列表
        </Button>

        <Card
          className="course-intro-card"
          style={{ borderTop: `4px solid ${course.color}` }}
        >
          <Space
            direction="vertical"
            size="large"
            style={{ width: '100%' }}
          >
            <div>
              <Title
                level={1}
                style={{ marginBottom: 8, color: course.color, fontSize: 32 }}
              >
                {course.title}
              </Title>
              <Paragraph className="course-intro-description">
                {course.description}
              </Paragraph>
            </div>

            <div>
              <Text className="section-title">教学目标</Text>
              <ul className="objectives-list">
                {(course.objectives || []).map((obj, index) => (
                  <li key={index}>{obj}</li>
                ))}
              </ul>
            </div>

            <div className="intro-footer">
              <Button
                type="primary"
                size="large"
                icon={<ArrowRightOutlined />}
                onClick={handleEnterCourse}
                className="enter-course-button"
                style={{
                  background: course.color,
                  borderColor: course.color,
                }}
              >
                进入课程
              </Button>
            </div>
          </Space>
        </Card>
      </div>
    </div>
  );
}

