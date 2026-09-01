# 栈、队列与双端队列｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在具体编程任务中识别何时使用栈、队列或双端队列。
2. 完成一个包含多种数据流处理功能的模拟系统。
3. 掌握针对数据结构边界条件（如空、满、非法操作）的测试方法。
4. 依据代码效率与规范性的量规进行自我评估。

## 真实问题情境
假设你正在开发一个简易的“后台任务处理器”，该系统需要同时处理三种不同类型的请求：
1. **撤销操作（Undo）**：用户的操作记录需要保存，且最近的操作必须最先被撤销。
2. **打印任务（Print）**：多个用户提交的打印请求必须按照提交顺序依次处理，不能插队。
3. **回文检测（Palindrome）**：系统接收一串字符流，需要快速判断该字符串是否正读反读一致。
这三种需求分别对应栈、队列和双端队列的典型应用场景。你需要设计一个类来统一管理这些功能。

## 输入输出或材料
- **输入**：一系列命令字符串。
  - `U <content>`：记录 undo 操作。
  - `Z`：执行撤销（Undo）。
  - `P <task>`：添加打印任务。
  - `N`：执行下一个打印任务。
  - `C <string>`：检查字符串是否为回文。
- **输出**：每个命令的执行结果（如撤销的内容、打印的任务、布尔值）。
- **材料**：Python 3 环境，`collections` 模块。

## 分步任务
1. **定义数据结构**：在类初始化方法中，分别实例化一个栈（用于 Undo）、一个队列（用于打印）和一个双端队列（用于回文检查临时存储）。
2. **实现撤销逻辑**：收到 `U` 命令将内容压栈；收到 `Z` 命令弹栈。若栈空，返回 "Nothing to undo"。
3. **实现打印逻辑**：收到 `P` 命令入队；收到 `N` 命令出队。若队空，返回 "No print jobs"。
4. **实现回文逻辑**：收到 `C` 命令，将字符串字符依次放入双端队列。每次从两端各取一个字符比较，若不等则返回 False，全部相等返回 True。

## 参考实现/推导
```python
from collections import deque

class TaskProcessor:
    def __init__(self):
        self.undo_stack = deque()  # 栈
        self.print_queue = deque() # 队列
        # 双端队列用于回文检查，无需长期存储
    
    def process(self, command):
        parts = command.split(maxsplit=1)
        op = parts[0]
        
        if op == 'U':
            self.undo_stack.append(parts[1])
            return "Recorded"
        elif op == 'Z':
            if not self.undo_stack:
                return "Nothing to undo"
            return self.undo_stack.pop()
        elif op == 'P':
            self.print_queue.append(parts[1])
            return "Queued"
        elif op == 'N':
            if not self.print_queue:
                return "No print jobs"
            return self.print_queue.popleft()
        elif op == 'C':
            text = parts[1]
            d = deque(text)
            while len(d) > 1:
                if d.pop() != d.popleft():
                    return False
            return True
        return "Unknown Command"
```

## 测试与边界情况
必须验证以下边界条件以确保系统健壮性：
1. **空结构操作**：连续发送 `Z` 或 `N` 命令，确保系统不崩溃且返回特定提示。
2. **单元素情况**：回文检查输入单字符（如 "A"），应返回 True；打印队列仅剩一个任务时出队。
3. **非法输入**：发送未定义的命令字符，系统应能识别并返回错误信息。
4. **大量数据**：模拟 1000 次入队出队操作，观察内存占用与响应时间，验证 `deque` 性能优于 `list`。

## 评价量规
| 维度 | 优秀 (5 分) | 合格 (3 分) | 待改进 (1 分) |
| :--- | :--- | :--- | :--- |
| **结构选择** | 准确使用栈、队列、Deque 对应功能 | 混用结构但功能实现 | 全部使用 list 模拟 |
| **边界处理** | 所有空操作均有明确提示 | 部分空操作未处理 | 程序直接崩溃 |
| **代码规范** | 变量命名清晰，有注释，模块化 | 命名随意，无注释 | 代码混乱难以阅读 |
| **复杂度意识** | 使用 deque 保证 $O(1)$ 操作 | 使用 list pop(0) | 未考虑复杂度 |

## 拓展问题
1. 如果打印任务需要支持“优先级”，队列结构应如何调整？（提示：优先队列）
2. 如果撤销操作需要支持“重做（Redo）”，需要增加什么数据结构？（提示：第二个栈）
3. 在多线程环境下，当前的 `deque` 实现是否安全？若不安全，应添加什么机制？（提示：锁）
