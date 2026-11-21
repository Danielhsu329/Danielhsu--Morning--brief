@echo off
chcp 65001 > nul
title 全球宏觀與產業策略晨報 — 一鍵發布工具

echo ==================================================
echo   正在檢查並發布最新晨報至 GitHub Pages...
echo ==================================================
echo.

python C:\morning_brief_web\publish_brief.py %*

if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 發布過程發生異常，請檢視上方錯誤訊息。
    pause
    exit /b %errorlevel%
)

echo.
echo 正在等待 GitHub Pages 部署更新（約 12 秒，按任意鍵可立即開啟）...
timeout /t 12 > nul

echo 正在開啟預設瀏覽器檢查最新晨報...
start "" "https://danielhsu329.github.io/Danielhsu--Morning--brief/"