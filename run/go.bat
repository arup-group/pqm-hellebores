@rem Simplified run script for Windows cmd.exe
@pushd .
@rem Change to root directory of project
@cd %~dp0
@rem Make environment variables that we set have local scope only
@setlocal
@rem If there isn't one already active, activate the virtual environment
@if "%VIRTUAL_ENV%"=="" if exist ..\.venv-windows call ..\.venv-windows\scripts\activate
@python go.py
@endlocal
@popd


