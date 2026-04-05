"""
内容清洗模块
清洗和格式化爬取的内容
"""
import re
from pathlib import Path
from typing import Optional, Dict, Any
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import markdownify


class ContentCleaner:
    """内容清洗类"""
    
    @staticmethod
    def clean_text_content(
        content: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        清洗文本内容
        
        Args:
            content: 原始文本内容
            file_path: 文件路径（如果从文件读取）
        
        Returns:
            Dict包含清洗后的内容和元数据
        """
        original_content_length = len(content) if content else 0
        print(f"[清洗] 开始清洗文本内容，原始长度: {original_content_length} 字符")
        
        if file_path and Path(file_path).exists():
            try:
                file_size = Path(file_path).stat().st_size
                print(f"[清洗] 从文件读取: {file_path}, 文件大小: {file_size} 字节")
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    file_content_length = len(file_content)
                    print(f"[清洗] 文件读取内容长度: {file_content_length} 字符")
                    # 如果文件内容更长，使用文件内容
                    if file_content_length > original_content_length:
                        content = file_content
                        original_content_length = file_content_length
                        print(f"[清洗] 使用文件内容（更长）")
            except Exception as e:
                print(f"[清洗] 读取文件失败: {str(e)}")
                return {
                    "cleaned_content": "",
                    "error": f"读取文件失败: {str(e)}"
                }
        
        # 基本清洗
        cleaned = ContentCleaner._basic_clean(content)
        cleaned_length = len(cleaned)
        print(f"[清洗] 清洗后长度: {cleaned_length} 字符 (原始: {original_content_length})")
        
        # 提取元数据
        metadata = ContentCleaner._extract_metadata(content)
        
        # 转换为Markdown（如果需要）
        markdown_content = ContentCleaner._to_markdown(cleaned)
        
        result = {
            "cleaned_content": cleaned,
            "markdown_content": markdown_content,
            "metadata": metadata,
            "word_count": len(cleaned.split()),
            "char_count": len(cleaned)
        }
        print(f"[清洗] 返回结果，cleaned_content长度: {len(result['cleaned_content'])} 字符")
        return result
    
    @staticmethod
    def clean_pdf_content(file_path: str) -> Dict[str, Any]:
        """
        提取和清洗PDF内容
        
        Args:
            file_path: PDF文件路径
        
        Returns:
            Dict包含提取的文本和元数据
        """
        if not Path(file_path).exists():
            return {
                "cleaned_content": "",
                "error": "PDF文件不存在"
            }
        
        try:
            doc = fitz.open(file_path)
            text_parts = []
            metadata = {}
            
            # 提取元数据
            if doc.metadata:
                metadata = {
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "subject": doc.metadata.get("subject", ""),
                    "creator": doc.metadata.get("creator", ""),
                    "producer": doc.metadata.get("producer", ""),
                    "creation_date": doc.metadata.get("creationDate", ""),
                    "modification_date": doc.metadata.get("modDate", "")
                }
            
            # 提取每页文本
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
            
            doc.close()
            
            # 合并文本
            full_text = "\n\n".join(text_parts)
            full_text_length = len(full_text)
            print(f"[清洗] PDF提取完成，总页数: {len(doc)}, 提取文本长度: {full_text_length} 字符")
            
            # 清洗文本
            cleaned = ContentCleaner._basic_clean(full_text)
            cleaned_length = len(cleaned)
            print(f"[清洗] PDF清洗后长度: {cleaned_length} 字符 (原始: {full_text_length})")
            
            result = {
                "cleaned_content": cleaned,
                "markdown_content": cleaned,  # PDF文本通常不需要Markdown转换
                "metadata": metadata,
                "page_count": len(doc),
                "word_count": len(cleaned.split()),
                "char_count": len(cleaned)
            }
            print(f"[清洗] PDF返回结果，cleaned_content长度: {len(result['cleaned_content'])} 字符")
            return result
        
        except Exception as e:
            return {
                "cleaned_content": "",
                "error": f"PDF处理失败: {str(e)}"
            }
    
    @staticmethod
    def _basic_clean(text: str) -> str:
        """基本文本清洗"""
        if not text:
            return ""

        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 移除特殊控制字符（保留 \n 和 \t）
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        # 保留段落：不要把所有空白压成一个空格（会导致“挤在一起”）
        # 1) 每行内部多空格收敛
        text = "\n".join([re.sub(r"[ \t]{2,}", " ", line).rstrip() for line in text.split("\n")])
        # 2) 多个空行收敛
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        # 移除首尾空白
        text = text.strip()
        
        return text
    
    @staticmethod
    def _extract_metadata(content: str) -> Dict[str, Any]:
        """从内容中提取元数据"""
        metadata = {}
        
        # 尝试提取标题（第一行或前100字符）
        lines = content.split('\n')
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 200 and len(first_line) > 5:
                metadata["title"] = first_line
        
        # 提取可能的日期
        date_pattern = r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?'
        dates = re.findall(date_pattern, content[:1000])
        if dates:
            metadata["dates"] = dates[:3]  # 最多3个日期
        
        return metadata
    
    @staticmethod
    def _to_markdown(text: str) -> str:
        """
        将文本转换为Markdown格式
        这里做简单的格式化，复杂转换需要更高级的库
        """
        # 如果已经是 Markdown（来自 trafilatura 的 markdown 输出），直接返回以保留格式/代码块
        if "```" in text or text.lstrip().startswith("#") or "\n- " in text or "\n## " in text:
            # 确保代码块的语言标识不被破坏
            return ContentCleaner._preserve_code_blocks(text)

        # 简单的段落处理（兜底）
        lines = text.split('\n')
        markdown_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                markdown_lines.append('')
                continue
            
            # 检测可能的标题（短行且包含中文）
            if len(line) < 50 and any('\u4e00' <= c <= '\u9fff' for c in line):
                # 可能是标题，添加Markdown标题标记
                if not line.startswith('#'):
                    markdown_lines.append(f"## {line}")
                else:
                    markdown_lines.append(line)
            else:
                markdown_lines.append(line)
        
        return '\n'.join(markdown_lines)
    
    @staticmethod
    def _preserve_code_blocks(text: str) -> str:
        """
        确保代码块的语言标识被正确保留
        修复可能的格式问题（如 ```text 被误处理）
        """
        import re
        
        # 匹配代码块：```lang\n...\n```
        pattern = r'```(\w+)?\n(.*?)```'
        
        def normalize_code_block(match):
            lang = match.group(1) or ''
            code_content = match.group(2)
            
            # 如果语言标识为空或为 'text'，尝试检测
            if not lang or lang == 'text':
                # 简单检测：基于代码内容特征
                code_lower = code_content.lower().strip()
                if re.search(r'\b(def|import|from|class|lambda|yield|async|await|print\(|if __name__)', code_lower):
                    lang = 'python'
                elif re.search(r'\b(function|const|let|var|=>|console\.log|document\.)', code_lower):
                    lang = 'javascript'
                elif re.search(r'\b(public\s+(static\s+)?(void|class|int)|System\.out\.println)', code_lower):
                    lang = 'java'
                elif re.search(r'\b(#include|int\s+main|printf|cout\s*<<)', code_lower):
                    lang = 'cpp'
                elif re.search(r'\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE)', code_lower, re.IGNORECASE):
                    lang = 'sql'
                elif re.search(r'<[a-z][\s\S]*>', code_content[:200]):
                    lang = 'html'
                elif re.search(r'\{[^}]*:[^}]*\}', code_content[:500]):
                    lang = 'css'
                else:
                    lang = 'text'  # 保持默认
            
            return f"```{lang}\n{code_content}```"
        
        # 替换所有代码块
        normalized = re.sub(pattern, normalize_code_block, text, flags=re.DOTALL)
        return normalized
    
    @staticmethod
    def clean_html_content(html: str) -> str:
        """
        从HTML提取并清洗文本内容
        
        Args:
            html: HTML内容
        
        Returns:
            清洗后的文本
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 移除script和style标签
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 提取文本
            text = soup.get_text()
            
            # 清洗
            cleaned = ContentCleaner._basic_clean(text)
            
            return cleaned
        
        except Exception as e:
            return f"HTML解析失败: {str(e)}"

