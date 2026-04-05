"""
简单修复websearch.py的编码问题
直接替换有问题的行
"""
file_path = "tools/search/websearch.py"

# 读取文件
with open(file_path, 'rb') as f:
    raw = f.read()

# 尝试解码
try:
    content = raw.decode('utf-8', errors='replace')
except:
    content = raw.decode('gbk', errors='replace')

# 修复第29行的问题
lines = content.split('\n')
if len(lines) > 28:
    # 修复第29行（索引28）
    if 'url' in lines[28] and 'title' in lines[28]:
        lines[28] = '    使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title'

# 修复其他常见的乱码
content = '\n'.join(lines)
content = content.replace('?', '')
content = content.replace('url?title?', 'url 和 title')
content = content.replace('未设?', '未设置')
content = content.replace('可以直接?', '可以直接抛')
content = content.replace('?1?', '第 1 页')
content = content.replace('?1 页内?', '第 1 页内容')
content = content.replace('错??', '错误 和 ')
content = content.replace('查?0 结果', '查询 0 结果')
content = content.replace('不再?Agent', '不再让 Agent')
content = content.replace('提前结束?', '提前结束。')
content = content.replace('规范?URL：去?fragment', '规范化 URL：去掉 fragment')
content = content.replace('造成重复?', '造成重复。')
content = content.replace('?预留：', ' 预留：')
content = content.replace('放哪?header', '放哪个 header')
content = content.replace('例?"Bearer', '例如 "Bearer')
content = content.replace('结果?', '结果。')
content = content.replace('否则 403?', '否则 403）')
content = content.replace('?timeout', '将 timeout')
content = content.replace('本?SearxNG', '本地 SearxNG')
content = content.replace('结果页?', '结果页。')
content = content.replace('调整?', '调整。')
content = content.replace('可能变化?', '可能变化）')
content = content.replace('备用?', '备用：')
content = content.replace('选择?', '选择器')
content = content.replace('无效链?', '无效链接')
content = content.replace('过?javascript', '过滤 javascript')
content = content.replace('外部链?', '外部链接')
content = content.replace('抓?DuckDuckGo', '抓取 DuckDuckGo')
content = content.replace('DuckDuckGo?HTML', 'DuckDuckGo 的 HTML')
content = content.replace('使用?', '使用。')
content = content.replace('标准结构?', '标准结构：')
content = content.replace('重定向链?', '重定向链接')
content = content.replace('找摘?', '找摘要')
content = content.replace('流程中?', '流程中断')
content = content.replace('备?', '备选')
content = content.replace('本?自建', '本地/自建')
content = content.replace('结构化?', '结构化）')
content = content.replace('不依赖 8090?', '不依赖 8090）')
content = content.replace('便捷函数?', '便捷函数。')
content = content.replace('整?Agent', '整个 Agent')
content = content.replace('兜底?', '兜底。')

# 写入文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("修复完成！")

