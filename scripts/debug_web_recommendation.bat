@echo off
chcp 65001 >nul
cd /d "%~dp0\..\.."
python -c "import sys; sys.path.insert(0, 'calibre-web'); exec(open('calibre-web/scripts/debug_web_recommendation.py', encoding='utf-8').read())"
pause

