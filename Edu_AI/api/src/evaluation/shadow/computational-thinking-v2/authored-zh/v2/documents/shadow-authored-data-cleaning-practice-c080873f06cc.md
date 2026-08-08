# 数据质量、清洗与特征｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在真实业务场景中识别数据质量问题。
2. 独立完成从原始数据到可用特征集的全流程处理。
3. 能够设计测试用例验证清洗逻辑的边界稳定性。
4. 依据评价量规评估数据处理方案的有效性。

## 真实问题情境
某电商平台希望构建“用户购买力预测模型”。原始数据来源于日志系统，存在大量脏数据。业务部门反馈，模型预测结果波动大，怀疑是输入数据质量不稳定导致。你需要作为数据工程师，对原始交易数据进行标准化清洗，并构造关键特征，确保下游模型输入的稳定性。若数据质量不达标，可能导致促销预算浪费或用户流失。

## 输入输出与材料
**输入材料**：`transactions_raw.csv`，包含字段：`user_id` (用户 ID), `amount` (交易金额), `timestamp` (时间戳), `category` (类别)。
**预期输出**：`features_clean.csv`，包含字段：`user_id`, `avg_amount` (日均消费), `weekend_flag` (是否周末), `total_trans` (总交易数)。
**数据特点**：`amount` 存在负值（退款未标记）和极大值（测试数据）；`timestamp` 格式不统一；`category` 存在缺失。

## 分步任务
1. **数据加载与概览**：读取 CSV，打印前 5 行及各列数据类型，统计缺失值比例。
2. **异常值清洗**：针对 `amount` 字段，剔除负值及超过 99% 分位数的极端值。
3. **缺失值处理**：针对 `category` 字段，若缺失率高于 50% 则删除该列，否则填充为“未知”。
4. **特征构造**：基于 `timestamp` 生成 `weekend_flag`（周六日为 1，否则为 0）；基于 `user_id` 聚合生成 `avg_amount`。
5. **数据导出**：将处理后的数据保存为新文件。

## 参考实现
```python
import pandas as pd

def process_transactions(input_path, output_path):
    df = pd.read_csv(input_path)
    
    # 任务 1：概览
    print(f"缺失比例：{df.isnull().mean()}")
    
    # 任务 2：清洗 amount
    df = df[df['amount'] > 0]
    threshold = df['amount'].quantile(0.99)
    df = df[df['amount'] <= threshold]
    
    # 任务 3：处理 category
    if df['category'].isnull().mean() > 0.5:
        df.drop('category', axis=1, inplace=True)
    else:
        df['category'].fillna('未知', inplace=True)
        
    # 任务 4：构造特征
    df['date'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['weekend_flag'] = df['date'].dt.dayofweek.apply(lambda x: 1 if x >= 5 else 0)
    
    # 聚合特征
    feature_df = df.groupby('user_id').agg(
        avg_amount=('amount', 'mean'),
        total_trans=('amount', 'count'),
        weekend_flag=('weekend_flag', 'max') # 只要有一次周末即为 1
    ).reset_index()
    
    # 任务 5：导出
    feature_df.to_csv(output_path, index=False)
    return feature_df
```

## 测试与边界情况
为确保代码健壮性，需执行以下测试：
1. **空文件测试**：输入空 CSV，程序应报错提示或生成空输出，不应崩溃。
2. **全缺失测试**：若 `amount` 列全为缺失或负值，清洗后数据应为空，需检查后续聚合逻辑是否支持空 DataFrame。
3. **时间格式错误**：若 `timestamp` 包含无法解析的字符串，`errors='coerce'` 应将其转为 NaT，需验证后续 `.dt` 访问是否安全。
4. **单用户测试**：若数据仅包含一个用户，聚合逻辑应正常返回单行结果。

## 评价量规
| 维度 | 优秀 (5 分) | 合格 (3 分) | 不合格 (1 分) |
| :--- | :--- | :--- | :--- |
| **完整性** | 所有缺失值均有处理逻辑，无报错 | 主要字段无缺失，次要字段忽略 | 存在未处理的空值导致运行中断 |
| **准确性** | 异常值剔除符合业务逻辑（如负值） | 仅剔除极端值，未处理负值 | 未处理异常值，直接影响均值 |
| **特征有效性** | 构造的特征具有业务解释性 | 构造了特征但无实际意义 | 未构造新特征，仅原样输出 |
| **代码规范** | 函数封装良好，变量命名清晰 | 代码可运行但结构松散 | 代码无法运行或硬编码路径 |

## 拓展问题
1. **自动化 pipeline**：如果数据每天更新，如何设计定时任务自动执行此清洗脚本？请简述调度思路。
2. **动态阈值**：99% 分位数是固定阈值，若业务促销导致正常金额普遍升高，如何设计动态阈值以适应分布变化？
3. **隐私保护**：在输出 `user_id` 时，如何对其进行哈希处理以满足隐私合规要求，同时保证可关联性？
4. **分布漂移**：若清洗后的数据分布与上个月相比发生显著变化（KS 检验显著），应如何预警？
