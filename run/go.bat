rem Simplified run script for Windows cmd.exe
pushd .
cd %~dp0
setlocal
rem If there isn't one already active, activate the virtual environment
if "%VIRTUAL_ENV%"=="" if exist ..\venv-windows\ call ..\venv-windows\scripts\activate
python go.py
endlocal
popd


