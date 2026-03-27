@echo off
echo Cleaning Python bytecode cache...
cd /d "%~dp0"
for /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo Removing: %%d
        rd /s /q "%%d"
    )
)
for /r . %%f in (*.pyc) do (
    echo Removing: %%f
    del /q "%%f"
)
echo Done. All .pyc cache files removed.
pause
