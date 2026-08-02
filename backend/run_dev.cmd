@echo off
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
venv\Scripts\python.exe -u -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-exclude data/*
