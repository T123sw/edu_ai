# html2ppt 来源说明

本目录原为嵌套 git 仓库（gitlink），2026-06-30 扁平化并入主仓库以保证
跨机器一致性（原嵌套仓库无 `.gitmodules`，clone 主仓库时此目录会是空的）。

- 上游仓库：https://github.com/Sun-Jia-Jun/ppt-generation-service.git
- 扁平化时基于的 commit：`ce0ccfd1f6f5e4ae918f4ab540171b9937569cc7`
- 本地相对该 commit 有未提交改动（已随扁平化保留在工作区）

如需与上游同步，可在临时目录单独 clone 上游仓库做 diff/merge，再把变更
手动应用到此目录。`node_modules/` 等依赖不入库，换机器后在本目录及
`dom-to-pptx/` 子目录分别 `npm install`。
