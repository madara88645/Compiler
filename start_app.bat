@echo off
echo Starting Prompt Compiler Dev Environment...

:: Start Backend (Port 8080 to avoid cognitive-ai conflict)
start "Backend (FastAPI)" cmd /k "python -m uvicorn api.main:app --reload --port 8080"

:: Start Frontend
cd web
start "Frontend (Next.js)" cmd /k "npm run dev"

echo Servers started!
echo Backend: http://localhost:8080
echo Frontend: http://localhost:3000
