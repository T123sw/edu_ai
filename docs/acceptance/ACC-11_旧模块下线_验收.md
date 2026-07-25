# ACC-11 旧模块下线验收

状态：通过

日期：2026-07-25

对应规格：[SPEC-11](../spec/SPEC-11_旧模块下线.md)

## 1. 验收结论

Phase 6 已完成。AI 课堂成为唯一受支持的课件生成、播放、PPTX 和 MP4 导出路径；旧课件服务、数字人服务及桥接运行时已删除，安装和启动流程不再依赖它们。

## 2. 验收项

| 编号 | 标准 | 结果 |
| --- | --- | --- |
| AC-11-1 | 后端不注册旧教学视频、讲师会话和直连 PPT 路由 | 通过 |
| AC-11-2 | 前端无旧播放器路由、WebRTC hook 和旧 PPT 生成面板 | 通过 |
| AC-11-3 | 活跃运行时源码无退休 vendor 引用 | 通过 |
| AC-11-4 | 两棵退休 vendor 目录无 tracked 文件 | 通过 |
| AC-11-5 | 安装、启动、env 模板无旧服务、端口和 GPU 依赖 | 通过 |
| AC-11-6 | 聊天 PPT 意图安全跳转到 Classroom Studio | 通过 |
| AC-11-7 | 前端测试、lint、构建和课堂渲染冒烟通过 | 通过 |
| AC-11-8 | 迁移专项后端测试通过 | 通过 |

## 3. 自动化证据

迁移专项：

```text
42 passed  # PPT 退役、路由、schema 与内容协议聚焦测试
11 passed  # 最终 legacy route/handoff/startup 聚焦测试
5 passed   # 启动、安装、env 防回归测试
```

前端：

```text
60 tests passed
eslint: 0 errors, 78 existing warnings
vite production build: passed, 5482 modules transformed
```

完整后端应用/聊天套件：

```text
725 passed, 18 failed, 2 warnings
```

18 个失败均位于报告生成/持久化、会话增强、旧 RouteChat fallback 等本阶段未修改的既有区域。以 Phase 6 开始前的 `08f0db3` 做隔离审计时，完整套件已有 `780 passed, 24 failed`；当前 18 项中的 17 项直接出现在该失败清单中，另一项 stream persistence 也能在该基线单独复现。Phase 6 引起的过期旧服务测试已删除或改为 handoff 断言，迁移专项测试全绿。这些既有失败另行治理，不阻断旧模块物理下线。

## 4. 静态与浏览器证据

- `app/` 与前端活跃源码中退休 vendor 运行时引用：0。
- 两棵退休 vendor 目录剩余文件：0。
- 部署脚本与 env 模板退休服务标记：0。
- 无头视频渲染 fixture 成功显示“第二幕：可重复录制 / OpenMAIC 课件视频导出验收”。

## 5. 签收

结论：通过。Phase 0–6 迁移主线全部完成。可选视频 B（确定性逐帧渲染）仍是独立远期能力，不属于本轮迁移 blocker。
