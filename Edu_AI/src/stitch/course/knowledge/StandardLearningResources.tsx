import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approvePendingStandardResources,
  createStandardResourceBatch,
  getStandardResourceBatch,
  getStandardResources,
  retryStandardResourceBatch,
  reviewStandardResource,
} from "../../api/standardResources";
import { listMyCourseResourceLearningProgress } from "../../api/resourceLearning";
import type {
  ResourceLearningProgress as ResourceLearningProgressData,
  StandardResourceBatch,
  StandardResourceLeaf,
  StandardResourceSlot,
} from "../../api/types";
import { useAuthSession } from "../../authSession";
import { MaterialIcon } from "../../shared";
import { useCourseRoute } from "../CourseRouteProvider";
import {
  groupStandardResourceLeaves,
  STANDARD_RESOURCE_KIND_META,
  standardBatchProgress,
  standardReviewLabel,
  standardSelectionSummary,
  toggleStandardResourceLeafScope,
} from "./standardLearningResourcesPresentation";
import { ResourceLearningProgress } from "./ResourceLearningProgress";
import { ResourceLearningAnalytics } from "./ResourceLearningAnalytics";
import {
  buildStudentClassroomLearningHref,
  resourceLearningProgressKey,
} from "./resourceLearningPresentation";
import "./standardLearningResources.css";


function resourcePreview(slot: StandardResourceSlot): string {
  const resource = (slot.resource || {}) as Record<string, unknown>;
  const content = resource.content;
  if (typeof content === "string") return content;
  const stage = resource.stage as { name?: string } | undefined;
  if (stage?.name) return `课堂：${stage.name}`;
  if (content && typeof content === "object") {
    return JSON.stringify(content, null, 2);
  }
  return "该资源已生成，可审核后发布给学生。";
}

function ResourceSlotCard({
  slot,
  courseId,
  isStudent,
  learningProgress,
  canManage,
  busy,
  onReview,
}: {
  slot: StandardResourceSlot;
  courseId: string;
  isStudent: boolean;
  learningProgress?: ResourceLearningProgressData;
  canManage: boolean;
  busy: boolean;
  onReview: (slot: StandardResourceSlot, decision: "approved" | "rejected") => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const meta = STANDARD_RESOURCE_KIND_META[slot.standard_kind];
  const generated = Boolean(slot.resource);
  const canReview = canManage && slot.review_status === "pending";
  const approvedClassroomVersion =
    isStudent &&
    slot.standard_kind === "classroom" &&
    slot.review_status === "approved" &&
    slot.approved_version
      ? slot.approved_version
      : null;

  return (
    <article className={`standard-resource-card standard-resource-card--${slot.review_status}`}>
      <header>
        <span className="standard-resource-card__icon" aria-hidden="true">
          <MaterialIcon name={meta.icon} />
        </span>
        <span className="standard-resource-card__title">
          <strong>{meta.label}</strong>
          <small>{meta.description}</small>
        </span>
        <span className={`standard-resource-status standard-resource-status--${slot.review_status}`}>
          {standardReviewLabel(slot.review_status)}
        </span>
      </header>

      {generated ? (
        <>
          <button
            type="button"
            className="standard-resource-card__preview-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            <MaterialIcon name={expanded ? "expand_less" : "visibility"} />
            {expanded ? "收起预览" : "预览内容"}
          </button>
          {expanded && (
            <pre className="standard-resource-card__preview">{resourcePreview(slot)}</pre>
          )}
          {approvedClassroomVersion ? (
            <>
              <ResourceLearningProgress progress={learningProgress} />
              <a
                className="standard-resource-card__learn"
                href={buildStudentClassroomLearningHref(
                  courseId,
                  slot.material_id,
                  approvedClassroomVersion,
                )}
              >
                <MaterialIcon name="play_circle" />
                {learningProgress ? "继续学习" : "开始学习"}
              </a>
            </>
          ) : null}
          {canManage && slot.standard_kind === "classroom" && slot.approved_version ? (
            <>
              <button
                type="button"
                className="standard-resource-card__preview-toggle"
                aria-expanded={analyticsOpen}
                onClick={() => setAnalyticsOpen((current) => !current)}
              >
                <MaterialIcon name="analytics" />
                {analyticsOpen ? "收起学习分析" : "学习分析"}
              </button>
              {analyticsOpen ? (
                <ResourceLearningAnalytics
                  courseId={courseId}
                  resourceId={slot.material_id}
                  version={slot.approved_version}
                />
              ) : null}
            </>
          ) : null}
          {canReview && (
            <div className="standard-resource-card__review-actions">
              <button
                type="button"
                disabled={busy}
                className="standard-resource-card__approve"
                onClick={() => onReview(slot, "approved")}
              >
                <MaterialIcon name="check_circle" />
                批准发布
              </button>
              <button
                type="button"
                disabled={busy}
                className="standard-resource-card__reject"
                onClick={() => onReview(slot, "rejected")}
              >
                <MaterialIcon name="undo" />
                退回修改
              </button>
            </div>
          )}
          {slot.approved_version && slot.current_version !== slot.approved_version ? (
            <p className="standard-resource-card__version-note">
              学生仍在使用已发布的第 {slot.approved_version} 版
            </p>
          ) : null}
        </>
      ) : (
        <p className="standard-resource-card__empty">等待教师生成</p>
      )}
    </article>
  );
}


type StandardLearningResourcesProps = {
  readOnly?: boolean;
  compact?: boolean;
  onCancel?: () => void;
};

export function StandardLearningResources({
  readOnly = false,
  compact = false,
  onCancel,
}: StandardLearningResourcesProps) {
  const { courseId, courseRole } = useCourseRoute();
  const { user } = useAuthSession();
  const isStudent = user?.role === "student";
  const canManage = !readOnly && (courseRole === "owner" || courseRole === "editor");
  const [leaves, setLeaves] = useState<StandardResourceLeaf[]>([]);
  const [selectedLeafIds, setSelectedLeafIds] = useState<Set<string>>(new Set());
  const [batch, setBatch] = useState<StandardResourceBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [expandedLeafId, setExpandedLeafId] = useState<string | null>(null);
  const [openChapterIds, setOpenChapterIds] = useState<Set<string>>(new Set());
  const [progressByResourceKey, setProgressByResourceKey] = useState(
    new Map<string, ResourceLearningProgressData>(),
  );

  const loadCatalog = useCallback(async () => {
    if (!courseId) return;
    setLoading(true);
    try {
      const [catalog, progressItems] = await Promise.all([
        getStandardResources(courseId),
        isStudent
          ? listMyCourseResourceLearningProgress(courseId).catch(() => [])
          : Promise.resolve([]),
      ]);
      setLeaves(catalog.leaves);
      setProgressByResourceKey(
        new Map(
          progressItems.map((progress) => [
            resourceLearningProgressKey(
              progress.resource_id,
              progress.resource_version,
            ),
            progress,
          ]),
        ),
      );
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "标准学习资源加载失败");
    } finally {
      setLoading(false);
    }
  }, [courseId, isStudent]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (!courseId || !batch || !["queued", "running"].includes(batch.status)) return;
    const timer = window.setInterval(() => {
      getStandardResourceBatch(courseId, batch.batch_id)
        .then((next) => {
          setBatch(next);
          if (!["queued", "running"].includes(next.status)) void loadCatalog();
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [batch, courseId, loadCatalog]);

  const groups = useMemo(() => groupStandardResourceLeaves(leaves), [leaves]);
  const selectedCount = selectedLeafIds.size;
  const availableStudentResources = leaves.reduce(
    (count, leaf) => count + leaf.slots.length,
    0,
  );

  useEffect(() => {
    if (!compact || groups.length === 0) return;
    setOpenChapterIds((current) => current.size
      ? current
      : new Set([groups[0].chapterId]));
  }, [compact, groups]);

  function toggleLeaf(leafId: string) {
    setSelectedLeafIds((current) => toggleStandardResourceLeafScope(current, [leafId]));
  }

  function toggleChapter(leafIds: readonly string[]) {
    setSelectedLeafIds((current) => toggleStandardResourceLeafScope(current, leafIds));
  }

  function toggleChapterOpen(chapterId: string) {
    setOpenChapterIds((current) => {
      const next = new Set(current);
      if (next.has(chapterId)) next.delete(chapterId);
      else next.add(chapterId);
      return next;
    });
  }

  async function generateSelected() {
    if (!courseId || !selectedCount) return;
    setWorking(true);
    setError("");
    try {
      const created = await createStandardResourceBatch(
        courseId,
        [...selectedLeafIds],
      );
      setBatch(created);
      setSelectedLeafIds(new Set());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成任务提交失败");
    } finally {
      setWorking(false);
    }
  }

  async function review(
    slot: StandardResourceSlot,
    decision: "approved" | "rejected",
  ) {
    if (!courseId) return;
    let reason = "";
    if (decision === "rejected") {
      reason = window.prompt("请填写退回原因，便于下一次重新生成时参考：")?.trim() || "";
      if (!reason) return;
    }
    setWorking(true);
    setError("");
    try {
      await reviewStandardResource(courseId, slot.material_id, decision, reason);
      await loadCatalog();
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "审核操作失败");
    } finally {
      setWorking(false);
    }
  }

  async function retryFailed() {
    if (!courseId || !batch) return;
    setWorking(true);
    try {
      setBatch(await retryStandardResourceBatch(courseId, batch.batch_id));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "失败项目重试失败");
    } finally {
      setWorking(false);
    }
  }

  async function approveBatch() {
    if (!courseId || !batch) return;
    setWorking(true);
    try {
      await approvePendingStandardResources(courseId, batch.batch_id);
      await loadCatalog();
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批量审核失败");
    } finally {
      setWorking(false);
    }
  }

  if (loading) {
    return (
      <section className={`standard-resources standard-resources--loading${compact ? " standard-resources--compact" : ""}`}>
        正在读取标准学习资源…
      </section>
    );
  }

  return (
    <section
      className={`standard-resources${compact ? " standard-resources--compact" : ""}`}
      aria-labelledby={compact ? undefined : "standard-resources-title"}
      aria-label={compact ? "学习资源生成配置" : undefined}
    >
      {!compact ? (
        <header className="standard-resources__header">
          <div>
            <span className="standard-resources__eyebrow">按知识点组织</span>
            <h2 id="standard-resources-title">标准学习资源</h2>
            <p>
              {canManage
                ? "系统只为叶子知识点生成 AI 课堂、学习指南和练习；审核通过后学生才能看到。"
                : "这里汇集教师审核发布的课堂、学习指南和练习。"}
            </p>
          </div>
          {canManage && leaves.length > 0 ? (
            <div className="standard-resources__toolbar">
              <button
                type="button"
                className="standard-resources__select-all"
                onClick={() => setSelectedLeafIds(
                  selectedCount === leaves.length
                    ? new Set()
                    : new Set(leaves.map((leaf) => leaf.leaf_id)),
                )}
              >
                {selectedCount === leaves.length ? "取消全选" : "选择全部知识点"}
              </button>
              <button
                type="button"
                className="standard-resources__generate"
                disabled={!selectedCount || working}
                onClick={() => void generateSelected()}
              >
                <MaterialIcon name="auto_awesome" />
                {working ? "正在提交…" : `生成 ${selectedCount * 3} 项资源`}
              </button>
            </div>
          ) : null}
        </header>
      ) : null}

      {error && <div className="standard-resources__error" role="alert">{error}</div>}

      {batch ? (
        <div className="standard-resource-batch" aria-live="polite">
          <div>
            <strong>本次生成进度</strong>
            <span>{standardBatchProgress(batch).label}</span>
          </div>
          <div className="standard-resource-batch__track" aria-hidden="true">
            <span style={{ width: `${standardBatchProgress(batch).percent}%` }} />
          </div>
          <div className="standard-resource-batch__actions">
            {batch.failed_items > 0 ? (
              <button type="button" disabled={working} onClick={() => void retryFailed()}>
                <MaterialIcon name="refresh" />重试失败项
              </button>
            ) : null}
            {batch.succeeded_items > 0 ? (
              <button type="button" disabled={working} onClick={() => void approveBatch()}>
                <MaterialIcon name="done_all" />批准本批待审资源
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {leaves.length === 0 ? (
        <div className="standard-resources__empty">
          <MaterialIcon name="account_tree" />
          <strong>还没有可生成资源的叶子知识点</strong>
          <p>请先在课程知识结构中补充具体知识点。</p>
        </div>
      ) : !canManage && availableStudentResources === 0 ? (
        <div className="standard-resources__empty">
          <MaterialIcon name="hourglass_empty" />
          <strong>教师还没有发布标准学习资源</strong>
          <p>资源审核完成后会自动出现在这里。</p>
        </div>
      ) : compact && canManage ? (
        <div className="standard-resources__chapters">
          {groups.map((group) => {
            const chapterLeafIds = group.leaves.map((leaf) => leaf.leaf_id);
            const chapterSelectedCount = chapterLeafIds.filter((leafId) => selectedLeafIds.has(leafId)).length;
            const chapterOpen = openChapterIds.has(group.chapterId);
            const chapterSelected = chapterSelectedCount === chapterLeafIds.length;

            return (
              <section key={group.chapterId} className="standard-resource-chapter standard-resource-chapter--compact">
                <header className="standard-resource-chapter__compact-header">
                  <button
                    type="button"
                    aria-expanded={chapterOpen}
                    onClick={() => toggleChapterOpen(group.chapterId)}
                  >
                    <MaterialIcon name={chapterOpen ? "expand_less" : "chevron_right"} />
                    <strong>{group.chapterTitle}</strong>
                    <span>{group.leaves.length} 个知识点 · 已选 {chapterSelectedCount}</span>
                  </button>
                  <button type="button" onClick={() => toggleChapter(chapterLeafIds)}>
                    {chapterSelected ? "取消本章" : "全选本章"}
                  </button>
                </header>

                {chapterOpen ? (
                  <div className="standard-resource-chapter__compact-leaves">
                    {group.leaves.map((leaf) => {
                      const detailsOpen = expandedLeafId === leaf.leaf_id;
                      const path = leaf.path_titles.join(" / ");

                      return (
                        <section key={leaf.leaf_id} className="standard-resource-leaf standard-resource-leaf--compact">
                          <div className="standard-resource-leaf__compact-row">
                            <label>
                              <input
                                type="checkbox"
                                checked={selectedLeafIds.has(leaf.leaf_id)}
                                onChange={() => toggleLeaf(leaf.leaf_id)}
                              />
                              <span>
                                <strong>{leaf.title}</strong>
                                <small title={path}>{path}</small>
                              </span>
                            </label>
                            <div className="standard-resource-leaf__status-summary" aria-label={`${leaf.title}资源状态`}>
                              {leaf.slots.map((slot) => (
                                <span
                                  key={slot.standard_kind}
                                  className={`standard-resource-status--${slot.review_status}`}
                                >
                                  {STANDARD_RESOURCE_KIND_META[slot.standard_kind].label} · {standardReviewLabel(slot.review_status)}
                                </span>
                              ))}
                            </div>
                            <button
                              type="button"
                              aria-label={`${detailsOpen ? "收起" : "查看"}${leaf.title}详情`}
                              aria-expanded={detailsOpen}
                              onClick={() => setExpandedLeafId((current) => current === leaf.leaf_id ? null : leaf.leaf_id)}
                            >
                              {detailsOpen ? "收起详情" : "查看详情"}
                            </button>
                          </div>
                          {detailsOpen ? (
                            <div className="standard-resource-leaf__slots standard-resource-leaf__slots--compact">
                              {leaf.slots.map((slot) => (
                                <ResourceSlotCard
                                  key={slot.standard_kind}
                                  slot={slot}
                                  courseId={courseId ?? ""}
                                  isStudent={isStudent}
                                  learningProgress={
                                    slot.approved_version
                                      ? progressByResourceKey.get(
                                          resourceLearningProgressKey(
                                            slot.material_id,
                                            slot.approved_version,
                                          ),
                                        )
                                      : undefined
                                  }
                                  canManage={canManage}
                                  busy={working}
                                  onReview={(target, decision) => void review(target, decision)}
                                />
                              ))}
                            </div>
                          ) : null}
                        </section>
                      );
                    })}
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      ) : (
        <div className="standard-resources__chapters">
          {groups.map((group) => (
            <details key={group.chapterId} className="standard-resource-chapter" open>
              <summary>
                <span><MaterialIcon name="folder_open" />{group.chapterTitle}</span>
                <small>{group.leaves.length} 个知识点</small>
              </summary>
              <div className="standard-resource-chapter__leaves">
                {group.leaves.map((leaf) => (
                  <section key={leaf.leaf_id} className="standard-resource-leaf">
                    <header className="standard-resource-leaf__header">
                      {canManage ? (
                        <label>
                          <input
                            type="checkbox"
                            checked={selectedLeafIds.has(leaf.leaf_id)}
                            onChange={() => toggleLeaf(leaf.leaf_id)}
                          />
                          <span>{leaf.title}</span>
                        </label>
                      ) : (
                        <h3>{leaf.title}</h3>
                      )}
                      <small>{leaf.path_titles.join(" / ")}</small>
                    </header>
                    <div className="standard-resource-leaf__slots">
                      {leaf.slots.map((slot) => (
                        <ResourceSlotCard
                          key={slot.standard_kind}
                          slot={slot}
                          courseId={courseId ?? ""}
                          isStudent={isStudent}
                          learningProgress={
                            slot.approved_version
                              ? progressByResourceKey.get(
                                  resourceLearningProgressKey(
                                    slot.material_id,
                                    slot.approved_version,
                                  ),
                                )
                              : undefined
                          }
                          canManage={canManage}
                          busy={working}
                          onReview={(target, decision) => void review(target, decision)}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}

      {compact && canManage && leaves.length > 0 ? (
        <footer className="standard-resources__compact-footer">
          <div className="standard-resources__compact-selection">
            <strong>{standardSelectionSummary(selectedCount).label}</strong>
            <button
              type="button"
              onClick={() => setSelectedLeafIds(
                selectedCount === leaves.length
                  ? new Set()
                  : new Set(leaves.map((leaf) => leaf.leaf_id)),
              )}
            >
              {selectedCount === leaves.length ? "取消全选" : "选择全部知识点"}
            </button>
          </div>
          <div className="standard-resources__compact-actions">
            <button
              type="button"
              className="standard-resources__compact-cancel"
              onClick={() => onCancel?.()}
            >
              取消
            </button>
            <button
              type="button"
              className="standard-resources__generate"
              disabled={!selectedCount || working}
              onClick={() => void generateSelected()}
            >
              <MaterialIcon name="auto_awesome" />
              {working ? "正在提交…" : `开始生成 ${selectedCount * 3} 项资源`}
            </button>
          </div>
        </footer>
      ) : null}
    </section>
  );
}
