"""
修复websearch.py所有编码问题
"""
import re

# 读取文件
with open('tools/search/websearch.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# 修复所有包含乱码字符的行
fixes = [
    # 第14行
    (r'"""\?SerpAPI 响应里抽\?url \+ title\?"""', '"""从SerpAPI响应里提取url + title"""'),
    # 第29行
    (r'使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url \?title\?', 
     '使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title'),
    # logger.info行中的乱码
    (r'logger\.info\("正在谷歌搜索\?(\d+) 页内\?"\)', r'logger.info("正在谷歌搜索第\1 页内容")'),
    (r'logger\.info\("正在谷歌搜索\?1 页内\?"\)', 'logger.info("正在谷歌搜索第1 页内容")'),
    # 其他可能的乱码
    (r'logger\.warning\(f"SerpAPI \?(\d+) 页返回错\?', r'logger.warning(f"SerpAPI 第\1 页返回错误'),
    (r'logger\.info\(f"\?(\d+) 页没有有效结果，提前结束\?"\)', r'logger.info(f"第\1 页没有有效结果，提前结束")'),
    (r'logger\.info\("没有更多分页结果，提前结束\?"\)', 'logger.info("没有更多分页结果，提前结束")'),
    (r'logger\.warning\(f"SerpAPI 首次请求返回错误（视为当前查\?0 结果）：', 
     'logger.warning(f"SerpAPI 首次请求返回错误（视为当前查询0 结果）：'),
]

for pattern, replacement in fixes:
    content = re.sub(pattern, replacement, content)

# 删除所有替换字符
content = content.replace('', '')

# 保存文件
with open('tools/search/websearch.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("修复完成！")

