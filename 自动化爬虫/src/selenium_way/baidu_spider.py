"""
百度搜索爬虫模块
通过百度搜索获取PDF文件链接并下载
"""
import os
import re
import time
import random
import requests
from pathlib import Path
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

def fetch_pdf_links(keyword: str, pages: int = 1):
    """
    从百度搜索结果中提取PDF链接
    
    Args:
        keyword: 搜索关键词
        pages: 搜索页数
    
    Returns:
        list: PDF链接列表
    """
    links = []
    
    for pn in range(0, pages * 10, 10):
        try:
            url = f"https://www.baidu.com/s?wd={keyword}%20filetype%3Apdf&pn={pn}"
            print(f"正在搜索第 {pn//10 + 1} 页: {keyword}")
            
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 查找所有链接
            for a in soup.select('a[href]'):
                href = a.get('href')
                if href and '.pdf' in href.lower():
                    # 处理重定向链接
                    if 'http' in href:
                        links.append(href)
            
            # 随机延时，避免被封
            time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            print(f"搜索第 {pn//10 + 1} 页时出错: {e}")
            continue
    
    # 去重
    unique_links = list(dict.fromkeys(links))
    print(f"找到 {len(unique_links)} 个PDF链接")
    return unique_links

def download_pdfs(links, save_dir: Path, max_files: int = 10):
    """
    下载PDF文件
    
    Args:
        links: PDF链接列表
        save_dir: 保存目录
        max_files: 最大下载文件数
    
    Returns:
        list: 成功下载的文件路径列表
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    downloaded_files = []
    
    for i, link in enumerate(links[:max_files], 1):
        try:
            print(f"正在下载第 {i}/{min(len(links), max_files)} 个文件: {link[:50]}...")
            
            # 获取文件信息
            head_response = requests.head(link, headers=HEADERS, timeout=10, allow_redirects=True)
            
            # 如果HEAD请求失败，尝试GET请求
            if not head_response.ok:
                response = requests.get(link, headers=HEADERS, stream=True, timeout=20)
            else:
                response = head_response
            
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' not in content_type and 'octet-stream' not in content_type:
                print(f"跳过非PDF文件: {link}")
                continue
            
            # 生成文件名
            filename = re.sub(r'[\\\\/:*?"<>|]', '_', link.split('/')[-1])
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            
            # 限制文件名长度
            if len(filename) > 60:
                filename = filename[:57] + '.pdf'
            
            file_path = save_dir / filename
            
            # 下载文件
            if not head_response.ok:
                response = requests.get(link, headers=HEADERS, stream=True, timeout=20)
            
            if response.ok:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # 验证文件大小
                if file_path.stat().st_size > 1024:  # 大于1KB
                    downloaded_files.append(str(file_path))
                    print(f"下载成功: {filename}")
                else:
                    file_path.unlink(missing_ok=True)
                    print(f"文件过小，已删除: {filename}")
            else:
                print(f"下载失败: {link} - HTTP {response.status_code}")
                
        except Exception as e:
            print(f"下载失败 {link}: {e}")
            continue
        
        # 下载间隔
        time.sleep(random.uniform(0.5, 1.5))
    
    return downloaded_files

def run(out_dir: str, keyword: str, pages: int = 1, max_files: int = 10):
    """
    运行百度爬虫
    
    Args:
        out_dir: 输出目录
        keyword: 搜索关键词
        pages: 搜索页数
        max_files: 最大下载文件数
    
    Returns:
        list: 下载的PDF文件路径列表
    """
    print(f"开始百度爬虫: 关键词='{keyword}', 页数={pages}, 最大文件数={max_files}")
    
    # 创建输出目录
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 搜索PDF链接
    pdf_links = fetch_pdf_links(keyword, pages)
    
    if not pdf_links:
        print("未找到任何PDF链接")
        return []
    
    # 下载PDF文件
    downloaded_files = download_pdfs(pdf_links, out_path, max_files)
    
    print(f"百度爬虫完成: 找到 {len(pdf_links)} 个链接，下载 {len(downloaded_files)} 个文件")
    return downloaded_files

if __name__ == "__main__":
    # 测试代码
    test_keyword = "数据结构"
    test_pages = 1
    test_max_files = 5
    
    result = run("./test_output", test_keyword, test_pages, test_max_files)
    print(f"测试结果: {result}")
