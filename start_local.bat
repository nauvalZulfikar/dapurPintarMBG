@echo off
cd /d "C:\Users\Administator\Desktop\dapurPintarMBG"

echo Starting local backend...
start "DapurPintar Backend" cmd /k "C:\Users\Administator\AppData\Local\Programs\Python\Python314\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000"

echo Starting local frontend...
start "DapurPintar Frontend" cmd /k "cd frontend && npm run dev -- --host"

timeout /t 3 /nobreak >nul
echo.
echo Local:   http://localhost:5173
echo Network: http://192.168.8.139:5173
