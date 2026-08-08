# 离散模拟与实验设计｜核心讲义

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 理解离散事件模拟（Discrete Event Simulation, DES）的基本定义及其与连续模拟的区别。
2. 掌握构建模拟模型的核心步骤，包括状态定义、事件逻辑与数据收集。
3. 能够设计简单的对照实验来验证模拟结果的可靠性，并识别常见的设计误区。

## 概念与边界
离散模拟是指系统状态仅在离散的时间点上发生变化的建模方法。与连续模拟（如微分方程描述的物理运动）不同，离散模拟关注的是“事件”的发生时刻，例如顾客到达、服务完成或机器故障。在计算思维中，离散模拟常用于解决排队论、网络流量、生产调度等问题。

实验设计在此语境下，指为了回答特定问题而规划模拟运行方案的过程。核心在于控制变量：保持模型逻辑不变，仅调整输入参数（如到达率、服务时间分布），观察输出指标（如平均等待时间）的变化。必须区分“验证”（Verification，确保代码逻辑符合设计）与“确认”（Validation，确保模型符合现实世界）。

## 机制与步骤
构建一个有效的离散模拟通常遵循以下五个步骤：
1. **定义系统状态**：确定描述系统所需的最小变量集合，如队列长度、服务器状态（忙/闲）。
2. **定义事件集合**：列出所有能改变系统状态的动作，如“到达事件”、“离开事件”。
3. **初始化**：设定初始时间 $t=0$，初始状态，以及模拟终止条件（如固定时长或固定事件数）。
4. **事件循环**：按时间顺序处理事件。每次取出下一个最早发生的事件，更新系统状态和时间，并可能生成未来事件。
5. **数据统计**：在状态变化时记录感兴趣的性能指标，最后计算平均值或分布。

## 完整示例：单服务台排队系统
假设一个银行柜台，顾客到达间隔服从指数分布，服务时间也服从指数分布。我们需要模拟平均等待时间。

```python
import random
import heapq

def simulate_queue(arrival_rate, service_rate, total_time):
    # 状态：当前时间，下一个到达时间，服务器忙碌直到何时，队列
    t = 0.0
    next_arrival = random.expovariate(arrival_rate)
    server_busy_until = 0.0
    queue = []
    total_wait = 0.0
    customers_served = 0
    
    # 事件堆：(时间，事件类型) 0=到达，1=离开
    events = [(next_arrival, 0)] 
    
    while t < total_time:
        t, event_type = heapq.heappop(events)
        
        if event_type == 0: # 顾客到达
            if t >= total_time: break
            if server_busy_until <= t:
                # 服务器空闲，直接服务
                service_time = random.expovariate(service_rate)
                server_busy_until = t + service_time
                heapq.heappush(events, (server_busy_until, 1))
            else:
                # 服务器忙，加入队列
                queue.append(t)
            # 生成下一个到达事件
            next_arrival = t + random.expovariate(arrival_rate)
            heapq.heappush(events, (next_arrival, 0))
            
        elif event_type == 1: # 服务完成
            customers_served += 1
            if queue:
                arrive_time = queue.pop(0)
                total_wait += (t - arrive_time)
                service_time = random.expovariate(service_rate)
                server_busy_until = t + service_time
                heapq.heappush(events, (server_busy_until, 1))
    
    if customers_served == 0: return 0
    return total_wait / customers_served

# 运行实验
random.seed(42)
avg_wait = simulate_queue(arrival_rate=1.0, service_rate=1.2, total_time=1000)
print(f"平均等待时间：{avg_wait:.2f}")
```

## 复杂度与权衡
离散模拟的时间复杂度通常与事件数量 $N$ 成正比，若使用优先队列管理事件，复杂度为 $O(N \log N)$。空间复杂度取决于队列最大长度。
权衡在于精度与成本：模拟时间越长，统计结果越稳定，但计算成本越高。对于随机模拟，必须进行多次独立重复实验（Replications）以计算置信区间，单次运行结果往往不可靠。

## 常见误区
1. **随机种子固定**：调试时固定种子可复现问题，但正式实验需改变种子以评估方差。
2. **忽略预热期**：系统从空状态启动初期的数据可能不具代表性，应丢弃初始阶段数据（Warm-up period）。
3. **混淆因果**：参数变化导致结果变化，需排除随机波动干扰，建议使用假设检验。

## 自测题与答案
1. **问**：为何离散模拟中通常使用优先队列来管理事件？
   **答**：因为事件必须严格按时间顺序处理，优先队列能保证每次以 $O(\log N)$ 效率取出最早发生的事件。
2. **问**：如果模拟结果显示平均等待时间为 0，可能是什么原因？
   **答**：可能是服务率远大于到达率，或者模拟时间太短未产生排队，亦或是代码逻辑错误导致队列未被记录。
3. **问**：实验设计中，为什么要进行多次独立运行？
   **答**：为了消除随机性的影响，通过多次运行计算均值和方差，从而评估结果的统计显著性。
