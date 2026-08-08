from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def generate(output: Path) -> None:
    width, height = 1400, 820
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = _font(38, bold=True)
    heading_font = _font(28, bold=True)
    body_font = _font(22)
    small_font = _font(18)

    draw.text((52, 34), "从连续信息到离散编码：像素与声音采样", fill="#0f172a", font=title_font)
    draw.rounded_rectangle((42, 105, 675, 760), radius=22, fill="#ffffff", outline="#cbd5e1", width=3)
    draw.rounded_rectangle((725, 105, 1358, 760), radius=22, fill="#ffffff", outline="#cbd5e1", width=3)

    draw.text((72, 135), "图像：空间采样与像素量化", fill="#1d4ed8", font=heading_font)
    grid_x, grid_y, cell = 96, 215, 58
    values = [
        [24, 38, 62, 94, 126, 158, 188, 214],
        [32, 48, 76, 110, 146, 180, 208, 228],
        [44, 66, 96, 132, 170, 202, 226, 240],
        [58, 84, 116, 154, 194, 222, 240, 250],
        [72, 102, 138, 178, 214, 236, 248, 255],
        [88, 122, 160, 202, 230, 246, 255, 255],
        [108, 144, 188, 222, 242, 252, 255, 255],
        [130, 170, 208, 234, 248, 255, 255, 255],
    ]
    for row, row_values in enumerate(values):
        for col, value in enumerate(row_values):
            color = (24, 80 + value // 3, min(255, 110 + value // 2))
            x0 = grid_x + col * cell
            y0 = grid_y + row * cell
            draw.rectangle((x0, y0, x0 + cell, y0 + cell), fill=color, outline="#ffffff", width=2)

    draw.text((96, 695), "每个方格是一个像素；亮度/颜色被量化为有限整数", fill="#334155", font=body_font)
    draw.text((96, 727), "示例：8 × 8 像素 × 每像素位深 → 可计算原始存储量", fill="#475569", font=small_font)

    draw.text((755, 135), "声音：时间采样与幅度量化", fill="#7c3aed", font=heading_font)
    chart_left, chart_top, chart_right, chart_bottom = 775, 225, 1315, 620
    axis_y = (chart_top + chart_bottom) // 2
    draw.line((chart_left, axis_y, chart_right, axis_y), fill="#94a3b8", width=2)
    draw.line((chart_left, chart_top, chart_left, chart_bottom), fill="#94a3b8", width=2)

    points = []
    for x in range(chart_left, chart_right + 1, 3):
        t = (x - chart_left) / (chart_right - chart_left)
        amplitude = 118 * math.sin(t * math.pi * 4.2) + 28 * math.sin(t * math.pi * 10)
        points.append((x, axis_y - amplitude))
    draw.line(points, fill="#7c3aed", width=4)

    sample_count = 17
    levels = [axis_y - 140 + i * 35 for i in range(9)]
    for level in levels:
        draw.line((chart_left, level, chart_right, level), fill="#e2e8f0", width=1)
    for i in range(sample_count):
        x = chart_left + i * (chart_right - chart_left) / (sample_count - 1)
        t = (x - chart_left) / (chart_right - chart_left)
        exact_y = axis_y - (118 * math.sin(t * math.pi * 4.2) + 28 * math.sin(t * math.pi * 10))
        quantized_y = min(levels, key=lambda level: abs(level - exact_y))
        draw.line((x, axis_y, x, quantized_y), fill="#38bdf8", width=2)
        draw.ellipse((x - 7, quantized_y - 7, x + 7, quantized_y + 7), fill="#0284c7", outline="#ffffff", width=2)

    draw.text((780, 650), "紫色曲线：连续声波", fill="#7c3aed", font=body_font)
    draw.text((1045, 650), "蓝点：离散采样值", fill="#0369a1", font=body_font)
    draw.text((780, 695), "采样率决定每秒记录多少点；位深决定每个点可用多少幅度等级", fill="#334155", font=body_font)
    draw.text((780, 727), "采样点数 × 位深 × 声道数 × 时长 → 未压缩音频大小", fill="#475569", font=small_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the data-encoding teaching diagram")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    generate(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
