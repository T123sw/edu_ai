# 堆与优先队列｜核心讲义

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 理解堆（Heap）的逻辑结构（完全二叉树）与物理存储（数组）之间的映射关系。
2. 掌握优先队列（Priority Queue）的抽象数据类型定义及其与堆的实现关系。
3. 能够手动执行堆的插入（Sift Up）、删除堆顶（Sift Down）及堆化（Heapify）操作。
4. 分析堆操作的时间复杂度，并识别常见的使用误区。

## 概念与边界
**堆**是一种特殊的完全二叉树。在**最大堆**中，任意节点的值均大于或等于其子节点的值；在**最小堆**中，任意节点的值均小于或等于其子节点的值。堆通常使用数组进行顺序存储，若根节点索引为 $0$，则对于索引为 $i$ 的节点：
- 父节点索引：$parent(i) = \lfloor (i-1)/2 \rfloor$
- 左子节点索引：$left(i) = 2i + 1$
- 右子节点索引：$right(i) = 2i + 2$

**优先队列**是一种抽象数据类型（ADT），支持插入元素和按优先级取出元素。堆是实现优先队列最高效的结构之一，但优先队列也可通过有序数组或链表实现（效率较低）。需注意，堆并不保证全局有序，仅保证父节点与子节点间的偏序关系，因此遍历堆数组得不到有序序列。

## 机制与步骤
### 1. 插入操作（Sift Up）
新元素置于数组末尾，然后与其父节点比较。若违反堆性质（如最大堆中子大于父），则交换位置，并继续向上比较，直至根节点或满足性质。
### 2. 删除堆顶（Sift Down）
将堆顶元素与末尾元素交换，移除末尾元素。新的堆顶元素向下调整：与左右子节点中较大者（最大堆）比较，若小于子节点则交换，直至叶子节点或满足性质。
### 3. 堆化（Heapify）
将无序数组构建为堆。从最后一个非叶子节点开始，向前遍历至根节点，对每个节点执行 Sift Down 操作。此方法复杂度为 $O(n)$，优于逐个插入的 $O(n \log n)$。

## 完整示例
假设构建最大堆，输入数组为 $[3, 1, 4, 1, 5]$。
1. 初始状态：$[3, 1, 4, 1, 5]$。最后一个非叶子节点索引为 $\lfloor 5/2 \rfloor - 1 = 1$（值为 1）。
2. 调整索引 1：子节点为索引 3（值 1）和 4（值 5）。5 最大，交换 1 和 5。数组变为 $[3, 5, 4, 1, 1]$。
3. 调整索引 0：子节点为索引 1（值 5）和 2（值 4）。5 最大，交换 3 和 5。数组变为 $[5, 3, 4, 1, 1]$。
4. 检查索引 1（值为 3）：子节点为 1 和 1，无需交换。
5. 最终堆数组：$[5, 3, 4, 1, 1]$。

## 参考代码（Python）
```python
class MaxHeap:
    def __init__(self):
        self.heap = []

    def parent(self, i): return (i - 1) // 2
    def left(self, i): return 2 * i + 1
    def right(self, i): return 2 * i + 2

    def insert(self, key):
        self.heap.append(key)
        i = len(self.heap) - 1
        while i > 0 and self.heap[self.parent(i)] < self.heap[i]:
            p = self.parent(i)
            self.heap[i], self.heap[p] = self.heap[p], self.heap[i]
            i = p

    def extract_max(self):
        if not self.heap: return None
        if len(self.heap) == 1: return self.heap.pop()
        root = self.heap[0]
        self.heap[0] = self.heap.pop()
        i = 0
        while True:
            l, r = self.left(i), self.right(i)
            largest = i
            if l < len(self.heap) and self.heap[l] > self.heap[largest]: largest = l
            if r < len(self.heap) and self.heap[r] > self.heap[largest]: largest = r
            if largest == i: break
            self.heap[i], self.heap[largest] = self.heap[largest], self.heap[i]
            i = largest
        return root
```

## 复杂度与权衡
- 插入与删除操作的时间复杂度均为 $O(\log n)$，因为树的高度为 $\log n$。
- 建堆操作的时间复杂度为 $O(n)$，这是通过聚合分析得出的结论，而非简单的 $n \times \log n$。
- 空间复杂度为 $O(n)$ 用于存储数组。
- 权衡：堆适合动态获取极值，但不适合查找任意元素（需 $O(n)$）。

## 常见误区
1. **误区一**：认为堆的数组表示是有序的。实际上只有堆顶是极值，其余部分无序。
2. **误区二**：建堆复杂度认为是 $O(n \log n)$。实际上自底向上建堆是线性的。
3. **误区三**：混淆最大堆与最大优先队列。最大堆是结构，优先队列是接口，二者概念层级不同。

## 自测题
1. 在索引从 0 开始的堆数组中，索引为 6 的节点的父节点索引是多少？
2. 若向包含 $n$ 个元素的堆中插入 $n$ 个新元素，总时间复杂度是多少？
3. 为什么堆不适合用于范围查询（如查找所有小于 10 的值）？

## 自测题答案
1. 父节点索引为 $\lfloor (6-1)/2 \rfloor = 2$。
2. 每次插入 $O(\log k)$，总复杂度约为 $O(n \log n)$。
3. 因为堆仅保证局部偏序，不保证子树整体范围，最坏需遍历所有节点。
