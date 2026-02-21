@echo off
:: 터미널 한글 깨짐 방지
chcp 65001 > nul
title Daewoong Chatbot Online Sync Tool

echo ======================================================
echo   [1/2] New Trial 최신 로직 반영 중...
echo ======================================================
:: 'new trial' 폴더에서 검증된 똑똑한 코드들을 실제 배포용(루트)으로 복사합니다.
copy /y "new trial\app.py" "app.py"
copy /y "new trial\utils.py" "utils.py"
copy /y "new trial\requirements.txt" "requirements.txt"

echo.
echo ======================================================
echo   [2/2] GitHub 서버로 지식 및 링크 동기화 중...
echo ======================================================
:: Git 설정 및 동기화 강화
git config user.email "mih97250706@gmail.com"
git config user.name "Editor-MJS"

:: 현재 브랜치를 main으로 강제 설정 (master일 경우 대비)
git branch -M main

git add .
git commit -m "Auto Update: Applied New Trial Logic and Knowledge Base"
git push origin main

echo.
echo ======================================================
echo   🚀 동기화 시도가 완료되었습니다!
echo   * 주의: 'fatal'이나 'error' 메시지가 떴다면 
echo     아직 컴퓨터와 GitHub가 완전히 연결되지 않은 것입니다.
echo ======================================================
echo.
pause
