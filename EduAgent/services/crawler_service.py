"""
爬虫服务模块
封装自动化爬虫模块的调用，提供批量爬取URL的功能
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import os

# 添加自动化爬虫模块到路径
SPIDER_MODULE_PATH = Path(__file__).resolve().parent.parent.parent / "自动化爬虫" / "src" / "selenium_way"
SPIDER_ROOT_PATH = Path(__file__).resolve().parent.parent.parent / "自动化爬虫" / "src"

# 添加多个路径以确保能找到所有依赖
paths_to_add = [
    str(SPIDER_MODULE_PATH),
    str(SPIDER_ROOT_PATH),
]

for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    # 尝试导入setup（可能失败，但不影响主要功能）
    try:
        import setup
    except ImportError:
        # setup.py可能依赖automation_spider.config，如果不存在就创建兼容配置
        try:
            # 尝试导入我们的兼容setup
            import sys
            compat_setup_path = Path(__file__).parent / "spider_setup.py"
            if compat_setup_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("spider_setup", compat_setup_path)
                spider_setup = importlib.util.module_from_spec(spec)
                sys.modules["setup"] = spider_setup
                spec.loader.exec_module(spider_setup)
        except Exception:
            # 如果都失败，创建一个最小化的setup模块
            import types
            setup = types.ModuleType("setup")
            setup.timeout = 10
            sys.modules["setup"] = setup
    
    # 导入爬虫类
    from crawle_url import crawle_url
except ImportError as e:
    print(f"[WARNING] 无法导入爬虫模块: {e}")
    print(f"[DEBUG] 尝试的路径: {SPIDER_MODULE_PATH}")
    print(f"[DEBUG] 路径是否存在: {SPIDER_MODULE_PATH.exists()}")
    if SPIDER_MODULE_PATH.exists():
        print(f"[DEBUG] 目录内容: {list(SPIDER_MODULE_PATH.iterdir())[:5]}")
    crawle_url = None

from models.crawl_result import CrawlResult, CrawlBatchResult
from define import ROOT_DIR


class CrawlerService:
    """爬虫服务类"""
    
    def __init__(self, output_base_path: Optional[Path] = None):
        """
        初始化爬虫服务
        
        Args:
            output_base_path: 输出基础路径，默认为 ROOT_DIR / "crawled_data"
        """
        self.output_base_path = output_base_path or (ROOT_DIR / "crawled_data")
        self.output_base_path.mkdir(parents=True, exist_ok=True)
    
    def crawl_urls(
        self, 
        urls: List[str], 
        query: str = "unknown",
        max_urls: Optional[int] = None,
        timeout_per_url: int = 30,
    ) -> CrawlBatchResult:
        """
        批量爬取URL列表
        
        Args:
            urls: URL列表
            query: 查询关键词（用于组织输出目录）
            max_urls: 最多爬取的URL数量
            timeout_per_url: 单个URL爬取超时时间（秒）
        
        Returns:
            CrawlBatchResult: 批量爬取结果
        """
        if crawle_url is None:
            return CrawlBatchResult(
                query=query,
                total_urls=len(urls),
                failed_count=len(urls),
                results=[
                    CrawlResult(
                        url=url,
                        status="failed",
                        error_message="爬虫模块未正确导入"
                    ) for url in urls
                ]
            )
        
        # 限制URL数量
        if max_urls:
            urls = urls[:max_urls]
        
        # 创建输出目录
        query_safe = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        output_path = self.output_base_path / query_safe
        output_path.mkdir(parents=True, exist_ok=True)
        
        
        results = []
        success_count = 0
        failed_count = 0

        # 创建爬虫实例
        crawler = crawle_url("\n".join(urls), str(output_path))

        try:
            # 执行爬取
            crawler.run()

            # 处理结果
            for url in urls:
                result = self._process_crawl_result(url, output_path, query_safe)
                results.append(result)

                if result.status == "success":
                    success_count += 1
                else:
                    failed_count += 1

        except Exception as e:
            # 如果整体爬取失败，为每个URL创建失败结果
            for url in urls:
                if not any(r.url == url for r in results):
                    results.append(CrawlResult(
                        url=url,
                        status="failed",
                        error_message=f"爬取过程异常: {str(e)}",
                        crawled_at=datetime.now()
                    ))
                    failed_count += 1

        finally:
            # 确保关闭浏览器驱动
            try:
                crawler.close()
            except Exception:
                pass
        
        return CrawlBatchResult(
            query=query,
            total_urls=len(urls),
            success_count=success_count,
            failed_count=failed_count,
            results=results
        )
    
    def _process_crawl_result(
        self, 
        url: str, 
        output_path: Path,
        query_safe: str
    ) -> CrawlResult:
        """
        处理单个URL的爬取结果
        
        Args:
            url: URL地址
            output_path: 输出路径
            query_safe: 安全的查询字符串（用于路径）
        
        Returns:
            CrawlResult: 爬取结果
        """
        result = CrawlResult(
            url=url,
            status="failed",
            crawled_at=datetime.now()
        )
        
        try:
            # 判断URL类型
            is_pdf = url.lower().endswith('.pdf')
            
            if is_pdf:
                # PDF文件路径
                pdf_dir = output_path / "output" / "urls" / "pdf"
                result.content_type = "pdf"
                
                # 查找对应的PDF文件
                if pdf_dir.exists():
                    # 从URL提取文件名
                    filename = self._extract_filename_from_url(url)
                    pdf_file = pdf_dir / f"{filename}.pdf"
                    
                    # 尝试多种可能的文件名
                    if not pdf_file.exists():
                        for f in pdf_dir.glob("*.pdf"):
                            # 检查文件名是否匹配
                            if filename.lower() in f.stem.lower():
                                pdf_file = f
                                break
                    
                    if pdf_file.exists():
                        result.file_path = str(pdf_file)
                        result.status = "success"
                        result.title = pdf_file.stem
            else:
                # 文本文件路径
                text_dir = output_path / "output" / "urls" / "text"
                result.content_type = "text"
                
                if text_dir.exists():
                    # 从URL提取文件名
                    filename = self._extract_filename_from_url(url)
                    text_file = text_dir / f"{filename}.txt"
                    
                    # 尝试多种可能的文件名
                    if not text_file.exists():
                        for f in text_dir.glob("*.txt"):
                            if filename.lower() in f.stem.lower():
                                text_file = f
                                break
                    
                    if text_file.exists():
                        result.file_path = str(text_file)
                        result.status = "success"
                        
                        # 读取文件内容（完整读取，不截断）
                        try:
                            file_size = text_file.stat().st_size
                            print(f"[爬取] URL: {url}")
                            print(f"[爬取] 文件路径: {text_file}")
                            print(f"[爬取] 文件大小: {file_size} 字节")
                            
                            with open(text_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                content_length = len(content)
                                print(f"[爬取] 读取内容长度: {content_length} 字符")
                                
                                # 保存完整内容（不截断）
                                result.content = content
                                result.title = text_file.stem

                                image_dir = output_path / "output" / "urls" / "images" / text_file.stem
                                if image_dir.exists():
                                    manifest_path = image_dir / "_manifest.json"
                                    if manifest_path.exists():
                                        try:
                                            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                                                image_assets = json.load(manifest_file)
                                            result.metadata["image_assets"] = image_assets
                                            result.metadata["image_paths"] = [
                                                asset["file_path"]
                                                for asset in image_assets
                                                if isinstance(asset, dict) and asset.get("file_path")
                                            ]
                                        except Exception as manifest_error:
                                            print(f"[爬取] 读取图片清单失败: {manifest_error}")
                                    else:
                                        result.metadata["image_paths"] = [
                                            str(path)
                                            for path in sorted(image_dir.iterdir())
                                            if path.is_file()
                                        ]

                                site_icon_dir = output_path / "output" / "urls" / "site_icons"
                                if site_icon_dir.exists():
                                    matching_icons = sorted(site_icon_dir.glob(f"{text_file.stem}_*"))
                                    if matching_icons:
                                        result.metadata["site_icon_path"] = str(matching_icons[0])
                                
                                print(f"[爬取] 保存到result.content的长度: {len(result.content)} 字符")
                                print(f"[爬取] 前100字符预览: {result.content[:100]}...")
                        except Exception as e:
                            print(f"[爬取] 读取文件失败: {str(e)}")
                            result.error_message = f"读取文件失败: {str(e)}"
        
        except Exception as e:
            result.error_message = f"处理结果失败: {str(e)}"
            result.status = "failed"
        
        return result
    
    def _extract_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        from urllib.parse import urlparse
        import os
        
        parsed = urlparse(url)
        path = parsed.path
        base_name = os.path.basename(path)
        
        if '.' in base_name:
            filename_without_ext = os.path.splitext(base_name)[0]
            if filename_without_ext.lower().endswith('.pdf'):
                filename_without_ext = os.path.splitext(filename_without_ext)[0]
            return filename_without_ext
        else:
            return base_name or "untitled"


# 单例实例
_crawler_service_instance: Optional[CrawlerService] = None


def get_crawler_service() -> CrawlerService:
    """获取爬虫服务单例"""
    global _crawler_service_instance
    if _crawler_service_instance is None:
        _crawler_service_instance = CrawlerService()
    return _crawler_service_instance
