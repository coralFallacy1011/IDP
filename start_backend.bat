@echo off
echo ============================================
echo IDP Legal AI Platform - Startup Script
echo ============================================
echo.

echo [1/3] Starting Hardhat Local Blockchain...
start "Hardhat Node" cmd /k "cd /d %~dp0IDP\blockchain && powershell -ExecutionPolicy Bypass -Command \"node_modules\.bin\hardhat.cmd node\""
echo Hardhat node starting on port 8545...
timeout /t 3 /nobreak > nul

echo [2/3] Deploying Smart Contract...
cd /d %~dp0IDP\blockchain
powershell -ExecutionPolicy Bypass -Command "node scripts/deploy_simple.js"
echo Contract deployed!
echo.

echo [3/3] Starting Flask Backend (port 5000)...
start "Flask Backend" cmd /k "cd /d %~dp0IDP\backend && ..\biometric_venv\Scripts\python app.py"
echo Flask backend starting on port 5000...
echo.

echo ============================================
echo All services started!
echo   - Hardhat node: http://127.0.0.1:8545
echo   - Flask backend: http://127.0.0.1:5000
echo   - Frontend: npm run dev in ./frontend/
echo ============================================
pause
