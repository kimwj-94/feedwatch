@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  FeedWatch 데모 서버  http://localhost:5180
echo  - 브라우저가 자동으로 열립니다.
echo  - 종료: 이 창에서 Ctrl + C 후 닫기
echo ============================================================
start "" http://localhost:5180
py scripts\devserver.py 5180 web
