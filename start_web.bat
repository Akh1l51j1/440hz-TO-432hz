@echo off
echo Starting 432 Hz Converter Web UI...
echo Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0web"
..\venv\Scripts\python.exe manage.py runserver --noreload
