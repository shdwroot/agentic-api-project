@echo off
setlocal EnableExtensions

rem Keep the virtual environment and uv cache out of a synchronized Documents
rem checkout. This is the native Windows equivalent of scripts/uv-local.
set "UV_LOCAL_ROOT=%TEMP%\agentic-api-framework"
if not defined UV_PROJECT_ENVIRONMENT set "UV_PROJECT_ENVIRONMENT=%UV_LOCAL_ROOT%\venv"
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%UV_LOCAL_ROOT%\uv-cache"

if not exist "%UV_LOCAL_ROOT%" mkdir "%UV_LOCAL_ROOT%"
uv %*
exit /b %ERRORLEVEL%
