# Patch 002 · `@openmaic/renderer` 的 `@openmaic/dsl` 依赖协议改为 `file:`

> 对应 [SPEC-01 §2](../SPEC-01_Sidecar裁剪与部署.md#2-引入方式演进两步)（补丁需落 fork 并记录）、[SPEC-08](../SPEC-08_前端集成_DSL与Renderer播放.md)（Phase 3 前端引包）。
> 作用：让 `packages/@openmaic/renderer` 能被**纯 npm 项目**（edu_ai 前端，非 pnpm workspace）
> 通过 `file:` 依赖直接安装，不需要把 edu_ai 前端也并进 sidecar 的 pnpm workspace。

## 问题

`packages/@openmaic/renderer/package.json` 里：

```json
"dependencies": {
  "@openmaic/dsl": "workspace:*",
  ...
}
```

`workspace:*` 是 pnpm/yarn 的 workspace 协议，只有在**同一个 pnpm/yarn workspace**
内才能解析。edu_ai 前端（`Edu_AI/`）是独立的 npm 项目（`package-lock.json`），把
renderer 通过 `file:../openmaic-sidecar/packages/@openmaic/renderer` 装进来时，
npm 会尝试安装 renderer 自己 `package.json` 里声明的依赖——遇到 `workspace:*`
这种 npm 不认识的协议会直接报错，导致 `npm install` 失败。

两个可选方案：① 把 edu_ai 前端也拉进 sidecar 的 pnpm workspace（会把一个独立
app 的构建跟 vendor 进来的 OpenMAIC 单体仓耦合在一起，日后拉上游更新时容易
产生无关冲突）；② 只改这一行协议（本补丁）。选②，改动最小。

## 补丁

```diff
   "dependencies": {
-    "@openmaic/dsl": "workspace:*",
+    "@openmaic/dsl": "file:../dsl",
     "clsx": "^2.1.1",
```

`file:../dsl` 是相对 `packages/@openmaic/renderer/` 的路径，指向同级的
`packages/@openmaic/dsl/`——两者本来就是 vendor 进来的兄弟目录，路径关系不变，
`file:` 协议是 npm/pnpm/yarn 都支持的通用写法，pnpm workspace 内该依赖仍然按
`file:` 解析到同一份物理目录，行为等价，不影响 sidecar 自身（Next.js 应用/
`generate-classroom` 等）的运行。

## 涉及文件

- `openmaic-sidecar/packages/@openmaic/renderer/package.json`

## 验证

- edu_ai 前端 `npm install` 能正常装下 `@openmaic/renderer`（file: 依赖），不再
  报 `workspace:` 协议解析错误。
- sidecar 自身在 `openmaic-sidecar/` 目录下用 pnpm 跑（`pnpm dev`/`pnpm build`）
  行为不变——pnpm 对 `file:` 依赖的解析同样落到同一份物理目录，等价于原来的
  `workspace:*`。
