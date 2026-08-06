import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Avatar, Button, Card, Space, Typography } from "antd";
import {
  ArrowRightOutlined,
  CloudServerOutlined,
  CommentOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LeftOutlined,
  RightOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { backendCourseToSummary, listCourses } from "../api/courses";
import type { BackendCourse } from "../api/types";
import { AppSurface, routeHref, routes, useAppShell } from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";
import "./HomeDashboard.css";

const { Title, Paragraph, Text } = Typography;

const AUTH_STORAGE_KEY = "edu-ai-auth";
const COURSES_PER_PAGE = 4;

const iconMap: Record<string, ReactNode> = {
  CommentOutlined: <CommentOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  CloudServerOutlined: <CloudServerOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
};

function getStoredUsername() {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return "用户";
    const parsed = JSON.parse(raw) as { user?: { username?: string } };
    return parsed.user?.username?.trim() || "用户";
  } catch {
    return "用户";
  }
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 6) return "凌晨好";
  if (hour < 9) return "早上好";
  if (hour < 12) return "上午好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  if (hour < 22) return "晚上好";
  return "夜深了";
}

export function HomeDashboardPage() {
  const { setSelectedCourse } = useAppShell();
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const username = useMemo(() => getStoredUsername(), []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await listCourses();
        if (!cancelled) {
          setCourses(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "课程列表加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const handleCourseClick = (course: BackendCourse, globalIndex: number) => {
    setSelectedCourse(backendCourseToSummary(course, globalIndex));
    window.location.hash = buildTeacherCourseHash(routes.courseDetail, course.id);
  };

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  if (!loading && !error && courses.length === 0) {
    return (
      <AppSurface>
        <div className="welcome-page welcome-page-empty">
          <div className="welcome-empty-card">
            <Title level={3}>暂无课程</Title>
            <Text type="secondary">请前往课程管理页面创建课程</Text>
          </div>
        </div>
      </AppSurface>
    );
  }

  return (
    <AppSurface>
      <div className="welcome-page">
        <div className="welcome-topbar">
          <a href={routeHref(routes.home)} className="welcome-brand">
            Edu AI
          </a>
          <div className="welcome-topbar-actions">
            <a href={routeHref(routes.profile)} className="welcome-user-pill">
              <span className="welcome-user-avatar">{username[0]?.toUpperCase() || "U"}</span>
              <span className="welcome-user-name">{username}</span>
            </a>
          </div>
        </div>

        <div className="welcome-hero">
          <div className="welcome-content">
            <Space direction="vertical" size="large" align="center" style={{ width: "100%" }}>
              <Avatar
                size={80}
                style={{
                  background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  fontSize: 32,
                  marginBottom: 16,
                  boxShadow: "0 4px 12px rgba(102, 126, 234, 0.3)",
                }}
              >
                {username[0]?.toUpperCase() || "U"}
              </Avatar>
              <Title level={1} className="welcome-title">
                {getGreeting()}，{username}！
              </Title>
              <Paragraph className="welcome-subtitle">欢迎使用 知学启思 教学平台</Paragraph>
              <Text type="secondary" className="welcome-description">
                融合前沿 AI 技术，赋能教育创新。选择下方课程开始你的智能学习之旅。
              </Text>
            </Space>
          </div>
        </div>

        <div className="welcome-features">
          <Title level={2} className="features-title">
            <RocketOutlined style={{ marginRight: 12, color: "#1890ff" }} />
            我的课程
          </Title>

          {loading ? (
            <div className="welcome-status-card">
              <Text type="secondary">正在加载课程...</Text>
            </div>
          ) : error ? (
            <div className="welcome-status-card">
              <Text type="danger">{error}</Text>
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
                  {currentCourses.map((course, index) => {
                    const globalIndex = currentPage * COURSES_PER_PAGE + index;
                    return (
                      <div className="course-col" key={course.id}>
                        <Card
                          className="course-card"
                          hoverable
                          onClick={() => handleCourseClick(course, globalIndex)}
                          style={{
                            borderTop: `4px solid ${course.color}`,
                            height: "100%",
                            transition: "all 0.3s ease",
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
                            onClick={(event) => {
                              event.stopPropagation();
                              handleCourseClick(course, globalIndex);
                            }}
                          >
                            进入课程 <ArrowRightOutlined />
                          </Button>
                        </Card>
                      </div>
                    );
                  })}
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
          <Text type="secondary">如有任何问题或建议，请联系系统管理员</Text>
        </div>
      </div>
    </AppSurface>
  );
}
