rem Simplified run script for Windows cmd.exe
pushd .
cd %~dp0
if exist ..\venv-windows\ (call ..\venv-windows\scripts\activate)
python go.py
popd

