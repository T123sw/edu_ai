# 2026-04-15 Lesson Plan Engine Outline-to-Content

## Goal

在现有 chat v2 `lesson_plan` workflow 已接通的前提下，补齐真正可运行的教案生成 engine，使链路具备：

1. 信息充分时生成结构化教案大纲并进入确认态
2. 用户确认后基于已确认大纲生成结构化正文
3. 通过 `RouteChatService -> LegacyChatRuntime -> ChatService.get_lesson_plan_engine()` 自动接线

## Scope

- 新增默认 lesson plan engine builder
- 新增 lesson plan outline/content prompt 组装与 JSON 解析
- 在 legacy runtime / chat service 暴露 `get_lesson_plan_engine`
- 补充 lesson plan engine 与路由接线测试

## Out Of Scope

- 大纲修改意见的结构化回传协议
- 新增独立 `/api/chat/v2/lesson-plan` 专用接口
- 前端 artifact 展示升级

## Test Strategy

1. engine 在 `strong_soft_confirm` 下返回 `lesson_plan_outline + awaiting_human`
2. engine 在 `generation_ready + lesson_plan_outline` 下返回 `lesson_plan_content + completed`
3. route service 在未显式注入 engine 时可经 legacy getter 取到 lesson plan engine
4. 现有 lesson plan runtime / route tests 不回退
