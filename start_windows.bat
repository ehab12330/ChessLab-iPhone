@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto fail
py -3 app.py
if errorlevel 1 goto fail
exit /b 0
:fail
 echo Please install Python 3 with Tcl/Tk and the Python launcher.
 pause
