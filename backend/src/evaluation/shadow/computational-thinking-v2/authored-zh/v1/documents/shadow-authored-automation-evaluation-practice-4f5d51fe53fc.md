# 自动化方案设计与评价｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在真实情境中应用自动化设计流程，完成从需求分析到代码实现的全过程。
2. 掌握针对数据批处理任务的输入输出规范设计与异常处理机制。
3. 能够使用评价量规对自动化脚本进行多维度测试与打分。
4. 具备拓展思维，能针对现有方案的局限性提出改进策略。

## 真实问题情境
某高校教务处每学期需处理数千条学生选课数据。目前人工操作存在以下痛点：
- 数据源格式不统一（有的含空格，有的日期格式错误）。
- 需剔除重复选课记录。
- 需将不合格记录单独归档以便人工核查。
- 人工处理耗时约 4 小时/次，且易疲劳出错。

请设计一个自动化脚本，完成数据清洗与分类任务。

## 输入输出与材料
- **输入文件**：`raw_data.csv`，包含字段 `StudentID`, `CourseID`, `Timestamp`。
- **输出文件 1**：`valid_data.csv`，清洗后的有效选课记录。
- **输出文件 2**：`error_log.txt`，记录格式错误或重复的行号及原因。
- **材料要求**：使用 Python 标准库（如 `csv`）或常用数据处理库。

## 分步任务
1.  **需求抽象**：定义什么是“有效数据”（如 ID 为 10 位数字，时间格式正确，无重复主键）。
2.  **流程设计**：绘制流程图，包含读取、校验、去重、写入四个环节。
3.  **代码实现**：编写脚本，确保包含异常捕获机制（Try-Except）。
4.  **自我测试**：使用构造的边界数据运行脚本，观察日志输出。

## 参考实现
```python
import csv

def process_selection(input_file, valid_file, error_file):
    seen_keys = set()
    with open(input_file, 'r', encoding='utf-8') as src, \
         open(valid_file, 'w', newline='', encoding='utf-8') as dst, \
         open(error_file, 'w', encoding='utf-8') as err:
        
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        
        for line_num, row in enumerate(reader, start=2):
            try:
                sid = row['StudentID'].strip()
                if not sid.isdigit() or len(sid) != 10:
                    raise ValueError("Invalid ID format")
                
                key = f"{sid}-{row['CourseID']}"
                if key in seen_keys:
                    raise ValueError("Duplicate record")
                
                seen_keys.add(key)
                writer.writerow(row)
            except Exception as e:
                err.write(f"Line {line_num}: {str(e)}\n")
```

## 测试与边界情况
为确保方案鲁棒性，必须测试以下边界情况：
1.  **空文件**：输入文件仅有表头，脚本不应崩溃，输出空结果。
2.  **特殊字符**：字段中包含逗号或引号，CSV 解析器需正确处理。
3.  **缺失字段**：某行缺少 `StudentID`，脚本应捕获 KeyError 并记录日志，而非中断。
4.  **大文件测试**：验证内存占用，若数据量过大，需考虑分块处理。

## 评价量规
使用下表对自动化方案进行评分（总分 100 分）：

| 维度 | 优秀 (90-100) | 良好 (70-89) | 合格 (60-69) | 不合格 (<60) |
| :--- | :--- | :--- | :--- | :--- |
| **正确性** | 所有用例通过，数据零丢失 | 主要用例通过，少量边界错误 | 基本功能实现，常有报错 | 无法运行或结果错误 |
| **鲁棒性** | 完善异常处理，日志清晰 | 有异常捕获，日志一般 | 仅处理部分异常 | 无异常处理，易崩溃 |
| **可维护性** | 代码模块化，变量命名规范 | 代码结构清晰 | 代码冗长，命名随意 | 逻辑混乱，难以阅读 |
| **效率** | 算法复杂度优，运行快速 | 满足基本性能要求 | 运行缓慢但可接受 | 性能无法接受 |

## 拓展问题
1.  若数据量从 1 万条增加到 1000 万条，当前脚本可能面临内存不足。请思考如何利用生成器或数据库流式处理优化？
2.  如果规则发生变化（如学号变为 12 位），如何修改代码以减少改动范围？（提示：配置文件中定义规则）。
3.  如何设计一个监控机制，当自动化脚本连续失败 3 次时自动发送通知给管理员？
