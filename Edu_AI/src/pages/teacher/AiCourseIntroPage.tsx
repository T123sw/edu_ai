import React from 'react';
import { useParams } from 'react-router-dom';
import CourseIntroPage from './CourseIntroPage';

export default function AiCourseIntroPage() {
  const { courseId } = useParams<{ courseId: string }>();
  // 复用现有课程介绍页面（它内部自己读取 courseId/或从 store 拉取）
  return <CourseIntroPage />;
}

