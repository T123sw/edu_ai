import { StandardLearningResources } from "../course/knowledge/StandardLearningResources";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { MaterialIcon } from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";
import "./learningResourceGeneration.css";

export function LearningResourceGenerationPage() {
  const { courseId } = useCourseRoute();

  return (
    <section className="learning-resource-generation">
      <header className="learning-resource-generation__header">
        <a href={buildTeacherCourseHash("knowledge", courseId)}>
          <MaterialIcon name="arrow_back" />
          返回课程知识
        </a>
        <div>
          <span>按叶子知识点组织</span>
          <h2>学习资源生成</h2>
          <p>选择知识点，生成 AI 课堂、学习指南和练习。任务提交后可离开页面，系统会在后台继续处理。</p>
        </div>
      </header>
      <StandardLearningResources />
    </section>
  );
}
