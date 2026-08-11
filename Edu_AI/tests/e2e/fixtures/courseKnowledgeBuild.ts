import type { Page, Route } from "playwright/test";

import type { JobRecord } from "../../../src/jobs/types";
import type {
  CourseKnowledgeBuild,
  CourseKnowledgeBuildConfig,
  KnowledgeGraphNode,
} from "../../../src/stitch/api/types";

const COURSE_ID = "course-physics";
const NOW = "2026-08-12T09:00:00+08:00";

const defaultConfig: CourseKnowledgeBuildConfig = {
  preset: "standard",
  graph_depth: 3,
  target_module_count: 4,
  target_points_per_module: 4,
  target_materials_per_leaf: 3,
  minimum_web_materials_per_leaf: 1,
  maximum_ai_materials_per_leaf: 1,
  max_search_results_per_leaf: 8,
  ai_supplement_enabled: true,
  content_language: "中文",
  update_strategy: "merge_rebuild",
};

function graphDraft(withTextbook: boolean): KnowledgeGraphNode {
  const leaf = (id: string, label: string, ref?: string): KnowledgeGraphNode => ({
    id,
    label,
    children: [],
    data: {
      level: 3,
      summary: `${label}的概念、规律与典型应用`,
      source_outline_refs: ref ? [ref] : [],
    },
  });
  return {
    id: "physics-root",
    label: "大学物理",
    data: { level: 1, summary: "由模型生成并等待教师审核的课程知识结构" },
    children: [
      {
        id: "mechanics",
        label: "经典力学",
        data: { level: 2, summary: "研究物体运动及其变化原因" },
        children: [
          leaf("motion", "运动学基础", withTextbook ? "chapter-1" : undefined),
          leaf("newton", "牛顿运动定律", withTextbook ? "chapter-2" : undefined),
        ],
      },
      {
        id: "energy",
        label: "功与能",
        data: { level: 2, summary: "使用能量观点分析物理过程" },
        children: [
          leaf("work", "功和动能定理", withTextbook ? "chapter-3" : undefined),
          leaf("conservation", "机械能守恒", withTextbook ? "chapter-4" : undefined),
        ],
      },
    ],
  };
}

function job(id: string, buildId: string, kind: string, status: JobRecord["status"], step: string): JobRecord {
  const updatedAt = kind === "build_knowledge_index"
    ? "2026-08-12T09:00:03+08:00"
    : kind === "generate_graph"
      ? "2026-08-12T09:00:02+08:00"
      : "2026-08-12T09:00:01+08:00";
  return {
    schema_version: 1,
    version: status === "succeeded" ? 2 : 1,
    edu_job_id: id,
    kind,
    status,
    step,
    progress: status === "succeeded" ? 100 : 5,
    message: status === "succeeded" ? "处理完成" : "正在处理",
    owner_user_id: "teacher-a",
    course_id: COURSE_ID,
    scope_type: "course",
    scope_id: COURSE_ID,
    input_summary: { build_id: buildId, title: "大学物理课程知识库" },
    result_ref: status === "succeeded"
      ? { resource_type: kind === "build_knowledge_index" ? "course_knowledge_base" : "knowledge_graph_draft", course_id: COURSE_ID, build_id: buildId }
      : null,
    retryable: false,
    cancelable: status !== "succeeded",
    created_at: NOW,
    started_at: NOW,
    finished_at: status === "succeeded" ? NOW : null,
    updated_at: status === "succeeded" ? updatedAt : NOW,
  };
}

function qualityChecks() {
  return [
    "graph_schema",
    "graph_scale",
    "textbook_mapping",
    "web_minimum",
    "material_coverage",
    "ai_limit",
    "index_integrity",
    "publication_atomicity",
  ].map((check_type) => ({ check_type, status: "passed" as const, details: {} }));
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body),
  });
}

export type CourseKnowledgeBuildFixture = {
  events: string[];
  build: () => CourseKnowledgeBuild;
};

export async function installCourseKnowledgeBuildRoutes(page: Page): Promise<CourseKnowledgeBuildFixture> {
  await page.addInitScript(() => {
    Object.defineProperty(globalThis, "BroadcastChannel", {
      value: undefined,
      configurable: true,
    });
  });
  const fixtureId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const buildId = `kb-e2e-${fixtureId}`;
  const graphJobId = `job-graph-${fixtureId}`;
  const buildJobId = `job-build-${fixtureId}`;
  const events: string[] = [];
  const jobs: JobRecord[] = [];
  let completed = false;
  let build: CourseKnowledgeBuild = {
    build_id: buildId,
    library_id: COURSE_ID,
    course_id: COURSE_ID,
    status: "draft",
    phase: "draft",
    progress: 0,
    revision: 1,
    graph_confirmed_at: null,
    confirmed_graph_revision: null,
    confirmed_by: null,
    config: { ...defaultConfig },
    textbooks: [],
    course_snapshot: { title: "大学物理", description: "本科物理基础课程" },
    topics: [],
    graph_draft: null,
    source_candidates: [],
    warnings: [],
    quality_score: null,
    quality_checks: [],
  };

  function completeGraph() {
    events.push("graph:complete");
    build = {
      ...build,
      revision: build.revision + 1,
      graph_draft: graphDraft(Boolean(build.textbooks?.length)),
    };
  }

  function completeBuild() {
    events.push("web:discover-and-ingest");
    events.push("quality:evaluate");
    events.push("build:publish");
    completed = true;
    const root = build.graph_draft!;
    const leaves = root.children!.flatMap((module) => module.children || []);
    build = {
      ...build,
      status: "succeeded",
      phase: "completed",
      progress: 100,
      topics: leaves.map((node) => ({
        topic_id: node.id,
        title: node.label,
        query: `${node.label} 中文 教程`,
        english_query: `${node.label} tutorial`,
        objective: node.data?.summary || "掌握核心知识",
      })),
      source_candidates: leaves.map((node) => ({
        candidate_id: `web-${node.id}`,
        topic_id: node.id,
        title: `${node.label}公开课程资料`,
        url: `https://example.edu/${node.id}`,
        domain: "example.edu",
        source_type: "web",
        language: "zh-CN",
        license_name: null,
        license_url: null,
        authority_tier: "education",
        review_status: "ready",
        review_reason: "内容与知识点相关且可访问",
        selected: true,
        relevance_score: 0.92,
      })),
      metrics: { web_material_count: leaves.length, textbook_chunk_count: build.textbooks?.length ? 8 : 0, ai_material_count: leaves.length },
      quality_score: 100,
      quality_checks: qualityChecks(),
    };
  }

  await page.route("http://localhost:8001/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds` && method === "POST") {
      events.push("draft:create");
      return json(route, build);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}` && method === "GET") {
      events.push("draft:read");
      return json(route, build);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}` && method === "PATCH") {
      const body = request.postDataJSON() as { expected_revision: number; config: CourseKnowledgeBuildConfig };
      events.push("config:save");
      if (body.expected_revision !== build.revision) return json(route, { detail: "revision conflict" }, 409);
      build = { ...build, revision: build.revision + 1, config: body.config };
      return json(route, build);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}/textbooks` && method === "POST") {
      events.push("textbook:upload");
      const textbook = {
        textbook_id: "textbook-e2e",
        filename: "大学物理验收教材.md",
        extension: ".md" as const,
        size_bytes: 4096,
        content_hash: "sha256-e2e",
        status: "ready" as const,
        uploaded_by: "teacher-a",
        uploaded_at: NOW,
        parse_result: {
          parser: "markdown",
          summary: "已识别四个教材章节",
          outline: [1, 2, 3, 4].map((number) => ({ id: `chapter-${number}`, title: `第${number}章`, level: 1 })),
          char_count: 3200,
          chapter_count: 4,
          chunk_count: 8,
          warnings: [],
          parsed_at: NOW,
        },
        error: null,
      };
      build = { ...build, revision: build.revision + 1, textbooks: [textbook] };
      return json(route, { build, textbook, job: job(`job-textbook-${fixtureId}`, buildId, "parse_textbook", "succeeded", "completed") });
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}/graph/generate` && method === "POST") {
      events.push("graph:generate");
      completeGraph();
      const graphJob = job(graphJobId, buildId, "generate_graph", "succeeded", "completed");
      jobs.splice(0, jobs.length, graphJob);
      return json(route, graphJob, 202);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}/graph` && method === "PUT") {
      events.push("graph:save");
      const body = request.postDataJSON() as { expected_revision: number; root: KnowledgeGraphNode };
      if (body.expected_revision !== build.revision) return json(route, { detail: "revision conflict" }, 409);
      build = { ...build, revision: build.revision + 1, graph_draft: body.root };
      return json(route, build);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}/graph/confirm` && method === "POST") {
      events.push("graph:confirm");
      build = {
        ...build,
        revision: build.revision + 1,
        graph_confirmed_at: NOW,
        confirmed_graph_revision: build.revision + 1,
        confirmed_by: "teacher-a",
      };
      return json(route, build);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-builds/${buildId}/start` && method === "POST") {
      events.push("build:start");
      if (!build.graph_confirmed_at) return json(route, { detail: "graph confirmation required" }, 409);
      build = { ...build, status: "queued", phase: "queued", progress: 5 };
      completeBuild();
      const buildJob = job(buildJobId, buildId, "build_knowledge_index", "succeeded", "completed");
      jobs.unshift(buildJob);
      return json(route, buildJob, 202);
    }

    if (path === "/api/jobs" && method === "GET") {
      return json(route, { items: jobs, next_cursor: null, server_time: NOW });
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-base/versions` && method === "GET") {
      return json(route, completed ? [{ version: 5, source_build_id: buildId, created_at: NOW, published_at: NOW, node_count: 7 }] : []);
    }

    if (path === `/api/courses/${COURSE_ID}/knowledge-base/documents` && method === "GET" && completed) {
      const docs = [
        { id: "doc-web-newton", name: "牛顿运动定律公开课程资料.md", source_type: "web" },
        { id: "doc-ai-energy", name: "机械能守恒学习材料（AI 补充）.md", source_type: "model_generated" },
        ...(build.textbooks?.length ? [{ id: "doc-textbook", name: "大学物理验收教材.md", source_type: "textbook" }] : []),
      ].map((item) => ({
        ...item,
        type: "file",
        file_path: null,
        url: null,
        course_id: COURSE_ID,
        scope_type: "knowledge_point",
        scope_id: "newton",
        library_type: "course",
        owner_user_id: "teacher-a",
        created_at: NOW,
        updated_at: NOW,
        status: "ready",
        active_index_version: "idx-e2e",
        pending_index_version: null,
        page_count: 1,
        chunk_count: 4,
        failed_units: 0,
        indexed_at: NOW,
        last_job_id: buildJobId,
        error_code: null,
        error_message: null,
      }));
      return json(route, docs);
    }

    return route.fallback();
  });

  return { events, build: () => build };
}
