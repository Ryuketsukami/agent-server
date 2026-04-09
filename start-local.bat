@echo off
REM Start the local LangGraph agent server with Cloudflare tunnel.
REM Usage: double-click or run from CMD/PowerShell: portfolio\backend\start-local.bat
REM
REM Prerequisites:
REM   - Ollama installed and running (ollama pull qwen3:8b)
REM   - Cloudflare tunnel "local-agent" created
REM   - Python venv at portfolio\backend\.venv with langgraph-cli installed

set SCRIPT_DIR=%~dp0
set PORT=8123
set CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe

REM --- Preflight: check Ollama model ---
ollama list 2>nul | findstr /C:"qwen3:8b" >nul
if errorlevel 1 (
    echo [WARN] qwen3:8b not found — pulling now...
    ollama pull qwen3:8b
)

REM --- Activate venv ---
if not exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    echo [ERROR] Python venv not found at %SCRIPT_DIR%.venv
    exit /b 1
)
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM --- Start Cloudflare tunnel in background ---
echo [1/2] Starting Cloudflare tunnel (local-agent -^> localhost:%PORT%)...
start "Cloudflare Tunnel" "%CLOUDFLARED%" tunnel run --url http://localhost:%PORT% local-agent

REM --- Start LangGraph server (foreground) ---
echo [2/2] Starting LangGraph server on port %PORT%...
echo.
echo === Local agent server running ===
echo   LangGraph:  http://localhost:%PORT%
echo   Tunnel:     (see Cloudflare Tunnel window for public URL)
echo   Close this window to stop the server.
echo.

cd /d "%SCRIPT_DIR%"

REM --- Load .env into the shell (skip comments and blank lines) ---
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq eol=# tokens=* delims=" %%A in ("%SCRIPT_DIR%.env") do (
        set "%%A"
    )
)

langgraph dev --port %PORT% --host 0.0.0.0
