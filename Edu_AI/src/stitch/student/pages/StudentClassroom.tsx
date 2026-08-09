import { useEffect, useRef, useState } from "react";

import { StudentGenerationFactory } from "../tools/StudentGenerationFactory";
import { deleteCourseMaterial, renameCourseMaterial } from "../../api/courses";
import { listClassrooms } from "../../api/classroom";
import type { ClassroomMaterial, CourseMaterialSpace } from "../../api/types";
import { useCourseRoute } from "../../course/CourseRouteProvider";
import { MaterialIcon } from "../../shared";
import { useCourseJobs } from "../../../jobs/jobStore";
import { buildClassroomPlayerHash } from "../../../openmaic/classroomGenerationFlow";
import { buildStudentHash, readStudentLocation } from "../routes/studentRoutes";
import { saveRecentLearningVisit } from "./studentRecentLearning";
import "../styles/studentClassroom.css";

function classroomTitle(item: ClassroomMaterial) {
  return item.title || item.topic || "未命名 AI 课堂";
}

export function StudentClassroomPage() {
  const { courseId } = useCourseRoute();
  const [space, setSpace] = useState<CourseMaterialSpace>(() => readStudentLocation(window.location.hash).space ?? "mine");
  const [items, setItems] = useState<ClassroomMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const classroomJobs = useCourseJobs(courseId ?? undefined, "generate_classroom");
  const completedJobs = useRef(new Set<string>());

  useEffect(() => {
    const sync = () => setSpace(readStudentLocation(window.location.hash).space ?? "mine");
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    const newlyCompleted = classroomJobs.filter((job) => job.status === "succeeded" && !completedJobs.current.has(job.edu_job_id));
    if (!newlyCompleted.length) return;
    newlyCompleted.forEach((job) => completedJobs.current.add(job.edu_job_id));
    setReload((value) => value + 1);
    setNotice("新的 AI 课堂已生成，并保存到个人空间");
  }, [classroomJobs]);

  useEffect(() => {
    if (!courseId) return;
    saveRecentLearningVisit(courseId, "student-classroom");
    let cancelled = false;
    setLoading(true);
    setError(null);
    void listClassrooms(courseId, space)
      .then((result) => { if (!cancelled) setItems(result); })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "AI 课堂加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, reload, space]);

  function changeSpace(next: CourseMaterialSpace) {
    setNotice(null);
    window.location.hash = buildStudentHash("student-classroom", { courseId, space: next });
  }

  async function rename(item: ClassroomMaterial) {
    if (!courseId || space !== "mine") return;
    const next = window.prompt("AI 课堂名称", classroomTitle(item))?.trim();
    if (!next || next === classroomTitle(item)) return;
    try {
      await renameCourseMaterial(courseId, "classroom", item.material_id, next);
      setNotice("名称已更新");
      setReload((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重命名失败");
    }
  }

  async function remove(item: ClassroomMaterial) {
    if (!courseId || space !== "mine" || !window.confirm(`删除“${classroomTitle(item)}”？此操作不可撤销。`)) return;
    try {
      await deleteCourseMaterial(courseId, "classroom", item.material_id);
      setNotice("个人 AI 课堂已删除");
      setReload((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败");
    }
  }

  return (
    <div className="student-classroom">
      <header className="student-classroom__header">
        <div><p>AI 课堂</p><h2>把课程主题变成可以播放的互动讲解</h2><span>个人课堂由你创建且仅自己可见；课程课堂由教师发布，所有课程成员可学习。</span></div>
        {space === "mine" ? <button onClick={() => setGeneratorOpen(true)}><MaterialIcon name="add" />创建 AI 课堂</button> : null}
      </header>

      <nav className="student-space-tabs" aria-label="AI 课堂空间">
        <button type="button" aria-current={space === "mine" ? "page" : undefined} onClick={() => changeSpace("mine")}>我的 AI 课堂</button>
        <button type="button" aria-current={space === "course" ? "page" : undefined} onClick={() => changeSpace("course")}>课程 AI 课堂</button>
      </nav>
      {notice ? <p className="student-resource-notice">{notice}</p> : null}
      {error ? <div className="student-resource-error" role="alert"><span>{error}</span><button onClick={() => setReload((value) => value + 1)}>重试</button></div> : null}

      {loading ? <div className="student-classroom__state">正在加载 AI 课堂…</div> : items.length === 0 ? <div className="student-classroom__state"><MaterialIcon name="slideshow" /><h3>{space === "mine" ? "还没有个人 AI 课堂" : "教师暂未发布 AI 课堂"}</h3><p>{space === "mine" ? "创建后会同时出现在个人资源中。" : "发布后会在这里直接出现。"}</p></div> : (
        <section className="student-classroom__grid" aria-label={space === "mine" ? "我的 AI 课堂" : "课程 AI 课堂"}>
          {items.map((item) => <article key={item.material_id}>
            <div className="student-classroom__visual"><MaterialIcon name="play_circle" /><span>{item.scenes_count ?? item.scenes?.length ?? 0} 个场景</span></div>
            <div className="student-classroom__body"><small>{space === "mine" ? "仅自己可见" : "教师发布"}</small><h3>{classroomTitle(item)}</h3><p>{item.summary || "进入播放器，按场景逐步学习。"}</p></div>
            <footer><button className="is-primary" onClick={() => { if (courseId) window.location.hash = buildClassroomPlayerHash(courseId, item.material_id); }}><MaterialIcon name="play_arrow" />开始学习</button>{space === "mine" ? <><button onClick={() => void rename(item)}>重命名</button><button className="is-danger" onClick={() => void remove(item)}>删除</button></> : null}</footer>
          </article>)}
        </section>
      )}

      {generatorOpen && courseId ? <div className="student-generator-modal" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setGeneratorOpen(false)}><section role="dialog" aria-modal="true" aria-label="创建 AI 课堂"><button className="student-generator-modal__close" aria-label="关闭" onClick={() => setGeneratorOpen(false)}><MaterialIcon name="close" /></button><StudentGenerationFactory courseId={courseId} allowedTools={["classroom"]} selectedDocumentIds={[]} /></section></div> : null}
    </div>
  );
}
