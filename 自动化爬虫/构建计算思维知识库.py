"""
构建"计算思维"课程知识库的爬虫脚本
根据计算思维知识图谱，批量抓取相关学习材料
"""
import os
import sys
from pathlib import Path

# 添加路径以便导入爬虫模块
sys.path.insert(0, str(Path(__file__).parent))

from src.selenium_way.get_PDF_links_by_keywords import pdf_runner
from src.selenium_way.Selenium_get_html import txt_runner
from src.selenium_way.CNKI import run as cnki_run

# 课程知识库路径
COURSE_KB_PATH = Path(r"D:\Edu_AI_1\Edu_AI\api\course_data\courses\computational-thinking\knowledge_base\documents")

# 计算思维相关关键词（根据知识图谱设计）
KEYWORDS_CONFIG = {
    "核心概念": [
        "计算思维",
        "计算思维基础",
        "Computational Thinking"
    ],
    "分解": [
        "问题分解",
        "系统分解",
        "模块化设计",
        "分治法",
        "递归算法"
    ],
    "模式识别": [
        "模式识别",
        "数据结构",
        "算法设计",
        "算法分析"
    ],
    "抽象": [
        "数据抽象",
        "抽象思维",
        "数据结构",
        "面向对象",
        "算法抽象"
    ],
    "算法": [
        "算法设计",
        "排序算法",
        "搜索算法",
        "图算法",
        "动态规划",
        "贪心算法"
    ]
}

def ensure_kb_directory():
    """确保知识库目录存在"""
    COURSE_KB_PATH.mkdir(parents=True, exist_ok=True)
    print(f"✓ 知识库目录已准备: {COURSE_KB_PATH}")

def crawl_pdfs(keywords_list, category_name, pages=2):
    """抓取PDF文件"""
    output_path = COURSE_KB_PATH / "pdf" / category_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"📚 开始抓取 {category_name} 类别的PDF文件")
    print(f"{'='*60}")
    
    for keyword in keywords_list:
        print(f"\n🔍 搜索关键词: {keyword}")
        try:
            pdf_runner(
                path=str(output_path.parent),  # 输出到pdf目录
                keywords=keyword,
                pages=pages,
                startpage=0
            )
            print(f"✓ {keyword} 抓取完成")
        except Exception as e:
            print(f"✗ {keyword} 抓取失败: {e}")

def crawl_texts(keywords_list, category_name, pages=2):
    """抓取网页文本"""
    output_path = COURSE_KB_PATH / "text" / category_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"📄 开始抓取 {category_name} 类别的文本内容")
    print(f"{'='*60}")
    
    for keyword in keywords_list:
        print(f"\n🔍 搜索关键词: {keyword}")
        try:
            txt_runner(
                path=str(COURSE_KB_PATH.parent),  # 输出到knowledge_base目录
                keywords=keyword,
                pages=pages
            )
            print(f"✓ {keyword} 抓取完成")
        except Exception as e:
            print(f"✗ {keyword} 抓取失败: {e}")

def crawl_cnki(keywords_list, category_name, pages=1):
    """抓取CNKI知网论文（需要配置账号）"""
    output_path = COURSE_KB_PATH / "cnki" / category_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"📖 开始抓取 {category_name} 类别的CNKI论文")
    print(f"{'='*60}")
    
    for keyword in keywords_list:
        print(f"\n🔍 搜索关键词: {keyword}")
        try:
            cnki_run(
                output_path=str(output_path),
                keyword=keyword,
                pages=pages
            )
            print(f"✓ {keyword} 抓取完成")
        except Exception as e:
            print(f"✗ {keyword} 抓取失败: {e}")

def main():
    """主函数：构建计算思维知识库"""
    print("="*60)
    print("🚀 开始构建'计算思维'课程知识库")
    print("="*60)
    
    # 确保目录存在
    ensure_kb_directory()
    
    # 询问用户要抓取的类型
    print("\n请选择要抓取的内容类型：")
    print("1. PDF文件（推荐，内容完整）")
    print("2. 网页文本（速度快，内容多样）")
    print("3. CNKI知网论文（需要账号，质量高）")
    print("4. 全部类型（最全面，但耗时较长）")
    
    choice = input("\n请输入选项 (1-4，默认1): ").strip() or "1"
    
    # 询问抓取页数
    pages = input("请输入每个关键词抓取的页数 (默认2): ").strip()
    pages = int(pages) if pages.isdigit() else 2
    
    # 询问是否抓取CNKI（需要账号）
    crawl_cnki_flag = False
    if choice in ["3", "4"]:
        cnki_confirm = input("\n⚠️  CNKI抓取需要配置账号，是否继续？(y/n，默认n): ").strip().lower()
        crawl_cnki_flag = (cnki_confirm == "y")
    
    # 开始抓取
    total_categories = len(KEYWORDS_CONFIG)
    current = 0
    
    for category_name, keywords_list in KEYWORDS_CONFIG.items():
        current += 1
        print(f"\n\n{'#'*60}")
        print(f"📂 处理类别 {current}/{total_categories}: {category_name}")
        print(f"关键词数量: {len(keywords_list)}")
        print(f"{'#'*60}")
        
        if choice in ["1", "4"]:
            crawl_pdfs(keywords_list, category_name, pages)
        
        if choice in ["2", "4"]:
            crawl_texts(keywords_list, category_name, pages)
        
        if choice in ["3", "4"] and crawl_cnki_flag:
            crawl_cnki(keywords_list, category_name, pages=1)  # CNKI默认只抓1页
    
    print("\n" + "="*60)
    print("✅ 知识库构建完成！")
    print("="*60)
    print(f"\n📁 文件保存位置:")
    print(f"   PDF: {COURSE_KB_PATH / 'pdf'}")
    print(f"   文本: {COURSE_KB_PATH / 'text'}")
    if crawl_cnki_flag:
        print(f"   CNKI: {COURSE_KB_PATH / 'cnki'}")
    print("\n💡 提示: 抓取的文件需要手动整理和筛选，建议:")
    print("   1. 检查文件质量，删除无关或低质量内容")
    print("   2. 重命名文件，使用有意义的名称")
    print("   3. 将优质文档移动到knowledge_base/documents根目录")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，已停止抓取")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

