#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式批量 Markdown 拆分工具（一次决策，全局应用）
支持：递归搜索 + 全局层级选择 + 代表性预览
"""

import os
import re
import sys
from pathlib import Path
from markdown_it import MarkdownIt


def safe_filename(title: str, index: int) -> str:
    if not title.strip():
        return f"section_{index:03d}.md"
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)
    clean = clean.strip()[:60]
    clean = clean or f"section_{index:03d}"
    return f"{index:03d}_{clean}.md"


def analyze_headings(md_text: str):
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(md_text)
    heading_info = {i: [] for i in range(1, 7)}
    i = 0
    while i < len(tokens):
        if tokens[i].type == "heading_open":
            level = int(tokens[i].tag[1])
            inline_tok = tokens[i + 1] if i + 1 < len(tokens) else None
            title = ""
            if inline_tok and inline_tok.type == "inline" and inline_tok.children:
                title = "".join(child.content for child in inline_tok.children).strip()
            heading_info[level].append(title)
        i += 1
    return heading_info


def split_by_level(md_text: str, min_level: int):
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(md_text)
    lines = md_text.splitlines(keepends=True)

    sections = []
    current_title = ""
    current_lines = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline_tok = tokens[i + 1] if i + 1 < len(tokens) else None
            title = ""
            if inline_tok and inline_tok.type == "inline" and inline_tok.children:
                title = "".join(child.content for child in inline_tok.children)

            if level >= min_level:
                if current_lines:
                    sections.append((current_title, "".join(current_lines)))
                start, end = tok.map
                current_title = title
                current_lines = list(lines[start:end])
                j = i + 2
                while j < len(tokens):
                    next_tok = tokens[j]
                    if next_tok.type == "heading_open":
                        break
                    if next_tok.map:
                        s, e = next_tok.map
                        if s >= end:
                            current_lines.extend(lines[s:e])
                            end = e
                    j += 1
                i = j
                continue
        i += 1

    if current_lines:
        sections.append((current_title, "".join(current_lines)))
    elif md_text.strip():
        sections.append(("", md_text))
    return sections


def preview_sections(sections, max_lines=4):
    print("\n🔍 拆分预览（每节前{}行）：".format(max_lines))
    print("-" * 60)
    for i, (title, content) in enumerate(sections[:3], 1):
        print(f"\n📄 节 {i}: '{title or '(无标题)'}'")
        lines = content.strip().splitlines()[:max_lines]
        for line in lines:
            print(f"  > {line[:80]}{'...' if len(line) > 80 else ''}")
        if len(sections) > 3 and i == 3:
            print(f"  ... 还有 {len(sections) - 3} 节")
            break
    print("-" * 60)


def _save_sections(sections, base_name: str, output_dir: Path):
    file_output_dir = output_dir / base_name
    file_output_dir.mkdir(parents=True, exist_ok=True)
    for idx, (title, content) in enumerate(sections, 1):
        filename = safe_filename(title, idx)
        filepath = file_output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    print("📚 批量 Markdown 拆分工具（一次决策，全局应用）")
    print("=" * 60)

    # 输入目录
    while True:
        input_path_str = input("请输入包含 Markdown 文件的目录路径: ").strip()
        input_dir = Path(input_path_str).resolve()
        if input_dir.is_dir():
            break
        print("❌ 路径无效或不是目录，请重试。")

    # 递归查找所有 .md 文件
    md_files = sorted([f for f in input_dir.rglob("*.md") if f.is_file()])
    if not md_files:
        print("⚠️  该目录及其子目录下没有 .md 文件。")
        return

    print(f"\n📂 找到 {len(md_files)} 个 Markdown 文件（递归搜索）")

    # === 第一步：收集所有文件中出现的标题层级 ===
    all_levels = set()
    sample_file = None
    sample_text = ""

    print("\n🔍 正在分析标题结构（最多扫描前5个非空文件）...")
    scanned = 0
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8").strip()
            if not text:
                continue
            heading_info = analyze_headings(text)
            levels_in_file = {lvl for lvl, titles in heading_info.items() if titles}
            all_levels.update(levels_in_file)
            if sample_file is None:
                sample_file = f
                sample_text = text
            scanned += 1
            if scanned >= 5:  # 避免大文件卡顿
                break
        except Exception as e:
            print(f"  ⚠️ 跳过文件 {f.name}: {e}")

    if not all_levels:
        print("\n⚠️  所有文件均未检测到 Markdown 标题。")
        handle_no_heading = input(
            "是否将所有文件保存为单章节？(y/n) [默认 y]: "
        ).strip().lower()
        if handle_no_heading in ('n', 'no'):
            print("❌ 操作取消")
            return
        # 全部作为单文件处理
        output_dir = Path(input("请输入输出目录名 [默认: split_output]: ").strip() or "split_output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        for f in md_files:
            try:
                text = f.read_text(encoding="utf-8")
                _save_sections([("", text)], f.stem, output_dir)
            except Exception as e:
                print(f"❌ 处理 {f.name} 失败: {e}")
        print(f"\n🎉 成功保存 {len(md_files)} 个完整文件到 {output_dir}")
        return

    # === 第二步：用户选择全局拆分层级 ===
    available_levels = sorted(all_levels)
    print(f"\n📊 在文件中检测到的标题层级: {available_levels}")

    # 默认策略：优先 2 或 3
    default_level = 3 if 3 in available_levels else (2 if 2 in available_levels else min(available_levels))
    print(f"💡 建议使用层级: {default_level}（适合章节/小节拆分）")

    while True:
        choice = input(
            f"\n请选择全局最小拆分层级 {available_levels}，或回车使用默认 ({default_level}): "
        ).strip()
        if choice == "":
            chosen_level = default_level
            break
        elif choice.isdigit() and int(choice) in available_levels:
            chosen_level = int(choice)
            break
        else:
            print(f"❌ 请输入有效层级: {available_levels}")

    # === 第三步：预览（使用 sample_file）===
    print(f"\n🎯 将对所有文件按层级 ≥{chosen_level} 拆分")
    sections = split_by_level(sample_text, chosen_level)
    print(f"📌 预览文件: {sample_file.relative_to(input_dir)} → 拆分为 {len(sections)} 节")
    do_preview = input("是否预览拆分效果？(y/n) [默认 y]: ").strip().lower()
    if do_preview != 'n':
        preview_sections(sections)

    confirm = input("\n确认对所有文件应用此拆分策略？(y/n) [默认 y]: ").strip().lower()
    if confirm == 'n':
        print("❌ 操作已取消")
        return

    # === 第四步：批量处理 ===
    output_dir = Path(input("请输入输出目录名 [默认: split_output]: ").strip() or "split_output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8")
            heading_info = analyze_headings(text)
            has_heading = any(titles for titles in heading_info.values())
            if not has_heading:
                # 无标题：保存为单文件
                sections = [("", text)]
            else:
                sections = split_by_level(text, chosen_level)
            _save_sections(sections, f.stem, output_dir)
            success += 1
        except Exception as e:
            print(f"❌ 处理失败 {f.name}: {e}")

    print(f"\n🎉 完成！成功处理 {success}/{len(md_files)} 个文件")
    print(f"📁 输出目录: {output_dir}")


if __name__ == "__main__":
    main()