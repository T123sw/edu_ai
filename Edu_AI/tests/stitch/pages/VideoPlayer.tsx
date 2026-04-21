import { useEffect, useMemo, useState } from "react";
import {
  askAiLecturer,
  createAiLecturerCourse,
  generateAiLecturerFullVideo,
  generateAiLecturerScript,
  getAiLecturerDownloadUrl,
  getAiLecturerTaskStatus,
  getAiLecturerVideoUrl,
  getAiLecturerWebRtcUrl,
  speakAiLecturerSentence,
  stopAiLecturerSpeaking,
} from "../api/video";
import { courseMaterialToMarkdown, getCourseMaterials, getKnowledgeGraph } from "../api/courses";
import { MarkdownPreview } from "../components/MarkdownPreview";
import type { CourseMaterial, KnowledgeGraphNode } from "../api/types";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  defaultCourse,
  routeHref,
  routes,
  useAppShell,
} from "../shared";

type Slide = {
  title: string;
  content: string;
};

function getDefaultMarkdown(courseTitle?: string) {
  return [
    `# ${courseTitle || "课程讲义"}`,
    "",
    "## 第一部分 课程导入",
    "",
    "- 课程背景",
    "- 学习目标",
    "",
    "## 第二部分 核心概念",
    "",
    "- 核心知识点一",
    "- 核心知识点二",
    "",
    "## 第三部分 总结",
    "",
    "- 重点回顾",
    "- 延伸思考",
  ].join("\n");
}

function fileNameFromUrl(url: string) {
  const normalized = url.split("?")[0];
  return normalized.slice(normalized.lastIndexOf("/") + 1);
}

function buildMaterialFallback(materials: CourseMaterial[]): KnowledgeGraphNode | null {
  if (!materials.length) return null;

  return {
    id: "materials-root",
    label: "课程内容",
    data: {
      type: "chapter",
      summary: "知识图谱不可用时，使用课程内容生成学习结构。",
    },
    children: materials.map((item, index) => ({
      id: item.material_id,
      label: item.title || item.topic || `内容 ${index + 1}`,
      data: {
        type: item.material_type || "topic",
        summary: item.summary || "课程学习资料",
      },
      children: [],
    })),
  };
}

function countNodes(node: KnowledgeGraphNode | null | undefined): number {
  if (!node) return 0;
  return 1 + (node.children || []).reduce((sum, child) => sum + countNodes(child), 0);
}

function findNodeById(node: KnowledgeGraphNode | null | undefined, nodeId: string | null): KnowledgeGraphNode | null {
  if (!node || !nodeId) return null;
  if (node.id === nodeId) return node;

  for (const child of node.children || []) {
    const found = findNodeById(child, nodeId);
    if (found) return found;
  }

  return null;
}

function nodeTypeLabel(node: KnowledgeGraphNode) {
  const type = node.data?.type?.toLowerCase();
  if (type === "chapter") return "章节";
  if (type === "section") return "小节";
  if (type === "topic") return "知识点";
  return "节点";
}

export function VideoPlayerPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;

  const [mode, setMode] = useState<"online" | "offline">("online");
  const [rawDocument, setRawDocument] = useState(getDefaultMarkdown(selectedCourse?.title));
  const [courseId, setCourseId] = useState("");
  const [outline, setOutline] = useState<Slide[]>([]);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [scriptSentences, setScriptSentences] = useState<string[]>([]);
  const [currentSentence, setCurrentSentence] = useState("");
  const [studentQuestion, setStudentQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [offlineTaskId, setOfflineTaskId] = useState("");
  const [offlineStatus, setOfflineStatus] = useState("");
  const [offlineVideoUrl, setOfflineVideoUrl] = useState("");
  const [offlineImageRoot, setOfflineImageRoot] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [materialsError, setMaterialsError] = useState<string | null>(null);
  const [activeMaterialId, setActiveMaterialId] = useState<string | null>(null);

  const [graphRoot, setGraphRoot] = useState<KnowledgeGraphNode | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [activeStructureId, setActiveStructureId] = useState<string | null>(null);
  const [expandedStructureIds, setExpandedStructureIds] = useState<Set<string>>(new Set());

  const webrtcUrl = getAiLecturerWebRtcUrl();
  const activeSlide = outline[activeSlideIndex] ?? null;
  const activeMaterial = materials.find((item) => item.material_id === activeMaterialId) ?? materials[0] ?? null;
  const activeMaterialMarkdown = activeMaterial ? courseMaterialToMarkdown(activeMaterial) : "";

  const fallbackStructure = useMemo(() => buildMaterialFallback(materials), [materials]);
  const structureRoot = graphRoot ?? fallbackStructure;
  const activeStructureNode = useMemo(
    () => findNodeById(structureRoot, activeStructureId) ?? structureRoot,
    [activeStructureId, structureRoot],
  );
  const structureNodeCount = useMemo(() => countNodes(structureRoot), [structureRoot]);

  const learningSummary = useMemo(() => {
    return `已解析 ${outline.length} 页，当前第 ${outline.length ? activeSlideIndex + 1 : 0} 页，当前讲稿 ${scriptSentences.length} 句。`;
  }, [activeSlideIndex, outline.length, scriptSentences.length]);

  useEffect(() => {
    setRawDocument(getDefaultMarkdown(selectedCourse?.title));
  }, [selectedCourse?.title]);

  useEffect(() => {
    let cancelled = false;

    async function loadMaterials() {
      try {
        setMaterialsLoading(true);
        setMaterialsError(null);
        const data = await getCourseMaterials(course.id);
        if (!cancelled) {
          setMaterials(data);
          setActiveMaterialId((current) =>
            current && data.some((item) => item.material_id === current) ? current : (data[0]?.material_id ?? null),
          );
        }
      } catch (err) {
        if (!cancelled) {
          setMaterials([]);
          setActiveMaterialId(null);
          setMaterialsError(err instanceof Error ? err.message : "课程内容加载失败");
        }
      } finally {
        if (!cancelled) {
          setMaterialsLoading(false);
        }
      }
    }

    void loadMaterials();
    return () => {
      cancelled = true;
    };
  }, [course.id]);

  useEffect(() => {
    let cancelled = false;

    async function loadGraph() {
      try {
        setGraphLoading(true);
        setGraphError(null);
        const data = await getKnowledgeGraph(course.id);
        if (!cancelled) {
          setGraphRoot(data.root);
        }
      } catch (err) {
        if (!cancelled) {
          setGraphRoot(null);
          setGraphError(err instanceof Error ? err.message : "知识结构加载失败");
        }
      } finally {
        if (!cancelled) {
          setGraphLoading(false);
        }
      }
    }

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [course.id]);

  useEffect(() => {
    if (!structureRoot) {
      setActiveStructureId(null);
      setExpandedStructureIds(new Set());
      return;
    }

    setActiveStructureId((current) => current ?? structureRoot.id);
    setExpandedStructureIds((current) => {
      if (current.size > 0) return current;
      return new Set([structureRoot.id]);
    });
  }, [structureRoot]);

  useEffect(() => {
    if (!offlineTaskId || offlineStatus === "success" || offlineStatus === "failed") return;

    const timer = window.setInterval(async () => {
      try {
        const result = await getAiLecturerTaskStatus(offlineTaskId);
        setOfflineStatus(result.status);
        if (result.status === "success" && result.video_url) {
          setOfflineVideoUrl(getAiLecturerVideoUrl(result.video_url));
        }
        if (result.status === "failed") {
          setError(result.error || "离线视频生成失败。");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "任务状态查询失败。");
      }
    }, 4000);

    return () => window.clearInterval(timer);
  }, [offlineStatus, offlineTaskId]);

  async function withBusy(name: string, action: () => Promise<void>) {
    try {
      setBusy(name);
      setError(null);
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败。");
    } finally {
      setBusy("");
    }
  }

  async function handleCreateCourse() {
    await withBusy("create-course", async () => {
      const result = await createAiLecturerCourse({
        course_name: course.title || "课程学习",
        raw_document: rawDocument,
      });
      setCourseId(result.course_id);
      setOutline(result.pages || []);
      setActiveSlideIndex(0);
      setScriptSentences([]);
      setCurrentSentence("");
      setAnswerText("");
    });
  }

  async function handleGenerateScript() {
    if (!activeSlide || !outline.length) {
      setError("请先生成课程大纲。");
      return;
    }

    await withBusy("generate-script", async () => {
      const result = await generateAiLecturerScript({
        course_title: course.title || "课程学习",
        current_slide_content: activeSlide.content,
        page_index: activeSlideIndex,
        total_pages: outline.length,
      });
      setScriptSentences(result.sentences || []);
      setCurrentSentence(result.sentences?.[0] || "");
    });
  }

  async function handleSpeak(sentence: string) {
    await withBusy("speak", async () => {
      await speakAiLecturerSentence({ text: sentence, session_id: 0 });
      setCurrentSentence(sentence);
    });
  }

  async function handleStop() {
    await withBusy("stop", async () => {
      await stopAiLecturerSpeaking(0);
    });
  }

  async function handleInterruptAsk() {
    if (!studentQuestion.trim()) {
      setError("请输入学生提问内容。");
      return;
    }

    await withBusy("ask", async () => {
      const result = await askAiLecturer({
        question: studentQuestion.trim(),
        slide_context: activeSlide?.content || "",
        interrupted_sentence: currentSentence || "",
        session_id: 0,
      });
      setAnswerText(result.answer || "");
    });
  }

  async function handleGenerateOfflineVideo() {
    if (!outline.length) {
      setError("请先生成课程大纲。");
      return;
    }
    if (!offlineImageRoot.trim()) {
      setError("请填写 PPT 图片绝对路径前缀。");
      return;
    }

    await withBusy("offline", async () => {
      const normalizedRoot = offlineImageRoot.replace(/[\\]+/g, "/").replace(/\/$/, "");
      const result = await generateAiLecturerFullVideo({
        course_title: course.title || "课程学习",
        pages: outline.map((item, index) => ({
          ppt_image_path: `${normalizedRoot}/slide${index + 1}.png`,
          content_text: item.content,
        })),
      });
      setOfflineTaskId(result.task_id);
      setOfflineStatus("processing");
      setOfflineVideoUrl("");
    });
  }

  function toggleStructureNode(nodeId: string) {
    setExpandedStructureIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  function handleStructureSelect(node: KnowledgeGraphNode) {
    setActiveStructureId(node.id);
    if (materials.some((item) => item.material_id === node.id)) {
      setActiveMaterialId(node.id);
    }
  }

  function renderStructureNode(node: KnowledgeGraphNode, depth = 0): React.ReactNode {
    const hasChildren = Boolean(node.children?.length);
    const expanded = expandedStructureIds.has(node.id);
    const active = activeStructureId === node.id;

    return (
      <div key={node.id} className="space-y-2">
        <div
          className={`rounded-[20px] border transition ${
            active
              ? "border-[var(--accent-border)] bg-[var(--accent-soft)] shadow-[0_12px_24px_var(--accent-shadow)]"
              : "border-[var(--shell-border)] bg-[var(--surface-subtle)]"
          }`}
        >
          <div className="flex items-stretch gap-2 p-3" style={{ paddingLeft: `${14 + depth * 18}px` }}>
            {hasChildren ? (
              <button
                type="button"
                onClick={() => toggleStructureNode(node.id)}
                className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white text-[var(--accent-strong)]"
              >
                <MaterialIcon name={expanded ? "expand_less" : "expand_more"} className="text-sm" />
              </button>
            ) : (
              <div className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white text-[var(--muted-text)]">
                <MaterialIcon name="article" className="text-sm" />
              </div>
            )}

            <button type="button" onClick={() => handleStructureSelect(node)} className="min-w-0 flex-1 text-left">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--accent-strong)]">
                  {nodeTypeLabel(node)}
                </span>
              </div>
              <p className="mt-2 text-sm font-bold text-[var(--app-text)]">{node.label}</p>
              {node.data?.summary ? (
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--muted-text)]">{node.data.summary}</p>
              ) : null}
            </button>
          </div>
        </div>

        {hasChildren && expanded ? <div className="space-y-2">{node.children!.map((child) => renderStructureNode(child, depth + 1))}</div> : null}
      </div>
    );
  }

  return (
    <AppSurface className="flex h-screen overflow-hidden">
      <SidebarDock className="h-screen gap-6 overflow-hidden bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="px-2 py-4">
          <SidebarBackLink />
          <h2 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">{course.title}</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted-text)]">课程学习</p>
        </div>
        <SidebarNav activeRoute={routes.video} />
      </SidebarDock>

      <div className="grid min-w-0 flex-1 gap-6 overflow-hidden p-6 lg:grid-cols-[360px_minmax(0,1fr)_380px]">
        <aside className="overflow-hidden rounded-[32px] border border-[var(--shell-border)] bg-[var(--panel-surface)] shadow-[0_16px_32px_var(--panel-shadow)] lg:h-[calc(100vh-48px)]">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/92 p-6 backdrop-blur-xl">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">课程学习</p>
            <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">知识结构列表</h3>
            
          </div>

          <div className="space-y-5 overflow-y-auto p-5 lg:h-[calc(100vh-196px)]">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-[var(--accent-strong)]">学习路径</p>
                  <p className="mt-1 text-xs text-[var(--muted-text)]">
                    {graphRoot ? "当前结构直接来自知识图谱。" : "知识图谱不可用时，自动回退为课程内容列表。"}
                  </p>
                </div>
                <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">
                  {structureNodeCount} nodes
                </span>
              </div>

              <div className="mt-4 space-y-3">
                {graphLoading ? (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
                    正在加载知识结构...
                  </div>
                ) : structureRoot ? (
                  renderStructureNode(structureRoot)
                ) : (
                  <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
                    {graphError || "当前课程还没有可显示的知识结构。"}
                  </div>
                )}
              </div>
            </div>

          </div>
        </aside>

        <main className="min-w-0 overflow-y-auto rounded-[32px] border border-[var(--shell-border)] bg-[var(--app-bg)] lg:h-[calc(100vh-48px)]">
          <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-8 py-4 backdrop-blur-xl">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">课程学习</h1>
            <p className="mt-1 text-sm text-[var(--muted-text)]">
              {mode === "online"
                ? "在线学习模式：播放课堂、生成讲稿、学生提问与课程内容联动。"
                : "离线生成模式：根据当前大纲批量生成完整课程视频。"}
            </p>
          </header>

          <div className="w-full px-6 py-6 xl:px-8">
            <GlassPanel className="overflow-hidden bg-[#020617]">
              {mode === "online" ? (
                <iframe title="课程学习实时课堂" src={webrtcUrl} className="aspect-video w-full border-0 bg-black" />
              ) : offlineVideoUrl ? (
                <video controls className="aspect-video w-full bg-black" src={offlineVideoUrl} />
              ) : (
                <div className="aspect-video bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.32),transparent_24%),radial-gradient(circle_at_75%_58%,rgba(14,165,233,0.22),transparent_30%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#1d4ed8_100%)]" />
              )}
            </GlassPanel>

            {mode === "online" ? (
              <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-2xl font-black text-[var(--accent-strong)]">当前讲解</h2>
                    <button
                      type="button"
                      onClick={() => void handleGenerateScript()}
                      disabled={busy === "generate-script"}
                      className="rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                    >
                      {busy === "generate-script" ? "生成中..." : "生成当前页讲稿"}
                    </button>
                  </div>
                  <div className="mt-4 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">{activeSlide ? activeSlide.title : "未选择页面"}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--muted-text)]">
                      {activeSlide?.content || "请先生成课程大纲。"}
                    </p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {scriptSentences.map((sentence, index) => (
                      <button
                        key={`${index}-${sentence}`}
                        type="button"
                        onClick={() => void handleSpeak(sentence)}
                        className={`w-full rounded-[18px] border p-4 text-left ${
                          currentSentence === sentence ? "border-[var(--accent-border)] bg-[var(--accent-soft)]" : "border-[var(--shell-border)] bg-white"
                        }`}
                      >
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">讲稿句子 {index + 1}</p>
                        <p className="mt-2 text-sm leading-7 text-[var(--app-text)]">{sentence}</p>
                      </button>
                    ))}
                    {!scriptSentences.length ? <div className="text-sm text-[var(--muted-text)]">当前还没有生成讲稿。</div> : null}
                  </div>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">课堂问答</h2>
                  <textarea
                    value={studentQuestion}
                    onChange={(event) => setStudentQuestion(event.target.value)}
                    className="mt-4 min-h-[140px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4 text-sm outline-none"
                    placeholder="输入学生实时提问..."
                  />
                  <div className="mt-4 flex gap-3">
                    <button
                      type="button"
                      onClick={() => void handleStop()}
                      disabled={busy === "stop"}
                      className="flex-1 rounded-full border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600 disabled:opacity-60"
                    >
                      {busy === "stop" ? "停止中..." : "停止播报"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleInterruptAsk()}
                      disabled={busy === "ask"}
                      className="flex-1 rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                    >
                      {busy === "ask" ? "回答中..." : "提交提问"}
                    </button>
                  </div>
                  <div className="mt-5 rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4">
                    <p className="text-sm font-bold text-[var(--accent-strong)]">AI 回答</p>
                    <div className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                      <MarkdownPreview content={answerText || "学生提问后，回答会显示在这里。"} />
                    </div>
                  </div>
                </GlassPanel>
              </section>
            ) : (
              <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">离线整课视频生成</h2>
                  <p className="mt-3 text-sm leading-7 text-[var(--muted-text)]">
                    后端要求传入每一页 PPT 图片的绝对路径。这里默认按 `slide1.png`、`slide2.png` 的命名规则拼接。
                  </p>
                  <input
                    value={offlineImageRoot}
                    onChange={(event) => setOfflineImageRoot(event.target.value)}
                    className="mt-4 h-12 w-full rounded-[18px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 text-sm outline-none"
                    placeholder="例如：E:/AI_Lecturer/assets"
                  />
                  <button
                    type="button"
                    onClick={() => void handleGenerateOfflineVideo()}
                    disabled={busy === "offline"}
                    className="mt-4 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
                  >
                    {busy === "offline" ? "提交中..." : "提交整套课件渲染任务"}
                  </button>
                </GlassPanel>

                <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                  <h2 className="text-2xl font-black text-[var(--accent-strong)]">任务状态</h2>
                  <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                    <p>任务 ID：{offlineTaskId || "--"}</p>
                    <p>当前状态：{offlineStatus || "--"}</p>
                    <p>视频地址：{offlineVideoUrl || "--"}</p>
                  </div>
                  {offlineVideoUrl ? (
                    <div className="mt-5 flex gap-3">
                      <a
                        href={offlineVideoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full border border-[var(--shell-border)] bg-white px-4 py-3 text-center text-sm font-bold text-[var(--accent-strong)]"
                      >
                        在线预览
                      </a>
                      <a
                        href={getAiLecturerDownloadUrl(fileNameFromUrl(offlineVideoUrl))}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 rounded-full bg-[var(--accent)] px-4 py-3 text-center text-sm font-bold text-white"
                      >
                        下载视频
                      </a>
                    </div>
                  ) : null}
                </GlassPanel>
              </section>
            )}

            <section id="course-materials" className="mt-8">
              <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--shell-border)] pb-5">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">Course Content</p>
                    <h2 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">课程内容</h2>
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
                      学习视频下方保留课程内容预览区，便于在课程学习过程中对照讲义、资料与文本内容。
                    </p>
                  </div>
                  <div className="rounded-[20px] border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-3 text-sm font-semibold text-[var(--accent-strong)]">
                    {materialsLoading ? "加载中..." : `共 ${materials.length} 份内容`}
                  </div>
                </div>

                <div className="mt-6 grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
                  <div className="space-y-3">
                    {materialsLoading ? (
                      <div className="rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        正在加载课程内容...
                      </div>
                    ) : materialsError ? (
                      <div className="rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-600">
                        {materialsError}
                      </div>
                    ) : materials.length === 0 ? (
                      <div className="rounded-[22px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        当前课程还没有可展示的内容。
                      </div>
                    ) : (
                      materials.map((item, index) => {
                        const active = item.material_id === activeMaterial?.material_id;

                        return (
                          <button
                            key={item.material_id}
                            type="button"
                            onClick={() => setActiveMaterialId(item.material_id)}
                            className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${
                              active
                                ? "border-[var(--accent-border)] bg-[var(--accent-soft)] shadow-[0_14px_28px_var(--accent-shadow)]"
                                : "border-[var(--shell-border)] bg-[var(--surface-subtle)] hover:border-[var(--accent-border)] hover:bg-white"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted-text)]">
                                  第 {index + 1} 项 · {item.material_type || "content"}
                                </p>
                                <h3 className="mt-2 truncate text-sm font-bold text-[var(--app-text)]">
                                  {item.title || item.topic || item.material_id}
                                </h3>
                                <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--muted-text)]">
                                  {item.summary || "点击查看当前内容详情。"}
                                </p>
                              </div>
                              {item.is_pinned ? (
                                <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-[var(--accent-strong)]">
                                  置顶
                                </span>
                              ) : null}
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>

                  <div className="min-w-0 rounded-[24px] border border-[var(--shell-border)] bg-white/88 p-5">
                    {activeMaterial ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] pb-4">
                          <div>
                            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">
                              {activeMaterial.material_type || "content"}
                            </p>
                            <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">
                              {activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                            </h3>
                          </div>
                          <div className="rounded-full border border-[var(--shell-border)] bg-[var(--surface-subtle)] px-3 py-2 text-xs font-semibold text-[var(--muted-text)]">
                            {course.title}
                          </div>
                        </div>
                        <div className="mt-5 max-h-[560px] overflow-y-auto pr-2">
                          <MarkdownPreview content={activeMaterialMarkdown} />
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[20px] bg-[var(--surface-subtle)] px-4 py-5 text-sm text-[var(--muted-text)]">
                        选择左侧一项内容后，会在这里显示完整预览。
                      </div>
                    )}
                  </div>
                </div>
              </GlassPanel>
            </section>

            {error ? (
              <div className="mt-6 rounded-[22px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-600">
                {error}
              </div>
            ) : null}
          </div>
        </main>

        <aside className="flex flex-col overflow-hidden rounded-[32px] border border-[var(--shell-border)] bg-[linear-gradient(180deg,rgba(246,249,255,0.94)_0%,rgba(239,245,253,0.96)_100%)] shadow-[0_16px_32px_var(--panel-shadow)] lg:h-[calc(100vh-48px)] lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/95 p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--accent)] text-white">
                <MaterialIcon name="school" className="text-lg" />
              </div>
              <div>
                <h4 className="font-bold text-[var(--accent-strong)]">学习概览</h4>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[#1b6d24]">实时联动</p>
              </div>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-6 overflow-hidden p-6">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">学习状态</p>
              <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                <p>{learningSummary}</p>
                <p>课程 ID：{courseId || "--"}</p>
                <p>当前结构节点：{activeStructureNode?.label || "--"}</p>
                <p>当前播报句子：{currentSentence || "--"}</p>
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">节点说明</p>
              <div className="mt-4 rounded-[18px] bg-[var(--surface-subtle)] p-4 text-sm leading-7 text-[var(--muted-text)]">
                {activeStructureNode?.data?.summary || "选择左侧知识结构节点后，这里会显示当前节点摘要。"}
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5 shadow-[0_14px_28px_rgba(15,23,42,0.05)]">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">快速跳转</p>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={() => document.getElementById("course-materials")?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  className="flex w-full items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]"
                >
                  <span className="text-sm font-semibold text-[var(--app-text)]">课程内容</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </button>
                <a
                  href={routeHref(routes.ai)}
                  className="flex items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]"
                >
                  <span className="text-sm font-semibold text-[var(--app-text)]">问答工作台</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </a>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </AppSurface>
  );
}
