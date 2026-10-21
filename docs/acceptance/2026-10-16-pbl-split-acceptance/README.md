# PBL 代码生成与验收生成分离

已实现并验证；后端重启仍需管理员权限，尚未确认线上新流程生效。

每步先调用 build_step 生成 unit 和完整 referenceFiles，保存代码检查点，再调用 build_checks。第二次调用明确输入原始需求、计划、本步代码及哈希、前序代码与检查；输出只含本步教学说明、验收和可选负例，不能覆写给定参考代码。宿主组装后执行真实累计检查。失败时 repair_step → repair_checks，可保留正确代码，仅修复本步定位、动作与断言；前序检查与业务要求保留。

正常 N 步共 1+2N 次调用，不新增独立模型审阅。每轮修复另加两次。验收模型中断后可直接复用代码快照；版本、哈希、步骤归属、取消与租约检查仍保留。反馈优先保留失败项，避免成功日志挤掉关键错误。count/text/value 等运行语义已写入 JSON schema 字段说明，不新增项目专用规则。

应用内提示材料新增 build-pbl-project-v2 版本目录，新 Python 加载器使用此目录；旧目录内容已核对与失败任务记录的全部阶段哈希一致，避免旧进程动态读取新格式提示。

验证：全量 PBL 186 项通过、6 项跳过；最终流程、schema 与恢复专项 80 项通过。阅读清单真实模型隔离生成 4 步、最终 9 项浏览器累计检查通过，13 次调用、121.84 秒。正常阶段 9 次，末步重复按钮定位问题和一次 JSON 转义格式错误触发两轮修复；没有宣称模型首次输出全部正确。空白输入检查现在定位条目集合，计数为 0。原失败任务未重跑。

记录见 verification.json、real-model-verification.json、full-final.log 与 versioned.log。早期 full.log 在提示包目录迁移时中断，最终结果以 full-final.log 为准。原始私有模型输入输出留在 /tmp/edu-pbl-split-real/reading-list，公开 artifact 不含参考答案。

激活命令（需管理员执行）：

```sh
sudo systemctl restart edu-ai-backend
```

本次执行 `sudo -n systemctl restart edu-ai-backend` 返回需要密码，未通过其他方式替换服务。重启后再重试原任务；无需重建前端。
