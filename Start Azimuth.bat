@echo off
echo Starting Azimuth...
cd /d "%~dp0"
docker compose up -d
echo.
echo Azimuth is running!
echo Open http://localhost:3000 in your browser
echo.
pause