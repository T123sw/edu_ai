# 知识产权、开源许可与协作｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在真实项目情境中审计第三方组件的许可证合规性。
2. 掌握编写 NOTICE 文件及版权头部的实操技能。
3. 模拟开源协作流程，包括 Fork、修改、提交 PR 及处理冲突。
4. 依据评价量规自查项目的知识产权风险。

## 真实问题情境
假设你所在的“数据可视化小组”正在开发一个名为 DataViz 的分析工具。项目即将发布 v1.0 版本，需整合以下第三方组件：
- 组件 A：核心图表库，许可证为 MIT。
- 组件 B：数据清洗模块，许可证为 Apache-2.0。
- 组件 C：加密算法实现，许可证为 GPL-3.0。
- 组件 D：UI 主题包，无明确许可证文件，仅 README 写着“免费使用”。

团队希望 DataViz 最终能作为商业软件的一部分交付给客户，但必须确保法律合规。

## 输入输出或材料
- **输入**：上述组件列表及许可证文本、项目源码结构。
- **输出**：合规性分析报告、项目根目录 LICENSE 文件、NOTICE 文件、模拟的 PR 提交记录。
- **材料**：开源许可证选择器（OSI 标准）、项目代码仓库访问权限。

## 分步任务
1. **许可证审计**：调查组件 A、B、C、D 的具体条款，判断是否与商业分发兼容。
2. **决策与替换**：若存在冲突，提出解决方案（如替换组件或更改项目许可证）。
3. **文档编写**：编写项目的 LICENSE 文件和第三方 attribution 文件。
4. **协作模拟**：假设组件 B 发现 Bug，模拟向其上游仓库提交修复补丁的流程。

## 参考实现/推导
### 任务 1 与 2 推导
- 组件 A (MIT) 与 B (Apache-2.0) 均允许商业闭源使用。
- 组件 C (GPL-3.0) 具有强传染性。若 DataViz 静态链接或合并了 C 的代码，则 DataViz 整体必须开源 GPL，这与“商业软件部分交付”冲突。
- 组件 D (无许可) 法律风险最高，默认不可用。
- **解决方案**：移除组件 C，替换为 BSD 许可的加密库；移除组件 D，改用开源主题或自行开发。最终项目许可证建议选择 Apache-2.0 以保护专利贡献。

### 任务 3 文档编写
项目根目录 `NOTICE` 文件内容示例：
```text
DataViz Project
Copyright 2023 DataViz Team

This product includes software developed by Component A (MIT License).
This product includes software developed by Component B (Apache-2.0).
See LICENSE file for full terms.
```

### 任务 4 协作模拟
1. Fork 组件 B 仓库。
2. 创建分支 `fix/memory-leak`。
3. 提交代码并签署 DCO (Developer Certificate of Origin)。
4. 提交 Pull Request，描述复现步骤与修复方案。

## 测试与边界情况
- **合规测试**：使用扫描工具（如 FOSSA 或 Scancode）扫描代码库，确认无 GPL 代码残留。
- **边界情况**：
    - 若仅通过命令行调用组件 C（进程间通信），是否受 GPL 感染？通常不受，但需确保无动态链接。
    - 若组件 D 作者后续追加许可证声明，如何处理？需保留历史版本证据，最好事先联系确认。
- **验证脚本**：
```python
import os

def check_license_header(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read(500)
        if "Copyright" not in content and "License" not in content:
            return False
    return True

# 测试当前目录下的 py 文件
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            if not check_license_header(path):
                print(f"Warning: {path} missing license header")
```

## 评价量规

| 维度 | 优秀 (5 分) | 合格 (3 分) | 需改进 (1 分) |
| :--- | :--- | :--- | :--- |
| **合规性** | 所有依赖许可证兼容，无 GPL 污染风险 | 存在潜在风险但有规避说明 | 直接使用无许可或冲突组件 |
| **文档完整性** | LICENSE、NOTICE、README 齐全且准确 | 仅有 LICENSE 文件 | 无任何知识产权声明 |
| **协作规范** | PR 描述清晰，签署 DCO，尊重上游规范 | 提交代码但描述简略 | 直接修改上游代码未沟通 |
| **风险意识** | 能识别无许可组件风险并主动替换 | 知道风险但暂时忽略 | 认为网上代码均可免费商用 |

## 拓展问题
1. **双重许可模式**：若希望 DataViz 既支持开源社区又支持商业客户，应如何设计许可策略？（提示：参考 MySQL 模式）
2. **专利条款**：Apache-2.0 包含明确的专利授权条款，而 MIT 没有。这在大型企业合作中意味着什么风险？
3. **AI 生成代码**：若部分代码由 Copilot 生成，其著作权归属如何？当前法律界有何争议？
4. **跨国协作**：团队成员分布在不同国家，著作权法适用哪个司法管辖区？如何在 LICENSE 中约定？
