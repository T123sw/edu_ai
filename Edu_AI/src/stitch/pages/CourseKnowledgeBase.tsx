import { useEffect, useMemo, useRef, useState } from "react";
import {
  getKnowledgeBaseDocuments,
  reindexKnowledgeBaseDocument,
  retryKnowledgeBaseDocument,
  uploadKnowledgeBaseDocument,
} from "../api/courses";
import type { KnowledgeBaseDocument } from "../api/types";
import { registerCreatedJob } from "../../jobs/jobStore";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  cx,
  defaultCourse,
  routes,
  useAppShell,
} from "../shared";

type KnowledgeCategory = "教材" | "讲义" | "PPT" | "习题" | "实验手册";

const CATEGORY_STORAGE_KEY = "stitch-course-kb-category-map";

const knowledgeCategories: Array<{
  key: KnowledgeCategory;
  icon: string;
  accent: string;
  iconBg: string;
  note: string;
}> = [
  { key: "教材", icon: "menu_book", accent: "text-blue-700", iconBg: "bg-blue-50", note: "课程主教材、参考书与章节阅读材料" },
  { key: "讲义", icon: "description", accent: "text-emerald-700", iconBg: "bg-emerald-50", note: "课堂讲义、教学提纲与板书整理" },
  { key: "PPT", icon: "slideshow", accent: "text-amber-700", iconBg: "bg-amber-50", note: "授课演示文稿与课堂展示材料" },
  { key: "习题", icon: "quiz", accent: "text-rose-700", iconBg: "bg-rose-50", note: "练习题、作业、测验与答案解析" },
  { key: "实验手册", icon: "science", accent: "text-violet-700", iconBg: "bg-violet-50", note: "实验指导、步骤说明与实验记录模板" },
];

const documentStatusMeta: Record<
  KnowledgeBaseDocument["status"],
  { label: string; className: string }
> = {
  received: { label: "已接收", className: "bg-slate-100 text-slate-600" },
  parsing: { label: "解析中", className: "bg-blue-50 text-blue-700" },
  chunking: { label: "切分中", className: "bg-blue-50 text-blue-700" },
  embedding: { label: "向量化", className: "bg-blue-50 text-blue-700" },
  indexing: { label: "建索引", className: "bg-blue-50 text-blue-700" },
  ready: { label: "可检索", className: "bg-emerald-50 text-emerald-700" },
  partially_ready: { label: "部分可用", className: "bg-amber-50 text-amber-700" },
  failed: { label: "处理失败", className: "bg-rose-50 text-rose-700" },
};

function inferCategory(document: KnowledgeBaseDocument): KnowledgeCategory {
  const name = document.name.toLowerCase();
  if (name.includes("ppt") || name.endsWith(".ppt") || name.endsWith(".pptx")) return "PPT";
  if (name.includes("实验") || name.includes("lab")) return "实验手册";
  if (name.includes("习题") || name.includes("练习") || name.includes("quiz") || name.includes("exercise")) return "习题";
  if (name.includes("讲义") || name.includes("note")) return "讲义";
  return "教材";
}

function loadCategoryMap() {
  if (typeof window === "undefined") return {} as Record<string, KnowledgeCategory>;
  try {
    const raw = window.localStorage.getItem(CATEGORY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, KnowledgeCategory>) : {};
  } catch {
    return {};
  }
}

function saveCategoryMap(map: Record<string, KnowledgeCategory>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CATEGORY_STORAGE_KEY, JSON.stringify(map));
}

export function CourseKnowledgeBasePage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [categoryMap, setCategoryMap] = useState<Record<string, KnowledgeCategory>>({});
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedUploadCategory, setSelectedUploadCategory] = useState<KnowledgeCategory>("教材");
  const [pendingFileNames, setPendingFileNames] = useState("");
  const [reloadNonce, setReloadNonce] = useState(0);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);

  useEffect(() => {
    setCategoryMap(loadCategoryMap());
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getKnowledgeBaseDocuments(course.id);
        if (!cancelled) {
          setDocuments(data);
          setCategoryMap((current) => {
            const next = { ...current };
            let changed = false;
            for (const item of data) {
              if (!next[item.id]) {
                next[item.id] = inferCategory(item);
                changed = true;
              }
            }
            if (changed) {
              saveCategoryMap(next);
              return next;
            }
            return current;
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "知识库加载失败");
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
  }, [course.id, reloadNonce]);

  useEffect(() => {
    const handleUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ courseId?: string }>).detail;
      if (detail?.courseId === course.id) {
        setReloadNonce((current) => current + 1);
      }
    };
    window.addEventListener("edu-ai:knowledge-document-updated", handleUpdated);
    return () => window.removeEventListener("edu-ai:knowledge-document-updated", handleUpdated);
  }, [course.id]);

  const groupedResources = useMemo(
    () =>
      knowledgeCategories.map((category) => ({
        ...category,
        items: documents.filter((item) => (categoryMap[item.id] || inferCategory(item)) === category.key),
      })),
    [categoryMap, documents],
  );

  const usedCategoryCount = groupedResources.filter((group) => group.items.length > 0).length;

  async function handleUploadFiles(fileList: FileList | null) {
    if (!fileList?.length) return;

    const files = Array.from(fileList);
    setUploading(true);
    setUploadError(null);

    try {
      const uploadedDocs: KnowledgeBaseDocument[] = [];
      const nextCategoryMap = { ...categoryMap };

      for (const file of files) {
        const result = await uploadKnowledgeBaseDocument(course.id, file);
        registerCreatedJob(result.job);
        uploadedDocs.push(result.document);
        nextCategoryMap[result.document.id] = selectedUploadCategory;
      }

      saveCategoryMap(nextCategoryMap);
      setCategoryMap(nextCategoryMap);
      setDocuments((current) => [...uploadedDocs, ...current]);
      setPendingFileNames("");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleDocumentAction(document: KnowledgeBaseDocument) {
    setBusyDocumentId(document.id);
    setUploadError(null);
    try {
      const job = document.status === "failed"
        ? await retryKnowledgeBaseDocument(course.id, document.id)
        : await reindexKnowledgeBaseDocument(course.id, document.id);
      registerCreatedJob(job);
      setReloadNonce((current) => current + 1);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "提交文档处理任务失败");
    } finally {
      setBusyDocumentId(null);
    }
  }

  return (
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-(--accent-strong)">{course.title}</h1>
          <p className="mt-1 text-sm text-(--muted-text)">课程知识库</p>
        </div>
        <SidebarNav activeRoute={routes.knowledge} />
      </SidebarDock>

      <main className="flex flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-(--shell-border) bg-(--app-bg)/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <h1 className="mt-2 text-3xl font-black tracking-tight text-(--accent-strong) sm:text-4xl">{course.title} 课程知识库</h1>
        
        </header>

        <div className="flex-1 p-6 sm:p-8">
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_360px]">
            <div className="space-y-6">
              {loading ? (
                <GlassPanel className="border border-(--shell-border) bg-white/90 p-6 text-sm text-(--muted-text)">
                  正在加载知识库文档...
                </GlassPanel>
              ) : error ? (
                <GlassPanel className="border border-(--shell-border) bg-white/90 p-6 text-sm text-rose-600">{error}</GlassPanel>
              ) : (
                groupedResources.map((group) => (
                  <GlassPanel key={group.key} className="border border-(--shell-border) bg-white/90 p-5 sm:p-6">
                    <div className="flex flex-col gap-4 border-b border-(--shell-border) pb-5 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-4">
                        <div className={cx("grid h-12 w-12 place-items-center rounded-2xl", group.iconBg, group.accent)}>
                          <MaterialIcon name={group.icon} className="text-[22px]" />
                        </div>
                        <div>
                          <h3 className="text-2xl font-black tracking-tight text-(--accent-strong)">{group.key}</h3>
                          <p className="text-sm text-(--muted-text)">{group.note}</p>
                        </div>
                      </div>
                      <div className="inline-flex w-fit items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-slate-600">
                        {group.items.length} 个文件
                      </div>
                    </div>

                    <div className="mt-4 space-y-3">
                      {group.items.length === 0 ? (
                        <div className="rounded-[24px] bg-slate-50 px-4 py-4 text-sm text-(--muted-text)">当前分类暂无文件。</div>
                      ) : (
                        group.items.map((item) => (
                          <div
                            key={item.id}
                            className="group flex flex-col gap-4 rounded-[24px] border border-transparent bg-slate-50 px-4 py-4 transition hover:border-(--accent-border) hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                          >
                            <div className="flex min-w-0 items-start gap-4">
                              <div className={cx("grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white", group.accent)}>
                                <MaterialIcon name={group.icon} className="text-[22px]" />
                              </div>
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <h4 className="text-base font-bold text-(--app-text)">{item.name}</h4>
                                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-(--muted-text)">
                                    {item.type === "web" ? "网页" : "文件"}
                                  </span>
                                  <span className={cx(
                                    "rounded-full px-2.5 py-1 text-[10px] font-bold",
                                    documentStatusMeta[item.status].className,
                                  )}>
                                    {documentStatusMeta[item.status].label}
                                  </span>
                                </div>
                                <div className="mt-3 flex flex-wrap gap-4 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                  <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                                  <span>{item.scope_type === "knowledge_point" ? "知识点资料" : "课程资料"}</span>
                                  {item.status === "ready" || item.status === "partially_ready"
                                    ? <span>{item.chunk_count} 个检索片段</span>
                                    : null}
                                </div>
                              </div>
                            </div>

                            <div className="flex shrink-0 gap-2">
                              {item.url ? (
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-full bg-(--accent) px-4 py-2.5 text-sm font-bold text-white"
                                >
                                  打开链接
                                </a>
                              ) : (
                                <button
                                  type="button"
                                  disabled={busyDocumentId === item.id || ["parsing", "chunking", "embedding", "indexing"].includes(item.status)}
                                  onClick={() => void handleDocumentAction(item)}
                                  className="rounded-full bg-(--accent) px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {busyDocumentId === item.id
                                    ? "提交中..."
                                    : item.status === "failed"
                                      ? "重试处理"
                                      : ["parsing", "chunking", "embedding", "indexing"].includes(item.status)
                                        ? "处理中"
                                        : "重建索引"}
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </GlassPanel>
                ))
              )}
            </div>

            <div className="space-y-6">
              <GlassPanel className="border border-(--shell-border) bg-[linear-gradient(180deg,#f8fbff_0%,#eef4ff_100%)] p-6">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-(--accent-strong)">上传文档</p>
                <div className="mt-4 space-y-4">
                  <div>
                    <p className="mb-3 text-sm font-semibold text-(--app-text)">选择上传类别</p>
                    <div className="grid gap-2">
                      {knowledgeCategories.map((category) => (
                        <button
                          key={category.key}
                          type="button"
                          onClick={() => setSelectedUploadCategory(category.key)}
                          className={cx(
                            "flex items-center justify-between rounded-[18px] border px-4 py-3 text-left transition",
                            selectedUploadCategory === category.key
                              ? "border-(--accent-border) bg-white text-(--accent-strong) shadow-xs"
                              : "border-(--shell-border) bg-white/60 text-(--muted-text)",
                          )}
                        >
                          <span className="flex items-center gap-3">
                            <MaterialIcon name={category.icon} className={cx("text-base", category.accent)} />
                            <span className="text-sm font-semibold">{category.key}</span>
                          </span>
                          {selectedUploadCategory === category.key ? <span className="text-xs font-bold text-(--accent)">已选中</span> : null}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-[22px] bg-white p-4 shadow-xs">
                    <p className="text-sm font-semibold text-(--app-text)">上传入口</p>
                    <p className="mt-2 text-sm leading-6 text-(--muted-text)">
                      当前上传类别：<span className="font-bold text-(--accent-strong)">{selectedUploadCategory}</span>
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(event) => {
                        const files = event.target.files;
                        setPendingFileNames(files && files.length > 0 ? Array.from(files).map((file) => file.name).join("、") : "");
                        void handleUploadFiles(files);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                      className="mt-4 w-full rounded-[18px] bg-(--accent) px-4 py-3 text-sm font-bold text-white disabled:opacity-50"
                    >
                      {uploading ? "上传中..." : "选择文件并上传"}
                    </button>
                    {pendingFileNames ? <p className="mt-3 text-xs text-(--muted-text)">最近选择：{pendingFileNames}</p> : null}
                    {uploadError ? <p className="mt-3 text-xs text-rose-600">{uploadError}</p> : null}
                  </div>
                </div>
              </GlassPanel>

              <GlassPanel className="border border-(--shell-border) bg-[linear-gradient(180deg,#f8fbff_0%,#eef4ff_100%)] p-6">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-(--accent-strong)">资源概览</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-[22px] bg-white p-4 shadow-xs">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-(--muted-text)">总文档数</p>
                    <p className="mt-2 text-3xl font-black text-(--accent-strong)">{documents.length}</p>
                  </div>
                  <div className="rounded-[22px] bg-white p-4 shadow-xs">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-(--muted-text)">已启用分类</p>
                    <p className="mt-2 text-xl font-black text-(--accent-strong)">{usedCategoryCount}</p>
                  </div>
                </div>
              </GlassPanel>
            </div>
          </section>
        </div>
      </main>
    </AppSurface>
  );
}
