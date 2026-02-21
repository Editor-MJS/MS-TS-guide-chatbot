@echo off
:: Set terminal to UTF-8
chcp 65001 > nul
title Daewoong QC Precision Indexer

echo ======================================================
echo   Starting QC Precision Index Generator...
echo   (AI-Free / 100%% Accuracy Mode)
echo ======================================================
echo.

cd /d "C:\Users\mih97\Desktop\대웅제약 인턴\Step 6 Ms_TS 과제"

:: 실행 메시지를 간소화하고 바로 파이썬 실행
py -u Summary_Index_Maker_Offline_AI.py

echo.
echo ======================================================
echo   Process Finished Successfully.
echo   Check 'Chatbot_Knowledge_Base.json' for Chatbot Data.
echo   Press any key to close...
echo ======================================================
pause > nul
