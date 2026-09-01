# SPEC-11 旧模块下线

状态：已完成

日期：2026-07-25

对应验收：[ACC-11](../acceptance/ACC-11_旧模块下线_验收.md)

## 1. 目标

OpenMAIC 课堂链路完成互动播放、PPTX 和 MP4 导出后，仓库只保留这一条受支持的课件生产路径。旧课件服务、数字人服务及其桥接代码、入口、配置、依赖和 vendor 资产全部退出运行时。

## 2. 产品契约

1. 教师从“AI 课堂 / Classroom Studio”生成、编辑和播放课件。
2. 同一份 `Stage / Scene / Action / Slide` 数据导出 PPTX。
3. 同一份课堂与 `LessonTimeline` 导出 MP4、SRT 和时间轴。
4. 聊天不再识别普通 PPT/课件生成意图，也不再跳转到 AI 课堂。
5. 用户上传的 `.ppt`/`.pptx` 仍可作为知识资源或教学视频输入；普通 PPT 生成草稿和任务不再作为产品材料。
6. 数字人、WebRTC 讲师、旧教学视频会话不再是产品能力。

## 3. 后端约束

- FastAPI 不注册旧教学视频、讲师会话和旧直连 PPT 路由。
- 应用启动与关闭不管理旧外部进程。
- `app/` 运行时源码不引用已退休 vendor。
- 普通 PPT 生成工具、workflow、草稿存储和 HTML2PPT 客户端全部删除，不注册兼容入口。
- 旧 vendor 目录不再是 Git tracked content。

## 4. 前端约束

- 路由与导航不暴露旧 Video Player。
- 不保留旧 WebRTC hook、讲师 API 客户端或旧 PPT 生成面板。
- 课件入口统一指向 Classroom Studio。
- `VITE_API_BASE_URL` 是主应用唯一必需的前端服务地址。

## 5. 部署约束

- 安装脚本只安装主前端、主后端、OpenMAIC sidecar、PostgreSQL 客户端、Playwright Chromium 和 FFmpeg。
- 启动配置只管理主前端、FastAPI、OpenMAIC sidecar 与 PostgreSQL，不安装 EduAgent。
- 不需要 GPU、数字人模型权重或独立课件服务端口。
- FFmpeg/ffprobe 与 Chromium 继续服务于 OpenMAIC 课堂视频导出。

## 6. 删除边界

本阶段删除运行时代码、入口、配置、测试、vendor 源码以及专门描述已下线实现的文档。需要审计时通过 Git 历史读取，不在当前文档树保留重复副本。

## 7. 回退

所有删除均已形成独立 Git commit。若必须审计或恢复单个历史文件，应从对应 commit 读取，不得重新接入主运行时。
