import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { getCourseMaterials } from "../api/courses";
import { getStandardResources } from "../api/standardResources";
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
  LearningTaskResourceSnapshot,
} from "../api/types";
import { AssessmentEditor } from "../assessment/AssessmentEditor";
import { AssessmentRunner } from "../assessment/AssessmentRunner";
import { AssessmentAnalytics } from "../assessment/AssessmentAnalytics";
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
import {
  taskNeedsAssessment,
  taskTypeLabel,
} from "../course/learning/learningEvidencePresentation";
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

function snapshotText(snapshot: LearningTaskResourceSnapshot): string {
  const payload = snapshot.content_payload;
  if (typeof payload.content === "string") return payload.content;
  if (payload.stage && typeof payload.stage === "object") {
    const stage = payload.stage as { name?: string };
    if (stage.name) return `课堂：${stage.name}`;
  }
  return JSON.stringify(payload, null, 2);
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
  const [taskType, setTaskType] = useState<"reading" | "assessed">("reading");
  const [knowledgePoints, setKnowledgePoints] = useState("");
  const [selectedResources, setSelectedResources] = useState<Set<string>>(new Set());
  const [resourceQuery, setResourceQuery] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [assessmentDrafts, setAssessmentDrafts] = useState<Record<string, AssessmentDraft | null>>({});
  const [activeSnapshotId, setActiveSnapshotId] = useState<string | null>(null);

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
      const [taskData, personalMaterials, standardCatalog] = await Promise.all([
        listLearningTasks(courseId),
        isTeacher ? getCourseMaterials(courseId, { space: "mine" }) : Promise.resolve([]),
        isTeacher ? getStandardResources(courseId) : Promise.resolve(null),
      ]);
      const standardMaterials = standardCatalog
        ? standardCatalog.leaves.flatMap((leaf) =>
            leaf.slots.flatMap((slot) =>
              slot.resource && slot.approved_version ? [slot.resource] : [],
            ),
          )
        : [];
      const materialData = [...standardMaterials, ...personalMaterials].filter(
        (material, index, all) =>
          all.findIndex((candidate) =>
            candidate.material_type === material.material_type
            && candidate.material_id === material.material_id
          ) === index,
      );
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
  }, [courseId, isTeacher]);

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
    if (!courseId) return;
    const taskMaterials = materials.filter((material) => selectedResources.has(materialKey({
      material_type: material.material_type,
      material_id: material.material_id,
    })));
    if (taskMaterials.length === 0) {
      setError("请至少选择一项学习资料，其他信息均可留空。");
      return;
    }
    const generatedTitle = taskMaterials.length === 1
      ? materialTitle(taskMaterials[0])
      : `${materialTitle(taskMaterials[0])}等 ${taskMaterials.length} 项资料学习`;
    setBusy(true);
    setError(null);
    try {
      const created = await createLearningTask(courseId, {
        task_type: taskType,
        title: title.trim() || generatedTitle,
        instructions: instructions.trim(),
        resource_refs: taskMaterials.map((material) => ({
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
      setTaskType("reading");
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
    const blockers = taskNeedsAssessment(task)
      ? getAssessmentPublishBlockers(assessmentDrafts[task.task_id])
      : [];
    if (blockers.length > 0) {
      setError(blockers.join("；"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const draft = assessmentDrafts[task.task_id];
      if (taskNeedsAssessment(task) && !draft) return;
      const published = await publishLearningTask(
        courseId,
        task.task_id,
        draft?.draft_revision,
      );
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
    eventType: "started" | "resource_opened" | "resource_completed" | "completed",
    resourceRef?: LearningResourceRef,
  ) {
    if (!courseId) return false;
    setBusy(true);
    setError(null);
    try {
      const progress = eventType === "completed" || eventType === "resource_completed"
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
    if (ref.snapshot_id) {
      setActiveSnapshotId((current) =>
        current === ref.snapshot_id ? null : ref.snapshot_id || null,
      );
      return;
    }
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
            <fieldset className="learning-task-type">
              <legend>任务类型</legend>
              <label>
                <input
                  type="radio"
                  name="task-type"
                  value="reading"
                  checked={taskType === "reading"}
                  onChange={() => setTaskType("reading")}
                />
                <span><strong>阅读学习</strong><small>完成资源后形成活动证据，不要求测验。</small></span>
              </label>
              <label>
                <input
                  type="radio"
                  name="task-type"
                  value="assessed"
                  checked={taskType === "assessed"}
                  onChange={() => setTaskType("assessed")}
                />
                <span><strong>考核任务</strong><small>除学习资源外，还需配置并发布测验。</small></span>
              </label>
            </fieldset>
            <div className="learning-create__head">
              <div><p>新建学习任务</p><span>先保存为草稿，确认后再发布。</span></div>
              <button type="button" onClick={() => setCreating(false)} aria-label="关闭">×</button>
            </div>
            <label>任务标题（选填）<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder="留空时使用学习资料名称" /></label>
            <label>学习说明（选填）<textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} rows={4} maxLength={10000} /></label>
            <label>知识点（选填）<input value={knowledgePoints} onChange={(event) => setKnowledgePoints(event.target.value)} placeholder="留空时由模型从资料中归纳" /></label>
            <fieldset>
              <legend>选择学习资料（必选）</legend>
              {materials.length === 0 ? <p>当前还没有课程共享资料，请先添加资料后再创建学习任务。</p> : (
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
                              <span className="learning-resource-picker__type">
                                {material.origin_type === "standard" ? "标准学习资源" : "个人资源"}
                              </span>
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
              <button type="submit" className="learning-primary" disabled={busy || selectedResources.size === 0}>保存草稿</button>
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
                <span className="learning-badge">{taskTypeLabel(task.task_type)}</span>
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
                    <button
                      type="button"
                      className="learning-primary"
                      disabled={
                        busy
                        || (
                          taskNeedsAssessment(selectedTask)
                          && getAssessmentPublishBlockers(
                            assessmentDrafts[selectedTask.task_id],
                          ).length > 0
                        )
                      }
                      onClick={() => void publishTask(selectedTask)}
                    >
                      发布给学生
                    </button>
                  ) : null}
                </div>
                <ResourceLinks task={selectedTask} materials={sharedMaterialByKey} courseId={courseId} role={user?.role} />
                {selectedTask.status === "draft" && taskNeedsAssessment(selectedTask) ? (
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
                    {courseId && taskNeedsAssessment(selectedTask) ? <AssessmentAnalytics courseId={courseId} taskId={selectedTask.task_id} onReviewed={() => void loadTasks()} /> : null}
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
                  {task.resource_refs.map((ref) => {
                    const snapshot = task.resource_snapshots.find(
                      (item) => item.snapshot_id === ref.snapshot_id,
                    );
                    return (
                      <div key={ref.snapshot_id || materialKey(ref)} className="learning-snapshot-resource">
                        <button type="button" disabled={busy} onClick={() => void openResource(task, ref)}>
                          <MaterialIcon name="menu_book" />
                          <span>{snapshot?.title || materialTitle(sharedMaterialByKey.get(materialKey(ref)) ?? { ...ref, title: ref.material_id })}</span>
                          <small>{activeSnapshotId === ref.snapshot_id ? "收起内容" : "打开任务快照"}</small>
                        </button>
                        {snapshot && activeSnapshotId === snapshot.snapshot_id ? (
                          <div className="learning-snapshot-resource__content">
                            <pre>{snapshotText(snapshot)}</pre>
                            <button
                              type="button"
                              className="learning-primary"
                              disabled={busy}
                              onClick={() => void writeStudentEvent(task, "resource_completed", ref)}
                            >
                              <MaterialIcon name="task_alt" />完成本项学习
                            </button>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                {taskNeedsAssessment(task) ? (
                  <AssessmentRunner
                    courseId={courseId}
                    taskId={task.task_id}
                    onVerified={() => void loadTasks()}
                  />
                ) : null}
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
        task.resource_snapshots.find((item) => item.snapshot_id === ref.snapshot_id) ? (
          <div key={ref.snapshot_id || materialKey(ref)}>
            <MaterialIcon name="inventory_2" />
            <span>
              <strong>{task.resource_snapshots.find((item) => item.snapshot_id === ref.snapshot_id)?.title}</strong>
              <small>任务快照 · {ref.material_type}</small>
            </span>
          </div>
        ) : (
          <a key={materialKey(ref)} href={buildRoleCourseHash(role, routes.resources, courseId, { space: "course", material_type: ref.material_type, material_id: ref.material_id })}>
            <MaterialIcon name="menu_book" />
            <span><strong>{materialTitle(materials.get(materialKey(ref)) ?? { ...ref, title: ref.material_id })}</strong><small>{ref.material_type}</small></span>
          </a>
        )
      ))}
    </div>
  );
}
