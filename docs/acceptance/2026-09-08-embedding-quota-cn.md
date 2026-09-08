# Embedding 额度错误与报告检索决策修复

截图 image copy 10.png 对应后台日志显示：报告已提交，但在 GenerationSourceResolver → retrieve_documents → embed_query 阶段收到 HTTP 403、local:insufficient_quota，正文尚未开始生成。该问题不能靠修改模型或补充确认用语解决。

修复：
- Embedding 边界将额度不足转换为 EMBEDDING_QUOTA_EXHAUSTED 和用户可读提示；不再将原始 HTTP 响应体显示给用户。
- 检索工具保留明确失败原因，后台任务保留稳定错误码；历史任务 API 对旧 Embedding 原始错误做展示脱敏，不改写历史数据。
- submit_report 默认 source_mode=planned_evidence，沿用模型已获取证据；不再因 allow_rag=true 自动执行后台检索。需要追加检索时由模型显式选择 course_auto / selected_documents，代码仍校验检索权限。
- Skill 要求模型区分检索失败与空结果；必须依据指定资料时不得擅自降级。模型判断可以使用已有证据或基础知识时再推进。

验证：隔离回归覆盖权限开关与检索决策分离、显式追加检索、禁用权限不可覆盖、额度错误透传、原始响应隐藏和后台稳定错误码。未重放截图中的失败任务，未修改 Embedding 凭据或配额。服务商额度仍需管理员恢复。
