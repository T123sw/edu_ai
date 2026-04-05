"""
修复websearch.py的编码问题 - 最终版本
"""
import re

# 读取文件
with open('tools/search/websearch.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# 修复第14行（索引13）
if '?' in lines[13] or '' in lines[13]:
    lines[13] = '    """从SerpAPI响应里提取url + title"""\n'
    print("修复第14行")

# 修复第29行（索引28）- 查找包含问题的行
for i in range(27, 35):
    if '使用谷歌搜索引擎' in lines[i] and ('?' in lines[i] or '' in lines[i]):
        # 保留全角括号，只修复乱码
        lines[i] = '    使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title\n'
        print(f"修复第{i+1}行")
        break

# 保存文件
with open('tools/search/websearch.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("修复完成！请运行: python test_websearch_fix.py")

