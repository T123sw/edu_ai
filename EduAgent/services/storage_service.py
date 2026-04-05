"""
存储服务模块
管理爬取结果的存储和查询
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib

from models.crawl_result import CrawlResult, CrawlBatchResult
from define import ROOT_DIR


class StorageService:
    """存储服务类"""
    
    def __init__(self, storage_base_path: Optional[Path] = None):
        """
        初始化存储服务
        
        Args:
            storage_base_path: 存储基础路径，默认为 ROOT_DIR / "crawled_data"
        """
        self.storage_base_path = storage_base_path or (ROOT_DIR / "crawled_data")
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
    
    def save_crawl_batch(self, batch_result: CrawlBatchResult) -> str:
        """
        保存批量爬取结果
        
        Args:
            batch_result: 批量爬取结果
        
        Returns:
            batch_id: 批次ID
        """
        # 生成批次ID（基于查询和时间戳）
        batch_id = self._generate_batch_id(batch_result.query)
        
        # 创建批次目录
        batch_dir = self.storage_base_path / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存元数据
        metadata = {
            "batch_id": batch_id,
            "query": batch_result.query,
            "total_urls": batch_result.total_urls,
            "success_count": batch_result.success_count,
            "failed_count": batch_result.failed_count,
            "created_at": batch_result.created_at.isoformat()
        }
        
        metadata_file = batch_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 保存每个结果
        results_data = []
        for result in batch_result.results:
            result_data = result.dict()
            result_data["crawled_at"] = result.crawled_at.isoformat() if result.crawled_at else None
            
            # 保存内容到单独文件（如果内容较长）
            if result.content and len(result.content) > 1000:
                content_file = batch_dir / f"{self._url_hash(result.url)}_content.txt"
                with open(content_file, 'w', encoding='utf-8') as f:
                    f.write(result.content)
                result_data["content_file"] = str(content_file)
                result_data["content"] = result.content[:500]  # 只保留预览
            
            results_data.append(result_data)
        
        # 保存结果列表
        results_file = batch_dir / "results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        return batch_id
    
    def load_crawl_batch(self, batch_id: str) -> Optional[CrawlBatchResult]:
        """
        加载批量爬取结果
        
        Args:
            batch_id: 批次ID
        
        Returns:
            CrawlBatchResult 或 None
        """
        batch_dir = self.storage_base_path / batch_id
        
        if not batch_dir.exists():
            return None
        
        # 加载元数据
        metadata_file = batch_dir / "metadata.json"
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 加载结果
        results_file = batch_dir / "results.json"
        if not results_file.exists():
            return None
        
        with open(results_file, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
        
        # 恢复完整内容
        for result_data in results_data:
            if "content_file" in result_data:
                content_file = Path(result_data["content_file"])
                if content_file.exists():
                    with open(content_file, 'r', encoding='utf-8') as f:
                        result_data["content"] = f.read()
                del result_data["content_file"]
            
            # 恢复datetime
            if result_data.get("crawled_at"):
                result_data["crawled_at"] = datetime.fromisoformat(result_data["crawled_at"])
        
        results = [CrawlResult(**r) for r in results_data]
        
        return CrawlBatchResult(
            query=metadata["query"],
            total_urls=metadata["total_urls"],
            success_count=metadata["success_count"],
            failed_count=metadata["failed_count"],
            results=results,
            created_at=datetime.fromisoformat(metadata["created_at"])
        )
    
    def list_batches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出所有批次
        
        Args:
            limit: 返回数量限制
        
        Returns:
            批次列表
        """
        batches = []
        
        for batch_dir in self.storage_base_path.iterdir():
            if not batch_dir.is_dir():
                continue
            
            metadata_file = batch_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                batches.append({
                    "batch_id": metadata["batch_id"],
                    "query": metadata["query"],
                    "total_urls": metadata["total_urls"],
                    "success_count": metadata["success_count"],
                    "failed_count": metadata["failed_count"],
                    "created_at": metadata["created_at"]
                })
            except:
                continue
        
        # 按创建时间排序（最新的在前）
        batches.sort(key=lambda x: x["created_at"], reverse=True)
        
        return batches[:limit]
    
    def _generate_batch_id(self, query: str) -> str:
        """生成批次ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()[:8]
        return f"{timestamp}_{query_hash}"
    
    def _url_hash(self, url: str) -> str:
        """生成URL的哈希值"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:16]


# 单例实例
_storage_service_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """获取存储服务单例"""
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = StorageService()
    return _storage_service_instance

