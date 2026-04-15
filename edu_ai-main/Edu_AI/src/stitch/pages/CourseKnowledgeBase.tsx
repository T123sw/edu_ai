import { useEffect, useMemo, useState } from "react";
import { getKnowledgeBaseDocuments } from "../api/courses";
import type { KnowledgeBaseDocument } from "../api/types";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  defaultCourse,
  routes,
  useAppShell,
} from "../shared";

type DocGroupKey = "PDF" | "Markdown" | "文档" | "网页";

const categoryMeta: Record<DocGroupKey, { icon: string; accent: string; note: string }> = {
  PDF: { icon: "picture_as_pdf", accent: "text-rose-700", note: "适合归档与正式阅读" },
  Markdown: { icon: "description", accent: "text-slate-700", note: "适合结构化知识整理" },
  文档: { icon: "article", accent: "text-amber-700", note: "适合持续编辑与协作" },
  网页: { icon: "travel_explore", accent: "text-emerald-700", note: "外部链接与网络资料" },
};

function toGroup(document: KnowledgeBaseDocument): DocGroupKey {
  const name = document.name.toLowerCase();
  if (document.type === "web") return "网页";
  if (name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".md") || name.endsWith(".markdown")) return "Markdown";
  return "文档";
}

export function CourseKnowledgeBasePage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getKnowledgeBaseDocuments(course.id);
        if (!cancelled) {
          setDocuments(data);
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
  }, [course.id]);

  const groupedResources = useMemo(() => {
    const groups: Record<DocGroupKey, KnowledgeBaseDocument[]> = {
      PDF: [],
      Markdown: [],
      文档: [],
      网页: [],
    };
    for (const item of documents) {
      groups[toGroup(item)].push(item);
    }
    return (Object.keys(groups) as DocGroupKey[]).map((category) => ({
      category,
      items: groups[category],
      ...categoryMeta[category],
    }));
  }, [documents]);

  return (
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">{course.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">课程知识库</p>
        </div>
        <SidebarNav activeRoute={routes.knowledge} />
        <div className="rounded-[24px] bg-[var(--accent-soft)] p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">知识库状态</p>
          <div className="mt-3 space-y-2">
            <div className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[var(--accent-strong)]">文档数：{documents.length}</div>
            <div className="rounded-2xl border border-[var(--shell-border)] px-4 py-3 text-sm text-[var(--muted-text)]">来源：/knowledge-base/documents</div>
          </div>
        </div>
      </SidebarDock>

      <main className="flex flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">{course.module}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-strong)] sm:text-4xl">{course.title} 知识资源库</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
            这里只展示用户上传到课程知识库的文档，不包含工作台即时生成结果。
          </p>
        </header>

        <div className="flex-1 p-6 sm:p-8">
          {loading ? (
            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-[var(--muted-text)]">正在加载知识库文档...</GlassPanel>
          ) : error ? (
            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-rose-600">{error}</GlassPanel>
          ) : (
            <section className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_340px]">
              <div className="space-y-6">
                {groupedResources.map((group) => (
                  <GlassPanel key={group.category} className="border border-[var(--shell-border)] bg-white/90 p-5 sm:p-6">
                    <div className="flex flex-col gap-4 border-b border-[var(--shell-border)] pb-5 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`grid h-12 w-12 place-items-center rounded-2xl bg-slate-50 ${group.accent}`}>
                          <MaterialIcon name={group.icon} className="text-[22px]" />
                        </div>
                        <div>
                          <h3 className="text-2xl font-black tracking-tight text-[var(--accent-strong)]">{group.category}</h3>
                          <p className="text-sm text-[var(--muted-text)]">{group.note}</p>
                        </div>
                      </div>
                      <div className="inline-flex w-fit items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-slate-600">
                        {group.items.length} 个文件
                      </div>
                    </div>

                    <div className="mt-4 space-y-3">
                      {group.items.length === 0 ? (
                        <div className="rounded-[24px] bg-slate-50 px-4 py-4 text-sm text-[var(--muted-text)]">当前分类没有文件。</div>
                      ) : (
                        group.items.map((item) => (
                          <div
                            key={item.id}
                            className="group flex flex-col gap-4 rounded-[24px] border border-transparent bg-slate-50 px-4 py-4 transition hover:border-[var(--accent-border)] hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                          >
                            <div className="flex min-w-0 items-start gap-4">
                              <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white ${group.accent}`}>
                                <MaterialIcon name={group.icon} className="text-[22px]" />
                              </div>
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <h4 className="text-base font-bold text-[var(--app-text)]">{item.name}</h4>
                                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">
                                    {item.type}
                                  </span>
                                </div>
                                <div className="mt-3 flex flex-wrap gap-4 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                  <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                                  <span>{item.course_id}</span>
                                </div>
                              </div>
                            </div>

                            <div className="flex shrink-0 gap-2">
                              <button className="rounded-full bg-[var(--accent)] px-4 py-2.5 text-sm font-bold text-white">
                                {item.url ? "打开链接" : "查看记录"}
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </GlassPanel>
                ))}
              </div>

              <div className="space-y-6">
                <GlassPanel className="border border-[var(--shell-border)] bg-[linear-gradient(180deg,#f8fbff_0%,#eef4ff_100%)] p-6">
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">资源概览</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div className="rounded-[22px] bg-white p-4 shadow-sm">
                      <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">总文档数</p>
                      <p className="mt-2 text-3xl font-black text-[var(--accent-strong)]">{documents.length}</p>
                    </div>
                    <div className="rounded-[22px] bg-white p-4 shadow-sm">
                      <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">分类数</p>
                      <p className="mt-2 text-xl font-black text-[var(--accent-strong)]">
                        {groupedResources.filter((item) => item.items.length > 0).length}
                      </p>
                    </div>
                  </div>
                </GlassPanel>
              </div>
            </section>
          )}
        </div>
      </main>
    </AppSurface>
  );
}
