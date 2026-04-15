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
import { MarkdownPreview } from "../components/MarkdownPreview";
import { AppSurface, GlassPanel, MaterialIcon, SidebarBackLink, SidebarDock, SidebarNav, routeHref, routes, useAppShell } from "../shared";

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

export function VideoPlayerPage() {
  const { selectedCourse } = useAppShell();
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

  const activeSlide = outline[activeSlideIndex] ?? null;
  const webrtcUrl = getAiLecturerWebRtcUrl();

  useEffect(() => {
    setRawDocument(getDefaultMarkdown(selectedCourse?.title));
  }, [selectedCourse?.title]);

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

  const onlineSummary = useMemo(() => {
    return `已解析 ${outline.length} 页 | 当前第 ${outline.length ? activeSlideIndex + 1 : 0} 页 | 当前讲稿 ${scriptSentences.length} 句`;
  }, [activeSlideIndex, outline.length, scriptSentences.length]);

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
        course_name: selectedCourse?.title || "智能讲师课程",
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
        course_title: selectedCourse?.title || "智能讲师课程",
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
        course_title: selectedCourse?.title || "智能讲师课程",
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

  return (
    <AppSurface className="flex h-screen overflow-hidden">
      <SidebarDock className="h-screen gap-6 overflow-hidden bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="px-2 py-4">
          <SidebarBackLink />
          <h2 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">{selectedCourse?.title ?? "AI 智能讲师"}</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted-text)]">视频讲授空间</p>
        </div>
        <SidebarNav activeRoute={routes.video} />
        <a
          href={routeHref(routes.ai)}
          className="flex items-center justify-center gap-2 rounded-[22px] bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white shadow-[0_14px_30px_var(--accent-shadow)]"
        >
          <MaterialIcon name="forum" fill className="text-base" />
          返回问答工作台
        </a>
      </SidebarDock>

      <div className="grid min-w-0 flex-1 overflow-hidden lg:grid-cols-[360px_minmax(0,1fr)_380px]">
        <aside className="border-r border-[var(--shell-border)] bg-[var(--surface-subtle)] lg:h-screen lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/92 p-6 backdrop-blur-xl">
            <h3 className="text-lg font-bold text-[var(--accent-strong)]">课程讲义与大纲</h3>
            <p className="mt-1 text-xs uppercase tracking-[0.22em] text-[var(--muted-text)]">{courseId || "未生成课程 ID"}</p>
          </div>
          <div className="space-y-5 p-4">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("online")}
                className={`flex-1 rounded-full px-4 py-3 text-sm font-bold ${mode === "online" ? "bg-[var(--accent)] text-white" : "bg-white text-[var(--accent-strong)]"}`}
              >
                在线课堂
              </button>
              <button
                type="button"
                onClick={() => setMode("offline")}
                className={`flex-1 rounded-full px-4 py-3 text-sm font-bold ${mode === "offline" ? "bg-[var(--accent)] text-white" : "bg-white text-[var(--accent-strong)]"}`}
              >
                离线生成
              </button>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <p className="text-sm font-bold text-[var(--accent-strong)]">讲义 Markdown</p>
              <textarea
                value={rawDocument}
                onChange={(event) => setRawDocument(event.target.value)}
                className="mt-3 min-h-[220px] w-full rounded-[18px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-4 text-sm outline-none"
                placeholder="把课程 markdown 讲义贴在这里..."
              />
              <button
                type="button"
                onClick={() => void handleCreateCourse()}
                disabled={busy === "create-course" || !rawDocument.trim()}
                className="mt-3 w-full rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-60"
              >
                {busy === "create-course" ? "解析中..." : "解析并创建课程大纲"}
              </button>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-white p-4">
              <p className="text-sm font-bold text-[var(--accent-strong)]">页面大纲</p>
              <div className="mt-3 space-y-3">
                {outline.map((item, index) => (
                  <button
                    key={`${item.title}-${index}`}
                    type="button"
                    onClick={() => setActiveSlideIndex(index)}
                    className={`w-full rounded-[18px] border p-4 text-left ${
                      index === activeSlideIndex ? "border-[var(--accent-border)] bg-[var(--accent-soft)]" : "border-[var(--shell-border)] bg-[var(--surface-subtle)]"
                    }`}
                  >
                    <p className="text-sm font-bold text-[var(--app-text)]">第 {index + 1} 页：{item.title}</p>
                    <p className="mt-2 line-clamp-3 text-xs leading-6 text-[var(--muted-text)]">{item.content}</p>
                  </button>
                ))}
                {!outline.length ? <div className="text-sm text-[var(--muted-text)]">还没有课程大纲。</div> : null}
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 overflow-y-auto bg-[var(--app-bg)] lg:h-screen">
          <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-8 py-4 backdrop-blur-xl">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">AI 智能讲师</h1>
            <p className="mt-1 text-sm text-[var(--muted-text)]">
              {mode === "online" ? "在线模式：大纲解析、逐页讲稿、数字人播报与学生打断提问。" : "离线模式：整套课件异步生成 MP4 视频。"}
            </p>
          </header>

          <div className="mx-auto w-full max-w-5xl px-6 py-6 xl:px-8">
            <GlassPanel className="overflow-hidden bg-[#020617]">
              {mode === "online" ? (
                <iframe
                  title="AI 智能讲师实时课堂"
                  src={webrtcUrl}
                  className="aspect-video w-full border-0 bg-black"
                />
              ) : offlineVideoUrl ? (
                <video controls className="aspect-video w-full bg-black" src={offlineVideoUrl} />
              ) : (
                <div className="aspect-video bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.32),transparent_24%),radial-gradient(circle_at_75%_58%,rgba(14,165,233,0.22),transparent_30%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#1d4ed8_100%)]" />
              )}
            </GlassPanel>

            {mode === "online" ? (
              <>
                <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                  <GlassPanel className="border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-6">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="text-2xl font-black text-[var(--accent-strong)]">当前讲稿</h2>
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
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--muted-text)]">{activeSlide?.content || "请先创建课程大纲。"}</p>
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
                    <h2 className="text-2xl font-black text-[var(--accent-strong)]">学生打断提问</h2>
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
                        {busy === "ask" ? "回答中..." : "提交打断提问"}
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
              </>
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

            {error ? (
              <div className="mt-6 rounded-[22px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-600">
                {error}
              </div>
            ) : null}
          </div>
        </main>

        <aside className="flex flex-col border-l border-[var(--shell-border)] bg-[var(--surface-subtle)] lg:h-screen lg:overflow-auto">
          <div className="border-b border-[var(--shell-border)] bg-[var(--surface-elevated)]/95 p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--accent)] text-white">
                <MaterialIcon name="smart_toy" fill />
              </div>
              <div>
                <h4 className="font-bold text-[var(--accent-strong)]">讲师控制台</h4>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[#1b6d24]">实时联动</p>
              </div>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-6 overflow-hidden p-6">
            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">在线课堂概览</p>
              <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                <p>{onlineSummary}</p>
                <p>当前课程 ID：{courseId || "--"}</p>
                <p>当前播报句子：{currentSentence || "--"}</p>
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">讲义预览</p>
              <div className="mt-4 max-h-[320px] overflow-y-auto rounded-[18px] bg-[var(--surface-subtle)] p-4">
                <MarkdownPreview content={rawDocument} />
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-elevated)] p-5">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">快速跳转</p>
              <div className="mt-4 space-y-3">
                <a href={routeHref(routes.resources)} className="flex items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]">
                  <span className="text-sm font-semibold text-[var(--app-text)]">课程资源</span>
                  <MaterialIcon name="arrow_forward" className="text-[var(--accent)]" />
                </a>
                <a href={routeHref(routes.ai)} className="flex items-center justify-between rounded-[18px] bg-[var(--surface-subtle)] px-4 py-3 text-left transition hover:bg-[var(--accent-soft)]">
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
