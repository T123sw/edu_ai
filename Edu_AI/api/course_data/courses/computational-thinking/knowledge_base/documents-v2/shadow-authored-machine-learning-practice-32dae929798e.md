# 机器学习的基本流程｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
本案例旨在通过动手实践，让学生亲历机器学习的基本流程。学习完成后，学生应能：
1. 使用 Python 工具链完成数据划分、模型训练与验证。
2. 针对回归与分类不同场景，选择合适的评估指标。
3. 识别并处理流程中的边界情况，如数据缺失或异常值。

## 真实问题情境
某二手交易平台希望自动化评估手机回收价格，以减少人工估价成本。同时，平台需要识别恶意上传虚假信息的用户。这分别对应了**回归问题**（估价）和**分类问题**（风控）。本实践聚焦于核心的估价流程，但要求学生在拓展环节思考分类场景。

## 输入输出与材料
- **输入材料**：模拟数据集 `phones.csv`（包含字段：品牌编码、使用月数、内存 GB、成色评分、回收价）。
- **工具环境**：Python 3.8+, pandas, scikit-learn, numpy。
- **预期输出**：一个训练好的模型文件，以及包含评估指标的控制台报告。

## 分步任务
1. **数据加载与探索**：读取数据，检查是否存在空值或异常负数。
2. **特征工程与划分**：选取特征列与目标列，按 7:2:1 比例划分训练集、验证集、测试集。
3. **模型训练**：使用线性回归或决策树回归模型在训练集上拟合。
4. **流程验证**：在验证集上计算均方误差（MSE），若误差高于阈值，尝试调整模型参数。
5. **最终测试**：在测试集上报告最终性能，并保存模型。

## 参考实现与推导
以下代码实现了上述流程的核心逻辑，可直接运行：

```python
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import joblib

# 1. 模拟数据生成 (实际场景中应为 pd.read_csv)
np.random.seed(42)
data_size = 200
months = np.random.randint(1, 60, data_size)
memory = np.random.choice([64, 128, 256], data_size)
score = np.random.randint(1, 10, data_size)
# 真实关系：价格 = 5000 - 50*月数 + 10*内存 + 200*成色 + 噪声
price = 5000 - 50 * months + 10 * memory + 200 * score + np.random.normal(0, 100, data_size)

df = pd.DataFrame({'months': months, 'memory': memory, 'score': score, 'price': price})

# 2. 特征与目标分离
X = df[['months', 'memory', 'score']]
y = df['price']

# 3. 数据集划分 (先分出测试集，再分训练验证)
X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.1, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.22, random_state=42)

# 4. 模型训练
model = LinearRegression()
model.fit(X_train, y_train)

# 5. 验证与测试
val_pred = model.predict(X_val)
test_pred = model.predict(X_test)

val_mse = mean_squared_error(y_val, val_pred)
test_mse = mean_squared_error(y_test, test_pred)
test_r2 = r2_score(y_test, test_pred)

print(f"验证集 MSE: {val_mse:.2f}")
print(f"测试集 MSE: {test_mse:.2f}, R^2: {test_r2:.2f}")
print(f"模型系数: {model.coef_}")

# 6. 保存模型
joblib.dump(model, 'phone_price_model.pkl')
```

## 测试与边界情况
在实践过程中，必须考虑以下边界情况对流程的影响：
1. **异常输入**：若“使用月数”为负数或超过 200 个月，模型预测可能失效。需在预处理步骤添加截断或过滤逻辑。
2. **类别特征**：若引入“品牌”列（字符串），线性回归无法直接处理。需演示 One-Hot 编码或 Label 编码的插入位置（应在划分前还是划分后？通常建议在划分后分别 fit 以避免数据泄露）。
3. **数据泄露**：确保测试集数据从未参与任何标准化参数的计算。例如，`StandardScaler` 应在训练集上 fit，然后 transform 训练集、验证集和测试集。

## 评价量规
学生提交的实践报告将依据以下标准评分：

| 维度 | 优秀 (90-100) | 合格 (60-89) | 不合格 (<60) |
| :--- | :--- | :--- | :--- |
| **流程完整性** | 严格区分训练、验证、测试三步，代码逻辑清晰。 | 有划分步骤，但验证集用途不明确。 | 未划分数据集，直接用全数据测试。 |
| **指标选择** | 正确选用 MSE/R^2，并能解释含义。 | 仅输出误差数值，无指标名称。 | 使用分类指标（如准确率）评估回归任务。 |
| **边界处理** | 代码中包含异常值检查或注释说明。 | 仅处理正常数据。 | 代码无法运行或报错。 |
| **结果分析** | 能分析过拟合/欠拟合迹象并提出改进。 | 仅罗列运行结果。 | 无结果分析。 |

## 拓展问题
1. **任务转换**：如果平台需求变为“判断手机是否值得回收（是/否）”，流程中哪些部分必须修改？（提示：模型算法、评估指标、目标变量类型）。
2. **数据漂移**：若半年后手机市场整体降价，原有模型在测试集上表现依然良好，但在实际线上应用误差变大，这是什么原因？如何在流程中加入监控机制？
3. **伦理思考**：若模型发现某品牌手机估价普遍偏低，而该品牌用户多为特定群体，这是否涉及算法歧视？在数据收集阶段应如何规避？
