@echo off
chcp 65001 >nul
echo ========================================
echo 快速抓取"计算思维"核心材料
echo ========================================
echo.

cd /d "%~dp0"

set OUTPUT_PATH=D:\Edu_AI_1\Edu_AI\api\course_data\courses\computational-thinking\knowledge_base\documents

echo 正在抓取核心PDF材料...
echo.

echo [1/3] 抓取"计算思维"核心概念...
python -m automation_spider pdf --keywords "计算思维" --pages 2 --output "%OUTPUT_PATH%"

echo.
echo [2/3] 抓取"问题分解"相关材料...
python -m automation_spider pdf --keywords "问题分解" --pages 2 --output "%OUTPUT_PATH%"

echo.
echo [3/3] 抓取"算法设计"相关材料...
python -m automation_spider pdf --keywords "算法设计" --pages 2 --output "%OUTPUT_PATH%"

echo.
echo ========================================
echo 抓取完成！
echo 文件保存在: %OUTPUT_PATH%
echo ========================================
pause

