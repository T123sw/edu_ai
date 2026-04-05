#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 MinerU 批量处理工具（简化交互版）\n")

    # 固定根路径
    CRAWL_ROOT = Path("~/TTT/data/Edu_AI/crawl/PDF").expanduser().resolve()
    OUTPUT_BASE = Path("~/projects/qiaoyue/output").expanduser().resolve()

    # 检查 crawl 根目录是否存在
    if not CRAWL_ROOT.exists():
        print(f"❌ 错误：crawl 根目录不存在 → {CRAWL_ROOT}")
        sys.exit(1)

    # 获取子文件夹名
    subfolder = input("请输入 crawl 下的子文件夹名称（如：复变函数）: ").strip()
    if not subfolder:
        print("⚠️ 子文件夹名称不能为空。")
        sys.exit(1)

    pdf_dir = CRAWL_ROOT / subfolder
    if not pdf_dir.exists():
        print(f"❌ 错误：子文件夹不存在 → {pdf_dir}")
        sys.exit(1)
    if not pdf_dir.is_dir():
        print(f"❌ 错误：{pdf_dir} 不是一个目录。")
        sys.exit(1)

    # 查找所有 PDF
    pdf_files = [p for p in pdf_dir.rglob("*.pdf") if p.is_file()]

    if not pdf_files:
        print(f"⚠️ 在 {pdf_dir} 中未找到任何 PDF 文件。")
        sys.exit(0)

    print(f"\n✅ 找到 {len(pdf_files)} 个 PDF 文件。")
    print("\n📁 预览（最多显示5个）:")
    for i, p in enumerate(pdf_files[:5], 1):
        print(f"  {i}. {p.name}")
    if len(pdf_files) > 5:
        print(f"  ... 还有 {len(pdf_files) - 5} 个文件")

    # 设置输出目录（与子文件夹同名）
    output_dir = OUTPUT_BASE / subfolder
    print(f"\n📤 输出目录: {output_dir}")

    confirm = input("\n❓ 确认开始处理？(y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("🛑 用户取消操作。")
        sys.exit(0)

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 开始处理
    success = 0
    failed = 0

    print("\n⏳ 开始处理...\n")
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}] 处理: {pdf_path.name}")
        cmd = ["mineru", "-p", str(pdf_path), "-o", str(output_dir)]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("    ✅ 成功\n")
            success += 1
        except subprocess.CalledProcessError as e:
            print(f"    ❌ 失败: {e.stderr.strip()}\n")
            failed += 1
        except Exception as e:
            print(f"    ❌ 异常: {e}\n")
            failed += 1

    # 总结
    print("🏁 处理完成！")
    print(f"   成功: {success}")
    print(f"   失败: {failed}")
    print(f"   总计: {len(pdf_files)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 操作被用户中断。")
        sys.exit(1)