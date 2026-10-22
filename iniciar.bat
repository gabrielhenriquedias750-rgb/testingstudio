@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :erro
)
".venv\Scripts\python.exe" -c "import streamlit, pandas, google.genai, altair" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :erro
)
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto :erro
exit /b 0
:erro
echo Nao foi possivel iniciar. Confira a instalacao do Python e a conexao de rede.
pause
exit /b 1
