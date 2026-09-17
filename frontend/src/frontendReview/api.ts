import { allResources, uid, type LearningResource } from "../selfLearning/model";
import { readReviewState, reviewEnabled, reviewOwner, reviewRole, writeReviewState } from "../selfLearning/review";
import { reportParagraphs } from "../selfLearning/Content";

type History = { conversation_id: string; title: string; course_id: string; scope_type: string; scope_id?: string; history: { role: string; content: string }[]; updated_at: string; message_count: number };
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const now = () => new Date().toISOString();
export function installReviewApi() {
  if (!reviewEnabled()) throw new Error("演示适配器只能在前端预览中启用");
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.href);
    const path = url.pathname.replace(/^\/backend(?=\/api\/)/, "");
    if (!path.startsWith("/api/")) return originalFetch(input, init);
    const method = init?.method || (input instanceof Request ? input.method : "GET");
    const state = readReviewState();
    const route = new URLSearchParams(location.hash.split("?")[1] || "");
    const room = state.rooms.find(r => r.id === route.get("course_id")) || state.rooms[0];
    if (!room) return json({ detail: "请先在首页选择课堂" }, 404);
    const username = reviewRole() === "teacher" ? "预览教师" : "探索者";
    const resources = [...state.resources.filter(r => !r.courseId || r.courseId === room.id), ...allResources(room)];
    const material = (r: LearningResource) => ({ material_id: r.id, material_type: "report", title: r.title,
      topic: r.topic, course_id: room.id, scope_type: r.chapterId ? "knowledge_point" : "course", scope_id: r.chapterId,
      version: r.version || 1, visibility: "private", owner_user_id: username, created_at: new Date(r.createdAt).toISOString(), updated_at: new Date(r.createdAt).toISOString(),
      content: r.content || `# ${r.title}\n\n${reportParagraphs(r).join("\n\n")}`, content_hash: `review-${r.id}`, status: "completed" });
    const historyKey = `edu-review-conversations:${reviewOwner().replace(/^review:/, "")}:${room.id}`;
    let conversations: History[];
    try { conversations = JSON.parse(localStorage.getItem(historyKey) || "[]"); } catch { conversations = []; }
    const body = typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : {};
    const graph = { id: room.id, label: room.title, children: room.chapters.map(c => ({ id: c.id, label: c.title, type: "knowledge_point", children: [] })) };
    const docs = [{ id: `review-doc-${room.id}`, name: `${room.title} · 学习资料.md`, type: "text", status: "ready", course_id: room.id, library_type: "course", scope_type: "course", owner_user_id: username, page_count: 4, chunk_count: 12, created_at: now(), updated_at: now() }];
    if (path === "/api/chat/v2/generation/tools") return json({ tools: ["report", "lesson_plan", "blog", "quiz", "flashcard", "mind_map", "game", "classroom"].map(tool_id => ({ tool_id, output_scope: "personal", allowed_source_scopes: ["none", "personal", "course"], can_publish: false })) });
    if (path === "/api/chat/v2/generation/preflight") return json({ valid: true, documents: docs, warnings: [], ready_document_count: 1 });
    if (path === "/api/chat/conversations") {
      const scoped = conversations.filter(c => !url.searchParams.get("scope_id") || c.scope_id === url.searchParams.get("scope_id"));
      return json({ conversations: scoped, count: scoped.length, total: scoped.length, total_messages: scoped.reduce((n, c) => n + c.message_count, 0) });
    }
    if (path.startsWith("/api/chat/conversations/")) {
      const conversation = conversations.find(c => c.conversation_id === path.split("/").at(-1));
      if (method === "DELETE") { localStorage.setItem(historyKey, JSON.stringify(conversations.filter(c => c !== conversation))); return json({ ok: true }); }
      return json(conversation || { detail: "未找到这段示例对话" }, conversation ? 200 : 404);
    }
    if (path === "/api/chat/v2/stream" || path === "/api/chat/v2/reply") {
      const question = String(body.question || "");
      const generation = String(body.action_hint || "").startsWith("generate.") || /生成.*报告|整理.*报告|重试生成/.test(question);
      const scopeId = String(body.scope_id || route.get("scopeId") || "");
      const topic = room.chapters.find(c => c.id === scopeId)?.title || room.title;
      const unsupported = !!body.action_hint && body.action_hint !== "generate.report";
      const failed = question.includes("模拟失败") || unsupported;
      const resource: LearningResource = { id: uid(), title: question.replace(/^(请)?(帮我)?(生成|整理)(一份)?/, "").trim().slice(0, 70) || `${topic}补充报告`, topic,
        kind: "report", ready: true, minutes: 6, createdAt: Date.now(), courseId: room.id, chapterId: scopeId || undefined, version: 1 };
      resource.content = `# ${resource.title}\n\n这是一份用于确认前端流程的示例报告。\n\n## 核心理解\n\n${reportParagraphs(resource).join("\n\n")}\n\n## 下一步\n\n选择一个小案例，用自己的话解释，并加入本节学习。`;
      let reply = generation ? `已准备好「${resource.title}」的示例内容。你可以在右侧查看，也可以进入资源中心，将它加入本节学习。`
        : `我们围绕「${topic}」来讨论。先明确它要解决的问题，再结合一个具体例子梳理理解。你也可以点击右侧“教学报告”，体验补充资料的完整创作流程。\n\n这是前端预览中的示例回复。`;
      if (failed) reply = "本次为生成失败状态演示，未产生资源。可以发送“重试生成报告”继续体验。";
      if (unsupported) reply = "此入口已保留配置交互。当前演示支持教学报告，可用它体验生成到学习的完整流程。";
      if (generation && !failed) {
        state.resources.unshift(resource);
        state.jobs.unshift({ id: uid(), title: resource.title, resource, status: "done", elapsed: 6000, duration: 6000 });
        writeReviewState(state);
      }
      const conversation = conversations.find(c => c.conversation_id === body.conversation_id) || {
        conversation_id: uid(), title: question.slice(0, 28), course_id: room.id,
        scope_type: scopeId ? "knowledge_point" : "course", scope_id: scopeId || undefined, history: [], updated_at: now(), message_count: 0,
      };
      conversation.history.push({ role: "user", content: question }, { role: "assistant", content: reply });
      conversation.message_count = conversation.history.length; conversation.updated_at = now();
      if (!conversations.includes(conversation)) conversations.unshift(conversation);
      localStorage.setItem(historyKey, JSON.stringify(conversations));
      const payload = { message: { role: "assistant", content: reply }, conversation: { conversation_id: conversation.conversation_id }, action: { name: failed ? "agent.failed" : "chat.reply" }, sources: [],
        artifacts: generation && !failed ? [{ artifact_id: resource.id, artifact_type: "report", title: resource.title, content: resource.content, version: 1 }] : [], trace: { path: "frontend_review" } };
      if (path.endsWith("/reply")) return json(payload);
      const encoder = new TextEncoder();
      return new Response(new ReadableStream({ async start(controller) {
        const send = (type: string, value: unknown) => controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type, payload: value })}\n\n`));
        send("metadata", { conversation_id: conversation.conversation_id });
        send("status", { label: generation ? "正在准备示例资源…" : "正在整理示例回复…" });
        await new Promise(resolve => setTimeout(resolve, 600));
        send("delta", { content: reply }); send("result", payload); controller.close();
        window.dispatchEvent(new CustomEvent("review-materials-changed", { detail: generation && !failed ? resource.id : null }));
        window.dispatchEvent(new Event("focus"));
      } }), { headers: { "Content-Type": "text/event-stream" } });
    }
    if (path.endsWith("/knowledge-graph")) return json({ course_id: room.id, root: graph, version: 1 });
    if (path.endsWith("/scope-options")) return json({ course: { id: room.id, title: room.title }, nodes: room.chapters.map(c => ({ id: c.id, label: c.title, title: c.title })) });
    if (path.endsWith("/documents") || path === "/api/rag/documents") {
      if (method === "GET") return json(path.includes("personal-knowledge") || path === "/api/rag/documents" ? [] : docs);
      return json({ detail: "本轮预览保留上传入口，文件解析将在后端联调时接入。" }, 422);
    }
    if (path.includes("/documents/") && path.endsWith("/content")) return json({ document: docs[0], content: `# ${room.title}\n\n${room.goal}`, content_type: "text/markdown" });
    if (path.endsWith("/materials")) return json(state.resources.filter(r => !r.courseId || r.courseId === room.id).filter(r => r.kind === "report").map(material));
    if (path.includes("/materials/")) {
      const resource = resources.find(r => path.includes(`/${r.id}`));
      return resource ? json(material(resource)) : json({ detail: "示例资源不存在" }, 404);
    }
    if (path.startsWith("/api/jobs")) return json([]);
    if (path === `/api/courses/${room.id}` || path === "/api/courses") {
      const course = { id: room.id, title: room.title, description: room.goal, icon: "BookOutlined", color: "#8c77c4", revision: 1, membership_role: "owner", created_by: username };
      return json(path === "/api/courses" ? [course] : course);
    }
    if (method !== "GET") return json({ detail: "此操作尚未接入前端演示，确认页面后再联调后端。" }, 422);
    return json({});
  };
  return () => { window.fetch = originalFetch; };
}
