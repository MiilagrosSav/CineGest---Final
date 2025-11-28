@echo off
set PROJECT_DIR=E:\saval\jeje\CineGest---Final
set PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe

cd /d "%PROJECT_DIR%"

REM --- Crea la carpeta logs si no existe (para evitar errores) ---
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

"%PYTHON_EXE%" manage.py ejecutar_yield_management --verbosity=2 >> "%PROJECT_DIR%\logs\yield_management.log" 2>&1