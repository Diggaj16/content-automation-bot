@echo off
echo Starting content-automation-bot...

:: Start Redis
echo [1/4] Starting Redis...
docker start redis >nul 2>&1 || docker run -d --name redis -p 6379:6379 redis:alpine

:: Start Backend API
echo [2/4] Starting Backend API...
start "Backend API" cmd /k "cd /d %~dp0backend && python -m uvicorn app.api.main:app --reload --port 8000"

:: Wait for backend to be ready
echo Waiting for backend...
timeout /t 5 /nobreak >nul

:: Start Worker
echo [3/4] Starting Worker...
start "Worker" cmd /k "cd /d %~dp0backend && python -m arq app.queue.worker.WorkerSettings"

:: Start Frontend
echo [4/4] Starting Frontend...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo All services started!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
pause
