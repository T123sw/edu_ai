"""
当用户有指定url时，用这个文件
"""
import os
import trafilatura  #自动处理文本
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import time
import random
import re
from bs4 import BeautifulSoup
from methods import download_one,download_txt
from setup import *


class crawle_url(object):
    def __init__(self, urls, output_path):
        options = uc.ChromeOptions()

        # options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
        options.add_argument(f"user-agent={user_agent}")
        # undetected_chromedriver会自动管理ChromeDriver版本
        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)
        self.urls = urls if urls else None
        self.output_path = output_path
    def split_urls(self):
        if self.urls is None:
            return False
        else:
            parts = [k.strip() for k in self.urls.split("\n") if k.strip()]
            self.urls = parts
            return True

    def restart_driver(self):
        try:
            self.driver.quit()
        except:
            pass

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")

        # undetected_chromedriver会自动管理ChromeDriver版本
        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.implicitly_wait(timeout)

    def is_driver_alive(self):
        try:
            _ = self.driver.title
            return True
        except:
            return False

    def extract_filename_from_url(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        base_name = os.path.basename(path)
        if '.' in base_name:
            filename_without_ext = os.path.splitext(base_name)[0]
            if filename_without_ext.lower().endswith('.pdf'):
                filename_without_ext = os.path.splitext(filename_without_ext)[0]
            return filename_without_ext
        else:
            return base_name
    
    @staticmethod
    def detect_code_language(code_element, code_text, url=""):
        """
        检测代码块的语言类型
        
        Args:
            code_element: BeautifulSoup 的 code/pre 元素
            code_text: 代码文本内容
            url: 页面URL（用于辅助判断）
        
        Returns:
            语言标识符（如 'python', 'javascript', 'java' 等），无法识别时返回 'text'
        """
        # 1. 从HTML class属性检测（最常见）
        if code_element:
            classes = code_element.get('class', [])
            for cls in classes:
                cls_lower = cls.lower()
                # 常见格式: language-python, hljs python, code-python, lang-python
                if 'python' in cls_lower:
                    return 'python'
                elif 'javascript' in cls_lower or 'js' in cls_lower:
                    return 'javascript'
                elif 'java' in cls_lower and 'javascript' not in cls_lower:
                    return 'java'
                elif 'cpp' in cls_lower or 'c++' in cls_lower:
                    return 'cpp'
                elif 'c' in cls_lower and 'cpp' not in cls_lower and 'css' not in cls_lower:
                    return 'c'
                elif 'html' in cls_lower:
                    return 'html'
                elif 'css' in cls_lower:
                    return 'css'
                elif 'sql' in cls_lower:
                    return 'sql'
                elif 'bash' in cls_lower or 'shell' in cls_lower:
                    return 'bash'
                elif 'json' in cls_lower:
                    return 'json'
                elif 'xml' in cls_lower:
                    return 'xml'
                elif 'go' in cls_lower or 'golang' in cls_lower:
                    return 'go'
                elif 'rust' in cls_lower:
                    return 'rust'
                elif 'php' in cls_lower:
                    return 'php'
                elif 'ruby' in cls_lower:
                    return 'ruby'
                elif 'swift' in cls_lower:
                    return 'swift'
                elif 'kotlin' in cls_lower:
                    return 'kotlin'
                elif 'typescript' in cls_lower or 'ts' in cls_lower:
                    return 'typescript'
                elif 'scala' in cls_lower:
                    return 'scala'
                elif 'r' in cls_lower and len(cls_lower) == 1:
                    return 'r'
                elif 'matlab' in cls_lower:
                    return 'matlab'
            
            # 检查 data-lang, data-language 等属性
            for attr in ['data-lang', 'data-language', 'lang', 'language']:
                lang_val = code_element.get(attr, '').lower()
                if lang_val:
                    # 标准化常见变体
                    lang_map = {
                        'js': 'javascript', 'ts': 'typescript', 'py': 'python',
                        'cpp': 'cpp', 'c++': 'cpp', 'cxx': 'cpp',
                        'sh': 'bash', 'shell': 'bash', 'zsh': 'bash',
                        'rb': 'ruby', 'rs': 'rust', 'kt': 'kotlin',
                        'go': 'go', 'golang': 'go',
                    }
                    if lang_val in lang_map:
                        return lang_map[lang_val]
                    return lang_val.split()[0]  # 取第一个词
        
        # 2. 从代码内容特征检测（基于关键字）
        code_lower = code_text.lower().strip()
        if not code_lower:
            return 'text'
        
        # Python 特征
        if re.search(r'\b(def|import|from|class|lambda|yield|async|await|print\(|if __name__)', code_lower):
            return 'python'
        
        # JavaScript 特征
        if re.search(r'\b(function|const|let|var|=>|console\.log|document\.|window\.)', code_lower):
            return 'javascript'
        
        # Java 特征
        if re.search(r'\b(public\s+(static\s+)?(void|class|int)|System\.out\.println|package\s+)', code_lower):
            return 'java'
        
        # C/C++ 特征
        if re.search(r'\b(#include|int\s+main|printf|cout\s*<<|using\s+namespace)', code_lower):
            return 'cpp'
        
        # SQL 特征
        if re.search(r'\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE\s+TABLE)', code_lower, re.IGNORECASE):
            return 'sql'
        
        # HTML 特征
        if re.search(r'<[a-z][\s\S]*>', code_text[:200]):
            return 'html'
        
        # CSS 特征
        if re.search(r'\{[^}]*:[^}]*\}', code_text[:500]):
            return 'css'
        
        # JSON 特征
        if code_text.strip().startswith('{') or code_text.strip().startswith('['):
            try:
                import json
                json.loads(code_text)
                return 'json'
            except:
                pass
        
        # Bash/Shell 特征
        if re.search(r'^\s*#!/(usr/)?bin/(bash|sh|zsh)', code_text, re.MULTILINE):
            return 'bash'
        
        # 3. 从URL路径辅助判断（弱信号）
        if url:
            url_lower = url.lower()
            lang_patterns = {
                'python': ['python', 'py'],
                'javascript': ['javascript', 'js', 'node'],
                'java': ['java'],
                'cpp': ['cpp', 'c++'],
                'go': ['go', 'golang'],
            }
            for lang, keywords in lang_patterns.items():
                if any(kw in url_lower for kw in keywords):
                    return lang
        
        return 'text'  # 默认
    
    @staticmethod
    def _enhance_code_blocks(markdown_text, url=""):
        """
        增强 Markdown 中的代码块，为缺少语言标识的代码块添加语言检测
        
        Args:
            markdown_text: 包含代码块的 Markdown 文本
            url: 页面URL（用于辅助判断）
        
        Returns:
            增强后的 Markdown 文本
        """
        if not markdown_text or "```" not in markdown_text:
            return markdown_text
        
        # 匹配所有代码块：```lang 或 ```（无语言）
        pattern = r'```(\w+)?\n(.*?)```'
        
        def replace_code_block(match):
            lang = match.group(1) or ''
            code_content = match.group(2)
            
            # 如果已有语言标识，保持不变
            if lang and lang != 'text':
                return match.group(0)
            
            # 检测语言
            detected_lang = crawle_url.detect_code_language(None, code_content, url)
            return f"```{detected_lang}\n{code_content}```"
        
        # 替换所有代码块
        enhanced = re.sub(pattern, replace_code_block, markdown_text, flags=re.DOTALL)
        return enhanced

    def txt_url(self,url):
        if not self.is_driver_alive():
            self.restart_driver()
        output_path = os.path.join(self.output_path, "output","urls","text")
        os.makedirs(output_path, exist_ok=True)
        try:
            print(url)
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            html = self.driver.page_source
            html = html.encode('utf-8', errors='replace').decode('utf-8')

            # 优先输出 markdown，尽量保留段落/列表/标题（以及可能的代码块）
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_formatting=True,
                include_links=True,
                output_format="markdown",
            )

            # 兜底：如果 trafilatura 没提取到代码块，尝试从 HTML 的 <pre>/<code> 中补充
            try:
                soup = BeautifulSoup(html, "lxml")
                
                # 检查 trafilatura 是否已提取代码块
                has_code_blocks = "```" in (text or "")
                
                # 提取所有代码块（<pre> 或 <code>）
                code_elements = []
                # 优先找 <pre><code> 组合
                for pre in soup.find_all("pre"):
                    code_inside = pre.find("code")
                    if code_inside:
                        code_elements.append((code_inside, pre.get_text("\n")))
                    else:
                        code_elements.append((pre, pre.get_text("\n")))
                
                # 也找独立的 <code>（如果内容较长，可能是代码块）
                for code in soup.find_all("code"):
                    code_text = code.get_text("\n").strip()
                    if len(code_text) > 50 and code.parent.name != 'pre':  # 避免重复
                        code_elements.append((code, code_text))
                
                if code_elements:
                    # 去重（基于内容相似度）
                    seen_texts = set()
                    unique_blocks = []
                    for elem, code_text in code_elements:
                        code_text_clean = code_text.strip()
                        if len(code_text_clean) < 20:
                            continue
                        # 简单去重：如果内容几乎相同，跳过
                        text_hash = hash(code_text_clean[:200])
                        if text_hash not in seen_texts:
                            seen_texts.add(text_hash)
                            unique_blocks.append((elem, code_text_clean))
                    
                    if unique_blocks:
                        # 如果 trafilatura 没提取到代码块，追加
                        if not has_code_blocks:
                            extra = "\n\n## 代码片段（自动提取）\n"
                        else:
                            extra = "\n\n## 补充代码片段\n"
                        
                        for elem, code_text in unique_blocks[:10]:  # 最多10个
                            lang = crawle_url.detect_code_language(elem, code_text, url)
                            extra += f"\n```{lang}\n{code_text}\n```\n"
                        
                        text = (text or "") + extra
                
                # 如果 trafilatura 已提取代码块但缺少语言标识，尝试补充
                if has_code_blocks and text:
                    text = crawle_url._enhance_code_blocks(text, url)
                    
            except Exception as e:
                print(f"[WARN] 代码块提取失败: {e}")
                pass

            filename = self.extract_filename_from_url(url)
            arg = (output_path, text, filename)
            download_txt(arg)
            return True
        except Exception as e:
            print("[ERROR] 抓取正文失败：", e)
            return False

    def pdf_url(self,url):
        output_path = os.path.join(self.output_path, "output/urls/pdf")
        os.makedirs(output_path, exist_ok=True)

        filename = self.extract_filename_from_url(url)
        arg = (output_path, url, filename)
        return download_one(arg)

    def close(self):
        if self.driver:
            self.driver.quit()

    def run(self):
        if not self.urls:
            print("[ERROR] 没有可处理的URL")
            return
        self.split_urls()
        success_count = 0
        fail_count = 0

        for idx, url in enumerate(self.urls, 1):
            print(f"\n[INFO] 正在处理第 {idx}/{len(self.urls)} 个URL")

            try:
                if url.lower().endswith('.pdf'):
                   result = self.pdf_url(url)
                else:
                    result = self.txt_url(url)

                if result:
                    success_count += 1
                else:
                    fail_count += 1

                time.sleep(random.uniform(1, 4))

            except Exception as e:
                print(f"[ERROR] 处理 {url} 时发生未预期错误: {e}")
                fail_count += 1

        # 输出统计信息
        print(f"\n[SUMMARY] 任务完成 - 成功: {success_count}, 失败: {fail_count}")

if __name__ == "__main__":
    urls = "https://zhuanlan.zhihu.com/p/17997528668\n"
    d = "https://www.nhc.gov.cn/ewebeditor/uploadfile/2018/05/20180516113316628.pdf"
    output_path = "./output"
    os.makedirs(output_path, exist_ok=True)
    urls = urls+d
    c = crawle_url(d, output_path)
    c.run()