import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { getCourseMaterials } from "../api/courses";
import {
  createLearningTask,
  getLearningTaskProgress,
  listLearningTasks,
  publishLearningTask,
  recordLearningEvent,
} from "../api/learning";
import type {
  AssessmentDraft,
  CourseLearningSummary,
  CourseMaterial,
  LearningResourceRef,
  LearningTask,
} from "../api/types";
import { AssessmentEditor } from "../assessment/AssessmentEditor";
import { AssessmentRunner } from "../assessment/AssessmentRunner";
import { getAssessmentPublishBlockers } from "../assessment/assessmentAuthoring";
import { useAuthSession } from "../authSession";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { MaterialIcon, routes } from "../shared";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import {
  getCompletionBasisLabel,
  getLearningTaskPrimaryAction,
  getProgressLabel,
} from "./courseLearningPresentation";
import "./CourseLearning.css";


function materialKey(ref: LearningResourceRef): string {
  return `${ref.material_type}:${ref.material_id}`;
}

function materialTitle(material: CourseMaterial): string {
  return material.title || material.topic || material.material_id;
}

function formatUpdatedAt(value?: string): string {
  if (!value) return "时间未知";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(timestamp);
}

function createEventId(taskId: string, eventType: string): string {
  const randomId = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `learning:${taskId}:${eventType}:${randomId}`;
}

function formatPercent(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

export function CourseLearningPage() {
  const { user } = useAuthSession();
  const { courseId, courseRole } = useCourseRoute();
  const isTeacher = user?.role !== "student" && courseRole !== "viewer";
  const [tasks, setTasks] = useState<LearningTask[]>([]);
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [summary, setSummary] = useState<CourseLearningSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [knowledgePoints, setKnowledgePoints] = useState("");
  const [selectedResources, setSelectedResources] = useState<Set<string>>(new Set());
  const [resourceQuery, setResourceQuery] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [assessmentDrafts, setAssessmentDrafts] = useState<Record<string, AssessmentDraft | null>>({});

  const sharedMaterialByKey = useMemo(
    () => new Map(materials.map((material) => [
      materialKey({ material_type: material.material_type, material_id: material.material_id }),
      material,
    ])),
    [materials],
  );

  const resourceTypes = useMemo(
    () => [...new Set(materials.map((material) => material.material_type))].sort(),
    [materials],
  );

  const filteredMaterials = useMemo(() => {
    const normalizedQuery = resourceQuery.trim().toLocaleLowerCase();
    return materials.filter((material) => {
      if (resourceType && material.material_type !== resourceType) return false;
      if (!normalizedQuery) return true;
      return [
        materialTitle(material),
        material.material_type,
        material.created_by,
        material.material_id,
      ].some((value) => String(value ?? "").toLocaleLowerCase().includes(normalizedQuery));
    });
  }, [materials, resourceQuery, resourceType]);

  const selectedTask = tasks.find((task) => task.task_id === selectedTaskId) ?? null;
  const handleAssessmentDraftChange = useCallback(
    (taskId: string, draft: AssessmentDraft | null) => {
      setAssessmentDrafts((current) => ({ ...current, [taskId]: draft }));
    },
    [],
  );

  const loadTasks = useCallback(async () => {
    if (!courseId) return;
    setLoading(true);
    setError(null);
    try {
      const [taskData, materialData] = await Promise.all([
        listLearningTasks(courseId),
        getCourseMaterials(courseId, { space: "course" }),
      ]);
      setTasks(taskData);
      setMaterials(materialData);
      setSelectedTaskId((current) => (
        current && taskData.some((task) => task.task_id === current)
          ? current
          : taskData[0]?.task_id ?? null
      ));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "学习任务加载失败");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    if (!isTeacher || !courseId || !selectedTask || selectedTask.status !== "published") {
      setSummary(null);
      return;
    }
    let cancelled = false;
    getLearningTaskProgress(courseId, selectedTask.task_id)
      .then((value) => {
        if (!cancelled) setSummary(value);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "学习反馈加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, isTeacher, selectedTask]);

  async function submitTask(event: FormEvent) {
    event.preventDefault();
    if (!courseId || !title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createLearningTask(courseId, {
        title: title.trim(),
        instructions: instructions.trim(),
        resource_refs: materials
          .filter((material) => selectedResources.has(materialKey({
            material_type: material.material_type,
            material_id: material.material_id,
          })))
          .map((material) => ({
            material_type: material.material_type,
            material_id: material.material_id,
          })),
        knowledge_point_ids: knowledgePoints
          .split(/[，,\n]/)
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setTasks((current) => [created, ...current]);
      setSelectedTaskId(created.task_id);
      setCreating(false);
      setTitle("");
      setInstructions("");
      setKnowledgePoints("");
      setSelectedResources(new Set());
      setResourceQuery("");
      setResourceType("");
      setNotice("学习任务草稿已创建，可确认后发布给学生。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建学习任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function publishTask(task: LearningTask) {
    if (!courseId) return;
    const blockers = getAssessmentPublishBlockers(assessmentDrafts[task.task_id]);
    if (blockers.length > 0) {
      setError(blockers.join("；"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const draft = assessmentDrafts[task.task_id];
      if (!draft) return;
      const published = await publishLearningTask(courseId, task.task_id, draft.draft_revision);
      setTasks((current) => current.map((item) => item.task_id === task.task_id ? published : item));
      setSelectedTaskId(published.task_id);
      setNotice("任务已发布，学生端现在可以开始学习。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发布学习任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function writeStudentEvent(
    task: LearningTask,
    eventType: "started" | "resource_opened" | "completed",
    resourceRef?: LearningResourceRef,
  ) {
    if (!courseId) return false;
    setBusy(true);
    setError(null);
    try {
      const progress = eventType === "completed"
        ? 100
        : Math.max(1, task.my_progress?.progress_percent ?? 0);
      const result = await recordLearningEvent(courseId, task.task_id, {
        event_id: createEventId(task.task_id, eventType),
        event_type: eventType,
        progress_percent: progress,
        resource_ref: resourceRef,
      });
      setTasks((current) => current.map((item) => (
        item.task_id === task.task_id ? { ...item, my_progress: result.progress } : item
      )));
      if (eventType === "completed") {
        setNotice("已记录为学生自报完成；这不代表测评通过或已经掌握该内容。");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "学习进度保存失败");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function openResource(task: LearningTask, ref: LearningResourceRef) {
    const saved = await writeStudentEvent(task, "resource_opened", ref);
    if (!saved || !courseId) return;
    window.location.hash = buildRoleCourseHash(user?.role, routes.resources, courseId, {
      space: "course",
      material_type: ref.material_type,
      material_id: ref.material_id,
    });
  }

  if (loading) {
    return <div className="learning-state">正在加载学习任务…</div>;
  }

  return (
    <main className="learning-page">
      <section className="learning-hero">
        <div>
          <p className="learning-eyebrow">TEACHER · STUDENT LOOP</p>
          <h2>{isTeacher ? "发布任务，查看真实学习反馈" : "按照任务学习，进度自动同步"}</h2>
          <p>
            {isTeacher
              ? "课程共享资源与学习任务彼此独立：资源可持续维护，任务负责组织学习路径。"
              : "教师发布的任务会引用课程资源；即使暂时没有任务，你仍可浏览课程资源。"}
          </p>
        </div>
        {isTeacher ? (
          <button type="button" className="learning-primary" onClick={() => setCreating(true)}>
            <MaterialIcon name="fact_check" /> 新建学习任务
          </button>
        ) : (
          <a className="learning-secondary" href={buildRoleCourseHash(user?.role, routes.resources, courseId, { space: "course" })}>
            浏览课程资源
          </a>
        )}
      </section>

      {error ? <p className="learning-alert learning-alert--error">{error}</p> : null}
      {notice ? <p className="learning-alert learning-alert--success">{notice}</p> : null}

      {creating && isTeacher ? (
        <section className="learning-create" aria-label="新建学习任务">
          <form onSubmit={submitTask}>
            <div className="learning-create__head">
              <div><p>新建学习任务</p><span>先保存为草稿，确认后再发布。</span></div>
              <button type="button" onClick={() => setCreating(false)} aria-label="关闭">×</button>
            </div>
            <label>任务标题<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} required /></label>
            <label>学习说明<textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} rows={4} maxLength={10000} /></label>
            <label>知识点 ID<input value={knowledgePoints} onChange={(event) => setKnowledgePoints(event.target.value)} placeholder="多个知识点用逗号分隔" /></label>
            <fieldset>
              <legend>选择课程共享资源</legend>
              {materials.length === 0 ? <p>当前还没有共享资源，可先创建空任务，稍后补充。</p> : (
                <>
                  <div className="learning-resource-picker__toolbar">
                    <label>
                      搜索资源
                      <input
                        value={resourceQuery}
                        onChange={(event) => setResourceQuery(event.target.value)}
                        placeholder="按名称、创建者或 ID 搜索"
                      />
                    </label>
                    <label>
                      资源类型
                      <select value={resourceType} onChange={(event) => setResourceType(event.target.value)}>
                        <option value="">全部类型</option>
                        {resourceTypes.map((type) => <option key={type} value={type}>{type}</option>)}
                      </select>
                    </label>
                    <span>已选 {selectedResources.size} 项</span>
                  </div>
                  {filteredMaterials.length === 0 ? <p>没有匹配的课程共享资源；已选资源保持不变。</p> : (
                    <div className="learning-resource-picker">
                      {filteredMaterials.map((material) => {
                        const key = materialKey({ material_type: material.material_type, material_id: material.material_id });
                        return (
                          <label key={key}>
                            <input
                              type="checkbox"
                              checked={selectedResources.has(key)}
                              onChange={() => setSelectedResources((current) => {
                                const next = new Set(current);
                                if (next.has(key)) next.delete(key); else next.add(key);
                                return next;
                              })}
                            />
                            <span>
                              <strong>{materialTitle(material)}</strong>
                              <span className="learning-resource-picker__type">{material.material_type}</span>
                              <small>
                                {material.created_by || "未知创建者"} · {formatUpdatedAt(material.updated_at)} · {material.material_id.slice(-8)}
                              </small>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </fieldset>
            <div className="learning-create__actions">
              <button type="button" className="learning-secondary" onClick={() => setCreating(false)}>取消</button>
              <button type="submit" className="learning-primary" disabled={busy}>保存草稿</button>
            </div>
          </form>
        </section>
      ) : null}

      {tasks.length === 0 ? (
        <section className="learning-empty">
          <MaterialIcon name="fact_check" />
          <h3>{isTeacher ? "还没有学习任务" : "教师暂未发布学习任务"}</h3>
          <p>{isTeacher ? "从课程共享资源中组织第一个学习任务。" : "你可以先浏览课程资源，发布后任务会出现在这里。"}</p>
        </section>
      ) : isTeacher ? (
        <div className="learning-teacher-grid">
          <section className="learning-task-list">
            {tasks.map((task) => (
              <button
                key={task.task_id}
                type="button"
                className={task.task_id === selectedTaskId ? "is-active" : ""}
                onClick={() => setSelectedTaskId(task.task_id)}
              >
                <span className={`learning-badge learning-badge--${task.status}`}>{task.status === "draft" ? "草稿" : task.status === "published" ? "已发布" : "已关闭"}</span>
                <strong>{task.title}</strong>
                <small>{task.resource_refs.length} 项资源 · {task.knowledge_point_ids.length} 个知识点</small>
              </button>
            ))}
          </section>
          <section className="learning-detail">
            {selectedTask ? (
              <>
                <div className="learning-detail__head">
                  <div><h3>{selectedTask.title}</h3><p>{selectedTask.instructions || "暂无补充说明"}</p></div>
                  {getLearningTaskPrimaryAction("teacher", selectedTask) === "publish" ? (
                    <button type="button" className="learning-primary" disabled={busy || getAssessmentPublishBlockers(assessmentDrafts[selectedTask.task_id]).length > 0} onClick={() => void publishTask(selectedTask)}>发布给学生</button>
                  ) : null}
                </div>
                <ResourceLinks task={selectedTask} materials={sharedMaterialByKey} courseId={courseId} role={user?.role} />
                {selectedTask.status === "draft" ? (
                  <AssessmentEditor
                    courseId={courseId}
                    task={selectedTask}
                    onDraftChange={handleAssessmentDraftChange}
                  />
                ) : summary ? (
                  <>
                    <div className="learning-summary-grid">
                      <SummaryCard label="课程学生" value={summary.enrolled_students} />
                      <SummaryCard label="已开始" value={summary.started_students} />
                      <SummaryCard label="已完成" value={summary.completed_students} />
                      <SummaryCard label="完成率" value={formatPercent(summary.completion_rate)} />
                    </div>
                    <div className="learning-progress-table">
                      <div className="learning-progress-table__head"><span>学生</span><span>状态</span><span>进度</span><span>完成口径</span></div>
                      {summary.progress.map((item) => (
                        <div key={item.student_id}>
                          <strong>{item.student_id}</strong>
                          <span>{item.status === "completed" ? "已完成" : item.status === "in_progress" ? "进行中" : "未开始"}</span>
                          <span>{getProgressLabel(item.progress_percent, item.status)}</span>
                          <span>{getCompletionBasisLabel(item.completion_basis, item.status)}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : <div className="learning-draft-note">正在汇总学生学习进度…</div>}
              </>
            ) : null}
          </section>
        </div>
      ) : (
        <section className="learning-student-list">
          {tasks.map((task) => {
            const action = getLearningTaskPrimaryAction("student", task);
            const progress = task.my_progress?.progress_percent ?? 0;
            return (
              <article key={task.task_id} className="learning-student-card">
                <div className="learning-student-card__head">
                  <div><span className="learning-badge learning-badge--published">学习任务</span><h3>{task.title}</h3><p>{task.instructions || "按照关联资源完成学习。"}</p></div>
                  <strong>{getProgressLabel(progress, task.my_progress?.status ?? "not_started")}</strong>
                </div>
                {task.my_progress?.status === "completed" ? (
                  <p className="learning-completion-basis">
                    完成口径：{getCompletionBasisLabel(task.my_progress.completion_basis, task.my_progress.status)}
                  </p>
                ) : null}
                <div className="learning-progress"><span style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} /></div>
                <div className="learning-student-resources">
                  {task.resource_refs.map((ref) => (
                    <button key={materialKey(ref)} type="button" disabled={busy} onClick={() => void openResource(task, ref)}>
                      <MaterialIcon name="menu_book" />
                      <span>{materialTitle(sharedMaterialByKey.get(materialKey(ref)) ?? { ...ref, title: ref.material_id })}</span>
                      <small>打开资源</small>
                    </button>
                  ))}
                </div>
                <AssessmentRunner
                  courseId={courseId}
                  taskId={task.task_id}
                  onVerified={() => void loadTasks()}
                />
                <div className="learning-student-card__actions">
                  {action === "start" || action === "continue" ? (
                    <button type="button" className="learning-secondary" disabled={busy} onClick={() => void writeStudentEvent(task, "started")}>
                      {action === "start" ? "开始学习" : "继续学习"}
                    </button>
                  ) : action === "completed" ? <span className="learning-complete">✓ 已完成</span> : null}
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function ResourceLinks({
  task,
  materials,
  courseId,
  role,
}: {
  task: LearningTask;
  materials: Map<string, CourseMaterial>;
  courseId: string | null;
  role: "admin" | "teacher" | "student" | undefined;
}) {
  if (task.resource_refs.length === 0) return <p className="learning-no-resources">此任务暂未关联课程资源。</p>;
  return (
    <div className="learning-resource-links">
      {task.resource_refs.map((ref) => (
        <a key={materialKey(ref)} href={buildRoleCourseHash(role, routes.resources, courseId, { space: "course", material_type: ref.material_type, material_id: ref.material_id })}>
          <MaterialIcon name="menu_book" />
          <span><strong>{materialTitle(materials.get(materialKey(ref)) ?? { ...ref, title: ref.material_id })}</strong><small>{ref.material_type}</small></span>
        </a>
      ))}
    </div>
  );
}
