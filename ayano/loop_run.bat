@echo off
echo Starting loop execution of ayano_update.py...

FOR /L %%i IN (1,1,25) DO (
    echo.
    echo === Iteration %%i of 10 ===
    python ayano_update.py
    echo Waiting 10 seconds before next iteration...
    timeout /t 10 /nobreak > nul
)

echo.
echo All iterations completed.
pause