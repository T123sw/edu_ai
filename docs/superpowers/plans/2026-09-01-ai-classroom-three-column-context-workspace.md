# AI 课堂三栏学习工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 将 AI 课堂升级为全宽三栏工作台，在左栏提供课程目录与当前用户个人课堂，在中栏直接学习视频、文档和习题，并在右栏围绕当前完整资源持续问答。

**Architecture:** 保留 ClassroomStudioPage 作为页面协调器，新增独立布局、个人课堂列表、可嵌入播放器和资源目标模型。互动课堂继续使用现有中断恢复链路并扩充为完整课堂上下文；文档与习题使用新的静态资源问答服务。两类问答共用同一面板契约，按用户、课程、资源、版本隔离会话。

**Tech Stack:** React 18、TypeScript、CSS Grid、Node test runner、FastAPI、Pydantic、pytest、现有 CourseStorageManager/PostgreSQL material repository、现有 ChatModelGateway 与课堂 TTS。

---

## 0. 实施前约束

- 工作目录：D:\Edu_AI_1。
- 前端目录：D:\Edu_AI_1\Edu_AI。
- 后端目录：D:\Edu_AI_1\backend。
- 设计依据：docs/superpowers/specs/2026-09-01-ai-classroom-three-column-context-workspace-design-cn.md。
- 不改变标准资源审核发布口径和学生学习进度口径。
- 不新增数据库表；静态资源问答会话沿用原子文件会话存储，使用包含资源类型与版本的隔离键。
- 每个任务完成后只提交该任务列出的文件，不夹带工作区其他修改。

## 1. 文件结构

### 前端新文件

- frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.tsx：三栏语义结构和响应式抽屉入口。
- frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts：布局结构和 CSS 合同测试。
- frontend/src/stitch/course/classroomCatalog/MyClassroomList.tsx：当前课程个人课堂列表。
- frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.ts：个人课堂过滤、排序和状态文案。
- frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.test.ts：个人课堂纯函数测试。
- frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.ts：课程资源与个人课堂的互斥选中目标及深链接解析。
- frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.test.ts：目标切换、版本和路由测试。
- frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx：可嵌入中栏的课堂播放体验。
- frontend/src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.tsx：右栏上下文标题和复用问答面板。
- frontend/src/stitch/classroomQa/classroomQaController.ts：课堂与静态资源共用的最小问答控制器契约。
- frontend/src/stitch/classroomQa/useStaticResourceQa.ts：文档和习题问答控制器。
- frontend/src/stitch/classroomQa/useStaticResourceQa.test.ts：会话隔离和迟到响应测试。
- frontend/src/stitch/api/resourceQa.ts：静态资源问答 API。
- frontend/src/stitch/api/resourceQa.test.ts：路径、请求和鉴权音频测试。

### 前端修改文件

- frontend/src/stitch/pages/ClassroomStudio.tsx：加载目录与个人课堂、维护当前目标、组合三栏。
- frontend/src/stitch/pages/ClassroomPlayer.tsx：改为薄页面包装，复用 ClassroomPlaybackSurface。
- frontend/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx：课堂改为中栏直接播放，并向右栏公开资源上下文。
- frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css：全宽三栏、栏内滚动和断点。
- frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx：面向通用控制器，播放中断操作改为可选。
- frontend/src/stitch/classroomQa/ClassroomQaPanel.css：右栏固定高度、上下文标题和小屏抽屉样式。
- frontend/src/stitch/api/types.ts：个人课堂目标和静态资源问答契约。
- frontend/src/stitch/pages/classroomCatalogPage.test.ts：三栏、个人课堂与内嵌播放器集成合同。

### 后端新文件

- backend/src/app/schemas/resource_qa.py：静态资源问答请求与响应。
- backend/src/app/services/resource_qa_prompt.py：完整文档/习题抽取、问题相关片段选择和提示词。
- backend/src/app/services/resource_qa_service.py：资源权限解析、版本锁定、会话和回答编排。
- backend/src/app/api/resource_qa.py：静态资源问答及音频路由。
- backend/src/tests/test_resource_qa_prompt.py：全文命中和答案隐藏测试。
- backend/src/tests/test_resource_qa_service.py：幂等、版本隔离、权限和失败恢复测试。
- backend/src/tests/test_resource_qa_routes.py：认证、课程角色、跨用户和音频访问测试。

### 后端修改文件

- backend/src/app/services/classroom_qa_prompt.py：课堂上下文加入全课堂可检索内容。
- backend/src/app/services/classroom_qa_service.py：指标加入资源版本，并保持旧接口兼容。
- backend/src/app/bootstrap.py：注册静态资源问答路由。
- backend/src/tests/test_classroom_qa_prompt.py：完整课堂后段内容命中测试。
- backend/src/tests/test_classroom_qa_service.py：原课堂问答回归。
- backend/src/tests/test_student_classroom_permissions.py：个人课堂列表与读取隔离回归。

---

### Task 1: 建立全宽三栏布局合同

**Files:**
- Create: frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.tsx
- Create: frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts
- Modify: frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css
- Modify: frontend/src/stitch/pages/ClassroomStudio.tsx

- [ ] **Step 1: 写布局失败测试**

创建 ClassroomWorkspaceLayout.test.ts：

~~~ts
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path: string) => readFile(new URL(path, import.meta.url), "utf8");

test("desktop classroom workspace is full-width and has three semantic rails", async () => {
  const [component, css] = await Promise.all([
    source("./ClassroomWorkspaceLayout.tsx"),
    source("./courseClassroomCatalog.css"),
  ]);
  assert.match(component, /course-classroom-workspace__directory/);
  assert.match(component, /course-classroom-workspace__viewer/);
  assert.match(component, /course-classroom-workspace__qa/);
  assert.match(component, /aria-label="课程与个人课堂导航"/);
  assert.match(component, /aria-label="当前学习内容"/);
  assert.match(component, /aria-label="当前内容问答"/);
  assert.match(css, /grid-template-columns:\s*clamp\(310px,\s*18vw,\s*360px\)\s+minmax\(520px,\s*1fr\)\s+clamp\(340px,\s*21vw,\s*420px\)/);
  assert.doesNotMatch(css, /course-classroom-catalog__layout[^}]*max-width:\s*1560px/s);
});
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: 在 Edu_AI 中执行 node --import tsx --test src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts

Expected: FAIL，提示 ClassroomWorkspaceLayout.tsx 不存在。

- [ ] **Step 3: 创建最小语义布局组件**

创建 ClassroomWorkspaceLayout.tsx：

~~~tsx
import type { ReactNode } from "react";

type Props = {
  directory: ReactNode;
  viewer: ReactNode;
  qa: ReactNode;
  directoryOpen: boolean;
  qaOpen: boolean;
  onCloseDirectory: () => void;
  onCloseQa: () => void;
};

export function ClassroomWorkspaceLayout(props: Props) {
  return (
    <div className="course-classroom-workspace">
      {(props.directoryOpen || props.qaOpen) ? (
        <button
          type="button"
          className="catalog-drawer-scrim"
          aria-label="关闭侧栏"
          onClick={props.directoryOpen ? props.onCloseDirectory : props.onCloseQa}
        />
      ) : null}
      <aside
        className={"course-classroom-workspace__directory" + (props.directoryOpen ? " is-open" : "")}
        aria-label="课程与个人课堂导航"
      >
        {props.directory}
      </aside>
      <section className="course-classroom-workspace__viewer" aria-label="当前学习内容">
        {props.viewer}
      </section>
      <aside
        className={"course-classroom-workspace__qa" + (props.qaOpen ? " is-open" : "")}
        aria-label="当前内容问答"
      >
        {props.qa}
      </aside>
    </div>
  );
}
~~~

修改 courseClassroomCatalog.css 的页面和主体规则：

~~~css
.course-classroom-catalog {
  min-height: calc(100vh - var(--course-header-height));
  padding: 20px clamp(16px, 1.25vw, 24px) 24px;
}
.course-classroom-catalog__toolbar {
  margin: 0 0 14px;
  max-width: none;
}
.course-classroom-workspace {
  display: grid;
  grid-template-columns: clamp(310px, 18vw, 360px) minmax(520px, 1fr) clamp(340px, 21vw, 420px);
  gap: 16px;
  width: 100%;
  height: calc(100vh - var(--course-header-height) - 112px);
  min-height: 570px;
}
.course-classroom-workspace > * {
  min-width: 0;
  min-height: 0;
}
~~~

在 ClassroomStudio.tsx 中用 ClassroomWorkspaceLayout 替换原 course-classroom-catalog__layout 双栏，先把现有目录传给 directory、现有内容传给 viewer，并给 qa 传入静态不可提问空状态。

- [ ] **Step 4: 运行布局测试和现有目录测试**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts src/stitch/pages/classroomCatalogPage.test.ts

Expected: PASS。

- [ ] **Step 5: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.tsx frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css frontend/src/stitch/pages/ClassroomStudio.tsx
git commit -m "feat: add full-width classroom workspace shell"
~~~

### Task 2: 增加“我的课堂”列表与互斥目标模型

**Files:**
- Create: frontend/src/stitch/course/classroomCatalog/MyClassroomList.tsx
- Create: frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.ts
- Create: frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.test.ts
- Create: frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.ts
- Create: frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.test.ts
- Modify: frontend/src/stitch/pages/ClassroomStudio.tsx
- Modify: frontend/src/stitch/api/types.ts

- [ ] **Step 1: 写个人课堂排序和路由失败测试**

~~~ts
import assert from "node:assert/strict";
import test from "node:test";
import { presentMyClassrooms } from "./myClassroomPresentation.ts";

test("my classroom keeps only playable personal classrooms and sorts newest first", () => {
  const result = presentMyClassrooms([
    { material_id: "old", material_type: "classroom", title: "旧课堂", updated_at: "2026-08-01", scenes: [] },
    { material_id: "new", material_type: "classroom", title: "新课堂", updated_at: "2026-09-01", scenes: [{ id: "s1", type: "slide" }] },
    { material_id: "report", material_type: "report", title: "报告", updated_at: "2026-09-02" },
  ]);
  assert.deepEqual(result.map((item) => item.id), ["new", "old"]);
  assert.equal(result[0].status, "ready");
  assert.equal(result[1].status, "empty");
});
~~~

在 classroomWorkspaceTarget.test.ts 验证 personal_classroom_id 与 node_id/resource_id 互斥，且构造后的 Hash 只保留当前目标参数。

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/course/classroomCatalog/myClassroomPresentation.test.ts src/stitch/course/classroomCatalog/classroomWorkspaceTarget.test.ts

Expected: FAIL，提示模块不存在。

- [ ] **Step 3: 实现纯函数和类型**

在 api/types.ts 的 ClassroomMaterial 中补充：

~~~ts
owner_user_id?: string | null;
visibility?: "private" | "course" | string;
video_status?: "queued" | "running" | "ready" | "failed" | string;
video_url?: string | null;
~~~

myClassroomPresentation.ts：

~~~ts
import type { ClassroomMaterial } from "../../api/types";

export type MyClassroomItem = {
  id: string;
  title: string;
  updatedAt: string;
  status: "ready" | "generating" | "failed" | "empty";
  material: ClassroomMaterial;
};

export function presentMyClassrooms(materials: ClassroomMaterial[]): MyClassroomItem[] {
  return materials
    .filter((item) => item.material_type === "classroom")
    .map((material) => ({
      id: material.material_id,
      title: material.title?.trim() || "未命名课堂",
      updatedAt: material.updated_at || material.created_at || "",
      status: material.video_status === "failed"
        ? "failed"
        : material.video_status === "queued" || material.video_status === "running"
          ? "generating"
          : (material.scenes?.length || material.video_url) ? "ready" : "empty",
      material,
    }))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}
~~~

classroomWorkspaceTarget.ts 定义：

~~~ts
export type ClassroomWorkspaceTarget =
  | { kind: "overview"; nodeId: string | null }
  | { kind: "catalog_resource"; nodeId: string; resourceId: string }
  | { kind: "personal_classroom"; classroomId: string };
~~~

readWorkspaceTarget 必须优先拒绝同时存在 personal_classroom_id 和 resource_id 的 URL，返回 { kind: "overview", nodeId: null }；buildWorkspaceHash 必须只写入当前联合类型需要的参数。

- [ ] **Step 4: 实现列表组件并接入页面**

MyClassroomList.tsx 使用 section、标题“我的课堂”、button 列表和文字状态。仅 status=ready 的项目允许 onSelect；生成中、失败和空课堂保持不可播放状态。

ClassroomStudio.tsx 在 courseId 变化时并行调用：

~~~ts
Promise.allSettled([
  getClassroomCatalog(courseId),
  listClassrooms(courseId, "mine"),
]);
~~~

目录数据失败沿用整页重试；个人课堂失败只在左栏底部显示“个人课堂暂时无法加载”和局部重试。左栏内部使用上方 flex:1 的目录滚动区和底部 MyClassroomList。

- [ ] **Step 5: 运行前端测试**

Run: node --import tsx --test src/stitch/course/classroomCatalog/myClassroomPresentation.test.ts src/stitch/course/classroomCatalog/classroomWorkspaceTarget.test.ts src/stitch/api/classroom.test.ts src/stitch/pages/classroomCatalogPage.test.ts

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/MyClassroomList.tsx frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.ts frontend/src/stitch/course/classroomCatalog/myClassroomPresentation.test.ts frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.ts frontend/src/stitch/course/classroomCatalog/classroomWorkspaceTarget.test.ts frontend/src/stitch/pages/ClassroomStudio.tsx frontend/src/stitch/api/types.ts frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css
git commit -m "feat: add current-course personal classrooms"
~~~

### Task 3: 将课堂播放器抽为可嵌入中栏的 Surface

**Files:**
- Create: frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx
- Create: frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts
- Modify: frontend/src/stitch/pages/ClassroomPlayer.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx

- [ ] **Step 1: 写播放器复用失败测试**

测试必须检查：

~~~ts
assert.match(surface, /export function ClassroomPlaybackSurface/);
assert.match(surface, /courseId:\s*string/);
assert.match(surface, /classroomId:\s*string/);
assert.match(surface, /resourceVersion\?:\s*number/);
assert.match(surface, /mode:\s*"manage"\s*\|\s*"learn"/);
assert.match(playerPage, /<ClassroomPlaybackSurface/);
assert.match(viewer, /<ClassroomPlaybackSurface/);
assert.doesNotMatch(viewer, /进入课堂学习|预览课堂/);
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts

Expected: FAIL，提示新组件不存在。

- [ ] **Step 3: 抽取播放 Surface**

从 ClassroomPlayer.tsx 移动“加载 material、场景、播放控制器、学习追踪、全屏、字幕和作答”状态到 ClassroomPlaybackSurface.tsx。公开接口固定为：

~~~ts
export type ClassroomPlaybackSurfaceProps = {
  courseId: string;
  classroomId: string;
  resourceVersion?: number;
  mode: "manage" | "learn";
  catalogNodeId?: string | null;
  catalogResourceId?: string | null;
  onQaControllerChange?: (binding: ClassroomQaBinding | null) => void;
};
~~~

新增 ClassroomQaBinding：

~~~ts
export type ClassroomQaBinding = {
  controller: ClassroomInterruptionController;
  canAsk: boolean;
  title: string;
  kind: "classroom" | "personal_classroom";
  version: number | null;
};
~~~

Surface 不渲染 AppSurface、课程顶部导航或自己的问答栏；它通过 onQaControllerChange 把播放器问答控制器交给工作台右栏。卸载或资源变化时先回调 null，再释放播放器、学习会话、音频 URL 和未完成问答。

- [ ] **Step 4: 同时接回独立播放器页与目录中栏**

ClassroomPlayerPage 只负责读取 Hash 参数和渲染 AppSurface + ClassroomPlaybackSurface。CourseResourceViewer 在 standard_kind=classroom 时直接渲染 Surface；教师审核面板仍放在 Surface 下方。个人课堂目标由 ClassroomStudioPage 直接渲染同一个 Surface，resourceVersion 留空，mode 取当前目录 mode。

- [ ] **Step 5: 运行播放器与目录回归**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts src/stitch/pages/classroomResourceLearning.test.ts src/stitch/classroomQa/ClassroomQaPanel.test.ts src/stitch/pages/classroomCatalogPage.test.ts

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.test.ts frontend/src/stitch/pages/ClassroomPlayer.tsx frontend/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx frontend/src/stitch/pages/ClassroomStudio.tsx
git commit -m "refactor: embed classroom playback in learning workspace"
~~~

### Task 4: 让现有课堂问答读取完整课堂并优先当前场景

**Files:**
- Modify: backend/src/app/services/classroom_qa_prompt.py
- Modify: backend/src/tests/test_classroom_qa_prompt.py
- Modify: backend/src/tests/test_classroom_qa_service.py

- [ ] **Step 1: 写后半课堂内容命中失败测试**

在 test_classroom_qa_prompt.py 增加包含三个场景的 material，checkpoint 停在第一个场景，问题询问第三个场景“哈希冲突”。断言 context.full_classroom_sections 包含第三场景，且 build_classroom_qa_messages 输出包含“哈希冲突”。

核心断言：

~~~py
context = build_classroom_qa_context(
    material=material,
    checkpoint=checkpoint,
    recent_turns=[],
)
assert any("哈希冲突" in section for section in context.full_classroom_sections)
messages = build_classroom_qa_messages(question="后面如何处理哈希冲突？", context=context)
assert "哈希冲突" in messages[-1]["content"]
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: 在 backend 中执行 python -m pytest src/tests/test_classroom_qa_prompt.py -q

Expected: FAIL，ClassroomQaContext 没有 full_classroom_sections。

- [ ] **Step 3: 扩展上下文**

在 ClassroomQaContext 增加：

~~~py
full_classroom_sections: tuple[str, ...]
~~~

按场景顺序抽取每个 scene 的 title、speech action text、content 中的字符串叶子值。保留当前 scene_speech、completed_speech 和 interrupted_speech 作为高优先锚点；从完整课堂段落中按问题词项命中分数选择最多 12 段，每段最多 1200 字符，提示词明确“当前场景优先，完整课堂可检索”。

选择函数签名固定为：

~~~py
def select_relevant_classroom_sections(
    question: str,
    sections: tuple[str, ...],
    *,
    limit: int = 12,
) -> tuple[str, ...]:
~~~

无词项命中时保留当前场景段落并从全课堂首尾各取有限段，不得只取开头。

- [ ] **Step 4: 运行课堂问答测试**

Run: python -m pytest src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_service.py src/tests/test_classroom_qa_routes.py -q

Expected: PASS，旧 checkpoint、中断恢复、幂等和音频权限测试继续通过。

- [ ] **Step 5: 提交**

~~~powershell
git add backend/src/app/services/classroom_qa_prompt.py backend/src/tests/test_classroom_qa_prompt.py backend/src/tests/test_classroom_qa_service.py
git commit -m "feat: ground classroom questions in full lesson content"
~~~

### Task 5: 定义静态资源问答契约和完整资源提示词

**Files:**
- Create: backend/src/app/schemas/resource_qa.py
- Create: backend/src/app/services/resource_qa_prompt.py
- Create: backend/src/tests/test_resource_qa_prompt.py

- [ ] **Step 1: 写全文档和习题答案保护失败测试**

测试构造一份 20 节文档，问题只在第 19 节命中；再构造含 answer、correct_answer、explanation 的习题。断言：

~~~py
document = build_resource_qa_context(
    resource_kind="study_guide",
    material=guide,
    question="第十九节的尾递归条件是什么？",
    anchor={"page_number": 1},
    include_answers=False,
)
assert any("尾递归条件" in item.text for item in document.selected_sections)

practice = build_resource_qa_context(
    resource_kind="practice",
    material=quiz,
    question="这套题考查哪些知识？",
    anchor=None,
    include_answers=False,
)
rendered = "\n".join(item.text for item in practice.selected_sections)
assert "correct_answer" not in rendered
assert "标准答案" not in rendered
assert "题目 3" in rendered
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: python -m pytest src/tests/test_resource_qa_prompt.py -q

Expected: FAIL，模块不存在。

- [ ] **Step 3: 创建 Pydantic 契约**

resource_qa.py 定义：

~~~py
class ResourceQaAnchor(BaseModel):
    scene_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    question_id: str | None = None

class ResourceQaTurnRequest(BaseModel):
    client_turn_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    resource_version: int = Field(ge=1)
    context_scope: Literal["full_resource"] = "full_resource"
    anchor: ResourceQaAnchor | None = None

class ResourceQaTurnResponse(BaseModel):
    turn_id: str
    client_turn_id: UUID
    question: str
    answer_text: str
    transition_text: str
    tts_status: Literal["ready", "failed"]
    audio_url: str | None = None
    created_at: str

class ResourceQaSessionResponse(BaseModel):
    session_id: str
    course_id: str
    resource_kind: Literal["study_guide", "practice"]
    resource_id: str
    resource_version: int
    owner_user_id: str
    status: Literal["ready"]
    turns: list[ResourceQaTurnResponse] = Field(default_factory=list)
~~~

question 使用与 ClassroomQaTurnRequest 相同的 trim validator。

- [ ] **Step 4: 实现资源抽取与问题相关选择**

resource_qa_prompt.py 定义 ResourceQaSection、ResourceQaContext、build_resource_qa_context、build_resource_qa_messages 和 parse_resource_qa_answer。

抽取规则必须明确：

- study_guide：递归读取 title、heading、content、markdown、text、sections、blocks 等字符串叶子；保留 JSON 路径作为 section label。
- practice：按题号组合题干、选项和关联材料；include_answers=False 时递归删除 answer、answers、correct_answer、correctAnswer、solution、explanation、解析、标准答案字段。
- 相关段落选择先保留 anchor 命中段，再按中文二元词和字母数字词项交集排序；最多 16 段，每段最多 1600 字符。
- 无命中时采用首段、末段和均匀采样段，证明整个资源都处于可选范围。
- 提示词要求只基于提供段落回答，并返回 JSON answer_text/transition_text；学生习题模式明确禁止猜测或泄露答案。

- [ ] **Step 5: 运行测试**

Run: python -m pytest src/tests/test_resource_qa_prompt.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add backend/src/app/schemas/resource_qa.py backend/src/app/services/resource_qa_prompt.py backend/src/tests/test_resource_qa_prompt.py
git commit -m "feat: define full-resource QA context contracts"
~~~

### Task 6: 实现静态资源问答服务、权限和版本隔离

**Files:**
- Create: backend/src/app/services/resource_qa_service.py
- Create: backend/src/tests/test_resource_qa_service.py
- Modify: backend/src/app/services/classroom_qa_store.py

- [ ] **Step 1: 写权限、版本和幂等失败测试**

test_resource_qa_service.py 使用假的 material repository、gateway 和 TTS，至少覆盖：

~~~py
result = await service.submit_turn(
    course_id="course-1",
    resource_kind="study_guide",
    resource_id="guide-1",
    resource_version=2,
    owner_user_id="student-a",
    course_role="viewer",
    request=request,
)
repeat = await service.submit_turn(**same_args)
assert result == repeat
assert gateway.calls == 1
assert repository.requested_version == 2
~~~

并验证 viewer 只能读取 approved_version，owner/editor 可读取 current_version，版本 1 与版本 2 的 session_id 不同，practice viewer 的 gateway messages 不含标准答案。

- [ ] **Step 2: 运行测试并确认失败**

Run: python -m pytest src/tests/test_resource_qa_service.py -q

Expected: FAIL，ResourceQaService 不存在。

- [ ] **Step 3: 为现有会话存储增加隔离键入口**

在 ClassroomQaSessionStore 增加不破坏旧方法的：

~~~py
def resource_session_id(
    *,
    resource_kind: str,
    resource_id: str,
    resource_version: int,
) -> str:
    digest = hashlib.sha256(
        f"{resource_kind}\0{resource_id}\0{resource_version}".encode("utf-8")
    ).hexdigest()[:24]
    return f"resource_{digest}"
~~~

ResourceQaService 将这个值作为现有 store 的 classroom_id 内部隔离键；对外响应只返回 resource_kind/resource_id/resource_version，不泄露内部键。这样继续复用原子写、busy claim、幂等 turn 和所有者隔离。

- [ ] **Step 4: 实现资源解析和回答编排**

ResourceQaService 固定 material type 映射：

~~~py
MATERIAL_TYPE_BY_RESOURCE_KIND = {
    "study_guide": "report",
    "practice": "quiz",
}
~~~

使用 get_postgres_material_repository().get 与 get_version：

1. 记录不存在、origin_type 不是 standard 或 standard_kind 不匹配时返回 404。
2. viewer 请求版本必须等于 approved_version；否则返回 404。
3. owner/editor 请求版本必须存在，默认由前端传 current_version。
4. include_answers 仅在 course_role 为 owner/editor 时为 True。
5. build_resource_qa_context 使用整份版本 payload 和当前问题选择片段。
6. 最近 6 轮只来自当前隔离 session。
7. 调用现有 ChatModelGateway、ClassroomQaTtsService 和课堂问答解析式 JSON 输出。
8. 异常码使用 RESOURCE_QA_NOT_FOUND、RESOURCE_QA_BUSY、RESOURCE_QA_ANSWER_FAILED。

- [ ] **Step 5: 运行服务与存储回归**

Run: python -m pytest src/tests/test_resource_qa_service.py src/tests/test_classroom_qa_store.py src/tests/test_classroom_qa_service.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add backend/src/app/services/resource_qa_service.py backend/src/app/services/classroom_qa_store.py backend/src/tests/test_resource_qa_service.py
git commit -m "feat: add version-isolated static resource QA service"
~~~

### Task 7: 暴露静态资源问答 API 与受保护音频

**Files:**
- Create: backend/src/app/api/resource_qa.py
- Create: backend/src/tests/test_resource_qa_routes.py
- Modify: backend/src/app/bootstrap.py

- [ ] **Step 1: 写路由失败测试**

路由固定为：

~~~text
GET  /api/courses/{course_id}/resources/{resource_kind}/{resource_id}/qa/session?resource_version=2
POST /api/courses/{course_id}/resources/{resource_kind}/{resource_id}/qa/turns
GET  /api/courses/{course_id}/resources/{resource_kind}/{resource_id}/qa/sessions/{session_id}/audio/{filename}?resource_version=2
~~~

测试认证、非课程成员 403、viewer 未发布版本 404、重复 client_turn_id 幂等、其他用户音频 404、路径穿越 404。

- [ ] **Step 2: 运行测试并确认失败**

Run: python -m pytest src/tests/test_resource_qa_routes.py -q

Expected: FAIL，resource_qa 路由不存在。

- [ ] **Step 3: 实现路由**

resource_qa.py 使用 require_course_read 获得 CoursePrincipal，将 principal.user_id 和 principal.course_role 传给服务。resource_kind 只接受 study_guide、practice。所有 ResourceQaError 转换为：

~~~py
HTTPException(
    status_code=exc.status_code,
    detail={
        "code": exc.code,
        "message": exc.public_message,
        "retryable": exc.retryable,
    },
)
~~~

音频读取必须先加载当前用户、当前资源版本的 session，再确认 filename 注册在完成 turn 中，随后执行 Path.resolve + relative_to 和 is_file 校验。

- [ ] **Step 4: 注册路由并运行测试**

在 bootstrap.py 的 lazy import 区加入 resource_qa_router，并在 classroom_qa_router 后 include_router。

Run: python -m pytest src/tests/test_resource_qa_routes.py src/tests/test_classroom_qa_routes.py src/tests/test_student_classroom_permissions.py -q

Expected: PASS。

- [ ] **Step 5: 提交**

~~~powershell
git add backend/src/app/api/resource_qa.py backend/src/app/bootstrap.py backend/src/tests/test_resource_qa_routes.py
git commit -m "feat: expose authorized static resource QA API"
~~~

### Task 8: 增加前端静态资源问答 API 与迟到响应隔离

**Files:**
- Create: frontend/src/stitch/api/resourceQa.ts
- Create: frontend/src/stitch/api/resourceQa.test.ts
- Create: frontend/src/stitch/classroomQa/classroomQaController.ts
- Create: frontend/src/stitch/classroomQa/useStaticResourceQa.ts
- Create: frontend/src/stitch/classroomQa/useStaticResourceQa.test.ts
- Modify: frontend/src/stitch/api/types.ts

- [ ] **Step 1: 写 API 路径和控制器失败测试**

resourceQa.test.ts 断言资源标识经过 encodeURIComponent，turn body 包含 resource_version、context_scope=full_resource 和 anchor。

useStaticResourceQa.test.ts 使用可控 Promise：

1. resource A 提交后切换到 resource B。
2. A 的 Promise 后完成。
3. B 的 state 不出现 A 的回答。
4. 切回 A 时通过 loadSession 恢复 A 历史。

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/api/resourceQa.test.ts src/stitch/classroomQa/useStaticResourceQa.test.ts

Expected: FAIL，模块不存在。

- [ ] **Step 3: 增加前端契约与 API**

在 api/types.ts 定义 ResourceQaKind、ResourceQaAnchor、ResourceQaTurnRequest、ResourceQaTurn、ResourceQaSession 和 ResourceQaTurnSubmission，字段与后端 Pydantic 完全一致。

resourceQa.ts 导出：

~~~ts
export function getResourceQaSession(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
  resourceVersion: number,
): Promise<ResourceQaSession>;

export function submitResourceQaTurn(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
  request: ResourceQaTurnRequest,
): Promise<ResourceQaTurnSubmission>;
~~~

音频继续通过 apiBlob 获取并转换 object URL，不允许直接把受保护 API 路径交给 Audio。

- [ ] **Step 4: 实现静态控制器**

StaticResourceQaCoordinator 复用 classroomQaState reducer，并持有 operationToken。在独立的 classroomQaController.ts 中定义公开契约：

~~~ts
export type ClassroomQaController = {
  readonly state: ClassroomQaState;
  readonly supportsPlaybackInterruption: boolean;
  submitQuestion(question: string): Promise<void>;
  stopAnswer(): void;
  retry(): Promise<void>;
  resetForNavigation(): void;
};
~~~

静态实现 supportsPlaybackInterruption=false；提交时不调用 playback.interrupt；停止时只取消音频、浏览器语音并递增 operationToken；所有异步结果写入前先同时校验 operationToken 和 resource key。

- [ ] **Step 5: 运行测试**

Run: node --import tsx --test src/stitch/api/resourceQa.test.ts src/stitch/classroomQa/useStaticResourceQa.test.ts src/stitch/classroomQa/classroomQaState.test.ts

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/api/resourceQa.ts frontend/src/stitch/api/resourceQa.test.ts frontend/src/stitch/classroomQa/classroomQaController.ts frontend/src/stitch/classroomQa/useStaticResourceQa.ts frontend/src/stitch/classroomQa/useStaticResourceQa.test.ts frontend/src/stitch/api/types.ts
git commit -m "feat: add static resource QA client controller"
~~~

### Task 9: 让一个问答面板同时服务课堂、文档和习题

**Files:**
- Create: frontend/src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.tsx
- Create: frontend/src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.test.ts
- Modify: frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx
- Modify: frontend/src/stitch/classroomQa/useClassroomInterruption.ts
- Modify: frontend/src/stitch/classroomQa/ClassroomQaPanel.css

- [ ] **Step 1: 写通用面板失败测试**

测试检查：

~~~ts
assert.match(contextPanel, /正在围绕/);
assert.match(contextPanel, /已读取完整文档|已读取完整习题|已读取完整课堂/);
assert.match(panel, /supportsPlaybackInterruption/);
assert.doesNotMatch(panel, /ClassroomInterruptionController/);
assert.match(panel, /停止回答并继续授课/);
assert.match(panel, /停止回答/);
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.test.ts src/stitch/classroomQa/ClassroomQaPanel.test.ts

Expected: FAIL，面板仍绑定旧控制器类型。

- [ ] **Step 3: 统一控制器接口**

让 ClassroomInterruptionController 满足 Task 8 的 ClassroomQaController：增加 supportsPlaybackInterruption=true，并将 stopAnswerAndResume 暴露为 stopAnswer。内部仍执行原暂停恢复逻辑，现有协调器测试保持通过。

ClassroomQaPanel 接收：

~~~ts
type Props = {
  controller: ClassroomQaController;
  canAsk: boolean;
  title?: string;
  eyebrow?: string;
};
~~~

忙碌时按钮文案由 supportsPlaybackInterruption 决定：课堂显示“停止回答并继续授课”，静态资源显示“停止回答”。错误态的放弃按钮同样区分，不给文档显示“继续授课”。

- [ ] **Step 4: 增加上下文外壳**

ContextualClassroomQaPanel 接收 binding：

~~~ts
export type WorkspaceQaBinding =
  | { status: "empty" }
  | { status: "loading"; title: string; kindLabel: string }
  | { status: "error"; title: string; message: string; onRetry: () => void }
  | { status: "ready"; title: string; kindLabel: string; scopeLabel: string; controller: ClassroomQaController; canAsk: boolean };
~~~

ready 时顶部显示“正在围绕《标题》问答 · scopeLabel”，再渲染 ClassroomQaPanel。empty、loading、error 都不能发送。

- [ ] **Step 5: 运行面板与中断测试**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.test.ts src/stitch/classroomQa/ClassroomQaPanel.test.ts src/stitch/classroomQa/useClassroomInterruption.test.ts

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.tsx frontend/src/stitch/course/classroomCatalog/ContextualClassroomQaPanel.test.ts frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx frontend/src/stitch/classroomQa/useClassroomInterruption.ts frontend/src/stitch/classroomQa/ClassroomQaPanel.css
git commit -m "refactor: reuse classroom QA panel across resource types"
~~~

### Task 10: 将右栏绑定到中间当前展示物

**Files:**
- Create: frontend/src/stitch/course/classroomCatalog/workspaceQaBinding.ts
- Create: frontend/src/stitch/course/classroomCatalog/workspaceQaBinding.test.ts
- Modify: frontend/src/stitch/pages/ClassroomStudio.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/StudentReadingView.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/StudentPracticeView.tsx

- [ ] **Step 1: 写绑定选择失败测试**

workspaceQaBinding.test.ts 覆盖：

- overview -> empty；
- standard classroom -> 等待 Surface 提供播放器控制器；
- study_guide -> static kind=study_guide、版本取当前角色可见版本、scopeLabel=已读取完整文档；
- practice -> static kind=practice、scopeLabel=已读取完整习题；
- personal classroom -> 播放器控制器、resourceVersion 为空；
- 资源版本变化 -> 新 binding key。

固定版本函数：

~~~ts
export function visibleResourceVersion(
  resource: ClassroomCatalogResource,
  mode: "manage" | "learn",
): number | null {
  return mode === "learn"
    ? resource.approved_version ?? null
    : resource.current_version ?? resource.approved_version ?? null;
}
~~~

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/course/classroomCatalog/workspaceQaBinding.test.ts

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现绑定纯函数和页面控制**

ClassroomStudioPage 维护 playbackQaBinding 和静态资源 anchor。CourseResourceViewer 增加 onContextChange：

~~~ts
type ResourceContext = {
  title: string;
  kind: "classroom" | "study_guide" | "practice";
  resourceId: string;
  resourceVersion: number;
  anchor?: ResourceQaAnchor;
};
~~~

StudentReadingView 使用 anchor=undefined，使整份文档保持同一会话；StudentPracticeView 增加 onQuestionFocus，在题目 fieldset 获得焦点时传 question_id。anchor 变化不改变会话 key；资源 ID 或版本变化时 useStaticResourceQa 创建新协调器并处置旧协调器。

- [ ] **Step 4: 渲染右栏并验证迟到响应**

ClassroomWorkspaceLayout 的 qa 固定渲染 ContextualClassroomQaPanel。目录或个人课堂切换时先同步更新目标和右栏 loading，再加载中栏；旧控制器 dispose 后才能注册新 binding。onQaControllerChange 回调必须同时携带当前 target key，页面只接受仍等于活动 target key 的回调。

- [ ] **Step 5: 运行集成测试**

Run: node --import tsx --test src/stitch/course/classroomCatalog/workspaceQaBinding.test.ts src/stitch/classroomQa/useStaticResourceQa.test.ts src/stitch/pages/classroomCatalogPage.test.ts

Expected: PASS。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/workspaceQaBinding.ts frontend/src/stitch/course/classroomCatalog/workspaceQaBinding.test.ts frontend/src/stitch/pages/ClassroomStudio.tsx frontend/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx frontend/src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx frontend/src/stitch/course/classroomCatalog/StudentReadingView.tsx frontend/src/stitch/course/classroomCatalog/StudentPracticeView.tsx
git commit -m "feat: bind workspace QA to the active learning resource"
~~~

### Task 11: 完成响应式抽屉、栏内滚动和可访问性

**Files:**
- Modify: frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.tsx
- Modify: frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts
- Modify: frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css
- Modify: frontend/src/stitch/pages/ClassroomStudio.tsx

- [ ] **Step 1: 写断点和焦点合同失败测试**

测试 CSS：

~~~ts
assert.match(css, /@media\s*\(max-width:\s*1279px\)/);
assert.match(css, /@media\s*\(max-width:\s*959px\)/);
assert.match(css, /overscroll-behavior:\s*contain/);
assert.match(css, /prefers-reduced-motion:\s*reduce/);
~~~

测试组件包含目录和问答触发按钮的 aria-expanded、aria-controls，抽屉关闭后调用触发按钮 focus。

- [ ] **Step 2: 运行测试并确认失败**

Run: node --import tsx --test src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts

Expected: FAIL，缺少 1279/959 双断点和问答抽屉焦点合同。

- [ ] **Step 3: 实现断点**

- 不低于 1280px：三栏。
- 960–1279px：grid-template-columns: minmax(520px,1fr) clamp(340px,32vw,400px)，左栏 fixed 抽屉。
- 低于 960px：主体单栏，中栏满宽；左栏和右栏分别 fixed 抽屉；同一时间只允许一个抽屉打开。
- 目录、查看器和问答 history 使用 overscroll-behavior: contain。
- 抽屉 scrim z-index 低于抽屉、高于中栏；问答输入不得被移动端安全区遮挡。

- [ ] **Step 4: 实现焦点恢复**

ClassroomWorkspaceLayout 接收 directoryTriggerRef 与 qaTriggerRef。关闭时 requestAnimationFrame 后 focus 对应按钮；Escape 关闭当前抽屉；打开抽屉后聚焦其标题或首个可交互项。桌面三栏时不执行焦点陷阱。

- [ ] **Step 5: 运行前端全套测试和构建**

Run: npm test

Expected: 全部 Node 测试 PASS。

Run: npm run build

Expected: TypeScript 与 Vite build 成功，无未使用类型和 JSX 错误。

- [ ] **Step 6: 提交**

~~~powershell
git add frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.tsx frontend/src/stitch/course/classroomCatalog/ClassroomWorkspaceLayout.test.ts frontend/src/stitch/course/classroomCatalog/courseClassroomCatalog.css frontend/src/stitch/pages/ClassroomStudio.tsx
git commit -m "feat: make classroom workspace responsive and accessible"
~~~

### Task 12: 全链路回归、真实视口验收与验收文档

**Files:**
- Create: docs/acceptance/2026-09-01-ai-classroom-three-column-context-workspace.md
- Modify: docs/superpowers/specs/2026-09-01-ai-classroom-three-column-context-workspace-design-cn.md

- [ ] **Step 1: 运行后端目标测试**

Run: 在 backend 中执行：

~~~powershell
python -m pytest src/tests/test_resource_qa_prompt.py src/tests/test_resource_qa_service.py src/tests/test_resource_qa_routes.py src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_service.py src/tests/test_classroom_qa_routes.py src/tests/test_student_classroom_permissions.py src/tests/classroom_catalog -q
~~~

Expected: PASS，0 failed。

- [ ] **Step 2: 运行前端目标测试和完整构建**

Run: 在 Edu_AI 中执行 npm test

Expected: PASS，0 failed。

Run: npm run build

Expected: build 成功。

- [ ] **Step 3: 进行真实浏览器视口验收**

在 1024×768、1280×800、1440×900、1920×1080 和不低于 2560px 宽度逐项验证：

1. 1920 和超宽屏左侧安全边距为 16–24px，不再出现 1560px 居中大留白。
2. 1280 及以上三栏同时可见，中栏获得新增宽度。
3. 1024 左目录为抽屉，中栏与问答仍可用。
4. 低于 960 时目录与问答不能同时打开。
5. 我的课堂只出现当前用户当前课程的个人课堂。
6. 课程课堂和个人课堂均在中栏播放。
7. 文档能回答后半段问题，右栏标明“已读取完整文档”。
8. 习题问答覆盖完整题目且学生未提交时不泄露答案。
9. A/B 资源快速切换后迟到回答不出现在错误资源。
10. 教师批准发布、退回修改和学生进度写入正常。

- [ ] **Step 4: 检查权限和错误隔离**

使用两个学生账号验证个人课堂互不可见；使用学生 URL 直接请求待审核版本应为 404；让静态问答接口返回 502 时中栏仍能预览和作答；让个人课堂列表请求失败时课程目录仍可使用。

- [ ] **Step 5: 写验收记录并更新设计状态**

验收文档记录每条命令、通过数量、视口截图路径、权限矩阵和已知非阻塞问题。只有所有完成定义通过后，将设计文档状态从“设计已确认，待实施”改为“已实现并通过自动化与真实视口验收”。

- [ ] **Step 6: 检查工作区并提交**

Run: git status --short

Expected: 只出现验收文档和设计状态更新。

~~~powershell
git add docs/acceptance/2026-09-01-ai-classroom-three-column-context-workspace.md docs/superpowers/specs/2026-09-01-ai-classroom-three-column-context-workspace-design-cn.md
git commit -m "docs: record three-column classroom acceptance"
~~~

---

## 最终完成条件

- 12 个任务的测试先失败、最小实现、通过验证和提交记录均可追溯。
- 前端 npm test 与 npm run build 通过。
- 后端目标 pytest 套件通过。
- 真实浏览器的 1024、1280、1440、1920 和超宽屏验收通过。
- 当前课程个人课堂按用户隔离。
- 视频、完整文档和完整习题问答均有权限安全的资源上下文。
- 资源与版本切换不会混入历史或迟到响应。
- 教师审核发布、学生进度、课堂中断恢复和音频鉴权无回归。
