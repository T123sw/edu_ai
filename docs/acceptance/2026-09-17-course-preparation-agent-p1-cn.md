# 课程准备 Agent P1 验收记录

日期：2026-09-17。范围：契约与原子接收存储。状态：代码与本地验证完成；未在业务数据库执行迁移，未启用新课程创建 API，未接模型或前端。

依据：[主设计](../architecture/2026-09-17-course-preparation-agent-design-cn.md)、[具体设计](../architecture/2026-09-17-course-preparation-agent-technical-design-cn.md)、[分阶段计划](../superpowers/plans/2026-09-17-course-preparation-agent-implementation-cn.md)。

## 1. 本阶段交付

- `app/course_preparation/schemas.py`：四类请求、目标版本、来源默认策略、上传版本、来源会话和覆盖设置；拒绝未知字段及非法操作组合。
- `manifest.py`：稳定节点、教学目标、准确资源版本、正文哈希和检查定位；验证先修顺序、唯一性及核心目标覆盖。
- `contracts.py`：任务快照、事件信封、状态/阶段及必须显式注入的授权端口。
- `repository.py`：同事务创建 preparation、首次 attempt、accepted 事件；幂等重放、冲突、按 owner 查询、重新授权和游标事件读取。
- `app/database/models.py` 与 `alembic/versions/20260917_0022_course_preparation_intake.py`：三张表、用户外键、请求唯一键、attempt 及事件关联、状态约束。

沿用仓库集中定义 ORM 的模式，没有新增重复数据库 Base。生产授权适配器在 P2 接现有用户/成员/资源服务，P1 无默认放行授权，也没有对外注册创建接口。

## 2. 验证环境和结果

Python 3.12.14，Pydantic 2.12.5，SQLAlchemy 2.0.51，Alembic 1.19.1，psycopg 3.3.4。主要依赖版本与仓库锁文件一致。测试使用独立虚拟环境和本机临时 PostgreSQL 14 集群，端口 55439；每个 PostgreSQL 用例另建唯一 schema，结束后删除。

测试仅读取显式 `PREPARATION_TEST_DATABASE_URL`，不读取应用 `.env` 或 `DATABASE_URL`。SQLite 是契约测试补充，不是部署存储后端。项目目标数据库版本上的部署迁移仍需按后续发布流程验证。

从 `backend/src` 执行：

```bash
PREPARATION_TEST_DATABASE_URL='postgresql+psycopg://zxqs_ep@127.0.0.1:55439/postgres' \
  /tmp/edu-ai-preparation-py312/bin/python -m pytest \
  tests/course_preparation \
  tests/database/test_database_foundation.py \
  tests/resource_learning/test_database_schema.py -q
```

结果：**60 passed, 1 skipped，7.41 秒**。唯一跳过项是 SQLite 的并发竞争用例；对应 PostgreSQL 用例实际执行通过。临时环境路径用于记录本次命令，后续可使用相同依赖的项目 Python 环境。

另执行 `python -m alembic heads`，结果为唯一 head `20260917_0022`。新迁移在独立 schema 内完成 upgrade → 实际接收/查询 → downgrade，同时检查 ORM 字段、约束与迁移一致，以及 PostgreSQL 离线 DDL。未对完整业务数据集执行升级或回退。

## 3. 关键证据

| 场景 | 结果 |
| --- | --- |
| 客户端注入 owner、公共空间或自动执行模式 | schema 拒绝 |
| 新建指定旧资源、局部任务缺目标、修订缺基准、调整缺范围 | schema 拒绝 |
| 隐式/显式同一来源默认值 | 请求哈希一致 |
| 同用户同请求重复接收 | 返回同一任务，仅一条 attempt 和 accepted 事件 |
| 六线程均在初次查询时未找到任务，再竞争提交 | PostgreSQL 最终仅一份任务、attempt、事件 |
| 同请求 ID 不同需求 | 抛幂等冲突，原任务不改变 |
| 其他用户请求相同 request_id | 各自任务独立，无法查询对方任务或事件 |
| 接收后撤销引用访问 | 重放、读取状态和事件均重新授权并拒绝 |
| accepted 事件写入时注入异常 | preparation、attempt、事件全部回滚 |
| 用户外键失败 | 保留真实数据库错误，不吞成幂等重放 |
| 引擎连接池关闭后重新查询 | 任务从数据库恢复 |
| 非法等待用户状态、事件关联不存在 attempt | 数据库约束拒绝 |
| 核心目标无资源/检查、先修缺失/循环、检查版本不匹配 | manifest 结构校验拒绝 |
| 事件乱序插入后分页 | 按 sequence 正序返回并保留原会话关联 |
| 原数据库基础及学习资源 schema | 相关回归通过 |

测试先分别观察到请求模块、仓储模块缺失的失败，再实现并验证通过。成功不代表教学内容已被验证：P1 没有调用模型或真实解析/生成服务。

## 4. 下一阶段

P2 接真实授权、HTTP 接收/查询、执行租约、阶段检查点、取消与重试、子任务意图及预算账本。真实资源检查、manifest/overlay 原子提交和最终学习入口在 P5/P6；P1 不将任务接收视为课程准备完成。
