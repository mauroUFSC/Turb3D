@echo off
title Visualizador 3D - Modelo Turbiditico
cd /d "%~dp0"

REM Se o executavel standalone existir, tenta executa-lo diretamente
if exist "%~dp0VisualizadorTurbiditico3D.exe" (
    start "" "%~dp0VisualizadorTurbiditico3D.exe" %*
    exit /b
)

REM Caso contrario, executa via Python sem janela preta de console
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app_gui.py" %*
    exit /b
)

python "%~dp0app_gui.py" %*
