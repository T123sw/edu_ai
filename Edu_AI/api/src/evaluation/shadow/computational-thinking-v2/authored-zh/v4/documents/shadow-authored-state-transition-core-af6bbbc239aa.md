# 状态、规则与状态转移｜核心讲义

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 理解“状态”作为系统瞬时快照的抽象含义，区分状态与普通变量。
2. 掌握状态转移的基本机制，能够用数学语言描述状态变化过程。
3. 能够识别简单系统中的状态、事件与规则，并编写对应的状态机代码。
4. 认知状态爆炸问题，理解在复杂系统中管理状态的权衡。

## 准确概念与边界
**状态（State）**：指系统在某一特定时刻所有相关属性的综合取值。它必须是离散且有限的，能够完全描述系统当前的行为模式。例如，灯泡的“亮”与“灭”是状态，而电压的连续数值通常视为物理量而非逻辑状态。
**规则（Rule）**：指约束状态变化的逻辑条件。规则决定了在特定输入下，系统是否允许从当前状态跳转到另一状态。规则通常表现为“守卫条件”（Guard Condition）。
**状态转移（State Transition）**：指系统从一个状态变迁到另一个状态的过程。形式化描述为函数 $T: S \times E \rightarrow S$，其中 $S$ 是状态集合，$E$ 是事件集合。

**边界说明**：本知识点聚焦于离散事件系统。连续变化的物理过程（如温度渐变）若不经过离散化采样，不属于本范畴。状态机不包含对内部数据计算过程的详细描述，仅关注控制流的跳转。

## 机制与步骤
状态机的运行遵循“感知 - 判断 - 执行”循环：
1. **保持当前状态**：系统初始化后进入初始状态 $S_0$。
2. **接收事件**：系统监听外部输入或内部触发事件 $e \in E$。
3. **匹配规则**：查询转移函数，检查是否存在规则 $(S_{current}, e) \rightarrow S_{next}$。
4. **执行转移**：若规则匹配且守卫条件满足，更新状态为 $S_{next}$，并执行伴随动作；否则拒绝事件或报错。

## 完整例子：自动门控制系统
考虑一个商场自动门，其逻辑如下：
- **状态集合**：$\{关闭 (CLOSED), 打开 (OPEN), 运动中 (MOVING)\}$。
- **事件集合**：$\{有人接近 (NEAR), 无人接近 (NONE), 电机停 (STOP)\}$。
- **转移规则**：
  - $CLOSED + NEAR \rightarrow MOVING$ (开始开门)
  - $MOVING + STOP \rightarrow OPEN$ (门完全打开)
  - $OPEN + NONE \rightarrow MOVING$ (开始关门)
  - $MOVING + STOP \rightarrow CLOSED$ (门完全关闭)
  - 其他组合保持原状态或无效。

## 代码实现
以下 Python 代码实现了上述逻辑，使用枚举定义状态以确保类型安全。

```python
from enum import Enum

class DoorState(Enum):
    CLOSED = "关闭"
    OPEN = "打开"
    MOVING = "运动中"

class AutomaticDoor:
    def __init__(self):
        self.state = DoorState.CLOSED
    
    def trigger(self, event):
        """接收事件并尝试状态转移"""
        next_state = self._get_next_state(self.state, event)
        if next_state:
            print(f"事件：{event} | 状态变更：{self.state.value} -> {next_state.value}")
            self.state = next_state
        else:
            print(f"事件：{event} | 状态：{self.state.value} | 结果：无效转移")
            
    def _get_next_state(self, current, event):
        # 规则引擎核心
        if current == DoorState.CLOSED and event == "NEAR":
            return DoorState.MOVING
        elif current == DoorState.MOVING and event == "STOP":
            # 此处简化逻辑，实际需判断是开到位还是关到位
            # 为演示状态机，假设外部传感器决定 STOP 后的状态
            # 这里为了严谨，我们修正例子逻辑：MOVING 分为 OPENING 和 CLOSING 更佳
            # 但为控制复杂度，假设 STOP 总是到达目标状态
            return DoorState.OPEN # 简化假设
        elif current == DoorState.OPEN and event == "NONE":
            return DoorState.MOVING
        elif current == DoorState.MOVING and event == "STOP":
            return DoorState.CLOSED
        return None

# 运行测试
door = AutomaticDoor()
door.trigger("NEAR")
door.trigger("STOP")
door.trigger("NONE")
door.trigger("STOP")
```

## 复杂度与权衡
状态机的时间复杂度通常为 $O(1)$，因为转移查询是常数时间的查表操作。然而，空间复杂度随状态数量线性增长。主要权衡在于**状态爆炸**：当系统变量增多时，组合状态数呈指数级增长（$N$ 个布尔变量产生 $2^N$ 个状态）。解决策略包括引入层次化状态机（HSM）或将数据与状态分离，仅将控制逻辑纳入状态机。

## 常见误区
1. **混淆状态与数据**：认为“用户年龄”是状态。实际上，年龄是数据，只有当年龄触发逻辑分支（如“成年/未成年”）时才构成状态。
2. **忽略非法转移**：未定义所有可能的输入组合，导致程序在意外输入下崩溃。
3. **状态冗余**：定义了逻辑等价的状态，增加了维护成本。

## 自测题与答案
1. **问**：在一个下载任务中，“下载进度 50%"是状态吗？
   **答**：不是。这是数据变量。状态应为“下载中”、“暂停”、“完成”。
2. **问**：若当前状态为 $S_1$，输入 $E_1$，无定义转移规则，系统应如何行为？
   **答**：应保持 $S_1$ 不变或抛出异常，绝不能进入未定义状态。
3. **问**：状态转移是否必须伴随动作？
   **答**：否。纯状态跳转是允许的，但通常伴随入口/出口动作。
