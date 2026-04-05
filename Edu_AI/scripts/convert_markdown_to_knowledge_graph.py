#!/usr/bin/env python3
"""
将 markdown 格式的知识图谱转换为 JSON 格式
"""
import json
import re
from typing import Dict, List, Optional

def parse_markdown_flowchart(markdown_content: str) -> Dict:
    """
    解析 markdown flowchart 格式的知识图谱
    
    格式示例:
    root((计算思维与程序设计))
    root --> C1[第1章 计算思维与问题求解]
    C1 --> C1_1[1.1 计算、自动计算与计算机]
    """
    lines = markdown_content.strip().split('\n')
    
    # 存储节点和边
    nodes: Dict[str, Dict] = {}
    edges: List[tuple] = []
    
    # 找到 flowchart 开始
    in_flowchart = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # 检查是否是 flowchart 定义
        if line.startswith('flowchart'):
            in_flowchart = True
            continue
            
        if not in_flowchart:
            continue
        
        # 解析边: source --> target 或 source --- target，同时提取节点信息
        # 格式: source --> target[label] 或 source --> target((label))
        edge_match = re.match(r'^(\w+)\s*(--?>?)\s*(\w+)(\(\(([^)]+)\)\)|\[([^\]]+)\])?', line)
        if edge_match:
            source = edge_match.group(1)
            target = edge_match.group(3)
            target_label = edge_match.group(5) or edge_match.group(6)
            
            # 确保源节点存在
            if source not in nodes:
                nodes[source] = {
                    'id': source,
                    'label': source,  # 临时标签，后面会更新
                    'children': []
                }
            
            # 确保目标节点存在
            if target not in nodes:
                nodes[target] = {
                    'id': target,
                    'label': target_label or target,  # 使用提取的标签或节点ID
                    'children': []
                }
            elif target_label:
                # 更新标签
                nodes[target]['label'] = target_label
            
            edges.append((source, target))
            continue
            
        # 解析节点定义: node_id((label)) 或 node_id[label]（单独定义）
        node_match = re.match(r'^(\w+)(\(\(([^)]+)\)\)|\[([^\]]+)\])', line)
        if node_match:
            node_id = node_match.group(1)
            label = node_match.group(3) or node_match.group(4)
            if node_id not in nodes:
                nodes[node_id] = {
                    'id': node_id,
                    'label': label,
                    'children': []
                }
            else:
                # 更新标签
                nodes[node_id]['label'] = label
            continue
    
    # 构建树结构
    # 找到根节点（没有入边的节点）
    all_targets = {target for _, target in edges}
    root_id = None
    for node_id in nodes.keys():
        if node_id not in all_targets:
            root_id = node_id
            break
    
    if not root_id:
        # 如果没有找到根节点，使用第一个节点
        root_id = list(nodes.keys())[0] if nodes else None
    
    if not root_id:
        return None
    
    # 构建父子关系
    children_map: Dict[str, List[str]] = {}
    for source, target in edges:
        if source not in children_map:
            children_map[source] = []
        children_map[source].append(target)
    
    # 递归构建树
    def build_tree(node_id: str, depth: int = 1) -> Dict:
        node = nodes[node_id].copy()
        
        # 确定节点类型
        if depth == 1:
            node_type = 'concept'  # 根节点
        elif depth == 2:
            node_type = 'chapter'  # 章节
        elif depth == 3:
            node_type = 'section'  # 小节
        elif depth == 4:
            node_type = 'topic'  # 主题
        else:
            node_type = 'concept'  # 更深层的概念
        
        node['data'] = {
            'level': depth,
            'summary': node['label'],
            'hasChildren': node_id in children_map,
            'type': node_type
        }
        
        if node_id in children_map:
            node['children'] = [
                build_tree(child_id, depth + 1)
                for child_id in children_map[node_id]
            ]
        else:
            node['children'] = []
        
        return node
    
    root = build_tree(root_id, 1)
    
    # 确保根节点有 data 字段（如果构建时没有添加）
    if 'data' not in root:
        root['data'] = {
            'level': 1,
            'summary': root.get('label', ''),
            'hasChildren': len(root.get('children', [])) > 0,
            'type': 'concept'
        }
    
    return root

def main():
    # 读取 markdown 文件
    input_file = r'D:\Edu_AI_1\计算思维知识图谱.md'
    output_file = r'D:\Edu_AI_1\Edu_AI\api\course_data\courses\computational-thinking\knowledge_graph.json'
    
    print(f'读取文件: {input_file}')
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析 markdown
    print('解析 markdown 流程图...')
    root = parse_markdown_flowchart(content)
    
    if not root:
        print('错误: 无法解析知识图谱')
        return
    
    # 保存 JSON
    print(f'保存到: {output_file}')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
    
    # 统计信息
    def count_nodes(node: Dict) -> int:
        count = 1
        for child in node.get('children', []):
            count += count_nodes(child)
        return count
    
    total_nodes = count_nodes(root)
    print(f'转换完成! 共 {total_nodes} 个节点')
    print(f'根节点: {root["label"]}')

if __name__ == '__main__':
    main()

