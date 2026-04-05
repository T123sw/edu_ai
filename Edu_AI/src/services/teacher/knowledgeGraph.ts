/**
 * 教师端知识图谱（MVP 数据 + mock 接口）
 * 方案：严格树结构（每个子节点只属于一个父节点）
 * 当前边全部视为 related，但结构上预留 edge.type。
 */

export type NodeId = string;
export type EdgeId = string;

// G6 TreeGraph 需要的节点数据结构
export interface TreeGraphNode {
  id: NodeId;
  label: string;
  children?: TreeGraphNode[];
  // 自定义数据，用于右侧详情面板
  data: {
    level: number;
    summary?: string;
    hasChildren: boolean;
    type: 'concept' | 'example' | 'skill';
  };
}

// =========================
// 《计算思维》严格树（示例）
// =========================

type TreeNode = {
  label: string;
  summary?: string;
  children?: Record<string, TreeNode>;
};

const CT_TREE: Record<string, TreeNode> = {
  'ct-1': {
    label: '分解（Decomposition）',
    summary: '将复杂问题拆分为更小、更可管理的子问题。',
    children: {
      'ct-1-1': { label: '问题拆解', summary: '把大问题拆成若干子问题与约束。' },
      'ct-1-2': { label: '任务分解', summary: '把目标拆成可执行的步骤与子任务。' },
      'ct-1-3': { label: '模块化设计', summary: '通过模块划分降低复杂度与耦合。' },
    },
  },
  'ct-2': {
    label: '模式识别（Pattern Recognition）',
    summary: '发现相似性与规律，复用经验以提升效率。',
    children: {
      'ct-2-1': { label: '寻找相似性', summary: '识别不同问题之间可复用的结构。' },
      'ct-2-2': { label: '模式抽象', summary: '将相似问题归纳成统一模式。' },
      'ct-2-3': { label: '规律发现', summary: '从数据与现象中总结规律。' },
    },
  },
  'ct-3': {
    label: '抽象（Abstraction）',
    summary: '提取关键特征并忽略无关细节，形成模型。',
    children: {
      'ct-3-1': {
        label: '模型构建',
        summary: '用合适的方式描述问题的本质结构。',
        children: {
          'ct-3-1-1': { label: '状态机', summary: '用状态与转移描述系统行为。' },
          'ct-3-1-2': { label: '图模型', summary: '用点与边表达关系结构。' },
          'ct-3-1-3': { label: '仿真', summary: '用可运行模型模拟真实系统。' },
        },
      },
      'ct-3-2': { label: '关键特征提取', summary: '聚焦决定性因素与变量。' },
      'ct-3-3': { label: '忽略非关键细节', summary: '屏蔽噪声与无关信息。' },
    },
  },
  'ct-4': {
    label: '算法（Algorithms）',
    summary: '用步骤化的方法解决问题，并评估其正确性与效率。',
    children: {
      'ct-4-1': {
        label: '算法设计',
        summary: '构建解决问题的步骤与策略。',
        children: {
          'ct-4-1-1': { label: '分治', summary: '分解问题、分别求解、合并结果。' },
          'ct-4-1-2': { label: '贪心', summary: '每一步选择当前最优。' },
          'ct-4-1-3': { label: '动态规划', summary: '利用重叠子问题与最优子结构。' },
        },
      },
      'ct-4-2': { label: '算法分析', summary: '分析时间/空间成本与边界情况。' },
      'ct-4-3': { label: '算法优化', summary: '在正确基础上提升性能与可读性。' },
    },
  },
  'ct-5': {
    label: '数据与表示（Data Representation）',
    summary: '选择合适的数据结构与表示方法来存储与处理信息。',
    children: {
      'ct-5-1': { label: '数据结构', summary: '数组、链表、栈、队列、树、图等。' },
      'ct-5-2': { label: '数据编码', summary: '二进制、字符编码、压缩等。' },
      'ct-5-3': { label: '数据抽象', summary: '通过接口隐藏实现细节。' },
    },
  },
};

// =========================
// Graph helpers
// =========================

function findTreeNodeById(nodeId: string): { node: TreeNode; level: number } | null {
  if (nodeId === 'root') return { node: { label: '计算思维', children: CT_TREE }, level: 0 };

  const walk = (obj: Record<string, TreeNode>, level: number): { node: TreeNode; level: number } | null => {
    for (const [id, n] of Object.entries(obj)) {
      if (id === nodeId) return { node: n, level };
      if (n.children) {
        const hit = walk(n.children, level + 1);
        if (hit) return hit;
      }
    }
    return null;
  };

  return walk(CT_TREE, 1);
}

/**
 * 获取初始图数据（root + L1）
 */
export function getInitialTreeGraphData(): TreeGraphNode {
  return {
    id: 'root',
    label: '计算思维',
    data: {
      level: 0,
      summary: '计算思维课程知识图谱（概览）。',
      hasChildren: true,
      type: 'concept',
    },
    children: Object.entries(CT_TREE).map(([id, n]) => ({
      id,
      label: n.label,
      data: {
        level: 1,
        summary: n.summary,
        hasChildren: !!n.children,
        type: 'concept',
      },
      // 初始时，子节点为空，等待单击展开
      children: [],
    })),
  };
}

/**
 * mock：获取某个节点的子节点（用于动态展开）
 */
export function getChildrenNodes(nodeId: string): TreeGraphNode[] {
  const hit = findTreeNodeById(nodeId);
  if (!hit?.node?.children) return [];

  const { node, level } = hit;

  return Object.entries(node.children).map(([childId, child]) => ({
    id: childId,
    label: child.label,
    data: {
      level: level + 1,
      summary: child.summary,
      hasChildren: !!child.children,
      type: 'concept',
    },
    children: [],
  }));
}

/**
 * 获取节点详情（用于右侧面板）
 */
export function getNodeDetails(nodeId: string, rootNode?: TreeGraphNode) {
  // 如果提供了 rootNode，从树中查找
  if (rootNode) {
    const found = findNodeInTree(rootNode, nodeId);
    if (found) {
      return {
        id: found.id,
        label: found.label,
        level: found.data.level,
        summary: found.data.summary,
        hasChildren: found.data.hasChildren,
      };
    }
  }
  
  // 回退到旧的 mock 数据查找
  const hit = findTreeNodeById(nodeId);
  if (!hit) return null;

  const { node, level } = hit;
  return {
    id: nodeId,
    label: node.label,
    level,
    summary: node.summary,
    hasChildren: !!node.children,
  };
}

/**
 * 在树中查找节点
 */
function findNodeInTree(root: TreeGraphNode, nodeId: string): TreeGraphNode | null {
  if (root.id === nodeId) {
    return root;
  }
  if (root.children) {
    for (const child of root.children) {
      const found = findNodeInTree(child, nodeId);
      if (found) return found;
    }
  }
  return null;
}

/**
 * 从后端数据转换为 TreeGraphNode
 */
export function convertBackendToTreeGraph(backendNode: any): TreeGraphNode {
  return {
    id: backendNode.id || 'root',
    label: backendNode.label || '未命名节点',
    data: {
      level: backendNode.data?.level ?? 0,
      summary: backendNode.data?.summary,
      hasChildren: backendNode.data?.hasChildren ?? !!backendNode.children,
      type: backendNode.data?.type || 'concept',
    },
    children: backendNode.children
      ? backendNode.children.map((child: any) => convertBackendToTreeGraph(child))
      : [],
  };
}

/**
 * 获取某个节点的子节点（从树中查找）
 */
export function getChildrenNodesFromTree(nodeId: string, rootNode: TreeGraphNode): TreeGraphNode[] {
  const found = findNodeInTree(rootNode, nodeId);
  if (!found || !found.children) return [];
  
  // 返回子节点，但清空它们的 children（等待点击展开）
  return found.children.map(child => ({
    ...child,
    children: [],
  }));
}
