"""
修复websearch.py的编码问题
"""
import re

# 读取文件（使用errors='replace'来处理无法解码的字符）
with open('tools/search/websearch.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# 修复第14行的docstring
content = re.sub(
    r'"""\?SerpAPI 响应里抽\?url \+ title\?"""',
    '"""从SerpAPI响应里提取url + title"""',
    content
)

# 修复第29行的docstring（包含全角括号和乱码）
# 查找并替换有问题的docstring
content = re.sub(
    r'使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url \?title\?',
    '使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title',
    content
)

# 如果还有乱码字符，尝试替换
content = content.replace('', '')  # 删除替换字符

# 保存文件
with open('tools/search/websearch.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("修复完成！")
