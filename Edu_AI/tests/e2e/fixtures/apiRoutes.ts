import type { Page, Route } from "playwright/test";

export const physicsCourse = {
  id: "course-physics",
  title: "大学物理",
  description: "面向本科生的力学、电磁学与近代物理课程。",
  icon: "DatabaseOutlined",
  color: "#3157d5",
  objectives: ["理解核心物理概念", "能够分析典型问题"],
  knowledgeGraph: "力学与电磁学课程知识结构",
  revision: 4,
  membership_role: "editor",
  created_by: "teacher-a",
  created_at: "2026-08-01T08:00:00+08:00",
  updated_at: "2026-08-06T16:30:00+08:00",
};

const readyDocument = {
  id: "doc-mechanics",
  name: "大学物理·力学.pdf",
  type: "file",
  file_path: null,
  url: null,
  course_id: physicsCourse.id,
  scope_type: "course",
  scope_id: null,
  library_type: "course",
  owner_user_id: "teacher-a",
  created_at: "2026-08-02T09:00:00+08:00",
  updated_at: "2026-08-02T09:05:00+08:00",
  status: "ready",
  active_index_version: "idx-v1",
  pending_index_version: null,
  page_count: 42,
  chunk_count: 128,
  failed_units: 0,
  indexed_at: "2026-08-02T09:05:00+08:00",
  last_job_id: "job-index-mechanics",
  error_code: null,
  error_message: null,
};

const materials = [
  {
    material_id: "report-mechanics",
    material_type: "report",
    course_id: physicsCourse.id,
    title: "牛顿运动定律教学报告",
    summary: "包含概念、例题与课堂建议。",
    content: "# 牛顿运动定律\n\n稳定的浏览器验收内容。",
    created_by: "teacher-a",
    source_job_id: "job-report-mechanics",
    source_snapshot: { mode: "selected_documents" },
    visibility: "course",
    created_at: "2026-08-05T10:00:00+08:00",
    updated_at: "2026-08-05T10:03:00+08:00",
  },
  {
    material_id: "classroom-mechanics",
    material_type: "classroom",
    course_id: physicsCourse.id,
    title: "牛顿定律互动课堂",
    created_by: "teacher-a",
    source_job_id: "job-classroom-mechanics",
    visibility: "course",
    scenes_count: 1,
    stage: { id: "classroom-mechanics", name: "牛顿定律互动课堂" },
    scenes: [],
    created_at: "2026-08-05T11:00:00+08:00",
    updated_at: "2026-08-05T11:08:00+08:00",
  },
];

const jobs = {
  items: [],
  next_cursor: null,
  server_time: "2026-08-06T18:00:00+08:00",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body),
  });
}

export async function installTeacherApiRoutes(page: Page) {
  await page.route("https://images.unsplash.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/gif",
      body: Buffer.from(
        "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==",
        "base64",
      ),
    }),
  );

  await page.route("http://localhost:8001/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/api/auth/verify") {
      return json(route, {
        valid: true,
        user: { username: "teacher-a", role: "teacher" },
      });
    }
    if (path === "/api/auth/me") {
      return json(route, {
        username: "teacher-a",
        nickname: "唐老师",
        role: "teacher",
        course_count: 1,
      });
    }
    if (path === "/api/courses") {
      return json(route, [physicsCourse]);
    }
    if (path === `/api/courses/${physicsCourse.id}`) {
      return json(route, physicsCourse);
    }
    if (path.endsWith("/knowledge-base/documents")) {
      return json(route, [readyDocument]);
    }
    if (path.endsWith("/knowledge-graph")) {
      return json(route, {
        root: {
          id: "physics",
          label: "大学物理",
          data: { level: 0, summary: "课程知识结构" },
          children: [
            {
              id: "mechanics",
              label: "力学",
              data: { level: 1, summary: "运动与相互作用" },
              children: [],
            },
          ],
        },
      });
    }
    if (path.endsWith("/materials")) {
      const materialType = url.searchParams.get("material_type");
      return json(
        route,
        materialType
          ? materials.filter((item) => item.material_type === materialType)
          : materials,
      );
    }
    if (path.includes("/materials/")) {
      const material = materials.find((item) => path.includes(item.material_id));
      return json(route, material ?? { detail: "not found" }, material ? 200 : 404);
    }
    if (path.startsWith("/api/jobs")) {
      return json(route, jobs);
    }
    if (path === "/api/chat/v2/generation/preflight") {
      return json(route, {
        valid: true,
        source_mode: "none",
        ready_document_count: 0,
        documents: [],
        warnings: [],
      });
    }
    if (path === "/api/chat/v2/ppt/outline") {
      return json(route, { draft: { draft_id: "ppt-draft-fixture", status: "outline_ready" }, artifacts: [], trace: { path: "direct" } });
    }
    if (path === "/api/chat/v2/ppt/generate") {
      return json(route, { task_id: "job-generated-fixture", status: "pending" }, 202);
    }
    if (path.includes("/classrooms/generate") || (path.startsWith("/api/chat/v2/") && path.endsWith("/direct"))) {
      return json(route, { task_id: "job-generated-fixture", status: "pending" }, 202);
    }
    if (path === "/api/rag/documents") {
      return json(route, []);
    }
    if (path === "/api/runtime-config") {
      return json(route, { providers: [], updated_at: "2026-08-06T18:00:00+08:00" });
    }
    if (path.startsWith("/api/chat/")) {
      return json(route, {
        message: { role: "assistant", content: "固定问答响应" },
        conversation: { conversation_id: "conversation-fixture" },
        action: {},
        artifacts: [],
        trace: { path: "fast" },
      });
    }

    return json(route, {});
  });
}
