@echo off
chcp 65001 > nul
REM ============================================================
REM 股票价值投资财报分析软件 V1.0 - 一键打包脚本
REM 生成 dist\股票价值投资财报分析软件.exe（单文件，可独立运行）
REM ============================================================

cd /d "%~dp0"

echo ===================================
echo 开始打包 股票价值投资财报分析软件 V1.0
echo ===================================

REM 清理旧构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 将 pdf_libs 中的 fitz / pymupdf 复制到 ffa 目录
REM （PyInstaller 需要它们作为普通包才能正确打包到 exe 内）
echo [1/3] 准备 fitz / pymupdf 包...
if exist fitz rmdir /s /q fitz
if exist pymupdf rmdir /s /q pymupdf
xcopy /e /i /q "..\pdf_libs\fitz" "fitz" >nul
xcopy /e /i /q "..\pdf_libs\pymupdf" "pymupdf" >nul

REM 设置 Python 路径
set PYTHON="C:\Users\歌飛\AppData\Local\Programs\Python\Python314\python.exe"

REM 调用 PyInstaller
echo [2/3] 执行 PyInstaller 打包...
%PYTHON% -m PyInstaller --noconfirm --clean ^
    --name "股票价值投资财报分析软件" ^
    --windowed ^
    --onefile ^
    --add-data "rules.json;." ^
    --add-data "app\data\schema.sql;app\data" ^
    main.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请查看上方日志
    REM 清理临时复制的包
    if exist fitz rmdir /s /q fitz
    if exist pymupdf rmdir /s /q pymupdf
    pause
    exit /b 1
)

REM 清理临时复制的包（保持源码树干净）
echo [3/3] 清理临时文件...
if exist fitz rmdir /s /q fitz
if exist pymupdf rmdir /s /q pymupdf

echo.
echo [成功] EXE 已生成：dist\股票价值投资财报分析软件.exe
echo.
echo 此 exe 可直接复制到任何 Windows 11 电脑双击运行，无需安装 Python。
pause
