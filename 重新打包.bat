@echo off
cd /d "%~dp0"
python build.py
if errorlevel 1 goto fail
echo.
echo All done. Output: dist\MCInstanceTransfer-zh.exe
pause
exit /b 0
:fail
echo.
echo Build FAILED. Check the messages above.
pause
exit /b 1
