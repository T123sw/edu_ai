"""
最终修复websearch.py的编码问题
"""
import re

file_path = "tools/search/websearch.py"

# 读取文件
with open(file_path, 'rb') as f:
    raw = f.read()

# 尝试UTF-8解码，替换无法解码的字符
try:
    content = raw.decode('utf-8', errors='replace')
except:
    content = raw.decode('gbk', errors='replace')

# 修复第29行和第57行的问题（包含全角括号和乱码）
lines = content.split('\n')

# 修复第29行（索引28）
if len(lines) > 28:
    line = lines[28]
    # 移除所有不可见字符和乱码
    line = re.sub(r'[^\x20-\x7E\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', line)
    # 修复特定的模式
    if 'url' in line and 'title' in line:
        lines[28] = '    使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title'

# 修复第57行（索引56）
if len(lines) > 56:
    line = lines[56]
    # 移除所有不可见字符和乱码
    line = re.sub(r'[^\x20-\x7E\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', line)
    # 修复特定的模式
    if 'url' in line and 'title' in line:
        lines[56] = '    使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title'

# 重新组合
content = '\n'.join(lines)

# 移除所有U+FFFD替换字符
content = content.replace('\ufffd', '')
content = content.replace('\ue511', '')

# 修复常见的乱码模式（使用字符串替换，不用正则）
fixes = [
    ('url?title?', 'url 和 title'),
    ('未设?', '未设置'),
    ('可以直接?', '可以直接抛'),
    ('?1?', '第 1 页'),
    ('?1 页内?', '第 1 页内容'),
    ('查?0 结果', '查询 0 结果'),
    ('不再?Agent', '不再让 Agent'),
    ('提前结束?', '提前结束。'),
    ('规范?URL：去?fragment', '规范化 URL：去掉 fragment'),
    ('造成重复?', '造成重复。'),
    ('?预留：', ' 预留：'),
    ('放哪?header', '放哪个 header'),
    ('例?"Bearer', '例如 "Bearer'),
    ('结果?', '结果。'),
    ('否则 403?', '否则 403）'),
    ('?timeout', '将 timeout'),
    ('本?SearxNG', '本地 SearxNG'),
    ('结果页?', '结果页。'),
    ('调整?', '调整。'),
    ('可能变化?', '可能变化）'),
    ('备用?', '备用：'),
    ('选择?', '选择器'),
    ('无效链?', '无效链接'),
    ('过?javascript', '过滤 javascript'),
    ('外部链?', '外部链接'),
    ('抓?DuckDuckGo', '抓取 DuckDuckGo'),
    ('DuckDuckGo?HTML', 'DuckDuckGo 的 HTML'),
    ('使用?', '使用。'),
    ('标准结构?', '标准结构：'),
    ('重定向链?', '重定向链接'),
    ('找摘?', '找摘要'),
    ('流程中?', '流程中断'),
    ('备?', '备选'),
    ('本?自建', '本地/自建'),
    ('结构化?', '结构化）'),
    ('不依赖 8090?', '不依赖 8090）'),
    ('便捷函数?', '便捷函数。'),
    ('整?Agent', '整个 Agent'),
    ('兜底?', '兜底。'),
]

for old, new in fixes:
    content = content.replace(old, new)

# 写入文件（UTF-8编码）
with open(file_path, 'w', encoding='utf-8', errors='replace') as f:
    f.write(content)

print("修复完成！")

