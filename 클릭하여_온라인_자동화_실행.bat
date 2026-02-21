@echo off
:: Set terminal to UTF-8 to handle any path names
chcp 65001 > nul
title Daewoong QC Automation Tool

echo ======================================================
echo   Starting Automation Tool...
echo ======================================================
echo.

:: 1. Navigate to working directory
cd /d "C:\Users\mih97\Desktop\대웅제약 인턴\Step 6 Ms_TS 과제"

:: 2. Execute Python script
:: Using -u for unbuffered real-time log output
py -u excel_to_pdf_automation.py

echo.
echo ======================================================
echo   Tasks Completed.
echo   Press any key to close this window...
echo ======================================================
pause > nul
