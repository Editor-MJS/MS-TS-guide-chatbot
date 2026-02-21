@echo off
:: Set terminal to UTF-8
chcp 65001 > nul
title Daewoong Online AI Indexer

echo ======================================================
echo   Starting ONLINE AI Index Generator...
echo   (Using Gemini AI for Situational Analysis)
echo ======================================================
echo.

cd /d "C:\Users\mih97\Desktop\대웅제약 인턴\Step 6 Ms_TS 과제"

:: Execute Online Script
py -u Summary_Index_Maker_Online.py

echo.
echo ======================================================
echo   Process Finished.
echo   Check 'Chatbot_Navigation_Index_Online.pdf'
echo   Press any key to close...
echo ======================================================
pause > nul
