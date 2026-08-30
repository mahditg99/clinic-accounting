@echo off
cd /d %~dp0\..
echo Starting Azaran Teb Web App on http://127.0.0.1:8000
echo Login: admin / admin
python -m uvicorn webapp.main:app --reload --port 8000 --host 0.0.0.0
if errorlevel 1 pause