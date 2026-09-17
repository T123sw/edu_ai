# 真实修订测试失败

版本 b74b35ee 的模型未调用准备工具，却声称修订完成。API 轮次 status=succeeded 不能代表此用例通过：tool_attempts=0 且 preparation_receipts 为空，因此测试判定失败。

修复：服务端要求有保存/修订意图的轮次必须取得真实任务回执，缺少回执时一次定向工具重试，再失败则 PREPARATION_NOT_SUBMITTED，禁止保存伪成功回复。回归 4 passed / 18 deselected；完整真实修订须重新运行。
