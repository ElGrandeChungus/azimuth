@echo off
echo Stopping Azimuth...
cd /d "%~dp0"
docker compose down
echo.
echo Azimuth stopped.
echo.
pause