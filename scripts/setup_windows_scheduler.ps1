# Script para configurar Task Scheduler en Windows
# Ejecutar como Administrador en PowerShell

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Configurador de Yield Management Automatico" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$projectPath = "E:\saval\jeje\CineGest---Final"
$pythonExe = "python"

# Verificar si ya existe la tarea
$existingTask = Get-ScheduledTask -TaskName "CineGest-YieldManagement" -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "La tarea 'CineGest-YieldManagement' ya existe." -ForegroundColor Yellow
    $response = Read-Host "Deseas eliminarla y recrearla? (s/n)"
    
    if ($response -eq "s" -or $response -eq "S") {
        Unregister-ScheduledTask -TaskName "CineGest-YieldManagement" -Confirm:$false
        Write-Host "Tarea anterior eliminada." -ForegroundColor Green
    } else {
        Write-Host "Operacion cancelada." -ForegroundColor Red
        exit
    }
}

Write-Host ""
Write-Host "Configuracion:" -ForegroundColor Yellow
Write-Host "   Ruta del proyecto: $projectPath" -ForegroundColor Gray
Write-Host "   Python: $pythonExe" -ForegroundColor Gray
Write-Host "   Frecuencia: Cada hora" -ForegroundColor Gray
Write-Host ""

# Crear la accion
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "manage.py ejecutar_yield_management --verbosity=2" -WorkingDirectory $projectPath

# Crear el trigger (repetir cada hora por 30 dias, luego renovar)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 365)

# Configuracion de la tarea
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Registrar la tarea
try {
    Register-ScheduledTask -TaskName "CineGest-YieldManagement" -Action $action -Trigger $trigger -Settings $settings -Description "Ejecuta el yield management de CineGest cada hora automaticamente" -User $env:USERNAME -RunLevel Highest
    
    Write-Host ""
    Write-Host "Tarea programada creada exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Informacion de la tarea:" -ForegroundColor Cyan
    Write-Host "   Nombre: CineGest-YieldManagement" -ForegroundColor Gray
    Write-Host "   Primera ejecucion: En 5 minutos" -ForegroundColor Gray
    Write-Host "   Frecuencia: Cada 1 hora" -ForegroundColor Gray
    Write-Host "   Log: $projectPath\logs\yield_management.log" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Comandos utiles:" -ForegroundColor Yellow
    Write-Host "   Ver tarea:" -ForegroundColor Gray
    Write-Host "   Get-ScheduledTask -TaskName 'CineGest-YieldManagement'" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Ejecutar manualmente:" -ForegroundColor Gray
    Write-Host "   Start-ScheduledTask -TaskName 'CineGest-YieldManagement'" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Deshabilitar:" -ForegroundColor Gray
    Write-Host "   Disable-ScheduledTask -TaskName 'CineGest-YieldManagement'" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Eliminar:" -ForegroundColor Gray
    Write-Host "   Unregister-ScheduledTask -TaskName 'CineGest-YieldManagement'" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "IMPORTANTE: Tu computadora debe estar encendida para que funcione." -ForegroundColor Red
    Write-Host "   Para solucion sin PC encendida, usa GitHub Actions (ver docs)." -ForegroundColor Red
    Write-Host ""
    
}
catch {
    Write-Host ""
    Write-Host "Error al crear la tarea:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Asegurate de ejecutar este script como Administrador." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Preguntar si desea ejecutar una prueba
Write-Host "Deseas ejecutar una prueba ahora? (s/n): " -ForegroundColor Yellow -NoNewline
$testResponse = Read-Host

if ($testResponse -eq "s" -or $testResponse -eq "S") {
    Write-Host ""
    Write-Host "Ejecutando prueba..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName "CineGest-YieldManagement"
    Write-Host "Tarea iniciada. Revisa los logs en unos segundos." -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Configuracion completada" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
