@echo off
REM Script para eliminar la tarea programada de Yield Management
REM Ejecutar como Administrador

echo ================================================
echo     Eliminar Tarea de Yield Management
echo ================================================
echo.

schtasks /Query /TN "CineGest-YieldManagement" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo La tarea existe. Procediendo a eliminar...
    schtasks /Delete /TN "CineGest-YieldManagement" /F
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [OK] Tarea eliminada exitosamente
    ) else (
        echo.
        echo [ERROR] No se pudo eliminar la tarea
        echo Asegurate de ejecutar como Administrador
    )
) else (
    echo.
    echo [INFO] La tarea no existe o ya fue eliminada
)

echo.
echo ================================================
pause
