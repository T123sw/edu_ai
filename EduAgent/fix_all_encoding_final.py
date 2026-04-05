"""
修复websearch.py所有乱码字符
"""
import re

# 读取文件
with open('tools/search/websearch.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# 定义所有需要修复的乱码模式
fixes = [
    # 第60行
    (r'# ----------.*?1.*?----------', '# ---------- 第1 页----------'),
    # 第62行
    (r'logger\.info\("正在谷歌搜索.*?1 页内.*?"\)', 'logger.info("正在谷歌搜索第1 页内容")'),
    # 第68行
    (r'# 区分「配置类」错.*?「查询类」错.*?', '# 区分「配置类」错误和「查询类」错误'),
    # 第75行
    (r'logger\.warning\(f"SerpAPI 首次请求返回错误（视为当前查.*?0 结果）：', 
     'logger.warning(f"SerpAPI 首次请求返回错误（视为当前查询0 结果）：'),
    # 第76行
    (r'return \[\]  # 返回空列表，不再.*?Agent 崩掉', 'return []  # 返回空列表，不再让Agent崩掉'),
    # 第88行
    (r'logger\.info\("没有更多分页结果，提前结束.*?"\)', 'logger.info("没有更多分页结果，提前结束")'),
    # 第92行
    (r'logger\.info\(f"正在谷歌搜索.*?\{current_page\} 页内.*?"\)', 
     'logger.info(f"正在谷歌搜索第{current_page} 页内容")'),
    # 第100行
    (r'logger\.warning\(f"SerpAPI.*?\{current_page\} 页返回错.*? \{err\}"\)', 
     'logger.warning(f"SerpAPI 第{current_page} 页返回错误 {err}")'),
    # 第105行
    (r'logger\.info\(f".*?\{current_page\} 页没有有效结果，提前结束.*?"\)', 
     'logger.info(f"第{current_page} 页没有有效结果，提前结束")'),
    # 第119行
    (r'"""规范.*?URL：去.*?fragment，避免同一页面 #xxx 造成重复.*?"""', 
     '"""规范化URL：去除fragment，避免同一页面 #xxx 造成重复"""'),
    # 第132-134行
    (r'#.*?预留：将来接 Tavily/Brave/Exa/自建网关.*?', '# 预留：将来接 Tavily/Brave/Exa/自建网关'),
    (r'#.*?预留：key 放哪.*?header', '# 预留：key 放哪个header'),
    (r'#.*?预留：例.*?"Bearer " / "" / "Token "', '# 预留：例如"Bearer " / "" / "Token "'),
    # 第141行
    (r'调用 SearxNG JSON API 搜索并返回结构化结果.*?', '调用 SearxNG JSON API 搜索并返回结构化结果'),
    # 第163行
    (r'# SearxNG botdetection 可能要求这些头（否则 403.*?', 
     '# SearxNG botdetection 可能要求这些头（否则 403）'),
    # 第170行
    (r'#.*?timeout 显式拆为 \(connect, read\) 避免 DNS/连接阶段卡死太久', 
     '# 将timeout 显式拆为 (connect, read) 避免 DNS/连接阶段卡死太久'),
    # 第175-176行
    (r'不依赖本.*?SearxNG 的兜底搜索：抓取 Bing HTML 结果页.*?', 
     '不依赖本地SearxNG 的兜底搜索：抓取 Bing HTML 结果页面'),
    (r'注意：这是兜底方案，解析规则可能随页面变化而需要调整.*?', 
     '注意：这是兜底方案，解析规则可能随页面变化而需要调整'),
    # 第184-187行
    (r'# 尝试多种选择器（Bing 页面结构可能变化.*?', 
     '# 尝试多种选择器（Bing 页面结构可能变化）'),
    (r'# 3\. 备用.*?b_algo, \.b_algoSlug', '# 3. 备用：b_algo, .b_algoSlug'),
    # 第202行
    (r'# 尝试多种标题链接选择.*?', '# 尝试多种标题链接选择器'),
    # 第213行
    (r'# 跳过 Bing 内部链接和无效链.*?', '# 跳过 Bing 内部链接和无效链接'),
    # 第217行
    (r'# 尝试多种摘要选择.*?', '# 尝试多种摘要选择器'),
    # 第223行
    (r'# 确保是有效的外部链接（过.*?javascript: 和无效链接）', 
     '# 确保是有效的外部链接（过滤javascript: 和无效链接）'),
    # 第238-240行
    (r'# 如果仍然没有找到结果，尝试从页面中提取所有外部链.*?', 
     '# 如果仍然没有找到结果，尝试从页面中提取所有外部链接'),
    (r'logger\.warning\(f"Bing HTML 解析未找到标准结果，尝试提取所有外部链.*?"\)', 
     'logger.warning(f"Bing HTML 解析未找到标准结果，尝试提取所有外部链接")'),
    # 第260-261行
    (r'兜底搜索：抓.*?DuckDuckGo HTML 结果页.*?', 
     '兜底搜索：抓取DuckDuckGo HTML 结果页面'),
    (r'DuckDuckGo.*?HTML 结构相对稳定，优先使用.*?', 
     'DuckDuckGo 的HTML 结构相对稳定，优先使用'),
    # 第269-270行
    (r'# DuckDuckGo HTML 结果页的选择.*?', '# DuckDuckGo HTML 结果页的选择器'),
    (r'# 标准结构.*?result.*?\.web-result', '# 标准结构：result 或 .web-result'),
    # 第289行
    (r'# 处理 DuckDuckGo 重定向链.*?\(//duckduckgo\.com/l/\?uddg=\.\.\.\)', 
     '# 处理 DuckDuckGo 重定向链接(//duckduckgo.com/l/?uddg=...)'),
    # 第323行
    (r'# 尝试找摘.*?', '# 尝试找摘要'),
    # 第336-337行
    (r'# 如果 endpoint 仍是默认 localhost（且你没起服务），直接走兜底，避免连接拒绝导致流程中.*?', 
     '# 如果 endpoint 仍是默认 localhost（且你没起服务），直接走兜底，避免连接拒绝导致流程中断'),
    (r'# 优先使用 DuckDuckGo（对爬虫更友好），Bing 作为备.*?', 
     '# 优先使用 DuckDuckGo（对爬虫更友好），Bing 作为备选'),
    # 第357行
    (r'# 1\) 优先走本.*?自建 SearxNG（最快、最稳、结构化.*?', 
     '# 1) 优先走本地自建 SearxNG（最快、最稳、结构化）'),
    # 第364行
    (r'# 2\) 兜底：HTML 搜索抓取（不依赖 8090.*?', 
     '# 2) 兜底：HTML 搜索抓取（不依赖 8090）'),
    # 第405行
    (r'"""只要 links 的便捷函数.*?"""', '"""只要 links 的便捷函数"""'),
    # 第422-423行
    (r'# 工具函数必须"尽量不抛异常"，否则会打断整.*?Agent 流程', 
     '# 工具函数必须"尽量不抛异常"，否则会打断整个Agent 流程'),
    (r'# 同时避免网络调用卡死：用线程超时兜底.*?', 
     '# 同时避免网络调用卡死：用线程超时兜底'),
]

# 应用所有修复
for pattern, replacement in fixes:
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# 删除所有替换字符（U+FFFD）
content = content.replace('\ufffd', '')

# 保存文件
with open('tools/search/websearch.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("修复完成！")

