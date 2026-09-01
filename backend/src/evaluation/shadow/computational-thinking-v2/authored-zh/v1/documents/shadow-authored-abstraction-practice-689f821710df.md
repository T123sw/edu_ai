# 抽象、建模与信息隐藏｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在真实情境中识别需要抽象的关键实体，并构建状态模型。
2. 通过实践任务，实现一个具有信息隐藏特性的控制模块。
3. 学会设计测试用例以验证接口的健壮性及边界条件。

## 真实问题情境
假设你正在为一款**智能恒温器（Smart Thermostat）**开发控制软件。该设备连接温度传感器和 HVAC（暖通空调）系统。用户设定目标温度，设备需根据当前室温自动决定开启加热、制冷或待机。为了保护硬件驱动的稳定性和算法的专利性，具体的控制逻辑（如 PID 参数）不应暴露给上层应用。

## 输入输出与材料
- **输入材料**：
  1. 当前环境温度 $T_{current}$（浮点数，单位摄氏度）。
  2. 用户设定温度 $T_{set}$（浮点数，单位摄氏度）。
  3. 系统模式（"AUTO", "OFF"）。
- **输出材料**：
  1. 设备状态指令（"HEAT", "COOL", "IDLE"）。
  2. 内部日志（用于调试，不对外公开）。
- **开发环境**：Python 3.x 标准库。

## 分步任务
1. **实体抽象**：识别系统中的关键对象。忽略湿度、气压等次要因素，仅保留温度相关变量。
2. **状态建模**：定义恒温器的状态机。状态集合 $S = \{IDLE, HEATING, COOLING\}$。确定状态转换条件，例如当 $T_{current} < T_{set} - \delta$ 时转入加热状态，其中 $\delta$ 为死区阈值。
3. **接口设计**：定义 `Thermostat` 类。公开 `update()` 方法供外部传入传感器数据，隐藏内部状态变量 `_state` 和控制参数 `_threshold`。
4. **逻辑实现**：编写状态转换逻辑。确保外部无法直接强制切换状态，必须通过温度变化触发。
5. **封装验证**：尝试在类外部访问私有变量，确认是否被阻止或警告。

## 参考实现
以下代码实现了上述模型，重点展示了状态逻辑的隐藏。

```python
class Thermostat:
    def __init__(self, threshold=0.5):
        # 隐藏控制参数，外部不可见
        self._threshold = threshold 
        self._state = "IDLE"
        self._target_temp = 25.0
    
    def set_target(self, temp):
        if 10.0 <= temp <= 35.0:
            self._target_temp = temp
            return True
        return False
    
    def update(self, current_temp):
        """核心控制逻辑被隐藏在此方法内"""
        if self._state == "OFF":
            return "IDLE"
        
        # 状态机逻辑隐藏
        if current_temp < self._target_temp - self._threshold:
            self._state = "HEATING"
        elif current_temp > self._target_temp + self._threshold:
            self._state = "COOLING"
        else:
            self._state = "IDLE"
            
        return self._state

# 实例化与测试
device = Thermostat()
device.set_target(24.0)
print(device.update(20.0))  # 应输出 HEATING
# print(device._state)      # 虽可访问但约定为受保护，不应直接修改
```

## 测试与边界情况
在验证模型时，需重点测试以下边界：
1. **传感器故障**：当 `current_temp` 传入 `None` 或非数字类型时，系统应保持原状态或报错，不应崩溃。
2. **阈值边界**：当 $T_{current} = T_{set} \pm \delta$ 时，状态应在 `IDLE` 与动作状态间明确切换，避免频繁震荡。
3. **非法设定**：用户设定温度超出物理极限（如 100℃）时，`set_target` 应返回 `False` 并不更新内部模型。

测试代码示例：
```python
assert device.update(None) == "HEATING" # 需在实际代码中增加类型检查以通过此逻辑
assert device.set_target(50.0) == False
```

## 评价量规
| 评价维度 | 优秀 (3 分) | 合格 (2 分) | 需改进 (1 分) |
| :--- | :--- | :--- | :--- |
| **抽象准确性** | 准确忽略无关变量，模型简洁 | 包含少量无关变量 | 模型过于复杂或缺失关键变量 |
| **信息隐藏** | 内部状态完全私有，仅通过接口交互 | 部分内部变量公开 | 关键逻辑暴露在外部 |
| **边界处理** | 妥善处理非法输入和极端值 | 处理了部分边界 | 未考虑边界，程序易崩溃 |
| **代码规范** | 命名清晰，注释完整，可运行 | 基本可运行，注释少 | 代码无法运行或逻辑错误 |

## 拓展问题
1. **多变量建模**：如果系统需要增加湿度控制，如何修改现有模型而不破坏原有的温度控制接口？（提示：考虑使用组合模式或新增独立模块）。
2. **动态参数**：如果死区阈值 $\delta$ 需要根据用户习惯动态调整，应如何设计接口以允许调整参数，同时不暴露具体的算法权重？
3. **并发安全**：在多线程环境下，`update` 方法可能被同时调用，如何保证内部状态 `_state` 的一致性？（提示：思考锁机制或原子操作）。
